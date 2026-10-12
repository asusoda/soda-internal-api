"""OAuth sign-in for the MCP servers of services that take no API key, such as Notion and Google. No Flask here.

An officer starts the sign-in on the Integrations page and signs in with the service. The service sends the
browser back to the callback route with a code, and Platform trades the code for tokens. The tokens are org
secrets named oauth_<key>, refreshed before they expire. The agent acts as the person who signed in.

Notion: Platform finds the sign-in URLs from the MCP server (RFC 9728 and RFC 8414) and registers itself as a
client (RFC 7591). Google: Platform uses the Google OAuth app of connected accounts (ACCOUNTS_GOOGLE_*).
Both use PKCE. The sign-in must finish within PENDING_SECONDS.
"""

import base64
import hashlib
import hmac
import json
import os
import secrets as random
import time
from dataclasses import dataclass
from urllib.parse import urlencode, urlparse

import requests

from core import secrets
from core.errors import ServiceError
from core.log import get_logger
from modules.accounts import providers

logger = get_logger(__name__)

TIMEOUT_SECONDS = 20
PENDING_SECONDS = 900
REFRESH_MARGIN_SECONDS = 60
CALLBACK_PATH = "/api/dashboard/integrations/oauth/callback"
GOOGLE_AUTHORIZE = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN = "https://oauth2.googleapis.com/token"  # nosec B105 - a URL, not a password

secrets.declare_prefix("oauth_", "Sign-in tokens of a service connected with OAuth")


class OAuthError(ServiceError):
    """The sign-in could not start or finish. The message says why, with no secret in it."""


@dataclass(frozen=True)
class Service:
    # The integration key, such as notion
    key: str
    title: str
    # discover: find the URLs from the MCP server and register a client. google: the Google OAuth app.
    kind: str
    # The MCP server the sign-in is for, used to find the URLs
    resource: str = ""
    scopes: tuple[str, ...] = ()


SERVICES: dict[str, Service] = {}


def register(service: Service) -> None:
    SERVICES[service.key] = service


def _token_name(key: str) -> str:
    return f"oauth_{key}"


def _pending_name(key: str) -> str:
    return f"oauth_pending_{key}"


def redirect_uri() -> str:
    return f"{providers.base_url()}{CALLBACK_PATH}"


def _load(db, org_id: int, name: str) -> dict | None:
    raw = secrets.get_secret(db, org_id, name)
    if not raw:
        return None
    try:
        value = json.loads(raw)
    except ValueError:
        return None
    return value if isinstance(value, dict) else None


def _save(db, org_id: int, name: str, value: dict, actor: str | None) -> None:
    try:
        secrets.set_secret(db, org_id, name, json.dumps(value), actor)
    except secrets.SecretsError as e:
        raise OAuthError(str(e)) from e


def _service(key: str) -> Service:
    service = SERVICES.get(key)
    if service is None:
        raise OAuthError("This integration has no OAuth sign-in", 404)
    return service


def ready(key: str) -> str | None:
    """Why the sign-in cannot start on this server, or None when it can."""
    service = _service(key)
    if not providers.base_url():
        return "Set ACCOUNTS_BASE_URL, the public URL of this API, in Doppler"
    if service.kind == "google" and providers.get("google") is None:
        return "Set ACCOUNTS_GOOGLE_CLIENT_ID and ACCOUNTS_GOOGLE_CLIENT_SECRET in Doppler"
    return None


def status(db, org_id: int) -> dict[str, dict]:
    """For each service with OAuth: whether the org signed in, who, when, and why it cannot start."""
    result = {}
    for key, service in SERVICES.items():
        saved = _load(db, org_id, _token_name(key)) or {}
        result[key] = {
            "title": service.title,
            "connected": bool(saved.get("access_token")),
            "connected_by": saved.get("connected_by"),
            "connected_at": saved.get("connected_at"),
            "blocked": ready(key),
        }
    return result


def _get_json(url: str) -> dict | None:
    try:
        response = requests.get(url, timeout=TIMEOUT_SECONDS, headers={"Accept": "application/json"})
    except requests.RequestException:
        return None
    if response.status_code != 200:
        return None
    try:
        body = response.json()
    except ValueError:
        return None
    return body if isinstance(body, dict) else None


def _well_known(url: str, name: str) -> dict | None:
    """The metadata document name for url: first with the URL path appended, then at the root."""
    parsed = urlparse(url)
    origin = f"{parsed.scheme}://{parsed.netloc}"
    path = parsed.path.rstrip("/")
    return (_get_json(f"{origin}/.well-known/{name}{path}") if path else None) or _get_json(
        f"{origin}/.well-known/{name}"
    )


def _discover(resource: str) -> dict:
    """The authorization server metadata for an MCP server."""
    found = _well_known(resource, "oauth-protected-resource") or {}
    servers = found.get("authorization_servers")
    parsed = urlparse(resource)
    issuer = servers[0] if isinstance(servers, list) and servers else f"{parsed.scheme}://{parsed.netloc}"
    meta = _well_known(str(issuer), "oauth-authorization-server") or _well_known(str(issuer), "openid-configuration")
    if not meta or not meta.get("authorization_endpoint") or not meta.get("token_endpoint"):
        raise OAuthError("The service did not say where to sign in", 502)
    return meta


def _register(meta: dict) -> dict:
    """A client registered with the authorization server for this API's callback."""
    endpoint = meta.get("registration_endpoint")
    if not endpoint:
        raise OAuthError("The service does not let Platform register as a client", 502)
    body = {
        "client_name": "Platform",
        "redirect_uris": [redirect_uri()],
        "grant_types": ["authorization_code", "refresh_token"],
        "response_types": ["code"],
        "token_endpoint_auth_method": "none",  # nosec B105 - an OAuth client type, not a password
    }
    try:
        response = requests.post(str(endpoint), json=body, timeout=TIMEOUT_SECONDS)
        client = response.json()
    except (requests.RequestException, ValueError) as e:
        raise OAuthError("The service could not be reached", 502) from e
    if response.status_code >= 400 or not isinstance(client, dict) or not client.get("client_id"):
        raise OAuthError("The service refused to register Platform as a client", 502)
    return client


def _challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode()).digest()
    return base64.urlsafe_b64encode(digest).decode().rstrip("=")


def start(db, org_id: int, key: str, actor: str | None) -> str:
    """The URL where the officer signs in. Saves what the callback needs to finish."""
    service = _service(key)
    blocked = ready(key)
    if blocked:
        raise OAuthError(blocked, 409)
    verifier = random.token_urlsafe(64)
    state = f"{org_id}.{key}.{random.token_urlsafe(32)}"
    params = {
        "response_type": "code",
        "redirect_uri": redirect_uri(),
        "state": state,
        "code_challenge": _challenge(verifier),
        "code_challenge_method": "S256",
    }
    if service.kind == "google":
        app = providers.get("google")
        if app is None:
            raise OAuthError("The Google OAuth app is not set", 409)
        client = {"client_id": app.client_id, "client_secret": app.client_secret}
        authorize, token_url = GOOGLE_AUTHORIZE, GOOGLE_TOKEN
        params |= {"access_type": "offline", "prompt": "consent", "include_granted_scopes": "true"}
    else:
        meta = _discover(service.resource)
        client = _register(meta)
        authorize, token_url = str(meta["authorization_endpoint"]), str(meta["token_endpoint"])
        params["resource"] = service.resource
    params["client_id"] = str(client["client_id"])
    if service.scopes:
        params["scope"] = " ".join(service.scopes)
    pending = {
        "state": state,
        "verifier": verifier,
        "token_url": token_url,
        "client_id": str(client["client_id"]),
        "client_secret": client.get("client_secret") or None,
        "resource": service.resource if service.kind != "google" else None,
        "actor": actor,
        "created": time.time(),
    }
    _save(db, org_id, _pending_name(key), pending, actor)
    return f"{authorize}?{urlencode(params)}"


def _token_request(saved: dict, form: dict) -> dict:
    form = {**form, "client_id": saved["client_id"]}
    if saved.get("client_secret"):
        form["client_secret"] = saved["client_secret"]
    if saved.get("resource"):
        form["resource"] = saved["resource"]
    try:
        response = requests.post(saved["token_url"], data=form, timeout=TIMEOUT_SECONDS)
        body = response.json()
    except (requests.RequestException, ValueError) as e:
        raise OAuthError("The service could not be reached", 502) from e
    if response.status_code >= 400 or not isinstance(body, dict) or not body.get("access_token"):
        error = str(body.get("error", "")) if isinstance(body, dict) else ""
        logger.warning("oauth token request refused status=%s error=%s", response.status_code, error[:64])
        raise OAuthError("The service refused the sign-in", 502)
    return body


def _expires(body: dict) -> float | None:
    expires_in = body.get("expires_in")
    if isinstance(expires_in, int | float) and not isinstance(expires_in, bool):
        return time.time() + float(expires_in)
    return None


def finish(db, state: str, code: str) -> tuple[int, str]:
    """Trade the code for tokens and save them. Returns the org id and the service key."""
    parts = state.split(".", 2)
    if len(parts) != 3 or not parts[0].isdigit() or parts[1] not in SERVICES:
        raise OAuthError("This sign-in was not started here", 400)
    org_id, key = int(parts[0]), parts[1]
    pending = _load(db, org_id, _pending_name(key))
    if pending is None or not hmac.compare_digest(str(pending.get("state", "")), state):
        raise OAuthError("This sign-in was not started here, or it was already used", 400)
    secrets.delete_secret(db, org_id, _pending_name(key))
    if time.time() - float(pending.get("created") or 0) > PENDING_SECONDS:
        raise OAuthError("This sign-in took too long. Start it again", 400)
    body = _token_request(
        pending,
        {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri(),
            "code_verifier": pending["verifier"],
        },
    )
    saved = {
        "access_token": body["access_token"],
        "refresh_token": body.get("refresh_token"),
        "expires_at": _expires(body),
        "token_url": pending["token_url"],
        "client_id": pending["client_id"],
        "client_secret": pending.get("client_secret"),
        "resource": pending.get("resource"),
        "connected_by": pending.get("actor"),
        "connected_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    _save(db, org_id, _token_name(key), saved, pending.get("actor"))
    return org_id, key


def access_token(db, org_id: int, key: str) -> str | None:
    """A current access token for the org, refreshed when it is about to expire, or None when not signed in."""
    saved = _load(db, org_id, _token_name(key))
    if not saved or not saved.get("access_token"):
        return None
    expires_at = saved.get("expires_at")
    if expires_at is None or float(expires_at) - time.time() > REFRESH_MARGIN_SECONDS:
        return str(saved["access_token"])
    if not saved.get("refresh_token"):
        return None
    try:
        body = _token_request(saved, {"grant_type": "refresh_token", "refresh_token": saved["refresh_token"]})
    except OAuthError as e:
        logger.warning("oauth refresh failed org=%s key=%s reason=%s", org_id, key, e.message)
        return None
    saved |= {
        "access_token": body["access_token"],
        "refresh_token": body.get("refresh_token") or saved["refresh_token"],
        "expires_at": _expires(body),
    }
    _save(db, org_id, _token_name(key), saved, saved.get("connected_by"))
    return str(saved["access_token"])


def disconnect(db, org_id: int, key: str) -> None:
    _service(key)
    secrets.delete_secret(db, org_id, _token_name(key))
    secrets.delete_secret(db, org_id, _pending_name(key))


register(
    Service(
        key="notion",
        title="Notion",
        kind="discover",
        resource=os.environ.get("NOTION_MCP_URL", "https://mcp.notion.com/mcp"),
    )
)
register(
    Service(
        key="google",
        title="Google",
        kind="google",
        scopes=(
            "openid",
            "email",
            "https://www.googleapis.com/auth/gmail.readonly",
            "https://www.googleapis.com/auth/gmail.compose",
            "https://www.googleapis.com/auth/drive.readonly",
            "https://www.googleapis.com/auth/drive.file",
            "https://www.googleapis.com/auth/calendar.calendarlist.readonly",
            "https://www.googleapis.com/auth/calendar.events.freebusy",
            "https://www.googleapis.com/auth/calendar.events",
        ),
    )
)
