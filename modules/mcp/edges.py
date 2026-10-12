"""HTTP rules of the MCP server that sit in front of the mcp SDK. ASGI middleware, no Flask here.

- OriginCheck: the Streamable HTTP transport must refuse a request to /mcp whose Origin header is present and
  not allowed (403), against DNS rebinding.
- ScopeChallenge: a 401 from /mcp names the scopes to ask for first (scope hint). A tools/call from an OAuth
  token for a tool that needs a scope the token does not have gets 403 insufficient_scope with that scope, so
  the client can sign in again and ask for it (step-up).
- IssuerOnErrors: an error redirect from /authorize that the SDK makes gets iss (RFC 9207), as the metadata says.
- RegistrationLog: a refused /register is logged with the reason and a summary of the request, because the
  client often shows only a general error. Secrets and keys are never logged.
"""

import json
import re
from typing import cast
from urllib.parse import parse_qs, urlsplit, urlunsplit

from anyio import to_thread
from mcp.server.auth.provider import construct_redirect_uri

from core import audit
from core.db import db_connect
from core.log import get_logger
from modules.auth import machine_tokens
from modules.mcp import oauth, runtime

logger = get_logger(__name__)

# A body larger than this is not read for the step-up check; the SDK refuses it later
MAX_CHECKED_BODY = 4 * 1024 * 1024


def _header(scope, name: bytes) -> str | None:
    for key, value in scope.get("headers") or []:
        if key.lower() == name:
            return value.decode("latin-1")
    return None


async def _send_json(send, status: int, body: dict, headers: list[tuple[bytes, bytes]] | None = None) -> None:
    data = json.dumps(body).encode()
    await send(
        {
            "type": "http.response.start",
            "status": status,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(data)).encode()),
                *(headers or []),
            ],
        }
    )
    await send({"type": "http.response.body", "body": data})


def _is_mcp(scope, path: str) -> bool:
    return scope["type"] == "http" and scope.get("path", "").rstrip("/") == path


def origin_allowed(origin: str) -> bool:
    """The public origin of the MCP server, and any port on this computer (local tools such as MCP Inspector)."""
    parts = urlsplit(origin)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        return False
    if parts.hostname in oauth.LOOPBACK_HOSTS:
        return True
    public = oauth.public_url()
    if not public:
        return False
    ours = urlsplit(public)
    return (parts.scheme, (parts.netloc or "").lower()) == (ours.scheme, ours.netloc.lower())


class OriginCheck:
    def __init__(self, app, path: str):
        self.app = app
        self.path = path.rstrip("/")

    async def __call__(self, scope, receive, send):
        origin = _header(scope, b"origin") if _is_mcp(scope, self.path) else None
        if origin is None or origin_allowed(origin):
            return await self.app(scope, receive, send)
        logger.warning("mcp request refused: origin %s is not allowed", origin)
        body = {"jsonrpc": "2.0", "error": {"code": -32600, "message": "Origin not allowed"}}
        await _send_json(send, 403, body)


def _tool_names(message: object) -> list[str]:
    """The tools that a JSON-RPC tools/call runs: its name, or each call of a batch."""
    request = cast(dict, message) if isinstance(message, dict) else {}
    params = request.get("params") if request.get("method") == "tools/call" else None
    name = cast(dict, params).get("name") if isinstance(params, dict) else None
    if not isinstance(name, str):
        return []
    if name != runtime.BATCH:
        return [name]
    arguments = cast(dict, params).get("arguments")
    calls = cast(dict, arguments).get("calls") if isinstance(arguments, dict) else None
    items = [cast(dict, c) for c in calls if isinstance(c, dict)] if isinstance(calls, list) else []
    return [str(c["tool"]) for c in items if isinstance(c.get("tool"), str)]


def _missing_scopes(token: str, names: list[str]) -> tuple[list[str], str | None]:
    """The scopes that an OAuth token lacks for these tools, and its actor for the audit log."""
    db = db_connect.SessionLocal()
    try:
        caller = machine_tokens.verify(db, token)
        if caller is None or caller.kind != machine_tokens.OAUTH_KIND:
            return [], None
        missing = {scope for name in names if (scope := runtime.missing_scope(db, caller, name))}
        return sorted(missing), caller.actor
    finally:
        db.close()


def _replay(messages: list[dict], receive):
    """A receive that gives the messages already read, then the rest of the request."""
    pending = list(messages)

    async def replayed():
        return pending.pop(0) if pending else await receive()

    return replayed


class ScopeChallenge:
    def __init__(self, app, path: str):
        self.app = app
        self.path = path.rstrip("/")

    def _metadata_url(self) -> str:
        return f"{urlsplit(oauth.public_url())._replace(path='', query='').geturl()}{oauth.resource_metadata_path()}"

    async def __call__(self, scope, receive, send):
        if not _is_mcp(scope, self.path) or scope.get("method") != "POST":
            return await self.app(scope, receive, send)
        authorization = _header(scope, b"authorization") or ""
        token = authorization[7:].strip() if authorization.lower().startswith("bearer ") else ""
        receive = await self._step_up(scope, receive, send, token) if token else receive
        if receive is None:
            return None
        return await self.app(scope, receive, self._hint(send))

    def _hint(self, send):
        """Add the scope hint to a 401 of the SDK."""
        scopes = " ".join(oauth.BASE_SCOPES)

        async def hinted(message):
            if message["type"] == "http.response.start" and message["status"] == 401:
                headers = []
                for key, value in message.get("headers") or []:
                    if key.lower() == b"www-authenticate" and b"scope=" not in value:
                        value = value + f', scope="{scopes}"'.encode()
                    headers.append((key, value))
                message = {**message, "headers": headers}
            await send(message)

        return hinted

    async def _step_up(self, scope, receive, send, token: str):
        """Read the body. Answer 403 for a call that needs more scopes, else a receive that replays the body.

        Returns None when it answered.
        """
        size = _header(scope, b"content-length")
        if size is not None and size.isdigit() and int(size) > MAX_CHECKED_BODY:
            return receive
        messages, read, more = [], 0, True
        while more:
            message = await receive()
            messages.append(message)
            if message["type"] != "http.request":
                break
            read += len(message.get("body", b""))
            if read > MAX_CHECKED_BODY:
                # Too large to check: the SDK gets the body as it comes, and its own limit applies
                return _replay(messages, receive)
            more = message.get("more_body", False)
        body = b"".join(m.get("body", b"") for m in messages if m["type"] == "http.request")
        try:
            names = _tool_names(json.loads(body))
        except ValueError:
            names = []
        if names:
            missing, actor = await to_thread.run_sync(_missing_scopes, token, names)
            if missing:
                await self._challenge(send, missing, names, actor)
                return None
        return _replay(messages, receive)

    async def _challenge(self, send, missing: list[str], names: list[str], actor: str | None) -> None:
        scopes = " ".join(missing)
        description = f"This connection needs the {scopes} scope. Connect again so that an officer can approve it."
        header = (
            f'Bearer error="insufficient_scope", scope="{scopes}", '
            f'resource_metadata="{self._metadata_url()}", error_description="{description}"'
        )
        audit.record(
            f"tool {', '.join(names)}"[:255],
            source="mcp",
            actor_kind="machine",
            actor_id=actor,
            status=403,
            details={"step_up": missing},
        )
        body = {"error": "insufficient_scope", "error_description": description, "scope": scopes}
        await _send_json(send, 403, body, [(b"www-authenticate", header.encode())])


class IssuerOnErrors:
    def __init__(self, app, path: str):
        self.app = app
        self.authorize = f"{path.rstrip('/')}/authorize"

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope.get("path") != self.authorize:
            return await self.app(scope, receive, send)

        async def with_iss(message):
            if message["type"] == "http.response.start" and message["status"] in (302, 303):
                headers = []
                for key, value in message.get("headers") or []:
                    if key.lower() == b"location":
                        location = value.decode("latin-1")
                        query = parse_qs(urlsplit(location).query)
                        if "error" in query and "iss" not in query:
                            value = construct_redirect_uri(location, iss=oauth.public_url()).encode("latin-1")
                    headers.append((key, value))
                message = {**message, "headers": headers}
            await send(message)

        return await self.app(scope, receive, with_iss)


# The registration fields whose values RegistrationLog writes. The other fields get their names only
LOGGED_FIELDS = (
    "client_name",
    "redirect_uris",
    "token_endpoint_auth_method",
    "grant_types",
    "response_types",
    "application_type",
    "scope",
    "client_uri",
    "software_id",
)
MAX_LOGGED_BODY = 64 * 1024
# A URL in a log line: a scheme, then anything up to a space, quote or bracket
URL_IN_TEXT = re.compile(r"""\b[A-Za-z][A-Za-z0-9+.\-]*:/[^\s"'\\<>]*""")


def redact_urls(text: str) -> str:
    """The text with each URL cut to scheme, host, port and path. A user, password, query or fragment can hold
    a credential, so it becomes ?…"""

    def cut(match: re.Match) -> str:
        try:
            parts = urlsplit(match.group(0))
            port = parts.port
        except ValueError:
            return "<url>"
        host = parts.hostname or ""
        netloc = f"{host}:{port}" if port else host
        hidden = "?…" if parts.query or parts.fragment or "@" in parts.netloc else ""
        return urlunsplit((parts.scheme, netloc, parts.path, "", "")) + hidden

    return URL_IN_TEXT.sub(cut, text)


def registration_summary(body: bytes) -> str:
    """The safe part of a registration request: some field values, and the names of the other fields."""
    try:
        request = json.loads(body)
    except ValueError:
        return f"body is not JSON ({len(body)} bytes)"
    if not isinstance(request, dict):
        return f"body is a JSON {type(request).__name__}, not an object"
    fields = cast(dict, request)
    shown = {k: fields[k] for k in LOGGED_FIELDS if k in fields}
    others = sorted(str(k) for k in fields if k not in LOGGED_FIELDS)
    # json.dumps escapes newlines and other control characters, so a field name cannot forge a log line
    return redact_urls(f"{json.dumps(shown, default=str)[:1000]} other fields: {json.dumps(others)[:500]}")


class RegistrationLog:
    def __init__(self, app, path: str):
        self.app = app
        self.register = f"{path.rstrip('/')}/register"

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope.get("path") != self.register or scope.get("method") != "POST":
            return await self.app(scope, receive, send)
        kept, cut = bytearray(), False

        async def copied():
            # The handler gets every message unchanged; the log keeps at most MAX_LOGGED_BODY bytes
            nonlocal cut
            message = await receive()
            if message["type"] == "http.request":
                piece = message.get("body", b"")
                room = MAX_LOGGED_BODY - len(kept)
                kept.extend(piece[: max(room, 0)])
                cut = cut or len(piece) > room
            return message

        answer: dict = {"status": 0, "body": b""}

        async def watched(message):
            if message["type"] == "http.response.start":
                answer["status"] = message["status"]
            elif message["type"] == "http.response.body" and len(answer["body"]) < 2048:
                answer["body"] += message.get("body", b"")
            await send(message)

        await self.app(scope, copied, watched)
        if answer["status"] >= 400:
            client = (scope.get("client") or ("unknown", 0))[0]
            request = f"body larger than {MAX_LOGGED_BODY} bytes" if cut else registration_summary(bytes(kept))
            logger.warning(
                "client registration refused ip=%s status=%s answer=%s request=%s",
                client,
                answer["status"],
                redact_urls(answer["body"][:500].decode("utf-8", "replace")),
                request,
            )
