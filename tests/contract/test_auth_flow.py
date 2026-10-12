"""Login flow and the routes that used to need no credential: OAuth state, login codes, member login, game controls."""

from urllib.parse import parse_qs, urlparse

import pytest

from tests.contract.conftest import MEMBER_DISCORD_ID, MEMBER_EMAIL, OFFICER_DISCORD_ID


class LoginBot:
    def is_ready(self):
        return True

    def officer_guilds(self, user_id, org_roles):
        return [1001] if str(user_id) == OFFICER_DISCORD_ID else []

    def get_display_name(self, guild_id, user_id):
        return "officer"


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def json(self):
        return self.payload


@pytest.fixture
def enforce(monkeypatch):
    from core.config import config
    from modules.auth import access

    access.clear_cache()
    monkeypatch.setattr(config, "ACCESS_ENFORCE", True)
    yield
    access.clear_cache()


@pytest.fixture
def discord(app, monkeypatch):
    """Discord's token and user endpoints, answering for the officer."""
    import modules.auth.api as auth_api

    monkeypatch.setattr(app, "discord_directory", LoginBot())
    monkeypatch.setattr(auth_api.requests, "post", lambda *a, **k: FakeResponse({"access_token": "discord-token"}))
    monkeypatch.setattr(auth_api.requests, "get", lambda *a, **k: FakeResponse({"id": OFFICER_DISCORD_ID}))


def _query(response):
    return parse_qs(urlparse(response.headers["Location"]).query)


def test_login_sends_state_and_callback_returns_code(client, discord):
    state = _query(client.get("/api/auth/login"))["state"][0]
    response = client.get(f"/api/auth/callback?code=abc&state={state}")
    query = _query(response)
    assert "access_token" not in query and "refresh_token" not in query
    code = query["code"][0]

    exchanged = client.post("/api/auth/exchange", json={"code": code})
    assert exchanged.status_code == 200
    assert set(exchanged.get_json()) == {"access_token", "refresh_token"}
    assert client.post("/api/auth/exchange", json={"code": code}).status_code == 400


def test_callback_with_wrong_state_is_refused(client, discord, enforce):
    client.get("/api/auth/login")
    response = client.get("/api/auth/callback?code=abc&state=forged")
    assert "error" in _query(response)


def test_callback_with_wrong_state_only_logs_in_report_mode(client, discord):
    client.get("/api/auth/login")
    response = client.get("/api/auth/callback?code=abc&state=forged")
    assert "code" in _query(response)


def test_member_login_needs_matching_clerk_session(client, clerk_headers, enforce):
    body = {"name": "Alice", "email": MEMBER_EMAIL, "asu_id": "1200000001"}
    assert client.post("/api/points/soda/member_login", json=body).status_code == 403
    other = {**body, "email": "bob@asu.edu"}
    assert client.post("/api/points/soda/member_login", json=other, headers=clerk_headers).status_code == 403
    assert client.post("/api/points/soda/member_login", json=body, headers=clerk_headers).status_code == 200


def test_game_controls_need_an_officer(client, app, monkeypatch, officer_headers, enforce):
    monkeypatch.setattr(app, "discord_directory", LoginBot())
    assert client.post("/api/bot/awardpoints?team=a&points=5").status_code == 401
    assert client.get("/api/calendar/debug/organizations").status_code == 401
    assert client.get("/api/bot/", headers=officer_headers).status_code == 200


def test_login_started_from_the_dashboard_returns_there(client, discord, monkeypatch):
    from core.config import config

    monkeypatch.setattr(config, "DASHBOARD_URL", "https://dash.example.org")
    state = _query(client.get("/api/auth/login?client=dashboard"))["state"][0]
    response = client.get(f"/api/auth/callback?code=abc&state={state}")
    assert response.headers["Location"].startswith("https://dash.example.org/auth/?code=")

    state = _query(client.get("/api/auth/login"))["state"][0]
    response = client.get(f"/api/auth/callback?code=abc&state={state}")
    assert response.headers["Location"].startswith(f"{config.CLIENT_URL}/auth/?code=")


@pytest.fixture
def member_discord(monkeypatch):
    """Discord's token and user endpoints, answering for the member Alice."""
    import modules.auth.api as auth_api

    monkeypatch.setattr(auth_api.requests, "post", lambda *a, **k: FakeResponse({"access_token": "discord-token"}))
    monkeypatch.setattr(auth_api.requests, "get", lambda *a, **k: FakeResponse({"id": MEMBER_DISCORD_ID}))


def test_store_login_signs_the_member_in_and_returns_to_the_store(client, member_discord):
    from core.config import config

    login = client.get("/api/auth/store_login?org=soda")
    assert _query(login)["scope"] == ["identify"]
    state = _query(login)["state"][0]
    assert client.get("/api/points/soda/member_profile").status_code == 401

    response = client.get(f"/api/auth/callback?code=abc&state={state}")
    assert response.headers["Location"] == f"{config.CLIENT_URL}/store/soda"
    assert client.get("/api/storefront/soda/members/orders").status_code == 200
    profile = client.get("/api/points/soda/member_profile")
    assert profile.status_code == 200
    assert profile.get_json()["user"]["email"] == MEMBER_EMAIL


def test_store_login_needs_an_active_org(client):
    assert client.get("/api/auth/store_login?org=nope").status_code == 404
    assert client.get("/api/auth/store_login").status_code == 404


def test_store_login_with_wrong_state_is_refused_in_report_mode(client, member_discord):
    from core.config import config

    client.get("/api/auth/store_login?org=soda")
    response = client.get("/api/auth/callback?code=abc&state=forged")
    assert response.headers["Location"].startswith(f"{config.CLIENT_URL}/store/soda?error=")
    assert client.get("/api/storefront/soda/members/orders").status_code == 401


def test_officer_login_after_an_unfinished_store_login_returns_to_auth(client, discord):
    from core.config import config

    client.get("/api/auth/store_login?org=soda")
    state = _query(client.get("/api/auth/login"))["state"][0]
    response = client.get(f"/api/auth/callback?code=abc&state={state}")
    assert response.headers["Location"].startswith(f"{config.CLIENT_URL}/auth/?code=")
