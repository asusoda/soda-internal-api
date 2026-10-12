"""OAuth for the MCP server: a client registers, an officer approves it, and the client calls tools."""

import base64
import hashlib
import secrets
from urllib.parse import parse_qs, urlparse

import pytest

from tests.contract.conftest import FakeBot

HOST = "https://api.club.test"
# Derived from ACCOUNTS_BASE_URL: the API URL with /mcp
PUBLIC = f"{HOST}/mcp"
REDIRECT = "https://client.test/callback"
INIT = {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "test", "version": "0"}}


@pytest.fixture
def signed_in() -> dict:
    """The Discord user that the fake Discord sign-in returns."""
    return {"discord_id": "900000000000000001"}


@pytest.fixture
def oauth_client(app, monkeypatch, signed_in):
    from starlette.testclient import TestClient

    from core.config import config
    from modules.accounts import providers
    from modules.mcp import oauth
    from modules.mcp.server import build_app

    monkeypatch.setattr(config, "MCP_PUBLIC_URL", "")
    monkeypatch.setenv("ACCOUNTS_BASE_URL", HOST)
    monkeypatch.setattr(oauth, "discord_directory", FakeBot)

    def discord_user_id(client_id, client_secret, code, redirect_uri):
        assert redirect_uri == f"{PUBLIC}/oauth/callback"
        if code == "bad":
            raise providers.ProviderError("Discord sign-in failed")
        return signed_in["discord_id"]

    monkeypatch.setattr(providers, "discord_user_id", discord_user_id)
    with TestClient(build_app(host="api.club.test"), base_url=HOST, follow_redirects=False) as test_client:
        yield test_client


def _register(client, **extra) -> dict:
    body = {"redirect_uris": [REDIRECT], "client_name": "Test Agent", "token_endpoint_auth_method": "none"} | extra
    response = client.post("/mcp/register", json=body)
    assert response.status_code == 201, response.text
    return response.json()


def _pkce() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    return verifier, challenge


def _sign_in(client, client_id: str, challenge: str) -> str:
    """Run /authorize, /oauth/login and /oauth/callback. Returns the consent key of the form."""
    authorize = client.get(
        "/mcp/authorize",
        params={
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": REDIRECT,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "state": "xyz",
        },
    )
    assert authorize.status_code == 302, authorize.text
    login = urlparse(authorize.headers["location"])
    assert f"{login.scheme}://{login.netloc}{login.path}" == f"{PUBLIC}/oauth/login"
    to_discord = client.get(f"/mcp/oauth/login?{login.query}")
    assert to_discord.status_code == 302
    assert to_discord.headers["location"].startswith("https://discord.com/")
    state = parse_qs(urlparse(to_discord.headers["location"]).query)["state"][0]
    consent = client.get("/mcp/oauth/callback", params={"state": state, "code": "discord-code"})
    assert consent.status_code == 200, consent.text
    assert "Test Agent" in consent.text and REDIRECT in consent.text
    assert consent.headers["x-frame-options"] == "DENY"
    return consent.text.split('name="consent" value="')[1].split('"')[0]


def _soda_id(client, officer_headers) -> int:
    orgs = client.get("/api/organizations/", headers=officer_headers).get_json()
    return next(o["id"] for o in orgs if o["prefix"] == "soda")


def _approve(oauth_client, consent_key: str, org_id: int, scopes: list[str]) -> str:
    response = oauth_client.post(
        "/mcp/oauth/consent", data={"consent": consent_key, "org": str(org_id), "scope": scopes, "action": "approve"}
    )
    assert response.status_code == 303, response.text
    location = urlparse(response.headers["location"])
    assert f"{location.scheme}://{location.netloc}{location.path}" == REDIRECT
    query = parse_qs(location.query)
    assert query["state"] == ["xyz"]
    return query["code"][0]


def _token(oauth_client, **form):
    return oauth_client.post("/mcp/token", data=form)


def _rpc(oauth_client, access: str, method: str, params: dict | None = None):
    body = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}}
    headers = {"Authorization": f"Bearer {access}", "Accept": "application/json, text/event-stream"}
    return oauth_client.post("/mcp", json=body, headers=headers)


def test_discovery(oauth_client, client):
    refused = oauth_client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": INIT})
    assert refused.status_code == 401
    assert f'resource_metadata="{HOST}/.well-known/oauth-protected-resource/mcp"' in refused.headers["www-authenticate"]
    # The MCP server and the API (for a proxy that sends only /mcp to the MCP server) give the same documents
    for http in (oauth_client, client):
        resource = http.get("/.well-known/oauth-protected-resource/mcp")
        assert resource.status_code == 200
        body = resource.json() if http is oauth_client else resource.get_json()
        assert body["resource"] == PUBLIC
        assert body["authorization_servers"] == [PUBLIC]
        for where in ("/.well-known/oauth-authorization-server/mcp", "/.well-known/oauth-authorization-server"):
            server = http.get(where)
            assert server.status_code == 200
            body = server.json() if http is oauth_client else server.get_json()
            assert body["issuer"] == PUBLIC
            assert body["authorization_endpoint"] == f"{PUBLIC}/authorize"
            assert body["registration_endpoint"] == f"{PUBLIC}/register"
            assert body["code_challenge_methods_supported"] == ["S256"]
    assert oauth_client.get("/mcp/.well-known/oauth-authorization-server").json()["issuer"] == PUBLIC
    assert client.get("/.well-known/oauth-protected-resource/other").status_code == 404


def test_the_api_has_no_documents_when_oauth_is_off(client, monkeypatch):
    from core.config import config

    monkeypatch.setattr(config, "MCP_PUBLIC_URL", "")
    monkeypatch.delenv("ACCOUNTS_BASE_URL", raising=False)
    assert client.get("/.well-known/oauth-protected-resource/mcp").status_code == 404
    assert client.get("/.well-known/oauth-authorization-server").status_code == 404


@pytest.mark.parametrize(
    ("override", "base", "expected"),
    [
        ("", "https://api.club.test", "https://api.club.test/mcp"),
        ("", "https://api.club.test/", "https://api.club.test/mcp"),
        ("https://pod-8001.proxy.runpod.net/mcp", "https://api.club.test", "https://pod-8001.proxy.runpod.net/mcp"),
        ("https://mcp.club.test", "", "https://mcp.club.test/mcp"),
        ("", "http://localhost:8000", "http://localhost:8000/mcp"),
        ("", "http://api.club.test", ""),
        ("", "", ""),
    ],
)
def test_public_url(monkeypatch, override, base, expected):
    from core.config import config
    from modules.mcp import oauth

    monkeypatch.setattr(config, "MCP_PUBLIC_URL", override)
    monkeypatch.setenv("ACCOUNTS_BASE_URL", base)
    assert oauth.public_url() == expected


def test_a_bad_url_turns_oauth_off(app, monkeypatch):
    from starlette.testclient import TestClient

    from core.config import config
    from modules.mcp.server import build_app

    monkeypatch.setattr(config, "MCP_PUBLIC_URL", "http://mcp.club.test/mcp")
    with TestClient(build_app(host="testserver")) as test_client:
        assert test_client.get("/.well-known/oauth-protected-resource/mcp").status_code == 404
        assert test_client.post("/mcp/register", json={}).status_code == 404


def test_the_token_list_shows_the_mcp_server(oauth_client, client, officer_headers):
    body = client.get(f"/api/organizations/{_soda_id(client, officer_headers)}/tokens", headers=officer_headers)
    assert body.get_json()["mcp"] == {"url": PUBLIC, "oauth": True}


def test_full_flow(client, officer_headers, oauth_client):
    registered = _register(oauth_client)
    assert "client_secret" not in registered
    verifier, challenge = _pkce()
    consent_key = _sign_in(oauth_client, registered["client_id"], challenge)
    soda_id = _soda_id(client, officer_headers)
    code = _approve(oauth_client, consent_key, soda_id, ["org:read"])

    wrong = _token(
        oauth_client,
        grant_type="authorization_code",
        code=code,
        redirect_uri=REDIRECT,
        client_id=registered["client_id"],
        code_verifier="not-the-verifier-" + "x" * 30,
    )
    assert wrong.status_code == 400
    granted = _token(
        oauth_client,
        grant_type="authorization_code",
        code=code,
        redirect_uri=REDIRECT,
        client_id=registered["client_id"],
        code_verifier=verifier,
    )
    assert granted.status_code == 200, granted.text
    tokens = granted.json()
    assert tokens["access_token"].startswith("plat_")
    assert tokens["scope"] == "org:read"
    again = _token(
        oauth_client,
        grant_type="authorization_code",
        code=code,
        redirect_uri=REDIRECT,
        client_id=registered["client_id"],
        code_verifier=verifier,
    )
    assert again.status_code == 400

    assert _rpc(oauth_client, tokens["access_token"], "initialize", INIT).status_code == 200
    listed = _rpc(oauth_client, tokens["access_token"], "tools/list").json()["result"]["tools"]
    assert "org.info" in [t["name"] for t in listed]
    assert "points.leaderboard" not in [t["name"] for t in listed]

    listed_tokens = client.get(f"/api/organizations/{soda_id}/tokens", headers=officer_headers).get_json()["tokens"]
    row = next(t for t in listed_tokens if t["kind"] == "oauth")
    assert row["name"] == "Test Agent" and row["scopes"] == ["org:read"]

    refreshed = _token(
        oauth_client,
        grant_type="refresh_token",
        refresh_token=tokens["refresh_token"],
        client_id=registered["client_id"],
    )
    assert refreshed.status_code == 200, refreshed.text
    fresh = refreshed.json()
    assert _rpc(oauth_client, tokens["access_token"], "tools/list").status_code == 401
    assert _rpc(oauth_client, fresh["access_token"], "tools/list").status_code == 200
    old_refresh = _token(
        oauth_client,
        grant_type="refresh_token",
        refresh_token=tokens["refresh_token"],
        client_id=registered["client_id"],
    )
    assert old_refresh.status_code == 400

    revoked = client.delete(f"/api/organizations/{soda_id}/tokens/{row['id']}", headers=officer_headers)
    assert revoked.status_code == 200, revoked.get_json()
    assert _rpc(oauth_client, fresh["access_token"], "tools/list").status_code == 401
    after = _token(
        oauth_client,
        grant_type="refresh_token",
        refresh_token=fresh["refresh_token"],
        client_id=registered["client_id"],
    )
    assert after.status_code == 400


def test_machine_tokens_still_work(client, officer_headers, oauth_client):
    body = {"name": "test-agent", "kind": "agent", "scopes": ["org:read"]}
    soda_id = _soda_id(client, officer_headers)
    made = client.post(f"/api/organizations/{soda_id}/tokens", json=body, headers=officer_headers).get_json()
    called = _rpc(oauth_client, made["token"], "tools/call", {"name": "org.info", "arguments": {}})
    assert called.status_code == 200
    assert called.json()["result"]["structuredContent"]["prefix"] == "soda"


def test_officer_cannot_make_an_oauth_token_by_hand(client, officer_headers):
    body = {"name": "fake", "kind": "oauth", "scopes": ["org:read"]}
    soda_id = _soda_id(client, officer_headers)
    assert client.post(f"/api/organizations/{soda_id}/tokens", json=body, headers=officer_headers).status_code == 400


def test_deny_sends_access_denied(oauth_client):
    registered = _register(oauth_client)
    consent_key = _sign_in(oauth_client, registered["client_id"], _pkce()[1])
    response = oauth_client.post("/mcp/oauth/consent", data={"consent": consent_key, "action": "deny"})
    assert response.status_code == 303
    assert parse_qs(urlparse(response.headers["location"]).query) == {"error": ["access_denied"], "state": ["xyz"]}


def test_consent_needs_the_browser_that_signed_in(oauth_client, client, officer_headers):
    registered = _register(oauth_client)
    consent_key = _sign_in(oauth_client, registered["client_id"], _pkce()[1])
    oauth_client.cookies.clear()
    form = {"consent": consent_key, "org": str(_soda_id(client, officer_headers)), "scope": "org:read"}
    response = oauth_client.post("/mcp/oauth/consent", data=form | {"action": "approve"})
    assert response.status_code == 400


def test_consent_checks_org_and_scopes(oauth_client, client, officer_headers):
    registered = _register(oauth_client)
    consent_key = _sign_in(oauth_client, registered["client_id"], _pkce()[1])
    ais = next(
        o["id"] for o in client.get("/api/organizations/", headers=officer_headers).get_json() if o["prefix"] == "ais"
    )
    other_org = oauth_client.post(
        "/mcp/oauth/consent", data={"consent": consent_key, "org": str(ais), "scope": "org:read", "action": "approve"}
    )
    assert other_org.status_code == 400 and "officer" in other_org.text
    no_scope = oauth_client.post(
        "/mcp/oauth/consent",
        data={"consent": consent_key, "org": str(_soda_id(client, officer_headers)), "action": "approve"},
    )
    assert no_scope.status_code == 400 and "scopes" in no_scope.text


def test_callback_needs_the_cookie(oauth_client):
    registered = _register(oauth_client)
    _, challenge = _pkce()
    authorize = oauth_client.get(
        "/mcp/authorize",
        params={
            "response_type": "code",
            "client_id": registered["client_id"],
            "redirect_uri": REDIRECT,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        },
    )
    key = parse_qs(urlparse(authorize.headers["location"]).query)["request"][0]
    assert oauth_client.get("/mcp/oauth/callback", params={"state": key, "code": "discord-code"}).status_code == 400


def test_not_an_officer(oauth_client, monkeypatch, signed_in):
    from modules.mcp import oauth

    class NoOfficer(FakeBot):
        def officer_guilds(self, user_id, org_roles):
            return []

    monkeypatch.setattr(oauth, "discord_directory", NoOfficer)
    signed_in["discord_id"] = "900000000000000002"
    registered = _register(oauth_client)
    authorize = oauth_client.get(
        "/mcp/authorize",
        params={
            "response_type": "code",
            "client_id": registered["client_id"],
            "redirect_uri": REDIRECT,
            "code_challenge": _pkce()[1],
            "code_challenge_method": "S256",
        },
    )
    login = oauth_client.get(f"/mcp/oauth/login?{urlparse(authorize.headers['location']).query}")
    state = parse_qs(urlparse(login.headers["location"]).query)["state"][0]
    assert oauth_client.get("/mcp/oauth/callback", params={"state": state, "code": "discord-code"}).status_code == 403


@pytest.mark.parametrize(
    "uri", ["http://evil.test/callback", "javascript:alert(1)", "https://client.test/cb#frag", "data:text/html,x"]
)
def test_unsafe_redirect_uris_are_refused(oauth_client, uri):
    body = {"redirect_uris": [uri], "token_endpoint_auth_method": "none"}
    response = oauth_client.post("/mcp/register", json=body)
    assert response.status_code == 400


def test_loopback_and_app_redirects_are_allowed(oauth_client):
    _register(oauth_client, redirect_uris=["http://127.0.0.1:33418/callback", "cursor://anysphere.cursor-mcp/oauth"])


def test_confidential_client(oauth_client, monkeypatch, client, officer_headers):
    from cryptography.fernet import Fernet

    monkeypatch.setenv("SECRETS_KEY", Fernet.generate_key().decode())
    registered = _register(oauth_client, token_endpoint_auth_method="client_secret_post")
    assert registered["client_secret"]
    verifier, challenge = _pkce()
    code = _approve(
        oauth_client,
        _sign_in(oauth_client, registered["client_id"], challenge),
        _soda_id(client, officer_headers),
        ["org:read"],
    )
    form = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT,
        "client_id": registered["client_id"],
        "code_verifier": verifier,
    }
    assert _token(oauth_client, **form, client_secret="wrong").status_code == 401
    assert _token(oauth_client, **form, client_secret=registered["client_secret"]).status_code == 200


def test_confidential_client_needs_secrets_key(oauth_client, monkeypatch):
    monkeypatch.delenv("SECRETS_KEY", raising=False)
    body = {"redirect_uris": [REDIRECT], "token_endpoint_auth_method": "client_secret_post"}
    response = oauth_client.post("/mcp/register", json=body)
    assert response.status_code == 400
    assert "SECRETS_KEY" in response.json()["error_description"]


def test_cleanup(oauth_client, client, officer_headers):
    import datetime

    from core.db import db_connect
    from modules.auth.models import MachineToken
    from modules.mcp import oauth
    from modules.mcp.models import OAuthClient, OAuthGrant, OAuthRequest

    registered = _register(oauth_client)
    verifier, challenge = _pkce()
    code = _approve(
        oauth_client,
        _sign_in(oauth_client, registered["client_id"], challenge),
        _soda_id(client, officer_headers),
        ["org:read"],
    )
    _token(
        oauth_client,
        grant_type="authorization_code",
        code=code,
        redirect_uri=REDIRECT,
        client_id=registered["client_id"],
        code_verifier=verifier,
    )
    db = db_connect.SessionLocal()
    try:
        grant = db.query(OAuthGrant).filter_by(client_id=registered["client_id"]).one()
        token_id = grant.machine_token_id
        past = datetime.datetime(2020, 1, 1)
        grant.refresh_expires_at = past
        db.query(OAuthClient).filter_by(client_id=registered["client_id"]).update({"last_used_at": past})
        db.add(
            OAuthRequest(client_id=registered["client_id"], redirect_uri=REDIRECT, code_challenge="x", expires_at=past)
        )
        db.commit()
        oauth.cleanup(db)
        assert db.query(OAuthGrant).filter_by(client_id=registered["client_id"]).count() == 0
        assert db.query(OAuthClient).filter_by(client_id=registered["client_id"]).count() == 0
        assert db.query(OAuthRequest).filter_by(client_id=registered["client_id"]).count() == 0
        assert db.query(MachineToken).filter_by(id=token_id).one().revoked_at is not None
    finally:
        db.close()


def _connect(oauth_client, client, officer_headers, **form) -> tuple[dict, dict]:
    """Register, approve with org:read and the extra form fields, and get tokens. Returns (client, tokens)."""
    registered = _register(oauth_client)
    verifier, challenge = _pkce()
    consent_key = _sign_in(oauth_client, registered["client_id"], challenge)
    data = {"consent": consent_key, "org": str(_soda_id(client, officer_headers)), "scope": "org:read"}
    response = oauth_client.post("/mcp/oauth/consent", data=data | form | {"action": "approve"})
    assert response.status_code == 303, response.text
    code = parse_qs(urlparse(response.headers["location"]).query)["code"][0]
    tokens = _token(
        oauth_client,
        grant_type="authorization_code",
        code=code,
        redirect_uri=REDIRECT,
        client_id=registered["client_id"],
        code_verifier=verifier,
    )
    assert tokens.status_code == 200, tokens.text
    return registered, tokens.json()


def _oauth_row(client, officer_headers) -> dict:
    listed = client.get(f"/api/organizations/{_soda_id(client, officer_headers)}/tokens", headers=officer_headers)
    # Newest first
    return next(t for t in listed.get_json()["tokens"] if t["kind"] == "oauth")


def test_consent_sets_integration_limits(oauth_client, client, officer_headers):
    form = {"limit:github:repos": "My-Org/*, my-org/site", "limit:github:tools": ""}
    _connect(oauth_client, client, officer_headers, **form)
    assert _oauth_row(client, officer_headers)["limits"] == {"github": {"repos": ["my-org/*", "my-org/site"]}}


def test_consent_refuses_bad_limits_and_keeps_the_form(oauth_client, client, officer_headers):
    registered = _register(oauth_client)
    consent_key = _sign_in(oauth_client, registered["client_id"], _pkce()[1])
    data = {
        "consent": consent_key,
        "org": str(_soda_id(client, officer_headers)),
        "scope": "org:read",
        "limit:github:repos": "not a repo!",
        "action": "approve",
    }
    response = oauth_client.post("/mcp/oauth/consent", data=data)
    assert response.status_code == 400
    assert "Not a valid repos item" in response.text
    assert 'value="org:read" checked' in response.text
    assert "not a repo!" in response.text


def test_refresh_stops_when_the_officer_loses_the_role(oauth_client, client, officer_headers, monkeypatch):
    from core.db import db_connect
    from modules.auth.models import MachineToken
    from modules.mcp import oauth

    registered, tokens = _connect(oauth_client, client, officer_headers)
    row = _oauth_row(client, officer_headers)

    class NoOfficer(FakeBot):
        def officer_guilds(self, user_id, org_roles):
            return []

    monkeypatch.setattr(oauth, "discord_directory", NoOfficer)
    refused = _token(
        oauth_client,
        grant_type="refresh_token",
        refresh_token=tokens["refresh_token"],
        client_id=registered["client_id"],
    )
    assert refused.status_code == 400
    assert "no longer an officer" in refused.json()["error_description"]
    db = db_connect.SessionLocal()
    try:
        assert db.query(MachineToken).filter_by(id=row["id"]).one().revoked_at is not None
    finally:
        db.close()
    assert _rpc(oauth_client, tokens["access_token"], "tools/list").status_code == 401


def test_refresh_when_discord_does_not_answer(oauth_client, client, officer_headers, monkeypatch):
    import datetime

    from core.db import db_connect
    from core.integrations.discord import DiscordUnavailable
    from modules.mcp import oauth
    from modules.mcp.models import OAuthGrant

    registered, tokens = _connect(oauth_client, client, officer_headers)

    class Down(FakeBot):
        def officer_guilds(self, user_id, org_roles):
            raise DiscordUnavailable("down")

    monkeypatch.setattr(oauth, "discord_directory", Down)
    # A recent check is enough
    first = _token(
        oauth_client,
        grant_type="refresh_token",
        refresh_token=tokens["refresh_token"],
        client_id=registered["client_id"],
    )
    assert first.status_code == 200, first.text
    db = db_connect.SessionLocal()
    try:
        db.query(OAuthGrant).filter_by(client_id=registered["client_id"]).update(
            {"checked_at": datetime.datetime(2020, 1, 1)}
        )
        db.commit()
    finally:
        db.close()
    stale = _token(
        oauth_client,
        grant_type="refresh_token",
        refresh_token=first.json()["refresh_token"],
        client_id=registered["client_id"],
    )
    assert stale.status_code == 400
    assert "cannot check the officer role" in stale.json()["error_description"]


def test_requests_of_one_ip_are_limited(oauth_client, monkeypatch):
    from modules.mcp import oauth

    monkeypatch.setitem(oauth.RATE_LIMITS, "/register", (2, 3600))
    body = {"redirect_uris": [REDIRECT], "token_endpoint_auth_method": "none"}
    assert oauth_client.post("/mcp/register", json=body).status_code == 201
    assert oauth_client.post("/mcp/register", json=body).status_code == 201
    refused = oauth_client.post("/mcp/register", json=body)
    assert refused.status_code == 429
    assert int(refused.headers["retry-after"]) > 0
    # Other routes and the MCP route have their own counts
    assert oauth_client.get("/mcp/oauth/login?request=x").status_code == 400


def test_rate_limit_windows():
    from modules.mcp import oauth

    limiter = oauth.RateLimit(None, "/mcp")
    count, seconds = oauth.RATE_LIMITS["/token"]
    assert limiter._rule("/mcp/token") == "/token"
    assert limiter._rule("/mcp/oauth/consent") == "/oauth"
    assert limiter._rule("/mcp") is None and limiter._rule("/mcp/tokens") is None
    for _ in range(count):
        assert limiter.allow("/token", "1.2.3.4", now=1000.0 * seconds) == 0
    assert limiter.allow("/token", "1.2.3.4", now=1000.0 * seconds) > 0
    assert limiter.allow("/token", "5.6.7.8", now=1000.0 * seconds) == 0
    assert limiter.allow("/token", "1.2.3.4", now=1001.0 * seconds) == 0
