"""OAuth 2.1 for the MCP server: dynamic client registration, the authorization code flow with PKCE, refresh.

Every OAuth URL is under the public URL of /mcp (public_url), so one reverse proxy location reaches them all.
The mcp SDK serves <url>/register, /authorize, /token and /revoke and checks the protocol. This file stores
clients, requests and grants, makes the discovery documents, limits requests of each IP, and is the SDK's
provider. The sign-in and consent pages are in oauth_pages.py.

A client registers itself (RFC 7591), or uses the HTTPS URL of its Client ID Metadata Document as its
client_id (draft-ietf-oauth-client-id-metadata-document). Platform then fetches that document, checks it and
keeps it in oauth_clients for the time that its cache headers allow.

The access token is a machine token of kind oauth, so the MCP server, scopes, limits and the Tokens page
treat it as any other machine token. An officer approves the org, the scopes and the integration limits.
A refresh gives the same machine token row a new value, after a check that the officer still has the
officer role. When an officer revokes that token, the refresh token stops working too. No Flask here.
"""

import datetime
import hashlib
import http.client
import json
import secrets
import socket
import ssl
import threading
import time
from dataclasses import dataclass
from typing import cast
from urllib.parse import urlparse, urlsplit

from anyio import to_thread
from mcp.server.auth import provider as sdk
from mcp.server.auth.routes import build_metadata
from mcp.server.auth.settings import ClientRegistrationOptions, RevocationOptions
from mcp.shared.auth import OAuthClientInformationFull, OAuthToken, ProtectedResourceMetadata
from pydantic import AnyHttpUrl, AnyUrl, ValidationError
from sqlalchemy.exc import IntegrityError

from core import audit, net
from core import secrets as org_secrets
from core.config import config, superadmin_ids
from core.db import db_connect
from core.integrations.discord import DiscordDirectory, DiscordUnavailable
from core.log import get_logger
from core.time import utcnow
from modules.accounts import providers
from modules.auth import machine_tokens
from modules.auth.models import MachineToken
from modules.auth.scopes import SCOPES
from modules.mcp.models import OAuthClient, OAuthGrant, OAuthRequest
from modules.organizations.models import Organization

ACCESS_SECONDS = 3600
REFRESH_DAYS = 30
REQUEST_SECONDS = 600
CODE_SECONDS = 300
REFRESH_PREFIX = "platr_"
MAX_CLIENTS = 5000
MAX_CLIENT_BYTES = 8192
# A refresh needs a new check of the officer role. If Discord does not answer, a check this recent is enough
RECHECK_GRACE = datetime.timedelta(hours=24)
LOOPBACK_HOSTS = ("localhost", "127.0.0.1", "[::1]", "::1")
BLOCKED_SCHEMES = ("javascript", "data", "file", "vbscript", "about", "blob")
# Client ID Metadata Documents: the limits of the URL and the fetch, and how long a document stays cached
METADATA_MAX_URL = 2048
METADATA_MAX_BYTES = 5 * 1024
METADATA_TIMEOUT_SECONDS = 5
METADATA_DEFAULT_CACHE = datetime.timedelta(hours=1)
METADATA_MAX_CACHE = datetime.timedelta(hours=24)
# The document properties that Platform keeps. Others are ignored
METADATA_KEPT = (
    "client_name",
    "client_uri",
    "logo_uri",
    "redirect_uris",
    "grant_types",
    "response_types",
    "scope",
    "contacts",
    "tos_uri",
    "policy_uri",
    "software_id",
    "software_version",
)
USER_AGENT = "Platform MCP OAuth (+https://platform.thesoda.io)"
# The only client authentication of a document client: none, a public client with PKCE
PUBLIC_CLIENT = "none"
REGISTRATION = ClientRegistrationOptions(enabled=True)
REVOCATION = RevocationOptions(enabled=True)
# Requests of one client IP in a window, by the path under the public URL: (count, seconds)
RATE_LIMITS: dict[str, tuple[int, int]] = {
    "/register": (10, 3600),
    "/authorize": (30, 60),
    "/oauth": (30, 60),
    "/token": (60, 60),
    "/revoke": (30, 60),
}

logger = get_logger(__name__)
_directory: DiscordDirectory | None = None


class OAuthError(ValueError):
    pass


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _now() -> datetime.datetime:
    return utcnow()


def _epoch(moment: object) -> int:
    """Seconds since 1970 for a naive UTC datetime column."""
    return int(cast(datetime.datetime, moment).replace(tzinfo=datetime.UTC).timestamp())


def strings(value: object) -> list[str]:
    """A JSON list column as a list of strings."""
    return [str(v) for v in cast(list, value or [])]


def optional_text(value: object) -> str | None:
    return None if value is None else str(value)


# The public URL and the discovery documents


def url_problem(url: str) -> str | None:
    """Why OAuth cannot use this public URL of /mcp, or None when it can."""
    parsed = urlparse(url)
    if not parsed.hostname or parsed.query or parsed.fragment:
        return f"{url} must be a URL with no query or fragment"
    if parsed.scheme != "https" and not (parsed.scheme == "http" and parsed.hostname in LOOPBACK_HOSTS):
        return f"{url} must use https, or http on localhost"
    return None


def configured_url() -> str:
    """MCP_PUBLIC_URL, else <ACCOUNTS_BASE_URL>/mcp, else "". A URL with no path gets /mcp."""
    url = config.MCP_PUBLIC_URL or (f"{providers.base_url()}/mcp" if providers.base_url() else "")
    if url and urlparse(url).path in ("", "/"):
        url = url.rstrip("/") + "/mcp"
    return url.rstrip("/")


def public_url() -> str:
    """The public URL of /mcp, such as https://api.example.org/mcp, or "" when OAuth is off."""
    url = configured_url()
    return url if url and url_problem(url) is None else ""


def public_path() -> str:
    """The path of the public URL, such as /mcp. The MCP server serves /mcp and OAuth under it."""
    return urlparse(public_url()).path or "/mcp"


def resource_metadata_path() -> str:
    """Where a client reads the protected resource metadata (RFC 9728), at the root of the host."""
    return f"/.well-known/oauth-protected-resource{public_path()}"


def server_metadata_paths() -> list[str]:
    """Where a client looks for the authorization server metadata (RFC 8414) at the root of the host."""
    return [f"/.well-known/oauth-authorization-server{public_path()}", "/.well-known/oauth-authorization-server"]


def resource_metadata() -> dict:
    url = AnyHttpUrl(public_url())
    return ProtectedResourceMetadata(resource=url, authorization_servers=[url]).model_dump(
        mode="json", exclude_none=True
    )


def server_metadata_model():
    """The authorization server metadata (RFC 8414). It adds Client ID Metadata Documents and RFC 9207 iss."""
    metadata = build_metadata(AnyHttpUrl(public_url()), None, REGISTRATION, REVOCATION)
    metadata.client_id_metadata_document_supported = True
    metadata.authorization_response_iss_parameter_supported = True
    return metadata


def server_metadata() -> dict:
    return server_metadata_model().model_dump(mode="json", exclude_none=True)


def same_resource(resource: str) -> bool:
    """Whether an RFC 8707 resource names this MCP server: its public URL, or a path above it on the same origin."""
    ours, theirs = urlsplit(public_url()), urlsplit(resource.strip())
    if (theirs.scheme.lower(), (theirs.netloc or "").lower()) != (ours.scheme.lower(), ours.netloc.lower()):
        return False
    if theirs.query or theirs.fragment:
        return False
    path = theirs.path.rstrip("/")
    return ours.path.rstrip("/") == path or ours.path.startswith(path + "/")


# Requests of each IP


class RateLimit:
    """ASGI middleware: at most RATE_LIMITS requests of one client IP in a window. Counts in this process.

    The client IP is the address that uvicorn gives. Behind a reverse proxy, set FORWARDED_ALLOW_IPS to
    the proxy's address, so that uvicorn uses X-Forwarded-For.
    """

    MAX_KEYS = 50000

    def __init__(self, app, prefix: str):
        self.app = app
        self.prefix = prefix.rstrip("/")
        self.counts: dict[tuple[str, str], tuple[int, int]] = {}
        self.lock = threading.Lock()

    def _rule(self, path: str) -> str | None:
        if not path.startswith(self.prefix + "/"):
            return None
        rest = path[len(self.prefix) :]
        return next((r for r in RATE_LIMITS if rest == r or rest.startswith(r + "/")), None)

    def allow(self, rule: str, ip: str, now: float | None = None) -> int:
        """0 when the request may go on, else the seconds until the window ends."""
        count, seconds = RATE_LIMITS[rule]
        moment = time.time() if now is None else now
        window = int(moment // seconds)
        with self.lock:
            if len(self.counts) >= self.MAX_KEYS:
                self.counts = {k: v for k, v in self.counts.items() if v[0] == int(moment // RATE_LIMITS[k[0]][1])}
            seen_window, seen = self.counts.get((rule, ip), (window, 0))
            used = seen if seen_window == window else 0
            if used >= count:
                return max(1, int((window + 1) * seconds - moment))
            self.counts[(rule, ip)] = (window, used + 1)
        return 0

    async def __call__(self, scope, receive, send):
        rule = self._rule(scope.get("path", "")) if scope["type"] == "http" else None
        if rule is None:
            return await self.app(scope, receive, send)
        client = scope.get("client") or ("unknown", 0)
        wait = self.allow(rule, str(client[0]))
        if not wait:
            return await self.app(scope, receive, send)
        body = json.dumps({"error": "too_many_requests", "error_description": "Too many requests. Try again later"})
        await send(
            {
                "type": "http.response.start",
                "status": 429,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"retry-after", str(wait).encode()),
                    (b"content-length", str(len(body)).encode()),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body.encode()})


# Clients


def check_redirect_uri(uri: str) -> None:
    """Refuse a redirect URI that a browser cannot use safely. Plain http is only for this computer."""
    parsed = urlparse(uri)
    scheme = parsed.scheme.lower()
    if not scheme or scheme in BLOCKED_SCHEMES:
        raise OAuthError(f"Redirect URI {uri} is not allowed")
    if scheme == "http" and (parsed.hostname or "") not in LOOPBACK_HOSTS:
        raise OAuthError(f"Redirect URI {uri} must use https, or http on localhost")
    if parsed.fragment:
        raise OAuthError(f"Redirect URI {uri} must not have a fragment")


def register_client(db, info: dict) -> None:
    """Store a client from the SDK's registration handler. Raises OAuthError. Commits."""
    secret = info.pop("client_secret", None)
    for uri in info.get("redirect_uris") or []:
        check_redirect_uri(str(uri))
    if len(json.dumps(info, default=str)) > MAX_CLIENT_BYTES:
        raise OAuthError("The client metadata is too large")
    if db.query(OAuthClient).count() >= MAX_CLIENTS:
        raise OAuthError("This server cannot register more clients now")
    ciphertext = None
    if secret:
        ciphertext = org_secrets.encrypt(secret)
        if ciphertext is None:
            raise OAuthError('This server has no SECRETS_KEY. Register with token_endpoint_auth_method "none"')
    db.add(OAuthClient(client_id=info["client_id"], info=info, secret_ciphertext=ciphertext))
    db.commit()


# Client ID Metadata Documents


def is_metadata_url(client_id: str) -> bool:
    """Whether a client_id is the URL of a Client ID Metadata Document, not an id from /register."""
    return client_id.startswith("https://")


def check_metadata_url(url: str) -> None:
    """Refuse a client_id URL that the draft does not allow. Raises OAuthError."""
    parts = urlsplit(url)
    if len(url) > METADATA_MAX_URL:
        raise OAuthError(f"The client_id URL is longer than {METADATA_MAX_URL} characters")
    if parts.scheme != "https" or not parts.hostname:
        raise OAuthError("The client_id URL must use https")
    if parts.username is not None or parts.password is not None:
        raise OAuthError("The client_id URL must not have a user name or password")
    if parts.fragment or "#" in url:
        raise OAuthError("The client_id URL must not have a fragment")
    if len(parts.path) < 2:
        raise OAuthError("The client_id URL must have a path, such as /client.json")
    if {".", ".."} & set(parts.path.split("/")):
        raise OAuthError("The client_id URL must not have . or .. segments")


@dataclass(frozen=True)
class Fetched:
    status: int
    headers: dict[str, str]
    body: bytes


class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    """HTTPS to an address that was checked before. The certificate must still match the host name."""

    def __init__(self, host: str, port: int, address: str, timeout: float):
        self._tls = ssl.create_default_context()
        super().__init__(host, port, timeout=timeout, context=self._tls)
        self._address = address

    def connect(self) -> None:
        sock = socket.create_connection((self._address, self.port), self.timeout)
        self.sock = self._tls.wrap_socket(sock, server_hostname=self.host)


def fetch_metadata_document(url: str) -> Fetched:
    """GET a Client ID Metadata Document. Raises OAuthError.

    The host must resolve only to public addresses, and the connection goes to one of those addresses. Platform
    does not follow redirects and reads at most METADATA_MAX_BYTES and one byte more.
    """
    parts = urlsplit(url)
    host, port = str(parts.hostname), parts.port or 443
    try:
        address = net.public_addresses(host, port)[0]
    except (net.NoHost, net.NotPublic) as e:
        raise OAuthError(str(e)) from e
    target = parts.path + (f"?{parts.query}" if parts.query else "")
    connection = _PinnedHTTPSConnection(host, port, address, METADATA_TIMEOUT_SECONDS)
    try:
        connection.request("GET", target, headers={"Accept": "application/json", "User-Agent": USER_AGENT})
        response = connection.getresponse()
        body = response.read(METADATA_MAX_BYTES + 1)
        return Fetched(response.status, {k.lower(): v for k, v in response.getheaders()}, body)
    except (OSError, http.client.HTTPException) as e:
        raise OAuthError(f"The client metadata document could not be fetched: {type(e).__name__}") from e
    finally:
        connection.close()


def cache_time(headers: dict[str, str]) -> datetime.timedelta:
    """How long to keep a document: its Cache-Control max-age, from 0 to METADATA_MAX_CACHE."""
    directives = [d.strip().lower() for d in headers.get("cache-control", "").split(",") if d.strip()]
    if "no-store" in directives or "no-cache" in directives:
        return datetime.timedelta(0)
    for directive in directives:
        name, _, value = directive.partition("=")
        if name == "max-age" and value.strip().isdigit():
            return min(datetime.timedelta(seconds=int(value.strip())), METADATA_MAX_CACHE)
    return METADATA_DEFAULT_CACHE


def client_from_document(url: str, fetched: Fetched) -> dict:
    """The client metadata from a fetched document, after the checks of the draft and the MCP spec. Raises OAuthError."""
    if fetched.status != 200:
        raise OAuthError(f"The client metadata document returned {fetched.status}, not 200")
    if len(fetched.body) > METADATA_MAX_BYTES:
        raise OAuthError(f"The client metadata document is larger than {METADATA_MAX_BYTES} bytes")
    try:
        document = json.loads(fetched.body)
    except ValueError as e:
        raise OAuthError("The client metadata document is not JSON") from e
    if not isinstance(document, dict):
        raise OAuthError("The client metadata document must be a JSON object")
    if document.get("client_id") != url:
        raise OAuthError("The client_id in the document must be the URL of the document")
    for name in ("client_name", "redirect_uris"):
        if not document.get(name):
            raise OAuthError(f"The client metadata document must have {name}")
    if "client_secret" in document or "client_secret_expires_at" in document:
        raise OAuthError("The client metadata document must not have a client secret")
    method = document.get("token_endpoint_auth_method", PUBLIC_CLIENT)
    if method != PUBLIC_CLIENT:
        raise OAuthError(f'token_endpoint_auth_method "{method}" is not supported. Use "{PUBLIC_CLIENT}"')
    uris = document["redirect_uris"]
    if not isinstance(uris, list) or not all(isinstance(u, str) for u in uris):
        raise OAuthError("redirect_uris must be a list of URLs")
    for uri in uris:
        check_redirect_uri(uri)
    info = {key: document[key] for key in METADATA_KEPT if key in document}
    grants = info.setdefault("grant_types", ["authorization_code", "refresh_token"])
    if not isinstance(grants, list) or "authorization_code" not in grants:
        raise OAuthError("grant_types must have authorization_code")
    responses = info.setdefault("response_types", ["code"])
    if not isinstance(responses, list) or "code" not in responses:
        raise OAuthError("response_types must have code")
    # Platform scopes are granted on the consent page, so a client can ask for any of them
    asked = set(str(info.get("scope") or "").split())
    info |= {
        "client_id": url,
        "token_endpoint_auth_method": PUBLIC_CLIENT,
        "scope": " ".join(sorted(asked | set(SCOPES))),
    }
    try:
        return OAuthClientInformationFull.model_validate(info).model_dump(mode="json", exclude_none=True)
    except ValidationError as e:
        raise OAuthError(f"The client metadata document is not valid: {e.errors()[0]['msg']}") from e


def resolve_client(db, client_id: str) -> dict | None:
    """The metadata of a client: a registered one, or the document at a client_id URL. Commits a fetched document.

    A cached document is used until its cache time ends. A document that cannot be fetched or is not valid
    gives None, and is not cached.
    """
    if not is_metadata_url(client_id):
        return get_client(db, client_id)
    now = _now()
    row = db.query(OAuthClient).filter_by(client_id=client_id).first()
    if row is not None and row.cache_until is not None and cast(datetime.datetime, row.cache_until) > now:
        return dict(cast(dict, row.info))
    try:
        check_metadata_url(client_id)
        fetched = fetch_metadata_document(client_id)
        info = client_from_document(client_id, fetched)
    except OAuthError as e:
        logger.warning("client metadata document refused client_id=%s: %s", client_id, e)
        return None
    until = now + cache_time(fetched.headers)
    if row is None:
        if db.query(OAuthClient).count() >= MAX_CLIENTS:
            logger.warning("client metadata document refused client_id=%s: too many clients", client_id)
            return None
        db.add(OAuthClient(client_id=client_id, info=info, cache_until=until))
    else:
        row.info = info
        row.cache_until = until
    try:
        db.commit()
    except IntegrityError:
        # Another request stored the same document first
        db.rollback()
    return info


def client_host(client_id: str) -> str | None:
    """The host name of a client_id URL, which the consent page shows. None for a registered client."""
    return urlsplit(client_id).hostname if is_metadata_url(client_id) else None


def get_client(db, client_id: str) -> dict | None:
    """The stored metadata of a client with its secret, or None. A document client gets its last cached document."""
    row = db.query(OAuthClient).filter_by(client_id=client_id).first()
    if row is None:
        return None
    info = dict(row.info)
    if row.secret_ciphertext is not None:
        secret = org_secrets.decrypt(str(row.secret_ciphertext))
        if secret is None:
            return None
        info["client_secret"] = secret
    return info


def _touch(db, client_id: str) -> None:
    db.query(OAuthClient).filter_by(client_id=client_id).update({"last_used_at": _now()})


def client_name(info: dict) -> str:
    return str(info.get("client_name") or "MCP client").strip()[:120] or "MCP client"


# Authorization requests


def start(db, client_id: str, params: dict) -> str:
    """Store a request from /authorize. Returns the sign-in key for the browser cookie. Commits."""
    key = secrets.token_urlsafe(32)
    db.add(
        OAuthRequest(
            client_id=client_id,
            key_hash=_hash(key),
            redirect_uri=params["redirect_uri"],
            redirect_uri_explicit=params["redirect_uri_provided_explicitly"],
            state=params.get("state"),
            code_challenge=params["code_challenge"],
            requested_scopes=params.get("scopes"),
            resource=params.get("resource"),
            expires_at=_now() + datetime.timedelta(seconds=REQUEST_SECONDS),
        )
    )
    _touch(db, client_id)
    db.commit()
    return key


def find_request(db, key: str | None, *, signed_in: bool) -> OAuthRequest | None:
    """The open request for a cookie key: before Discord sign-in, or after it when signed_in is True."""
    if not key:
        return None
    row = db.query(OAuthRequest).filter_by(key_hash=_hash(key)).first()
    if row is None or row.expires_at <= _now() or row.code_hash is not None:
        return None
    if (row.discord_id is not None) != signed_in:
        return None
    return row


def discord_directory():
    """The Discord directory that reads officer roles with BOT_TOKEN."""
    global _directory
    if _directory is None:
        _directory = DiscordDirectory(config.BOT_TOKEN)
    return _directory


def officer_orgs(db, discord_id: str) -> list[Organization]:
    """Active orgs where the member holds the officer role, by name. Raises DiscordUnavailable."""
    orgs = db.query(Organization).filter_by(is_active=True).order_by(Organization.name).all()
    if discord_id in superadmin_ids():
        return orgs
    directory = discord_directory()
    if not directory.is_ready():
        raise DiscordUnavailable("BOT_TOKEN is not set")
    guilds = {
        str(g) for g in directory.officer_guilds(discord_id, [(str(o.guild_id), o.officer_role_id) for o in orgs])
    }
    return [o for o in orgs if str(o.guild_id) in guilds]


def signed_in(db, row: OAuthRequest, discord_id: str, org_ids: list[int]) -> str:
    """Record the Discord sign-in. Returns the consent key, which replaces the sign-in key. Commits."""
    key = secrets.token_urlsafe(32)
    row.discord_id = discord_id
    row.officer_org_ids = org_ids
    row.key_hash = _hash(key)
    db.commit()
    return key


def approve(db, row: OAuthRequest, organization_id: int, scopes: list[str], limits: dict | None = None) -> str:
    """Make the authorization code for an approved request. Returns the code. Raises OAuthError. Commits.

    limits is {integration: {name: [items]}}, as on the Tokens page.
    """
    if organization_id not in (row.officer_org_ids or []):
        raise OAuthError("Choose an org where you are an officer")
    chosen = sorted(set(scopes) & set(SCOPES))
    if not chosen:
        raise OAuthError("Choose one or more scopes")
    try:
        cleaned = machine_tokens.check_limits(limits)
    except machine_tokens.TokenError as e:
        raise OAuthError(str(e)) from e
    code = secrets.token_urlsafe(32)
    row.organization_id = organization_id
    row.scopes = chosen
    row.limits = cleaned
    row.code_hash = _hash(code)
    row.key_hash = None
    row.expires_at = _now() + datetime.timedelta(seconds=CODE_SECONDS)
    db.commit()
    return code


def deny(db, row: OAuthRequest) -> None:
    db.delete(row)
    db.commit()


def load_code(db, client_id: str, code: str) -> OAuthRequest | None:
    row = db.query(OAuthRequest).filter_by(code_hash=_hash(code), client_id=client_id).first()
    if row is None or row.expires_at <= _now() or row.organization_id is None:
        return None
    return row


# Tokens


def _token(access: str, refresh: str, scopes: list[str]) -> dict:
    return {
        "access_token": access,
        "expires_in": ACCESS_SECONDS,
        "scope": " ".join(scopes),
        "refresh_token": refresh,
    }


def exchange_code(db, client_id: str, code: str) -> dict:
    """Use an authorization code once and make the grant. Raises OAuthError. Commits."""
    row = load_code(db, client_id, code)
    if row is None:
        raise OAuthError("The authorization code is not valid")
    # The delete finds the row only once, so a code that two requests send gives one grant
    if db.query(OAuthRequest).filter_by(id=row.id, code_hash=row.code_hash).delete() != 1:
        db.rollback()
        raise OAuthError("The authorization code is not valid")
    client = db.query(OAuthClient).filter_by(client_id=client_id).first()
    name = client_name(dict(client.info)) if client is not None else "MCP client"
    access, token_row = machine_tokens.issue_oauth(
        db,
        organization_id=cast(int, row.organization_id),
        name=name,
        scopes=strings(row.scopes),
        created_by=str(row.discord_id),
        expires_seconds=ACCESS_SECONDS,
        limits=cast(dict, row.limits) or None,
    )
    refresh = REFRESH_PREFIX + secrets.token_urlsafe(32)
    db.add(
        OAuthGrant(
            machine_token_id=token_row.id,
            client_id=client_id,
            refresh_hash=_hash(refresh),
            refresh_expires_at=_now() + datetime.timedelta(days=REFRESH_DAYS),
            resource=row.resource,
        )
    )
    _touch(db, client_id)
    db.commit()
    return _token(access, refresh, strings(token_row.scopes))


def _grant_for_refresh(db, client_id: str, refresh: str) -> tuple[OAuthGrant, MachineToken] | None:
    if not refresh.startswith(REFRESH_PREFIX):
        return None
    grant = db.query(OAuthGrant).filter_by(refresh_hash=_hash(refresh), client_id=client_id).first()
    if grant is None or grant.refresh_expires_at <= _now():
        return None
    token = db.query(MachineToken).filter_by(id=grant.machine_token_id).first()
    if token is None or token.revoked_at is not None:
        return None
    return grant, token


def load_refresh(db, client_id: str, refresh: str) -> dict | None:
    found = _grant_for_refresh(db, client_id, refresh)
    if found is None:
        return None
    grant, token = found
    return {
        "token_id": cast(int, token.id),
        "scopes": strings(token.scopes),
        "expires_at": _epoch(grant.refresh_expires_at),
        "resource": optional_text(grant.resource),
        "subject": optional_text(token.created_by),
    }


def exchange_refresh(db, client_id: str, refresh: str, scopes: list[str]) -> dict:
    """New access and refresh tokens for a grant. The old values stop working. Raises OAuthError. Commits."""
    found = _grant_for_refresh(db, client_id, refresh)
    if found is None:
        raise OAuthError("The refresh token is not valid")
    grant, token = found
    now = _now()
    checked = _still_officer(db, token)
    if checked is False:
        machine_tokens.revoke(db, cast(int, token.organization_id), cast(int, token.id))
        audit.record(
            "mcp oauth revoked",
            source="mcp",
            actor_kind="system",
            actor_id=optional_text(token.created_by),
            details={"client_id": client_id, "token_id": cast(int, token.id), "reason": "not_officer"},
        )
        raise OAuthError("The officer who approved this connection is no longer an officer of the org")
    if checked is None and cast(datetime.datetime, grant.checked_at) <= now - RECHECK_GRACE:
        raise OAuthError("Platform cannot check the officer role now. Try again later")
    new_refresh = REFRESH_PREFIX + secrets.token_urlsafe(32)
    # The update finds the old hash only once, so a refresh token that two requests send rotates once
    changed = (
        db.query(OAuthGrant)
        .filter_by(id=grant.id, refresh_hash=grant.refresh_hash)
        .update(
            {
                "refresh_hash": _hash(new_refresh),
                "refresh_expires_at": now + datetime.timedelta(days=REFRESH_DAYS),
                **({"checked_at": now} if checked else {}),
            }
        )
    )
    if changed != 1:
        db.rollback()
        raise OAuthError("The refresh token is not valid")
    access = machine_tokens.rotate(db, token, ACCESS_SECONDS, scopes)
    _touch(db, client_id)
    db.commit()
    return _token(access, new_refresh, strings(token.scopes))


def _still_officer(db, token: MachineToken) -> bool | None:
    """Whether the officer who approved the token still has the officer role in its org. None if Discord cannot tell."""
    try:
        orgs = officer_orgs(db, str(token.created_by))
    except DiscordUnavailable:
        logger.warning("Discord unavailable during the officer check of an MCP OAuth refresh", exc_info=True)
        return None
    return cast(int, token.organization_id) in {cast(int, o.id) for o in orgs}


def client_of_token(db, token_id: int) -> str | None:
    """The OAuth client id of a machine token, or None for a token that an officer made."""
    grant = db.query(OAuthGrant).filter_by(machine_token_id=token_id).first()
    return str(grant.client_id) if grant is not None else None


def revoke(db, token_id: int) -> None:
    """Revoke the machine token of a grant. Its access and refresh tokens stop working. Commits."""
    row = db.query(MachineToken).filter_by(id=token_id).first()
    if row is not None:
        machine_tokens.revoke(db, int(row.organization_id), token_id)


def cleanup(db) -> dict:
    """Delete old requests, finished grants and unused clients. Commits."""
    now = _now()
    requests = db.query(OAuthRequest).filter(OAuthRequest.expires_at <= now).delete(synchronize_session=False)
    finished = [
        (grant.id, grant.machine_token_id)
        for grant, token in db.query(OAuthGrant, MachineToken).outerjoin(
            MachineToken, MachineToken.id == OAuthGrant.machine_token_id
        )
        if token is None or token.revoked_at is not None or grant.refresh_expires_at <= now
    ]
    # An expired grant leaves no live token on the Tokens page
    db.query(MachineToken).filter(
        MachineToken.id.in_([token_id for _, token_id in finished]), MachineToken.revoked_at.is_(None)
    ).update({"revoked_at": now}, synchronize_session=False)
    db.query(OAuthGrant).filter(OAuthGrant.id.in_([grant_id for grant_id, _ in finished])).delete(
        synchronize_session=False
    )
    in_use = db.query(OAuthGrant.client_id)
    unused = (
        db.query(OAuthClient)
        .filter(OAuthClient.last_used_at <= now - datetime.timedelta(days=7), ~OAuthClient.client_id.in_(in_use))
        .delete(synchronize_session=False)
    )
    db.commit()
    return {"requests": requests, "grants": len(finished), "clients": unused}


# The SDK provider


class PlatformAccessToken(sdk.AccessToken):
    token_id: int


class PlatformRefreshToken(sdk.RefreshToken):
    token_id: int


def _session(func, *args):
    db = db_connect.SessionLocal()
    try:
        return func(db, *args)
    finally:
        db.close()


async def _run(func, *args):
    return await to_thread.run_sync(_session, func, *args)


def _verify(db, token: str) -> PlatformAccessToken | None:
    caller = machine_tokens.verify(db, token)
    if caller is None:
        return None
    return PlatformAccessToken(
        token=token,
        client_id=client_of_token(db, caller.token_id) or caller.actor,
        scopes=sorted(caller.scopes),
        subject=caller.created_by,
        token_id=caller.token_id,
    )


class Provider(sdk.OAuthAuthorizationServerProvider[sdk.AuthorizationCode, PlatformRefreshToken, PlatformAccessToken]):
    """The OAuthAuthorizationServerProvider of the mcp SDK. login_url gives the sign-in page of a request."""

    def __init__(self, login_url):
        self.login_url = login_url

    async def get_client(self, client_id: str) -> OAuthClientInformationFull | None:
        info = await _run(resolve_client, client_id)
        return OAuthClientInformationFull.model_validate(info) if info is not None else None

    async def register_client(self, client_info: OAuthClientInformationFull) -> None:
        # Platform scopes are granted on the consent page, so a client can ask for any of them
        asked = set((client_info.scope or "").split())
        client_info.scope = " ".join(sorted(asked | set(SCOPES)))
        try:
            await _run(register_client, client_info.model_dump(mode="json", exclude_none=True))
        except OAuthError as e:
            code = "invalid_redirect_uri" if "Redirect URI" in str(e) else "invalid_client_metadata"
            raise sdk.RegistrationError(code, str(e)) from e

    async def authorize(self, client: OAuthClientInformationFull, params: sdk.AuthorizationParams) -> str:
        if params.resource and not same_resource(params.resource):
            raise sdk.AuthorizeError("invalid_target", f"This server is {public_url()}, not {params.resource}")
        key = await _run(start, str(client.client_id), params.model_dump(mode="json"))
        return self.login_url(key)

    async def load_authorization_code(
        self, client: OAuthClientInformationFull, authorization_code: str
    ) -> sdk.AuthorizationCode | None:
        def load(db):
            row = load_code(db, str(client.client_id), authorization_code)
            if row is None:
                return None
            return sdk.AuthorizationCode(
                code=authorization_code,
                scopes=strings(row.scopes),
                expires_at=float(_epoch(row.expires_at)),
                client_id=str(row.client_id),
                code_challenge=str(row.code_challenge),
                redirect_uri=AnyUrl(str(row.redirect_uri)),
                redirect_uri_provided_explicitly=bool(row.redirect_uri_explicit),
                resource=optional_text(row.resource),
                subject=optional_text(row.discord_id),
            )

        return await _run(load)

    async def exchange_authorization_code(
        self, client: OAuthClientInformationFull, authorization_code: sdk.AuthorizationCode
    ) -> OAuthToken:
        try:
            token = await _run(exchange_code, str(client.client_id), authorization_code.code)
        except OAuthError as e:
            raise sdk.TokenError("invalid_grant", str(e)) from e
        return OAuthToken.model_validate(token)

    async def load_refresh_token(
        self, client: OAuthClientInformationFull, refresh_token: str
    ) -> PlatformRefreshToken | None:
        found = await _run(load_refresh, str(client.client_id), refresh_token)
        if found is None:
            return None
        return PlatformRefreshToken(token=refresh_token, client_id=str(client.client_id), **found)

    async def exchange_refresh_token(
        self, client: OAuthClientInformationFull, refresh_token: PlatformRefreshToken, scopes: list[str]
    ) -> OAuthToken:
        try:
            token = await _run(exchange_refresh, str(client.client_id), refresh_token.token, scopes)
        except OAuthError as e:
            raise sdk.TokenError("invalid_grant", str(e)) from e
        return OAuthToken.model_validate(token)

    async def load_access_token(self, token: str) -> PlatformAccessToken | None:
        return await _run(_verify, token)

    async def revoke_token(self, token: PlatformAccessToken | PlatformRefreshToken) -> None:
        await _run(revoke, token.token_id)

    async def verify_token(self, token: str) -> PlatformAccessToken | None:
        """The SDK's TokenVerifier: every machine token, also one that an officer made, opens /mcp."""
        return await self.load_access_token(token)
