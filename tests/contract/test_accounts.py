"""Connected accounts: the login checks the Discord account, grants are encrypted, tokens refresh."""

import datetime
import random
from urllib.parse import parse_qs, urlparse

import pytest
from cryptography.fernet import Fernet

from core.db import db_connect
from modules.accounts import providers, service
from modules.accounts.models import AccountGrant, AccountLogin
from tests.contract.conftest import MEMBER_DISCORD_ID


class FakeResponse:
    def __init__(self, status_code, body):
        self.status_code = status_code
        self._body = body

    def json(self):
        return self._body


class FakeTokenEndpoint:
    def __init__(self):
        self.responses = []
        self.forms = []

    def post(self, url, data=None, timeout=None):
        self.forms.append(data)
        return self.responses.pop(0)


@pytest.fixture
def endpoint(monkeypatch):
    fake = FakeTokenEndpoint()
    monkeypatch.setattr(providers.requests, "post", fake.post)
    return fake


@pytest.fixture(autouse=True)
def configured(monkeypatch):
    monkeypatch.setenv("SECRETS_KEY", Fernet.generate_key().decode())
    monkeypatch.setenv("ACCOUNTS_BASE_URL", "https://api.test")
    monkeypatch.setenv("ACCOUNTS_CANVAS_CLIENT_ID", "canvas-id")
    monkeypatch.setenv("ACCOUNTS_CANVAS_CLIENT_SECRET", "canvas-secret")
    monkeypatch.delenv("ACCOUNTS_GOOGLE_CLIENT_ID", raising=False)


def _issue(prefix, *scopes):
    from modules.auth import machine_tokens
    from modules.organizations.models import Organization

    db = db_connect.SessionLocal()
    try:
        org_id = db.query(Organization.id).filter_by(prefix=prefix).scalar()
        value, _ = machine_tokens.issue(
            db, organization_id=org_id, name="club-agent", kind="agent", scopes=list(scopes)
        )
        return {"Authorization": f"Bearer {value}"}
    finally:
        db.close()


@pytest.fixture
def agent(app):
    return _issue("soda", "accounts:link", "accounts:token")


def _member_id():
    return str(random.randint(10**17, 10**18))


def _start(client, agent, discord_id, provider="canvas"):
    response = client.post(f"/api/accounts/members/{discord_id}/{provider}/login", headers=agent)
    assert response.status_code == 201, response.get_json()
    url = response.get_json()["url"]
    assert url.startswith("https://api.test/api/accounts/start/")
    return url.rsplit("/", 1)[1]


def _connect(client, agent, endpoint, monkeypatch, discord_id, expires_in=3600):
    """Run the whole browser login for discord_id. Returns the state."""
    state = _start(client, agent, discord_id)
    to_discord = client.get(f"/api/accounts/start/{state}")
    assert to_discord.status_code == 302
    assert parse_qs(urlparse(to_discord.location).query)["state"] == [state]

    monkeypatch.setattr(providers, "discord_user_id", lambda client_id, secret, code: discord_id)
    to_canvas = client.get(f"/api/accounts/discord/callback?state={state}&code=d")
    assert to_canvas.status_code == 302, to_canvas.get_data(as_text=True)
    query = parse_qs(urlparse(to_canvas.location).query)
    assert query["redirect_uri"] == ["https://api.test/api/accounts/canvas/callback"]

    body = {"access_token": "at-1", "refresh_token": "rt-1", "expires_in": expires_in, "scope": "url:GET|/courses"}
    endpoint.responses.append(FakeResponse(200, body))
    done = client.get(f"/api/accounts/canvas/callback?state={state}&code=c")
    assert done.status_code == 200 and "connected" in done.get_data(as_text=True)
    return state


def test_login_stores_an_encrypted_grant(app, agent, endpoint, monkeypatch):
    client = app.test_client()
    discord_id = _member_id()
    state = _connect(client, agent, endpoint, monkeypatch, discord_id)
    assert endpoint.forms[0]["code"] == "c" and endpoint.forms[0]["client_secret"] == "canvas-secret"

    token = client.get(f"/api/accounts/members/{discord_id}/canvas/token", headers=agent).get_json()
    assert token["access_token"] == "at-1" and token["scopes"] == ["url:GET|/courses"]

    db = db_connect.SessionLocal()
    try:
        grant = db.query(AccountGrant).filter_by(discord_id=discord_id).one()
        assert "at-1" not in str(grant.access_token) and "rt-1" not in str(grant.refresh_token)
    finally:
        db.close()

    listed = client.get(f"/api/accounts/members/{discord_id}", headers=agent).get_json()["accounts"]
    assert [a["provider"] for a in listed] == ["canvas"]
    assert "access_token" not in listed[0]

    again = client.get(f"/api/accounts/canvas/callback?state={state}&code=c")
    assert again.status_code == 404


def test_forwarded_link_does_not_connect_another_account(app, agent, monkeypatch):
    client = app.test_client()
    state = _start(client, agent, _member_id())
    client.get(f"/api/accounts/start/{state}")
    monkeypatch.setattr(providers, "discord_user_id", lambda client_id, secret, code: _member_id())
    refused = client.get(f"/api/accounts/discord/callback?state={state}&code=d")
    assert refused.status_code == 403
    assert client.get(f"/api/accounts/canvas/callback?state={state}&code=c").status_code == 404


def test_callback_needs_the_browser_that_signed_in(app, agent, endpoint, monkeypatch):
    discord_id = _member_id()
    first = app.test_client()
    state = _start(first, agent, discord_id)
    first.get(f"/api/accounts/start/{state}")
    monkeypatch.setattr(providers, "discord_user_id", lambda client_id, secret, code: discord_id)
    assert first.get(f"/api/accounts/discord/callback?state={state}&code=d").status_code == 302

    other = app.test_client()
    assert other.get(f"/api/accounts/canvas/callback?state={state}&code=c").status_code == 403
    assert other.get(f"/api/accounts/discord/callback?state={state}&code=d").status_code == 400
    assert endpoint.forms == []


def _expire(discord_id):
    db = db_connect.SessionLocal()
    try:
        grant = db.query(AccountGrant).filter_by(discord_id=discord_id).one()
        grant.expires_at = datetime.datetime(2020, 1, 1)
        db.commit()
    finally:
        db.close()


def test_expired_token_is_refreshed(app, agent, endpoint, monkeypatch):
    client = app.test_client()
    discord_id = _member_id()
    _connect(client, agent, endpoint, monkeypatch, discord_id)
    _expire(discord_id)

    endpoint.responses.append(FakeResponse(200, {"access_token": "at-2", "expires_in": 3600}))
    token = client.get(f"/api/accounts/members/{discord_id}/canvas/token", headers=agent).get_json()
    assert token["access_token"] == "at-2" and token["scopes"] == ["url:GET|/courses"]
    assert endpoint.forms[-1] == {
        "grant_type": "refresh_token",
        "refresh_token": "rt-1",
        "client_id": "canvas-id",
        "client_secret": "canvas-secret",
    }

    # The refresh response left out the refresh token, so the old one is kept
    _expire(discord_id)
    endpoint.responses.append(FakeResponse(400, {"error": "invalid_grant"}))
    revoked = client.get(f"/api/accounts/members/{discord_id}/canvas/token", headers=agent)
    assert revoked.status_code == 409
    assert endpoint.forms[-1]["refresh_token"] == "rt-1"
    assert client.get(f"/api/accounts/members/{discord_id}/canvas/token", headers=agent).status_code == 404


def test_refresh_outage_keeps_the_grant(app, agent, endpoint, monkeypatch):
    client = app.test_client()
    discord_id = _member_id()
    _connect(client, agent, endpoint, monkeypatch, discord_id)
    _expire(discord_id)
    endpoint.responses.append(FakeResponse(503, {}))
    assert client.get(f"/api/accounts/members/{discord_id}/canvas/token", headers=agent).status_code == 502
    assert client.get(f"/api/accounts/members/{discord_id}", headers=agent).get_json()["accounts"]


@pytest.mark.parametrize(
    ("status", "body"),
    [(400, {"error": "invalid_request"}), (401, {"error": "invalid_client"}), (400, {}), (401, None)],
)
def test_refresh_error_that_is_not_invalid_grant_keeps_the_grant(app, agent, endpoint, monkeypatch, status, body):
    client = app.test_client()
    discord_id = _member_id()
    _connect(client, agent, endpoint, monkeypatch, discord_id)
    _expire(discord_id)
    endpoint.responses.append(FakeResponse(status, body))
    assert client.get(f"/api/accounts/members/{discord_id}/canvas/token", headers=agent).status_code == 502
    assert client.get(f"/api/accounts/members/{discord_id}", headers=agent).get_json()["accounts"]


def test_disabled_provider_and_missing_key(client, agent, monkeypatch):
    assert client.get("/api/accounts/providers").get_json()["providers"] == ["canvas"]
    assert client.post(f"/api/accounts/members/{_member_id()}/google/login", headers=agent).status_code == 404
    monkeypatch.delenv("SECRETS_KEY")
    assert client.post(f"/api/accounts/members/{_member_id()}/canvas/login", headers=agent).status_code == 503


def test_scopes_and_orgs(client, agent, endpoint, monkeypatch, app):
    discord_id = _member_id()
    _connect(app.test_client(), agent, endpoint, monkeypatch, discord_id)
    linker = _issue("soda", "accounts:link")
    assert client.get(f"/api/accounts/members/{discord_id}/canvas/token", headers=linker).status_code == 403
    assert client.get(f"/api/accounts/members/{discord_id}", headers=linker).status_code == 200
    ais = _issue("ais", "accounts:link", "accounts:token")
    assert client.get(f"/api/accounts/members/{discord_id}/canvas/token", headers=ais).status_code == 404
    assert client.get(f"/api/accounts/members/{discord_id}/canvas/token").status_code == 401
    assert client.get("/api/accounts/members/abc", headers=agent).status_code == 400


def test_member_sees_and_removes_own_accounts(app, member_client, agent, endpoint, monkeypatch):
    _connect(app.test_client(), agent, endpoint, monkeypatch, MEMBER_DISCORD_ID)
    mine = member_client.get("/api/accounts/soda/me").get_json()["accounts"]
    assert [a["provider"] for a in mine] == ["canvas"]
    assert member_client.delete("/api/accounts/soda/me/canvas").get_json() == {"removed": True}
    assert member_client.get("/api/accounts/soda/me").get_json()["accounts"] == []


def test_prune_removes_expired_logins(client, agent):
    state = _start(client, agent, _member_id())
    db = db_connect.SessionLocal()
    try:
        later = datetime.datetime.now(datetime.UTC).replace(tzinfo=None) + datetime.timedelta(hours=1)
        assert service.prune(db, now=later)["logins"] >= 1
        assert db.query(AccountLogin).filter_by(state=state).first() is None
    finally:
        db.close()
