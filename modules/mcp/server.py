"""The MCP server: the same tools as /api/tools, over MCP streamable HTTP at /mcp.

Every request carries a machine token (Authorization: Bearer plat_...). The tool list is built
per request from that token, so a client sees only the tools its scopes and its org's modules allow.

With a public URL (oauth.public_url: MCP_PUBLIC_URL, else <ACCOUNTS_BASE_URL>/mcp), the server is also
an OAuth authorization server (oauth.py, oauth_pages.py): a client registers itself, an officer approves
it, and the client gets a machine token of kind oauth. /mcp then answers 401 with the protected resource
metadata URL, so a client can find the sign-in. The OAuth routes are under the public path, such as
/mcp/authorize, so a reverse proxy that sends /mcp to this server reaches them all.
"""

import functools
import json

from anyio import to_thread
from mcp import types
from mcp.server.auth.handlers.metadata import MetadataHandler
from mcp.server.auth.handlers.token import TokenHandler
from mcp.server.auth.middleware.client_auth import AuthenticationError
from mcp.server.auth.routes import cors_middleware, create_auth_routes
from mcp.server.auth.settings import AuthSettings
from mcp.server.lowlevel import Server
from mcp.server.transport_security import DEFAULT_MAX_REQUEST_BODY_SIZE, RequestBodyLimitMiddleware
from mcp.shared.inbound import MCP_PROTOCOL_VERSION_HEADER
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse, Response
from starlette.routing import Mount, Route, request_response

from core.db import db_connect
from core.log import get_logger
from core.tools import ToolError
from modules.auth import machine_tokens
from modules.mcp import client_auth, edges, oauth, oauth_pages, runtime

logger = get_logger(__name__)


class Unauthorized(Exception):
    pass


def _token(ctx) -> str | None:
    request = getattr(ctx, "request", None)
    header = request.headers.get("authorization", "") if request is not None else ""
    return header[7:].strip() if header.lower().startswith("bearer ") else None


def _list(token: str | None) -> list[types.Tool]:
    db = db_connect.SessionLocal()
    try:
        caller = machine_tokens.verify(db, token)
        if caller is None:
            raise Unauthorized("A valid machine token is required")
        # An OAuth client can ask for more scopes (step-up), so it also sees the tools that need one
        step_up = caller.kind == machine_tokens.OAUTH_KIND and bool(oauth.public_url())
        return [
            types.Tool(
                name=spec.name,
                description=_description(spec, caller),
                input_schema=spec.input_schema,
                annotations=types.ToolAnnotations(read_only_hint=spec.read_only, destructive_hint=spec.confirm),
            )
            for spec in runtime.available(db, caller, step_up=step_up)
        ]
    finally:
        db.close()


def _description(spec, caller) -> str:
    if not spec.scope or caller.allows(spec.scope):
        return spec.description
    return (
        f"{spec.description} Needs the {spec.scope} scope, which this connection does not have: "
        "a call asks an officer to approve it."
    )


def _call(token: str | None, name: str, arguments: dict | None) -> types.CallToolResult:
    db = db_connect.SessionLocal()
    try:
        caller = machine_tokens.verify(db, token)
        if caller is None:
            return _error("A valid machine token is required")
        try:
            result = runtime.call(db, caller, name, arguments, source="mcp")
        except ToolError as e:
            return _error(e.message)
        return types.CallToolResult(
            content=[types.TextContent(type="text", text=json.dumps(result, default=str))],
            structured_content=result if isinstance(result, dict) else {"result": result},
        )
    finally:
        db.close()


def _error(message: str) -> types.CallToolResult:
    return types.CallToolResult(content=[types.TextContent(type="text", text=message)], is_error=True)


async def on_list_tools(ctx, params) -> types.ListToolsResult:
    tools = await to_thread.run_sync(_list, _token(ctx))
    return types.ListToolsResult(tools=tools)


async def on_call_tool(ctx, params: types.CallToolRequestParams) -> types.CallToolResult:
    return await to_thread.run_sync(_call, _token(ctx), params.name, params.arguments)


def build_server() -> Server:
    return Server(
        "platform",
        instructions="Tools over this organization's platform data. Each token sees only its own org.",
        on_list_tools=on_list_tools,
        on_call_tool=on_call_tool,
    )


def build_app(host: str = "0.0.0.0"):  # nosec B104 - the container binds all interfaces, as main.py does
    """The ASGI app. Stateless JSON responses, so any number of processes can serve it.

    OAuth keeps its state in the database, so it works with more than one process too. Only the
    limit of requests of each IP counts in each process.
    """
    server = build_server()
    configured = oauth.configured_url()
    public = oauth.public_url()
    if configured and not public:
        logger.warning("MCP OAuth is off: %s", oauth.url_problem(configured))
    if not public:
        return edges.OriginCheck(server.streamable_http_app(stateless_http=True, json_response=True, host=host), "/mcp")
    path = oauth.public_path()
    provider = oauth.Provider(oauth_pages.login_url)
    # From strings, so the issuer keeps the URL as written: clients compare it as a string (RFC 8414)
    auth = AuthSettings.model_validate(
        {
            "issuer_url": public,
            "resource_server_url": public,
            "client_registration_options": oauth.REGISTRATION,
            "revocation_options": oauth.REVOCATION,
            # Tokens that officers make have no resource, so the server does not check it
            "validate_token_resource": False,  # nosec B105 - a setting name, not a password
        }
    )
    metadata = MetadataHandler(oauth.server_metadata_model())
    metadata_route = cors_middleware(metadata.handle, ["GET", "OPTIONS"])
    # Replaced below: the SDK's metadata lacks client_id_metadata_document_supported, and its token and
    # revoke routes do not accept private_key_jwt
    replaced = ("/.well-known/oauth-authorization-server", "/token", "/revoke")
    oauth_routes = [
        route
        for route in create_auth_routes(
            provider,
            auth.issuer_url,
            client_registration_options=oauth.REGISTRATION,
            revocation_options=oauth.REVOCATION,
        )
        if getattr(route, "path", "") not in replaced
    ]
    authenticator = client_auth.ClientAuthenticator(provider)
    oauth_routes += [
        _client_route("/token", TokenHandler(provider, authenticator).handle),
        _client_route("/revoke", functools.partial(_revoke, provider, authenticator)),
    ]
    oauth_routes.append(
        Route("/.well-known/oauth-authorization-server", endpoint=metadata_route, methods=["GET", "OPTIONS"])
    )
    root_metadata = [Route(oauth.server_metadata_path(), endpoint=metadata_route, methods=["GET", "OPTIONS"])]
    app = server.streamable_http_app(
        streamable_http_path=path,
        stateless_http=True,
        json_response=True,
        host=host,
        auth=auth,
        token_verifier=provider,
        custom_starlette_routes=root_metadata,
    )
    # The SDK's protected resource metadata has no scopes_supported, so oauth.resource_metadata replaces it
    resource_path = oauth.resource_metadata_path()
    app.router.routes[:] = [r for r in app.router.routes if getattr(r, "path", "") != resource_path]
    app.router.routes.append(
        Route(
            resource_path, endpoint=cors_middleware(_resource_metadata, ["GET", "OPTIONS"]), methods=["GET", "OPTIONS"]
        )
    )
    # After the /mcp route, so that a request to /mcp itself never reaches the mount
    app.router.routes.append(Mount(path, routes=[*oauth_routes, *oauth_pages.routes()]))
    edged = edges.RegistrationLog(edges.IssuerOnErrors(edges.ScopeChallenge(app, path), path), path)
    return oauth.RateLimit(edges.OriginCheck(edged, path), path)


async def _revoke(provider, authenticator, request) -> Response:
    """Token revocation (RFC 7009). The SDK's handler needs client_secret in every request, also from a client
    that has none, so this one replaces it. An unknown token, or one of another client, still gets 200."""
    try:
        client = await authenticator.authenticate_request(request)
    except AuthenticationError as e:
        return JSONResponse({"error": "invalid_client", "error_description": e.message}, status_code=401)
    form = await request.form()
    token = form.get("token")
    if not isinstance(token, str) or not token:
        return JSONResponse({"error": "invalid_request", "error_description": "token is required"}, status_code=400)
    found = await provider.load_access_token(token) or await provider.load_refresh_token(client, token)
    if found is not None and found.client_id == client.client_id:
        await provider.revoke_token(found)
    return Response(status_code=200, headers={"Cache-Control": "no-store", "Pragma": "no-cache"})


def _client_route(path: str, handle) -> Route:
    """A route that a client calls with its credentials, with CORS and a body limit, as the SDK makes them."""
    limited = RequestBodyLimitMiddleware(request_response(handle), DEFAULT_MAX_REQUEST_BODY_SIZE)
    app = CORSMiddleware(
        app=limited, allow_origins="*", allow_methods=["POST", "OPTIONS"], allow_headers=[MCP_PROTOCOL_VERSION_HEADER]
    )
    return Route(path, endpoint=app, methods=["POST", "OPTIONS"])


async def _resource_metadata(request) -> JSONResponse:
    return JSONResponse(oauth.resource_metadata(), headers={"Cache-Control": "public, max-age=3600"})
