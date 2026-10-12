"""The MCP server: the same tools as /api/tools, over MCP streamable HTTP at /mcp.

Every request carries a machine token (Authorization: Bearer plat_...). The tool list is built
per request from that token, so a client sees only the tools its scopes and its org's modules allow.

With a public URL (oauth.public_url: MCP_PUBLIC_URL, else <ACCOUNTS_BASE_URL>/mcp), the server is also
an OAuth authorization server (oauth.py, oauth_pages.py): a client registers itself, an officer approves
it, and the client gets a machine token of kind oauth. /mcp then answers 401 with the protected resource
metadata URL, so a client can find the sign-in. The OAuth routes are under the public path, such as
/mcp/authorize, so a reverse proxy that sends /mcp to this server reaches them all.
"""

import json

from anyio import to_thread
from mcp import types
from mcp.server.auth.handlers.metadata import MetadataHandler
from mcp.server.auth.routes import cors_middleware, create_auth_routes
from mcp.server.auth.settings import AuthSettings
from mcp.server.lowlevel import Server
from starlette.routing import Mount, Route

from core.db import db_connect
from core.log import get_logger
from core.tools import ToolError
from modules.auth import machine_tokens
from modules.mcp import oauth, oauth_pages, runtime

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
        return [
            types.Tool(
                name=spec.name,
                description=spec.description,
                input_schema=spec.input_schema,
                annotations=types.ToolAnnotations(read_only_hint=spec.read_only, destructive_hint=spec.confirm),
            )
            for spec in runtime.available(db, caller)
        ]
    finally:
        db.close()


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
        return server.streamable_http_app(stateless_http=True, json_response=True, host=host)
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
    # The SDK's own metadata route lacks client_id_metadata_document_supported, so this one replaces it
    oauth_routes = [
        route
        for route in create_auth_routes(
            provider,
            auth.issuer_url,
            client_registration_options=oauth.REGISTRATION,
            revocation_options=oauth.REVOCATION,
        )
        if getattr(route, "path", "") != "/.well-known/oauth-authorization-server"
    ]
    oauth_routes.append(
        Route("/.well-known/oauth-authorization-server", endpoint=metadata_route, methods=["GET", "OPTIONS"])
    )
    root_metadata = [
        Route(where, endpoint=metadata_route, methods=["GET", "OPTIONS"]) for where in oauth.server_metadata_paths()
    ]
    app = server.streamable_http_app(
        streamable_http_path=path,
        stateless_http=True,
        json_response=True,
        host=host,
        auth=auth,
        token_verifier=provider,
        custom_starlette_routes=root_metadata,
    )
    # After the /mcp route, so that a request to /mcp itself never reaches the mount
    app.router.routes.append(Mount(path, routes=[*oauth_routes, *oauth_pages.routes()]))
    return oauth.RateLimit(app, path)
