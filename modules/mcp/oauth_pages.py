"""The sign-in and consent pages of the MCP OAuth flow, served by the MCP server (Starlette). No Flask here.

The pages are under the public URL of /mcp, such as https://api.example.org/mcp/oauth/login.

1. <url>/authorize (the SDK) stores the request and sends the browser to <url>/oauth/login with the sign-in key.
2. /oauth/login puts the key in a cookie and sends the browser to Discord, with the key as the state.
3. /oauth/callback checks the state against the cookie, gets the Discord user and finds the orgs where
   the user is an officer. It replaces the cookie with a consent key and shows the consent page.
4. POST /oauth/consent checks the consent key in the form against the cookie. On approve it sends the
   browser to the client's redirect URI with a code; on deny, with error=access_denied.
"""

import html
from urllib.parse import urlparse

from anyio import to_thread
from mcp.server.auth.provider import construct_redirect_uri
from starlette.requests import Request
from starlette.responses import HTMLResponse, RedirectResponse, Response
from starlette.routing import Route

from core import audit
from core.config import config
from core.db import db_connect
from core.integrations import registry
from core.integrations.discord import DiscordUnavailable
from core.log import get_logger
from modules.accounts import providers
from modules.auth import machine_tokens
from modules.auth.scopes import SCOPES
from modules.mcp import oauth
from modules.organizations.models import Organization

logger = get_logger(__name__)

COOKIE = "platform_mcp_oauth"
HEADERS = {
    "Cache-Control": "no-store",
    "X-Frame-Options": "DENY",
    # No form-action: browsers apply it to the redirect after the form, and redirect URIs can use any scheme
    "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; frame-ancestors 'none'",
    "Referrer-Policy": "no-referrer",
}


def login_url(key: str) -> str:
    return construct_redirect_uri(f"{oauth.public_url()}/oauth/login", request=key)


def callback_url() -> str:
    """The Discord redirect. It must be a redirect of the Discord app."""
    return f"{oauth.public_url()}/oauth/callback"


def _cookie_path() -> str:
    return f"{oauth.public_path()}/oauth"


def _page(title: str, body: str, status: int = 200) -> HTMLResponse:
    document = (
        '<!doctype html><html><head><meta charset="utf-8">'
        f'<meta name="viewport" content="width=device-width, initial-scale=1"><title>{html.escape(title)}</title>'
        '</head><body style="font-family: system-ui, sans-serif; max-width: 36rem; margin: 4rem auto; '
        f'padding: 0 1rem; line-height: 1.5">{body}</body></html>'
    )
    return HTMLResponse(document, status_code=status, headers=HEADERS)


def _message(message: str, status: int) -> HTMLResponse:
    return _page("Platform sign-in", f"<p>{html.escape(message)}</p>", status)


AGAIN = "Connect again from your MCP client."


def _with_cookie(response: Response, value: str | None) -> Response:
    if value is None:
        response.delete_cookie(COOKIE, path=_cookie_path())
    else:
        response.set_cookie(
            COOKIE,
            value,
            max_age=oauth.REQUEST_SECONDS,
            path=_cookie_path(),
            httponly=True,
            secure=oauth.public_url().startswith("https://"),
            samesite="lax",
        )
    return response


def _session(func, *args):
    db = db_connect.SessionLocal()
    try:
        return func(db, *args)
    finally:
        db.close()


async def login(request: Request) -> Response:
    key = request.query_params.get("request")
    found = await to_thread.run_sync(_session, lambda db: oauth.find_request(db, key, signed_in=False) is not None)
    if not found or not key:
        return _message(f"This sign-in expired or did not start here. {AGAIN}", 400)
    redirect = RedirectResponse(providers.discord_consent_url(config.CLIENT_ID, key, callback_url()), 302)
    return _with_cookie(redirect, key)


def _limit_field(integration: str, name: str) -> str:
    return f"limit:{integration}:{name}"


def _limits_from_form(form) -> tuple[dict, dict[str, str]]:
    """The limits of the form as {integration: {name: [items]}}, and the text of each field to show again."""
    limits: dict[str, dict[str, list[str]]] = {}
    texts: dict[str, str] = {}
    for integration, names in machine_tokens.LIMIT_NAMES.items():
        for name in names:
            text = str(form.get(_limit_field(integration, name)) or "")
            texts[_limit_field(integration, name)] = text
            items = [item for item in text.replace(",", " ").split() if item]
            if items:
                limits.setdefault(integration, {})[name] = items
    return limits, texts


def _limit_inputs(texts: dict[str, str]) -> str:
    groups = []
    for integration, names in sorted(machine_tokens.LIMIT_NAMES.items()):
        found = registry.INTEGRATIONS.get(integration)
        title = html.escape(found.title if found is not None else integration)
        fields = "".join(
            '<label style="display: block; margin: 0.25rem 0">'
            f"<code>{html.escape(name)}</code> "
            f'<input type="text" name="{html.escape(_limit_field(integration, name))}" '
            f'value="{html.escape(texts.get(_limit_field(integration, name), ""))}" style="width: 100%"></label>'
            for name in names
        )
        groups.append(f"<p><strong>{title}</strong></p>{fields}")
    if not groups:
        return ""
    return (
        "<fieldset><legend>Limits (optional)</legend>"
        "<p>Limit the tools of a connected service, as on the Tokens page. Separate items with commas. "
        "Leave a field empty for no limit. Example: <code>my-org/*</code> for repos, "
        "<code>github.*issue*</code> for tools.</p>"
        f"{''.join(groups)}</fieldset>"
    )


WARNING = 'style="padding: 0.75rem; border: 1px solid #b26a00; background: #fff4e5"'


def _identity(client_id: str, name: str) -> str:
    """Who the client is. A metadata document client is the host of its client_id URL; a registered one is not known."""
    host = oauth.client_host(client_id)
    if host is None:
        return (
            f"<p {WARNING}>This client registered itself, so Platform cannot check that it is {name}. "
            "Approve only if you started this connection.</p>"
        )
    return (
        f"<p>Client: <strong>{html.escape(host)}</strong>. Platform read the name and addresses of this client "
        f"from <code>{html.escape(client_id)}</code>.</p>"
    )


def _destination(redirect_uri: str, name: str) -> str:
    """Where the code goes, with the host name first. A warning for an address on this computer."""
    parsed = urlparse(redirect_uri)
    where = parsed.hostname or parsed.scheme
    text = (
        f"<p>After you approve, Platform sends the browser to <strong>{html.escape(where)}</strong> "
        f"(<code>{html.escape(redirect_uri)}</code>).</p>"
    )
    if (parsed.hostname or "") in oauth.LOOPBACK_HOSTS:
        text += (
            f"<p {WARNING}>This address is on your computer. Any program on your computer can use it "
            f"and say that it is {name}. Approve only if you started this connection in {name} a moment ago.</p>"
        )
    return text


def _consent_page(db, row, consent_key: str, error: str | None = None, chosen: dict | None = None) -> HTMLResponse:
    """The consent form. chosen keeps the org, scopes and limit texts of a form with an error."""
    chosen = chosen or {}
    info = oauth.get_client(db, str(row.client_id)) or {}
    name = html.escape(oauth.client_name(info))
    orgs = (
        db.query(Organization)
        .filter(Organization.id.in_(row.officer_org_ids or []), Organization.is_active.is_(True))
        .order_by(Organization.name)
        .all()
    )
    picked = set(chosen["scopes"]) if "scopes" in chosen else set(row.requested_scopes or [])
    options = "".join(
        f'<option value="{int(org.id)}"{" selected" if str(org.id) == chosen.get("org") else ""}>'
        f"{html.escape(str(org.name))} ({html.escape(str(org.prefix))})</option>"
        for org in orgs
    )
    boxes = "".join(
        '<label style="display: block; margin: 0.25rem 0">'
        f'<input type="checkbox" name="scope" value="{html.escape(scope)}"{" checked" if scope in picked else ""}> '
        f"<code>{html.escape(scope)}</code>: {html.escape(SCOPES[scope])}</label>"
        for scope in sorted(SCOPES)
    )
    notice = f'<p style="color: #b00020">{html.escape(error)}</p>' if error else ""
    body = (
        f"<h1>Connect {name} to Platform</h1>"
        f"{_identity(str(row.client_id), name)}"
        f"<p><strong>{name}</strong> asks for a token to call the tools of an org. "
        "It gets the scopes that you choose and sees only that org.</p>"
        f"{_destination(str(row.redirect_uri), name)}"
        f"{notice}"
        f'<form method="post" action="{html.escape(oauth.public_path())}/oauth/consent">'
        f'<input type="hidden" name="consent" value="{html.escape(consent_key)}">'
        f'<p><label>Org <select name="org">{options}</select></label></p>'
        f"<fieldset><legend>Scopes</legend>{boxes}</fieldset>"
        f"{_limit_inputs(chosen.get('limits') or {})}"
        '<p><button type="submit" name="action" value="approve">Approve</button> '
        '<button type="submit" name="action" value="deny">Deny</button></p>'
        "</form>"
        "<p>The connection shows on the Tokens page of the org with the kind <code>oauth</code>. "
        "Revoke it there to disconnect the client. If you stop being an officer of the org, "
        "the connection stops at its next refresh, within an hour. If Discord cannot be reached then, "
        "it can continue for up to 24 hours more.</p>"
    )
    return _page(f"Connect {oauth.client_name(info)}", body, 400 if error else 200)


def _signed_in(db, key: str, discord_id: str):
    row = oauth.find_request(db, key, signed_in=False)
    if row is None:
        return _message(f"This sign-in expired. {AGAIN}", 400), None
    try:
        orgs = oauth.officer_orgs(db, discord_id)
    except DiscordUnavailable:
        logger.warning("Discord unavailable during MCP OAuth sign-in", exc_info=True)
        return _message("Discord is not available now. Try again shortly.", 503), None
    if not orgs:
        oauth.deny(db, row)
        return _message("Only an officer of an org can connect an MCP client. You are not an officer.", 403), None
    consent_key = oauth.signed_in(db, row, discord_id, [o.id for o in orgs])
    return _consent_page(db, row, consent_key), consent_key


async def callback(request: Request) -> Response:
    key = request.cookies.get(COOKIE)
    state = request.query_params.get("state")
    code = request.query_params.get("code")
    if not key or key != state or not code:
        return _with_cookie(
            _message(f"This sign-in did not start in this browser, or you cancelled it. {AGAIN}", 400), None
        )
    try:
        discord_id = await to_thread.run_sync(
            providers.discord_user_id, config.CLIENT_ID, config.CLIENT_SECRET, code, callback_url()
        )
    except providers.ProviderError:
        return _with_cookie(_message(f"Discord sign-in failed. {AGAIN}", 502), None)
    response, consent_key = await to_thread.run_sync(_session, _signed_in, key, discord_id)
    return _with_cookie(response, consent_key)


def _decide(db, key: str, action: str, org: str, scopes: list[str], limits: dict, texts: dict[str, str]):
    """The response to the consent form, and whether to keep the cookie."""
    row = oauth.find_request(db, key, signed_in=True)
    if row is None:
        return _message(f"This sign-in expired. {AGAIN}", 400), False
    redirect_uri, state, discord_id = str(row.redirect_uri), oauth.optional_text(row.state), str(row.discord_id)
    if action != "approve":
        oauth.deny(db, row)
        location = construct_redirect_uri(redirect_uri, error="access_denied", state=state, iss=oauth.public_url())
        return RedirectResponse(location, 303), False
    try:
        org_id = int(org)
    except ValueError:
        org_id = 0
    try:
        code = oauth.approve(db, row, org_id, scopes, limits)
    except oauth.OAuthError as e:
        chosen = {"org": org, "scopes": scopes, "limits": texts}
        return _consent_page(db, row, key, str(e), chosen), True
    prefix = db.query(Organization.prefix).filter_by(id=org_id).scalar()
    audit.record(
        "mcp oauth approved",
        source="mcp",
        org=str(prefix) if prefix else None,
        actor_kind="officer",
        actor_id=discord_id,
        details={"client_id": str(row.client_id), "scopes": oauth.strings(row.scopes), "limits": row.limits or {}},
    )
    # iss (RFC 9207) lets a client that uses more than one authorization server check where the code came from
    location = construct_redirect_uri(redirect_uri, code=code, state=state, iss=oauth.public_url())
    return RedirectResponse(location, 303), False


async def consent(request: Request) -> Response:
    form = await request.form()
    key = str(form.get("consent") or "")
    if not key or request.cookies.get(COOKIE) != key:
        return _message(f"This form did not come from this browser. {AGAIN}", 400)
    scopes = [str(s) for s in form.getlist("scope")]
    limits, texts = _limits_from_form(form)
    response, keep = await to_thread.run_sync(
        _session, _decide, key, str(form.get("action") or ""), str(form.get("org") or ""), scopes, limits, texts
    )
    return response if keep else _with_cookie(response, None)


def routes() -> list[Route]:
    """The page routes, to mount under the public path."""
    return [
        Route("/oauth/login", login, methods=["GET"]),
        Route("/oauth/callback", callback, methods=["GET"]),
        Route("/oauth/consent", consent, methods=["POST"]),
    ]
