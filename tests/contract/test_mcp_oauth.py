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


def _sign_in(client, client_id: str, challenge: str, name: str = "Test Agent") -> str:
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
    assert name in consent.text and REDIRECT in consent.text
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
    assert query["iss"] == [PUBLIC]
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
        # Spec clients insert the issuer's path; Composio reads only the root and needs this same issuer
        for where in ("/.well-known/oauth-authorization-server/mcp", "/.well-known/oauth-authorization-server"):
            server = http.get(where)
            assert server.status_code == 200
            body = server.json() if http is oauth_client else server.get_json()
            assert body["issuer"] == PUBLIC
            assert body["authorization_endpoint"] == f"{PUBLIC}/authorize"
            assert body["registration_endpoint"] == f"{PUBLIC}/register"
            assert body["code_challenge_methods_supported"] == ["S256"]
            assert body["client_id_metadata_document_supported"] is True
            assert body["authorization_response_iss_parameter_supported"] is True
    under_path = oauth_client.get("/mcp/.well-known/oauth-authorization-server").json()
    assert under_path["issuer"] == PUBLIC and under_path["client_id_metadata_document_supported"] is True
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
    listed = {t["name"]: t for t in _rpc(oauth_client, tokens["access_token"], "tools/list").json()["result"]["tools"]}
    assert "Needs the" not in listed["org.info"]["description"]
    # An OAuth token also sees the tools it can ask for with step-up
    assert "Needs the points:read scope" in listed["points.leaderboard"]["description"]

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
    assert parse_qs(urlparse(response.headers["location"]).query) == {
        "error": ["access_denied"],
        "state": ["xyz"],
        "iss": [PUBLIC],
    }


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


def test_loopback_redirects_are_allowed(oauth_client):
    _register(
        oauth_client, redirect_uris=["http://127.0.0.1:33418/callback", "http://localhost:8080/cb", "http://[::1]:9/cb"]
    )


@pytest.mark.parametrize(
    "uri", ["cursor://anysphere.cursor-mcp/oauth", "vscode://callback", "myapp:/cb", "http://api.club.test/cb"]
)
def test_app_schemes_are_refused(oauth_client, uri):
    response = oauth_client.post("/mcp/register", json={"redirect_uris": [uri], "token_endpoint_auth_method": "none"})
    assert response.status_code == 400
    assert response.json()["error"] == "invalid_redirect_uri"


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


# Client ID Metadata Documents

DOCUMENT_URL = "https://agent.example/oauth/client.json"


def _document(**changes) -> dict:
    document = {
        "client_id": DOCUMENT_URL,
        "client_name": "Example Agent",
        "redirect_uris": [REDIRECT, "http://127.0.0.1:33418/callback"],
        "token_endpoint_auth_method": "none",
    }
    return {k: v for k, v in (document | changes).items() if v is not None}


@pytest.fixture
def documents(monkeypatch):
    """A fake web: the URL a fetch asks for, and the answer for each URL. Counts the fetches."""
    import json

    from modules.mcp import oauth

    served: dict = {"answers": {}, "fetches": []}

    def fetch(url):
        served["fetches"].append(url)
        answer = served["answers"].get(url)
        if answer is None:
            raise oauth.OAuthError("could not be fetched")
        status, headers, body = answer
        return oauth.Fetched(status, headers, body if isinstance(body, bytes) else json.dumps(body).encode())

    monkeypatch.setattr(oauth, "fetch_metadata_document", fetch)
    served["answers"][DOCUMENT_URL] = (200, {"cache-control": "max-age=600"}, _document())
    _forget_documents()
    yield served
    _forget_documents()


def _forget_documents() -> None:
    """Delete the cached documents and what hangs on them: the tests share one database."""
    from core.db import db_connect
    from modules.mcp.models import OAuthClient, OAuthGrant, OAuthRequest

    db = db_connect.SessionLocal()
    try:
        for model in (OAuthGrant, OAuthRequest, OAuthClient):
            db.query(model).filter(model.client_id.like("https://agent.example/%")).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()


def _authorize(oauth_client, client_id: str, challenge: str, redirect: str = REDIRECT, **extra):
    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "state": "xyz",
    } | extra
    return oauth_client.get("/mcp/authorize", params=params)


def test_a_metadata_document_client_connects(oauth_client, client, officer_headers, documents):
    verifier, challenge = _pkce()
    consent_key = _sign_in(oauth_client, DOCUMENT_URL, challenge, name="Example Agent")
    page = oauth_client.post(
        "/mcp/oauth/consent",
        data={"consent": consent_key, "org": "0", "scope": "org:read", "action": "approve"},
    )
    assert "Client: <strong>agent.example</strong>" in page.text
    assert "registered itself" not in page.text
    code = _approve(oauth_client, consent_key, _soda_id(client, officer_headers), ["org:read"])
    tokens = _token(
        oauth_client,
        grant_type="authorization_code",
        code=code,
        redirect_uri=REDIRECT,
        client_id=DOCUMENT_URL,
        code_verifier=verifier,
    )
    assert tokens.status_code == 200, tokens.text
    refreshed = _token(
        oauth_client, grant_type="refresh_token", refresh_token=tokens.json()["refresh_token"], client_id=DOCUMENT_URL
    )
    assert refreshed.status_code == 200, refreshed.text
    # The document stays cached for its max-age, so the flow fetched it once
    assert documents["fetches"] == [DOCUMENT_URL]
    assert _oauth_row(client, officer_headers)["name"] == "Example Agent"


def test_a_registered_client_is_marked_as_not_checked(oauth_client):
    registered = _register(oauth_client)
    consent_key = _sign_in(oauth_client, registered["client_id"], _pkce()[1])
    response = oauth_client.post("/mcp/oauth/consent", data={"consent": consent_key, "org": "0", "action": "approve"})
    assert "registered itself" in response.text


def test_a_localhost_redirect_gets_a_warning(oauth_client, documents):
    authorize = _authorize(oauth_client, DOCUMENT_URL, _pkce()[1], redirect="http://127.0.0.1:33418/callback")
    login = oauth_client.get(f"/mcp/oauth/login?{urlparse(authorize.headers['location']).query}")
    state = parse_qs(urlparse(login.headers["location"]).query)["state"][0]
    page = oauth_client.get("/mcp/oauth/callback", params={"state": state, "code": "discord-code"})
    assert page.status_code == 200
    assert "<strong>127.0.0.1</strong>" in page.text
    assert "This address is on your computer" in page.text


@pytest.mark.parametrize(
    ("answer", "reason"),
    [
        ((404, {}, {}), "returned 404"),
        ((302, {"location": "https://evil.example/c.json"}, {}), "returned 302"),
        ((200, {}, b"not json"), "not JSON"),
        ((200, {}, b"[]"), "JSON object"),
        ((200, {}, b"x" * 6000), "larger than"),
        ((200, {}, _document(client_id="https://agent.example/other.json")), "URL of the document"),
        ((200, {}, _document(client_name=None)), "client_name"),
        ((200, {}, _document(client_secret="s")), "client secret"),
        ((200, {}, _document(token_endpoint_auth_method="client_secret_basic")), "not supported"),
        ((200, {}, _document(token_endpoint_auth_method="private_key_jwt")), "one of jwks and jwks_uri"),
        ((200, {}, _document(token_endpoint_auth_method="tls_client_auth")), "not supported"),
        ((200, {}, _document(redirect_uris=["http://evil.example/cb"])), "https"),
        ((200, {}, _document(grant_types=["client_credentials"])), "authorization_code"),
    ],
)
def test_bad_documents_are_refused_and_not_cached(oauth_client, documents, caplog, answer, reason):
    documents["answers"][DOCUMENT_URL] = answer
    refused = _authorize(oauth_client, DOCUMENT_URL, _pkce()[1])
    assert refused.status_code == 400
    assert reason in caplog.text
    _authorize(oauth_client, DOCUMENT_URL, _pkce()[1])
    assert documents["fetches"] == [DOCUMENT_URL, DOCUMENT_URL]


def test_a_document_that_fails_once_is_fetched_again(oauth_client, documents):
    answer = documents["answers"].pop(DOCUMENT_URL)
    assert _authorize(oauth_client, DOCUMENT_URL, _pkce()[1]).status_code == 400
    documents["answers"][DOCUMENT_URL] = answer
    assert _authorize(oauth_client, DOCUMENT_URL, _pkce()[1]).status_code == 302


def test_no_store_fetches_each_time(oauth_client, documents):
    documents["answers"][DOCUMENT_URL] = (200, {"cache-control": "no-store"}, _document())
    assert _authorize(oauth_client, DOCUMENT_URL, _pkce()[1]).status_code == 302
    assert _authorize(oauth_client, DOCUMENT_URL, _pkce()[1]).status_code == 302
    assert len(documents["fetches"]) == 2


def test_a_changed_document_replaces_the_cached_one(oauth_client, documents):
    import datetime

    from core.db import db_connect
    from modules.mcp.models import OAuthClient

    assert _authorize(oauth_client, DOCUMENT_URL, _pkce()[1]).status_code == 302
    db = db_connect.SessionLocal()
    try:
        db.query(OAuthClient).filter_by(client_id=DOCUMENT_URL).update({"cache_until": datetime.datetime(2020, 1, 1)})
        db.commit()
    finally:
        db.close()
    documents["answers"][DOCUMENT_URL] = (200, {}, _document(redirect_uris=["https://agent.example/new"]))
    # The old redirect URI is gone from the new document
    assert _authorize(oauth_client, DOCUMENT_URL, _pkce()[1]).status_code == 400


@pytest.mark.parametrize(
    "url",
    [
        "https://agent.example",
        "https://agent.example/",
        "https://agent.example/client.json#x",
        "https://user:pw@agent.example/client.json",
        "https://agent.example/a/../client.json",
        "https://agent.example/./client.json",
        "https://agent.example/" + "a" * 2100,
    ],
)
def test_client_id_urls_that_the_draft_does_not_allow(url):
    from modules.mcp import oauth

    with pytest.raises(oauth.OAuthError):
        oauth.check_metadata_url(url)


def test_a_client_id_url_with_a_query_is_allowed():
    from modules.mcp import oauth

    oauth.check_metadata_url("https://agent.example/client.json?v=2")


@pytest.mark.parametrize("host", ["localhost", "127.0.0.1", "10.0.0.5", "169.254.169.254", "[::1]"])
def test_the_fetch_refuses_private_addresses(host):
    from modules.mcp import oauth

    with pytest.raises(oauth.OAuthError, match="non-public"):
        oauth.fetch_metadata_document(f"https://{host}/client.json")


def test_the_fetch_connects_to_the_checked_address(monkeypatch):
    import socket

    from modules.mcp import oauth

    answers = iter(["93.184.216.34", "10.0.0.5"])
    monkeypatch.setattr(socket, "getaddrinfo", lambda host, port: [(socket.AF_INET, 0, 0, "", (next(answers), port))])
    seen = {}

    def connect(address, timeout):
        seen["address"] = address
        raise OSError("stop here")

    monkeypatch.setattr(socket, "create_connection", connect)
    with pytest.raises(oauth.OAuthError, match="could not be fetched"):
        oauth.fetch_metadata_document("https://agent.example/client.json")
    # A second lookup could give 10.0.0.5; the connection uses the address that passed the check
    assert seen["address"] == ("93.184.216.34", 443)


@pytest.mark.parametrize(
    ("header", "seconds"),
    [
        ("max-age=600", 600),
        ("public, max-age=120", 120),
        ("max-age=999999", 24 * 3600),
        ("no-store", 0),
        ("no-cache", 0),
        ("", 3600),
        ("max-age=abc", 3600),
    ],
)
def test_cache_time(header, seconds):
    from modules.mcp import oauth

    assert oauth.cache_time({"cache-control": header} if header else {}).total_seconds() == seconds


@pytest.mark.parametrize(
    ("resource", "status"),
    [
        (PUBLIC, 302),
        (f"{PUBLIC}/", 302),
        (HOST, 302),
        ("HTTPS://API.CLUB.TEST/mcp", 302),
        ("https://other.example/mcp", 302),
        ("https://api.club.test/other", 302),
    ],
)
def test_resource_must_name_this_server(oauth_client, resource, status):
    registered = _register(oauth_client)
    response = _authorize(oauth_client, registered["client_id"], _pkce()[1], resource=resource)
    assert response.status_code == status
    location = response.headers["location"]
    if "other" in resource:
        assert parse_qs(urlparse(location).query)["error"] == ["invalid_target"]
    else:
        assert urlparse(location).path == "/mcp/oauth/login"


# Origin, scope hint, step-up and iss on errors


def test_origin_is_checked(oauth_client, token_for_soda):
    headers = {"Authorization": f"Bearer {token_for_soda('org:read')}", "Accept": "application/json, text/event-stream"}
    body = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": INIT}
    for origin, status in [
        (None, 200),
        (HOST, 200),
        ("http://localhost:6274", 200),
        ("http://127.0.0.1:5173", 200),
        ("https://evil.example", 403),
        ("http://api.club.test", 403),
        ("null", 403),
    ]:
        sent = headers | ({"Origin": origin} if origin else {})
        response = oauth_client.post("/mcp", json=body, headers=sent)
        assert response.status_code == status, (origin, response.text)
        if status == 403:
            assert response.json() == {"jsonrpc": "2.0", "error": {"code": -32600, "message": "Origin not allowed"}}


def test_origin_is_checked_without_oauth(app, monkeypatch):
    from starlette.testclient import TestClient

    from core.config import config
    from modules.mcp.server import build_app

    monkeypatch.setattr(config, "MCP_PUBLIC_URL", "")
    monkeypatch.delenv("ACCOUNTS_BASE_URL", raising=False)
    with TestClient(build_app(host="testserver")) as test_client:
        body = {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}
        refused = test_client.post("/mcp", json=body, headers={"Origin": "https://evil.example"})
        assert refused.status_code == 403


@pytest.fixture
def token_for_soda(client, officer_headers):
    def issue(*scopes):
        body = {"name": "test-agent", "kind": "agent", "scopes": list(scopes)}
        made = client.post(
            f"/api/organizations/{_soda_id(client, officer_headers)}/tokens", json=body, headers=officer_headers
        )
        return made.get_json()["token"]

    return issue


def test_the_401_has_the_scope_hint(oauth_client):
    refused = oauth_client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}})
    assert refused.status_code == 401
    assert 'scope="org:read"' in refused.headers["www-authenticate"]
    assert oauth_client.get("/.well-known/oauth-protected-resource/mcp").json()["scopes_supported"] == ["org:read"]


def test_the_api_serves_the_same_resource_metadata(oauth_client, client):
    assert (
        client.get("/.well-known/oauth-protected-resource/mcp").get_json()
        == oauth_client.get("/.well-known/oauth-protected-resource/mcp").json()
    )


def _call(oauth_client, access: str, name: str, arguments: dict | None = None):
    return _rpc(oauth_client, access, "tools/call", {"name": name, "arguments": arguments or {}})


def test_step_up(oauth_client, client, officer_headers):
    registered, tokens = _connect(oauth_client, client, officer_headers)
    access = tokens["access_token"]
    assert _call(oauth_client, access, "org.info").status_code == 200
    refused = _call(oauth_client, access, "points.leaderboard")
    assert refused.status_code == 403
    challenge = refused.headers["www-authenticate"]
    assert 'error="insufficient_scope"' in challenge
    assert 'scope="points:read"' in challenge
    assert f'resource_metadata="{HOST}/.well-known/oauth-protected-resource/mcp"' in challenge
    # A batch asks for every missing scope at once
    batch = _call(
        oauth_client,
        access,
        "batch",
        {"calls": [{"tool": "points.leaderboard"}, {"tool": "events.list"}, {"tool": "org.info"}]},
    )
    assert batch.status_code == 403
    assert 'scope="calendar:read points:read"' in batch.headers["www-authenticate"]
    # An unknown tool is not a step-up: it gets the usual answer
    unknown = _call(oauth_client, access, "nope.nothing")
    assert unknown.status_code == 200 and unknown.json()["result"]["isError"] is True

    # The client signs in again with the scopes it had and the new one; the consent page selects them
    verifier, challenge_code = _pkce()
    authorize = _authorize(oauth_client, registered["client_id"], challenge_code, scope="org:read points:read")
    login = oauth_client.get(f"/mcp/oauth/login?{urlparse(authorize.headers['location']).query}")
    state = parse_qs(urlparse(login.headers["location"]).query)["state"][0]
    page = oauth_client.get("/mcp/oauth/callback", params={"state": state, "code": "discord-code"})
    assert 'value="org:read" checked' in page.text and 'value="points:read" checked' in page.text
    consent_key = page.text.split('name="consent" value="')[1].split('"')[0]
    code = _approve(oauth_client, consent_key, _soda_id(client, officer_headers), ["org:read", "points:read"])
    upgraded = _token(
        oauth_client,
        grant_type="authorization_code",
        code=code,
        redirect_uri=REDIRECT,
        client_id=registered["client_id"],
        code_verifier=verifier,
    ).json()
    assert upgraded["scope"] == "org:read points:read"
    assert _call(oauth_client, upgraded["access_token"], "points.leaderboard").status_code == 200


def test_officer_tokens_get_no_step_up(oauth_client, token_for_soda):
    access = token_for_soda("org:read")
    listed = [t["name"] for t in _rpc(oauth_client, access, "tools/list").json()["result"]["tools"]]
    assert "points.leaderboard" not in listed
    called = _call(oauth_client, access, "points.leaderboard")
    assert called.status_code == 200 and called.json()["result"]["isError"] is True


def test_sdk_error_redirects_have_iss(oauth_client):
    registered = _register(oauth_client)
    response = _authorize(oauth_client, registered["client_id"], _pkce()[1], resource="https://other.example/mcp")
    query = parse_qs(urlparse(response.headers["location"]).query)
    assert query["error"] == ["invalid_target"]
    assert query["iss"] == [PUBLIC]
    # A redirect to the sign-in page is not an error and gets no iss
    ok = _authorize(oauth_client, registered["client_id"], _pkce()[1])
    assert "iss" not in parse_qs(urlparse(ok.headers["location"]).query)


# Client keys (private_key_jwt)

ASSERTION_TYPE = "urn:ietf:params:oauth:client-assertion-type:jwt-bearer"


@pytest.fixture
def client_key():
    """An EC P-256 key pair: the private key, and the public JWK with kid key-1."""
    from cryptography.hazmat.primitives.asymmetric import ec
    from jwt.algorithms import ECAlgorithm

    from modules.mcp import client_auth

    client_auth.clear_cache()
    private = ec.generate_private_key(ec.SECP256R1())
    public = ECAlgorithm.to_jwk(private.public_key(), as_dict=True) | {"kid": "key-1", "use": "sig", "alg": "ES256"}
    yield private, public
    client_auth.clear_cache()


def _assertion(private, *, kid="key-1", alg="ES256", **claims) -> str:
    import time
    import uuid

    import jwt

    now = int(time.time())
    body = {"iss": DOCUMENT_URL, "sub": DOCUMENT_URL, "aud": f"{PUBLIC}/token", "jti": str(uuid.uuid4()), "iat": now}
    body |= {"exp": now + 60} | claims
    return jwt.encode({k: v for k, v in body.items() if v is not None}, private, algorithm=alg, headers={"kid": kid})


def _key_document(public: dict, **changes) -> dict:
    return _document(token_endpoint_auth_method="private_key_jwt", jwks={"keys": [public]}, **changes)


def _key_code(oauth_client, client, officer_headers) -> tuple[str, str]:
    """Sign in and approve a key client. Returns (code, verifier)."""
    verifier, challenge = _pkce()
    consent_key = _sign_in(oauth_client, DOCUMENT_URL, challenge, name="Example Agent")
    return _approve(oauth_client, consent_key, _soda_id(client, officer_headers), ["org:read"]), verifier


def _code_form(code: str, verifier: str, assertion: str | None) -> dict:
    form = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT,
        "client_id": DOCUMENT_URL,
        "code_verifier": verifier,
    }
    return form | ({"client_assertion_type": ASSERTION_TYPE, "client_assertion": assertion} if assertion else {})


def test_a_key_client_connects(oauth_client, client, officer_headers, documents, client_key):
    private, public = client_key
    documents["answers"][DOCUMENT_URL] = (200, {}, _key_document(public))
    code, verifier = _key_code(oauth_client, client, officer_headers)
    assert _token(oauth_client, **_code_form(code, verifier, None)).status_code == 401
    assertion = _assertion(private)
    granted = _token(oauth_client, **_code_form(code, verifier, assertion))
    assert granted.status_code == 200, granted.text
    refresh = {
        "grant_type": "refresh_token",
        "refresh_token": granted.json()["refresh_token"],
        "client_id": DOCUMENT_URL,
    }
    replayed = _token(oauth_client, **refresh, client_assertion_type=ASSERTION_TYPE, client_assertion=assertion)
    assert replayed.status_code == 401
    assert "used before" in replayed.json()["error_description"]
    fresh = _token(oauth_client, **refresh, client_assertion_type=ASSERTION_TYPE, client_assertion=_assertion(private))
    assert fresh.status_code == 200, fresh.text
    # Revoke takes the same client authentication; the issuer is also a valid audience
    revoked = oauth_client.post(
        "/mcp/revoke",
        data={
            "token": fresh.json()["access_token"],
            "client_id": DOCUMENT_URL,
            "client_assertion_type": ASSERTION_TYPE,
            "client_assertion": _assertion(private, aud=PUBLIC),
        },
    )
    assert revoked.status_code == 200
    assert _rpc(oauth_client, fresh.json()["access_token"], "tools/list").status_code == 401


@pytest.mark.parametrize(
    ("changes", "reason"),
    [
        ({"aud": "https://other.example/token"}, "audience"),
        ({"iss": "https://other.example/c.json"}, "issuer"),
        ({"sub": "someone"}, "sub"),
        ({"exp": 4102444800}, "expire within"),
        ({"jti": None}, "jti"),
        ({"exp": 1}, "expired"),
    ],
)
def test_bad_assertions_are_refused(oauth_client, client, officer_headers, documents, client_key, changes, reason):
    private, public = client_key
    documents["answers"][DOCUMENT_URL] = (200, {}, _key_document(public))
    code, verifier = _key_code(oauth_client, client, officer_headers)
    refused = _token(oauth_client, **_code_form(code, verifier, _assertion(private, **changes)))
    assert refused.status_code == 401
    assert reason in refused.json()["error_description"].lower() or reason in refused.json()["error_description"]


def test_an_assertion_needs_the_clients_key(oauth_client, client, officer_headers, documents, client_key):
    from cryptography.hazmat.primitives.asymmetric import ec

    _, public = client_key
    documents["answers"][DOCUMENT_URL] = (200, {}, _key_document(public))
    code, verifier = _key_code(oauth_client, client, officer_headers)
    other = ec.generate_private_key(ec.SECP256R1())
    refused = _token(oauth_client, **_code_form(code, verifier, _assertion(other)))
    assert refused.status_code == 401
    assert "not signed with a key of the client" in refused.json()["error_description"]


def test_a_shared_secret_algorithm_is_refused(oauth_client, client, officer_headers, documents, client_key):
    _, public = client_key
    documents["answers"][DOCUMENT_URL] = (200, {}, _key_document(public))
    code, verifier = _key_code(oauth_client, client, officer_headers)
    refused = _token(
        oauth_client, **_code_form(code, verifier, _assertion("a-shared-secret-of-32-bytes-long!", alg="HS256"))
    )
    assert refused.status_code == 401
    assert "alg HS256 is not allowed" in refused.json()["error_description"]


def test_keys_from_jwks_uri_and_rotation(oauth_client, client, officer_headers, documents, client_key, monkeypatch):
    import json

    from cryptography.hazmat.primitives.asymmetric import ec
    from jwt.algorithms import ECAlgorithm

    from modules.mcp import client_auth, oauth

    private, public = client_key
    keys_url = "https://agent.example/oauth/jwks.json"
    served = {"keys": [public]}
    fetches = []

    def fetch(url):
        fetches.append(url)
        return oauth.Fetched(200, {"cache-control": "max-age=3600"}, json.dumps(served).encode())

    monkeypatch.setattr(client_auth, "fetch_jwks", fetch)
    monkeypatch.setattr(client_auth, "JWKS_REFETCH_SECONDS", 0)
    documents["answers"][DOCUMENT_URL] = (
        200,
        {},
        _document(token_endpoint_auth_method="private_key_jwt", jwks_uri=keys_url),
    )
    code, verifier = _key_code(oauth_client, client, officer_headers)
    granted = _token(oauth_client, **_code_form(code, verifier, _assertion(private)))
    assert granted.status_code == 200, granted.text
    # The client rotates to key-2. Its kid is not in the cached set, so the set is fetched again
    rotated = ec.generate_private_key(ec.SECP256R1())
    served["keys"] = [ECAlgorithm.to_jwk(rotated.public_key(), as_dict=True) | {"kid": "key-2"}]
    refresh = {
        "grant_type": "refresh_token",
        "refresh_token": granted.json()["refresh_token"],
        "client_id": DOCUMENT_URL,
    }
    again = _token(
        oauth_client, **refresh, client_assertion_type=ASSERTION_TYPE, client_assertion=_assertion(rotated, kid="key-2")
    )
    assert again.status_code == 200, again.text
    assert fetches == [keys_url, keys_url]


@pytest.mark.parametrize(
    ("changes", "reason"),
    [
        ({"jwks": {"keys": [{"kty": "oct", "k": "c2VjcmV0"}]}}, "public keys only"),
        ({"jwks": {"keys": []}}, "one or more keys"),
        ({"jwks_uri": "https://agent.example/jwks.json"}, "one of jwks and jwks_uri"),
        ({"jwks": None, "jwks_uri": "http://agent.example/jwks.json"}, "must use https"),
    ],
)
def test_bad_client_keys_are_refused(oauth_client, documents, client_key, caplog, changes, reason):
    _, public = client_key
    document = _key_document(public)
    document |= changes
    documents["answers"][DOCUMENT_URL] = (200, {}, {k: v for k, v in document.items() if v is not None})
    assert _authorize(oauth_client, DOCUMENT_URL, _pkce()[1]).status_code == 400
    assert reason in caplog.text


def test_a_private_ec_key_is_refused(oauth_client, documents, client_key, caplog):
    from jwt.algorithms import ECAlgorithm

    private, _ = client_key
    secret_jwk = ECAlgorithm.to_jwk(private, as_dict=True)
    documents["answers"][DOCUMENT_URL] = (200, {}, _key_document(secret_jwk))
    assert _authorize(oauth_client, DOCUMENT_URL, _pkce()[1]).status_code == 400
    assert "public keys only" in caplog.text


def test_metadata_has_private_key_jwt(oauth_client):
    body = oauth_client.get("/.well-known/oauth-authorization-server/mcp").json()
    assert "private_key_jwt" in body["token_endpoint_auth_methods_supported"]
    assert "ES256" in body["token_endpoint_auth_signing_alg_values_supported"]


def test_assertion_cleanup():
    import datetime

    from core.db import db_connect
    from modules.mcp import client_auth
    from modules.mcp.models import OAuthAssertion

    db = db_connect.SessionLocal()
    try:
        db.add(OAuthAssertion(jti_hash="0" * 64, expires_at=datetime.datetime(2020, 1, 1)))
        db.commit()
        assert client_auth.cleanup(db) >= 1
        assert db.query(OAuthAssertion).filter_by(jti_hash="0" * 64).count() == 0
    finally:
        db.close()


def test_a_public_client_can_revoke(oauth_client, client, officer_headers):
    registered, tokens = _connect(oauth_client, client, officer_headers)
    other = _register(oauth_client)
    # A token of another client is left alone, with the same 200
    ignored = oauth_client.post("/mcp/revoke", data={"token": tokens["access_token"], "client_id": other["client_id"]})
    assert ignored.status_code == 200
    assert _rpc(oauth_client, tokens["access_token"], "tools/list").status_code == 200
    revoked = oauth_client.post(
        "/mcp/revoke", data={"token": tokens["refresh_token"], "client_id": registered["client_id"]}
    )
    assert revoked.status_code == 200
    assert _rpc(oauth_client, tokens["access_token"], "tools/list").status_code == 401
    assert oauth_client.post("/mcp/revoke", data={"client_id": registered["client_id"]}).status_code == 400


def test_documents_cannot_fill_the_registration_cap(oauth_client, documents, monkeypatch):
    from core.db import db_connect
    from modules.mcp import oauth
    from modules.mcp.models import OAuthClient

    db = db_connect.SessionLocal()
    try:
        documents_now = db.query(OAuthClient).filter(OAuthClient.cache_until.isnot(None)).count()
        registered_now = db.query(OAuthClient).filter(OAuthClient.cache_until.is_(None)).count()
    finally:
        db.close()
    monkeypatch.setattr(oauth, "MAX_DOCUMENT_CLIENTS", documents_now + 1)
    monkeypatch.setattr(oauth, "MAX_REGISTERED_CLIENTS", registered_now + 1)
    assert _authorize(oauth_client, DOCUMENT_URL, _pkce()[1]).status_code == 302
    other = "https://agent.example/oauth/other.json"
    documents["answers"][other] = (200, {}, _document(client_id=other))
    # The document cap is full, so a new document client is refused
    assert _authorize(oauth_client, other, _pkce()[1]).status_code == 400
    # A full document cap does not block registration
    _register(oauth_client)


def test_cleanup_deletes_unused_documents_at_once(oauth_client, documents):
    from core.db import db_connect
    from modules.mcp import oauth
    from modules.mcp.models import OAuthClient, OAuthRequest

    assert _authorize(oauth_client, DOCUMENT_URL, _pkce()[1]).status_code == 302
    db = db_connect.SessionLocal()
    try:
        oauth.cleanup(db)
        # An open request keeps the document
        assert db.query(OAuthClient).filter_by(client_id=DOCUMENT_URL).count() == 1
        db.query(OAuthRequest).filter_by(client_id=DOCUMENT_URL).delete()
        db.commit()
        oauth.cleanup(db)
        assert db.query(OAuthClient).filter_by(client_id=DOCUMENT_URL).count() == 0
    finally:
        db.close()


def test_a_large_chunked_body_skips_the_step_up_check(oauth_client, client, officer_headers, monkeypatch):
    import json

    from modules.mcp import edges

    _, tokens = _connect(oauth_client, client, officer_headers)
    monkeypatch.setattr(edges, "MAX_CHECKED_BODY", 100)
    body = json.dumps(
        {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "points.leaderboard", "arguments": {}}}
    ).encode()
    body = body[:-1] + b', "pad": "' + b"x" * 500 + b'"}'

    def chunks():
        # No Content-Length: the client streams the body in pieces
        for start in range(0, len(body), 64):
            yield body[start : start + 64]

    headers = {
        "Authorization": f"Bearer {tokens['access_token']}",
        "Accept": "application/json, text/event-stream",
        "Content-Type": "application/json",
    }
    response = oauth_client.post("/mcp", content=chunks(), headers=headers)
    # The check stopped at 100 bytes and the SDK got the whole body: the normal answer, not a step-up 403
    assert response.status_code == 200, response.text
    assert response.json()["result"]["isError"] is True


def test_a_full_rate_limit_table_stays_bounded(monkeypatch):
    from modules.mcp import oauth

    limiter = oauth.RateLimit(None, "/mcp")
    monkeypatch.setattr(limiter, "MAX_KEYS", 2)
    seconds = oauth.RATE_LIMITS["/token"][1]
    start = 1000.0 * seconds
    assert limiter.allow("/token", "a", now=start) == 0
    assert limiter.allow("/token", "b", now=start) == 0
    # The table is full of this window: a new IP waits, a counted one goes on
    assert limiter.allow("/token", "c", now=start) > 0
    assert limiter.allow("/token", "a", now=start + 0.5) == 0
    assert len(limiter.counts["/token"]) == 2
    # Another rule has its own table
    assert limiter.allow("/register", "c", now=start) == 0
    # In the next window the old entries are pruned, and the new IP gets a place
    assert limiter.allow("/token", "c", now=start + seconds) == 0
    assert set(limiter.counts["/token"]) == {"c"}


def test_a_failed_key_fetch_is_not_tried_again_at_once(monkeypatch, client_key):
    from modules.mcp import client_auth, oauth

    fetches = []

    def fetch(url):
        fetches.append(url)
        return oauth.Fetched(503, {}, b"")

    monkeypatch.setattr(client_auth, "fetch_jwks", fetch)
    url = "https://agent.example/oauth/jwks.json"
    for _ in range(3):
        with pytest.raises(oauth.OAuthError):
            client_auth._remote_keys(url)
    assert fetches == [url]


def test_the_key_cache_stays_bounded(monkeypatch, client_key):
    import json

    from modules.mcp import client_auth, oauth

    _, public = client_key
    monkeypatch.setattr(client_auth, "JWKS_MAX_ENTRIES", 3)
    monkeypatch.setattr(
        client_auth, "fetch_jwks", lambda url: oauth.Fetched(200, {}, json.dumps({"keys": [public]}).encode())
    )
    for n in range(10):
        client_auth._remote_keys(f"https://agent.example/jwks/{n}.json")
    assert len(client_auth._jwks_cache) == 3
    # The newest entries stay
    assert "https://agent.example/jwks/9.json" in client_auth._jwks_cache


def test_refused_registrations_are_logged(oauth_client, caplog):
    import logging

    body = {
        "client_name": "Example Agent",
        "redirect_uris": ["cursor://x/cb"],
        "token_endpoint_auth_method": "client_secret_post",
        "client_secret": "never-logged-secret",
        "jwks": {"keys": [{"kty": "oct", "k": "never-logged-key"}]},
    }
    with caplog.at_level(logging.WARNING, logger="modules.mcp.edges"):
        assert oauth_client.post("/mcp/register", json=body).status_code == 400
        assert (
            oauth_client.post(
                "/mcp/register", content=b"not json", headers={"content-type": "application/json"}
            ).status_code
            == 400
        )
        _register(oauth_client)
    refused = [r.getMessage() for r in caplog.records if "client registration refused" in r.getMessage()]
    assert len(refused) == 2
    assert "invalid_redirect_uri" in refused[0] and "cursor://x/cb" in refused[0]
    assert "client_secret_post" in refused[0] and "Example Agent" in refused[0]
    # Field names only, never secret or key values
    assert "client_secret" in refused[0] and "jwks" in refused[0]
    assert "never-logged" not in caplog.text
    assert "not JSON" in refused[1] or "invalid_client_metadata" in refused[1]


def test_registration_log_cuts_urls(oauth_client, caplog):
    import logging

    body = {
        "redirect_uris": ["cursor://user:pw-secret@x/cb?token=query-secret#frag-secret"],
        "client_uri": "https://a.example/?k=uri-secret",
    }
    with caplog.at_level(logging.WARNING, logger="modules.mcp.edges"):
        assert oauth_client.post("/mcp/register", json=body).status_code == 400
    line = next(r.getMessage() for r in caplog.records if "client registration refused" in r.getMessage())
    assert "cursor://x/cb?…" in line and "https://a.example/?…" in line
    # Neither in the summary nor in the answer, which repeats the refused URI
    assert "secret" not in caplog.text


def test_redact_urls():
    from modules.mcp import edges

    assert edges.redact_urls("go to https://h.example:8443/p?q=1 now") == "go to https://h.example:8443/p?… now"
    assert edges.redact_urls('"myapp:/cb?t=x"') == '"myapp:/cb?…"'
    assert edges.redact_urls("http://localhost:3000/callback") == "http://localhost:3000/callback"
    assert edges.redact_urls("no url here: a/b") == "no url here: a/b"


def test_registration_log_escapes_field_names(oauth_client, caplog):
    import logging

    body = {"redirect_uris": ["cursor://x/cb"], "x\nFAKE LINE": 1}
    with caplog.at_level(logging.WARNING, logger="modules.mcp.edges"):
        assert oauth_client.post("/mcp/register", json=body).status_code == 400
    line = next(r.getMessage() for r in caplog.records if "client registration refused" in r.getMessage())
    assert "\n" not in line
    assert '"x\\nFAKE LINE"' in line


def test_a_large_registration_passes_whole_and_is_not_kept(oauth_client, caplog, monkeypatch):
    import json
    import logging

    from modules.mcp import edges

    monkeypatch.setattr(edges, "MAX_LOGGED_BODY", 100)
    body = json.dumps({"redirect_uris": ["cursor://x/cb"], "pad": "x" * 500}).encode()

    def chunks():
        for start in range(0, len(body), 64):
            yield body[start : start + 64]

    with caplog.at_level(logging.WARNING, logger="modules.mcp.edges"):
        response = oauth_client.post("/mcp/register", content=chunks(), headers={"content-type": "application/json"})
    # The handler read the whole body: it refused the redirect URI, not a cut-off JSON document
    assert response.status_code == 400 and response.json()["error"] == "invalid_redirect_uri"
    line = next(r.getMessage() for r in caplog.records if "client registration refused" in r.getMessage())
    assert "body larger than 100 bytes" in line


def test_registration_log_cuts_urls_with_escaped_characters(oauth_client, caplog):
    import logging

    body = {
        "redirect_uris": ["cursor://x/cb?a=1\\&token=redirect-secret"],
        "client_uri": "https://x.test/?a=1\\&token=uri-secret",
    }
    with caplog.at_level(logging.WARNING, logger="modules.mcp.edges"):
        assert oauth_client.post("/mcp/register", json=body).status_code == 400
    line = next(r.getMessage() for r in caplog.records if "client registration refused" in r.getMessage())
    assert "https://x.test/?…" in line and "cursor://x/cb?…" in line
    assert "secret" not in caplog.text


# Client secrets in the Basic header or in the form (RFC 6749 2.3.1, RFC 7591 default client_secret_basic)


def _basic(client_id: str, secret: str) -> dict:
    import base64
    from urllib.parse import quote

    token = base64.b64encode(f"{quote(client_id)}:{quote(secret)}".encode()).decode()
    return {"Authorization": f"Basic {token}"}


def _secret_code(oauth_client, client, officer_headers, **registration) -> tuple[dict, str, str]:
    """Register a client with a secret, sign in and approve. Returns (client, code, verifier)."""
    registered = _register(oauth_client, **registration)
    verifier, challenge = _pkce()
    code = _approve(
        oauth_client,
        _sign_in(oauth_client, registered["client_id"], challenge),
        _soda_id(client, officer_headers),
        ["org:read"],
    )
    return registered, code, verifier


def test_a_secret_in_the_basic_header_works_for_a_post_client(oauth_client, client, officer_headers, monkeypatch):
    from cryptography.fernet import Fernet

    monkeypatch.setenv("SECRETS_KEY", Fernet.generate_key().decode())
    # No method given: the SDK records client_secret_post. The client follows RFC 7591 and sends Basic
    registered, code, verifier = _secret_code(oauth_client, client, officer_headers, token_endpoint_auth_method=None)
    assert registered["token_endpoint_auth_method"] == "client_secret_post"
    form = {"grant_type": "authorization_code", "code": code, "redirect_uri": REDIRECT, "code_verifier": verifier}
    # client_id only in the header, as RFC 6749 allows
    granted = oauth_client.post(
        "/mcp/token", data=form, headers=_basic(registered["client_id"], registered["client_secret"])
    )
    assert granted.status_code == 200, granted.text
    refresh = {"grant_type": "refresh_token", "refresh_token": granted.json()["refresh_token"]}
    again = oauth_client.post(
        "/mcp/token", data=refresh, headers=_basic(registered["client_id"], registered["client_secret"])
    )
    assert again.status_code == 200, again.text
    revoked = oauth_client.post(
        "/mcp/revoke",
        data={"token": again.json()["access_token"]},
        headers=_basic(registered["client_id"], registered["client_secret"]),
    )
    assert revoked.status_code == 200
    assert _rpc(oauth_client, again.json()["access_token"], "tools/list").status_code == 401


def test_a_secret_in_the_form_works_for_a_basic_client(oauth_client, client, officer_headers, monkeypatch):
    from cryptography.fernet import Fernet

    monkeypatch.setenv("SECRETS_KEY", Fernet.generate_key().decode())
    registered, code, verifier = _secret_code(
        oauth_client, client, officer_headers, token_endpoint_auth_method="client_secret_basic"
    )
    form = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT,
        "code_verifier": verifier,
        "client_id": registered["client_id"],
        "client_secret": registered["client_secret"],
    }
    assert oauth_client.post("/mcp/token", data=form).status_code == 200


def test_bad_client_secrets_are_refused_and_logged(oauth_client, client, officer_headers, monkeypatch, caplog):
    import logging

    from cryptography.fernet import Fernet

    monkeypatch.setenv("SECRETS_KEY", Fernet.generate_key().decode())
    registered, code, verifier = _secret_code(oauth_client, client, officer_headers, token_endpoint_auth_method=None)
    form = {"grant_type": "authorization_code", "code": code, "redirect_uri": REDIRECT, "code_verifier": verifier}
    with caplog.at_level(logging.WARNING, logger="modules.mcp.edges"):
        wrong = oauth_client.post(
            "/mcp/token", data=form, headers=_basic(registered["client_id"], "wrong-secret-value")
        )
        assert wrong.status_code == 401
        assert wrong.json()["error"] == "invalid_client"
        # The header and the form name different clients
        other = oauth_client.post(
            "/mcp/token",
            data=form | {"client_id": "someone-else"},
            headers=_basic(registered["client_id"], registered["client_secret"]),
        )
        assert other.status_code == 401
        missing = oauth_client.post("/mcp/token", data=form | {"client_id": registered["client_id"]})
        assert missing.status_code == 401
    lines = [r.getMessage() for r in caplog.records if "token request refused" in r.getMessage()]
    assert len(lines) == 3
    # A Basic-only request is logged with the client_id of its header
    assert '"basic"' in lines[0] and "Invalid client_secret" in lines[0] and registered["client_id"] in lines[0]
    assert "Client secret is required" in lines[2] and registered["client_id"] in lines[2]
    # Never the secret, the code or the verifier
    for value in ("wrong-secret-value", registered["client_secret"], code, verifier):
        assert value not in caplog.text


def test_a_large_basic_only_token_request_gets_its_client_id(oauth_client, client, officer_headers, monkeypatch):
    from cryptography.fernet import Fernet

    from modules.mcp import edges

    monkeypatch.setenv("SECRETS_KEY", Fernet.generate_key().decode())
    registered, code, verifier = _secret_code(oauth_client, client, officer_headers, token_endpoint_auth_method=None)
    # Larger than the refusal log keeps, smaller than the SDK's limit
    form = {"grant_type": "authorization_code", "code": code, "redirect_uri": REDIRECT, "code_verifier": verifier}
    form["pad"] = "x" * (edges.MAX_LOGGED_BODY + 40_000)
    granted = oauth_client.post(
        "/mcp/token", data=form, headers=_basic(registered["client_id"], registered["client_secret"])
    )
    assert granted.status_code == 200, granted.text


def test_two_client_authentication_methods_are_refused(oauth_client, client, officer_headers, monkeypatch):
    from cryptography.fernet import Fernet

    monkeypatch.setenv("SECRETS_KEY", Fernet.generate_key().decode())
    registered, code, verifier = _secret_code(oauth_client, client, officer_headers, token_endpoint_auth_method=None)
    secret, client_id = registered["client_secret"], registered["client_id"]
    form = {"grant_type": "authorization_code", "code": code, "redirect_uri": REDIRECT, "code_verifier": verifier}
    assertion = {"client_assertion_type": ASSERTION_TYPE, "client_assertion": "x.y.z"}
    for data, headers in [
        # A valid Basic secret with a different form secret
        (form | {"client_secret": "another-secret"}, _basic(client_id, secret)),
        (form | assertion, _basic(client_id, secret)),
        (form | {"client_id": client_id, "client_secret": secret} | assertion, {}),
    ]:
        refused = oauth_client.post("/mcp/token", data=data, headers=headers)
        assert refused.status_code == 401
        assert "one client authentication method" in refused.json()["error_description"]
    # One method alone still works, and the code was not used by the refused requests
    granted = oauth_client.post("/mcp/token", data=form, headers=_basic(client_id, secret))
    assert granted.status_code == 200, granted.text
