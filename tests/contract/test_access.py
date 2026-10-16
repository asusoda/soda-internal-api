"""Cross-org isolation: officers act only on their own organizations, and only the superadmin on superadmin routes.

SoDA is guild 1001 and AI Society guild 1002 (see conftest). The bot here answers per guild.
"""

import datetime
import logging

import jwt
import pytest

from tests.contract.conftest import OFFICER_DISCORD_ID

AIS_OFFICER_ID = "900000000000000003"
SUPERADMIN_ID = "900000000000000009"
OFFICER_GUILDS = {OFFICER_DISCORD_ID: [1001], AIS_OFFICER_ID: [1002]}


class ScopedBot:
    """Each user is an officer only in the guilds listed in OFFICER_GUILDS."""

    def __init__(self, ready=True):
        self.ready = ready

    def is_ready(self):
        return self.ready

    def officer_guilds(self, user_id, org_roles):
        return OFFICER_GUILDS.get(str(user_id), [])

    def check_user_officer_status(self, user_id, guild_id, role_id):
        return int(guild_id) in OFFICER_GUILDS.get(str(user_id), [])

    def get_guild_roles(self, guild_id):
        return []


@pytest.fixture(autouse=True)
def scoped(app, monkeypatch):
    from core.config import config
    from modules.auth import access

    access.clear_cache()
    monkeypatch.setattr(app, "discord_directory", ScopedBot())
    monkeypatch.setattr(config, "SUPERADMIN_USER_ID", SUPERADMIN_ID)
    monkeypatch.setattr(config, "ACCESS_ENFORCE", True)
    yield
    access.clear_cache()


def headers_for(discord_id):
    from modules.auth.tokens import token_manager

    return {"Authorization": f"Bearer {token_manager.generate_token(username='u', discord_id=discord_id)}"}


def test_officer_reads_own_org(client):
    assert client.get("/api/points/soda/users", headers=headers_for(OFFICER_DISCORD_ID)).status_code == 200
    assert client.get("/api/points/ais/users", headers=headers_for(AIS_OFFICER_ID)).status_code == 200


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", "/api/points/soda/users"),
        ("POST", "/api/points/soda/assign_points"),
        ("GET", "/api/storefront/soda/orders"),
        ("GET", "/api/organizations/1"),
        ("GET", "/api/organizations/1/calendar"),
        ("PUT", "/api/organizations/1/settings"),
    ],
)
def test_officer_refused_on_other_org(client, method, path):
    response = client.open(path, method=method, headers=headers_for(AIS_OFFICER_ID), json={})
    assert response.status_code == 403


def test_report_mode_logs_and_allows(client, monkeypatch, caplog):
    from core.config import config

    monkeypatch.setattr(config, "ACCESS_ENFORCE", False)
    with caplog.at_level(logging.WARNING, logger="access"):
        response = client.get("/api/points/soda/users", headers=headers_for(AIS_OFFICER_ID))
    assert response.status_code == 200
    (line,) = [r.getMessage() for r in caplog.records if r.name == "access"]
    assert "decision=would_deny" in line
    assert "reason=not_org_officer" in line
    assert "org=soda" in line


def test_superadmin_reads_any_org(client):
    for org in ("soda", "ais"):
        assert client.get(f"/api/points/{org}/users", headers=headers_for(SUPERADMIN_ID)).status_code == 200


def test_unknown_org_is_left_to_the_route(client):
    response = client.get("/api/organizations/999", headers=headers_for(AIS_OFFICER_ID))
    assert response.status_code == 404


def test_organization_list_shows_only_own_orgs(client):
    response = client.get("/api/organizations/", headers=headers_for(AIS_OFFICER_ID))
    assert [org["prefix"] for org in response.get_json()] == ["ais"]
    response = client.get("/api/organizations/", headers=headers_for(SUPERADMIN_ID))
    assert sorted(org["prefix"] for org in response.get_json()) == ["ais", "soda"]


def test_app_token_is_scoped_to_its_officer(client):
    from modules.auth.tokens import token_manager

    token = token_manager.generate_app_token("u", "integration", OFFICER_DISCORD_ID)
    headers = {"Authorization": f"Bearer {token}"}
    assert client.get("/api/points/soda/users", headers=headers).status_code == 200
    assert client.get("/api/points/ais/users", headers=headers).status_code == 403


def test_legacy_app_token_without_user_is_refused(client):
    from modules.auth.tokens import token_manager

    claims = {
        "exp": datetime.datetime.now(datetime.UTC) + datetime.timedelta(days=1),
        "name": "u",
        "app_name": "integration",
    }
    token = jwt.encode(claims, token_manager.private_key, algorithm=token_manager.algorithm)
    response = client.get("/api/points/soda/users", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 403


def test_bot_unavailable_refuses_in_enforce_mode(client, app, monkeypatch):
    monkeypatch.setattr(app, "discord_directory", ScopedBot(ready=False))
    assert client.get("/api/points/soda/users", headers=headers_for(OFFICER_DISCORD_ID)).status_code == 503


def test_superadmin_routes_need_the_superadmin(client):
    assert client.get("/api/superadmin/guild_roles/1001", headers=headers_for(OFFICER_DISCORD_ID)).status_code == 403
    assert client.get("/api/superadmin/guild_roles/1001", headers=headers_for(SUPERADMIN_ID)).status_code != 403


def test_superadmin_routes_refuse_officers_in_report_mode(client, monkeypatch):
    from core.config import config

    monkeypatch.setattr(config, "ACCESS_ENFORCE", False)
    assert client.get("/api/superadmin/audit", headers=headers_for(OFFICER_DISCORD_ID)).status_code == 403
    assert client.get("/api/superadmin/audit", headers=headers_for(SUPERADMIN_ID)).status_code == 200


def test_sys_admin_takes_a_list_of_ids(client, monkeypatch):
    from core.config import config

    second = "900000000000000010"
    monkeypatch.setattr(config, "SUPERADMIN_USER_ID", f"{SUPERADMIN_ID}, {second}")
    for discord_id in (SUPERADMIN_ID, second):
        assert client.get("/api/superadmin/check", headers=headers_for(discord_id)).status_code == 200
        assert client.get("/api/points/ais/users", headers=headers_for(discord_id)).status_code == 200
    assert client.get("/api/superadmin/check", headers=headers_for(OFFICER_DISCORD_ID)).status_code == 403


def test_member_cannot_list_all_orders(client, clerk_headers):
    assert client.get("/api/storefront/soda/orders", headers=clerk_headers).status_code == 403


def test_member_details_reach_only_the_orgs_officers_in_report_mode(client, monkeypatch):
    from core.config import config

    monkeypatch.setattr(config, "ACCESS_ENFORCE", False)
    path = "/api/points/soda/users/alice@asu.edu/points"
    own = client.get(path, headers=headers_for(OFFICER_DISCORD_ID)).get_json()["user"]
    assert own["asu_id"] == own["student_id"] == "1200000001"
    other = client.get(path, headers=headers_for(AIS_OFFICER_ID))
    assert other.status_code == 200
    assert {"asu_id", "student_id", "academic_standing", "class_standing", "major", "profile_fields"}.isdisjoint(
        other.get_json()["user"]
    )


def test_officer_cannot_change_the_officer_role_or_prefix(client):
    headers = headers_for(OFFICER_DISCORD_ID)
    for body in ({"officer_role_id": "1001"}, {"prefix": "taken"}):
        assert client.put("/api/organizations/1/settings", json=body, headers=headers).status_code == 403, body
    same_role = {"officer_role_id": "2001"}
    assert (
        client.put("/api/organizations/1/settings", json=same_role, headers=headers_for(SUPERADMIN_ID)).status_code
        == 200
    )


def test_settings_config_keeps_keys_that_have_their_own_routes(client, restore_soda_config):
    from core.db import db_connect
    from modules.organizations.models import Organization

    headers = headers_for(OFFICER_DISCORD_ID)
    body = {"config": {"access": {"knowledge_publisher": True}, "theme": "dark"}}
    assert client.put("/api/organizations/1/settings", json=body, headers=headers).status_code == 200
    for bad in ({"config": None}, {"config": ["x"]}, {"points_per_message": -1}, {"points_cooldown": "60"}, ["x"]):
        assert client.put("/api/organizations/1/settings", json=bad, headers=headers).status_code == 400, bad
    db = db_connect.SessionLocal()
    try:
        org = db.query(Organization).filter_by(id=1).one()
        config = org.config or {}
        assert config.get("theme") == "dark"
        assert "access" not in config
        assert org.points_per_message != -1
    finally:
        db.close()


def test_officer_cannot_edit_a_member_of_another_org(client):
    from core.db import db_connect
    from modules.users.models import User, UserOrganizationMembership

    body = {"name": "Taken", "email": "bob@asu.edu", "discord_id": "900000000000000077"}
    assert client.post("/api/users/ais/users", json=body, headers=headers_for(AIS_OFFICER_ID)).status_code == 201
    db = db_connect.SessionLocal()
    try:
        bob = db.query(User).filter_by(email="bob@asu.edu").one()
        rows = db.query(UserOrganizationMembership).filter_by(user_id=bob.id, organization_id=2).all()
        try:
            assert (bob.name, bob.discord_id) == ("Bob", None)
            assert rows
        finally:
            for row in rows:
                db.delete(row)
            db.commit()
    finally:
        db.close()


def test_superadmin_check_refuses_an_expired_token_with_401(client):
    from modules.auth.tokens import token_manager

    token = token_manager.generate_token("u", SUPERADMIN_ID, exp_minutes=-1)
    response = client.get("/api/superadmin/check", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401
