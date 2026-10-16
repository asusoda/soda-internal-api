"""Tools for the dashboard's officer actions: points, members, store, uptime, settings, secrets, tokens, webhooks."""

import json

import pytest
from cryptography.fernet import Fernet

from core.db import db_connect


def _issue(*scopes, name="officer-agent"):
    from modules.auth import machine_tokens

    db = db_connect.SessionLocal()
    try:
        value, _ = machine_tokens.issue(db, organization_id=1, name=name, kind="agent", scopes=list(scopes))
        return {"Authorization": f"Bearer {value}"}
    finally:
        db.close()


def _call(client, headers, tool, **arguments):
    return client.post(f"/api/tools/{tool}", json=arguments, headers=headers)


def _result(client, headers, tool, **arguments):
    response = _call(client, headers, tool, **arguments)
    assert response.status_code == 200, response.get_json()
    return response.get_json()["result"]


def _names(client, headers):
    return [t["name"] for t in client.get("/api/tools", headers=headers).get_json()["tools"]]


def test_points_award_list_and_delete(client):
    headers = _issue("points:write", "members:read")
    entries = _result(client, headers, "points.award", members=["alice", "bob@asu.edu"], points=3, event="tool-test")
    assert [e["points"] for e in entries["entries"]] == [3, 3]
    assert all(e["awarded_by_officer"].startswith("agent:officer-agent#") for e in entries["entries"])

    missing = _call(client, headers, "points.award", members=["alice", "nobody@asu.edu"], points=1, event="tool-test")
    assert missing.status_code == 404
    listed = _result(client, headers, "points.entries", event="tool-test")["entries"]
    assert len(listed) == 2

    history = _result(client, headers, "points.history", member="alice")
    assert any(e["event"] == "tool-test" for e in history["points_history"])

    preview = _result(client, headers, "points.delete", event="tool-test")
    assert preview["confirm_required"] is True and preview["preview"]["count"] == 2
    deleted = _result(client, headers, "points.delete", event="tool-test", confirm=True)
    assert sorted(deleted["deleted"]) == sorted(e["id"] for e in listed)
    assert _result(client, headers, "points.entries", event="tool-test")["entries"] == []


def test_points_csv_import_queues_the_job(client, monkeypatch):
    from core import jobs

    queued = []
    monkeypatch.setattr(jobs, "defer", lambda name, **kwargs: queued.append((name, kwargs)))
    headers = _issue("points:write")
    csv = "email,checked_in\nalice@asu.edu,yes\n"
    assert _result(client, headers, "points.import_csv", content=csv, event_name="GBM 2", event_points=5) == {
        "queued": True
    }
    assert queued == [
        (
            "points.import_event_csv",
            {"file_content": csv, "event_name": "GBM 2", "event_points": 5, "org_prefix": "soda"},
        )
    ]


def test_points_tools_need_their_scopes_and_module(client, officer_headers, restore_soda_config):
    reader = _issue("points:read")
    assert _call(client, reader, "points.entries").status_code == 404
    assert _call(client, reader, "members.list").status_code == 404
    writer = _issue("points:write")
    assert "points.award" in _names(client, writer)
    orgs = client.get("/api/organizations/", headers=officer_headers).get_json()
    soda = next(o["id"] for o in orgs if o["prefix"] == "soda")
    client.put(f"/api/organizations/{soda}/modules", json={"modules": {"points": False}}, headers=officer_headers)
    assert "points.award" not in _names(client, writer)


@pytest.fixture
def new_member():
    """Removes the member that a test adds."""
    from modules.users.models import User, UserOrganizationMembership

    email = "tool-member@asu.edu"
    yield email
    db = db_connect.SessionLocal()
    try:
        user = db.query(User).filter_by(email=email).first()
        if user is not None:
            db.query(UserOrganizationMembership).filter_by(user_id=user.id).delete()
            db.delete(user)
            db.commit()
    finally:
        db.close()


def test_members_list_add_and_update(client, new_member):
    headers = _issue("members:read", "members:write")
    found = _result(client, headers, "members.list", query="alice")
    assert found["total"] == 1 and found["members"][0]["email"] == "alice@asu.edu"
    assert isinstance(found["members"][0]["points"], int | float)

    added = _result(client, headers, "members.add", name="Tool Member", email=new_member, major="CS")
    assert added["member"]["email"] == new_member
    changed = _result(client, headers, "members.update", member=new_member, major="Math", profile_fields={"shirt": "M"})
    assert changed["member"]["major"] == "Math" and changed["member"]["profile_fields"] == {"shirt": "M"}
    assert _call(client, headers, "members.update", member="nobody@asu.edu", major="Art").status_code == 404


def test_discord_sync_previews_before_it_adds(client, monkeypatch):
    from modules.users import service as users

    class Directory:
        def is_ready(self):
            return True

        def list_members(self, guild_id):
            return [{"id": "900000000000000777", "username": "carol", "name": "Carol", "roles": ["2001"], "bot": False}]

        def get_guild_roles(self, guild_id):
            return [{"id": "2001", "name": "Officer", "color": "#000000", "position": 1, "managed": False}]

    monkeypatch.setattr(users, "bot_directory", lambda: Directory())
    headers = _issue("members:read", "members:write")
    assert _result(client, headers, "members.discord_roles")["roles"][0]["id"] == "2001"
    preview = _result(client, headers, "members.discord_sync", roles=["2001"])
    assert preview["confirm_required"] is True
    assert preview["preview"] == {"matched": 1, "new_users": 1, "joined": 1, "already": 0}
    assert _result(client, headers, "members.list", query="carol")["total"] == 0


def test_store_products_and_orders(client):
    headers = _issue("store:read", "store:write")
    created = _result(client, headers, "store.save_product", name="Mug", price=10, stock=3, category=" ")["product"]
    assert created["category"] is None
    changed = _result(client, headers, "store.save_product", id=created["id"], stock=7)["product"]
    assert changed["stock"] == 7
    assert any(p["name"] == "Mug" for p in _result(client, headers, "store.products")["products"])
    assert _call(client, headers, "store.save_product", name="No price").status_code == 400

    pending = _result(client, headers, "store.delete_products", ids=[created["id"]])
    assert pending["confirm_required"] is True
    assert _result(client, headers, "store.delete_products", ids=[created["id"]], confirm=True)["deleted"] == [
        created["id"]
    ]
    assert _call(client, headers, "store.delete_products", ids=[created["id"]], confirm=True).status_code == 404

    order = _result(client, headers, "store.orders", status="pending")["orders"][0]
    assert order["user_email"] == "alice@asu.edu"
    updated = _result(client, headers, "store.update_orders", ids=[order["id"]], status="processing")["orders"]
    assert updated[0]["status"] == "processing"
    assert _call(client, headers, "store.update_orders", ids=[order["id"]], status="lost").status_code == 400
    _result(client, headers, "store.update_orders", ids=[order["id"]], status="pending", message=None)
    assert _result(client, headers, "store.delete_orders", ids=[order["id"]])["confirm_required"] is True


def test_store_tools_need_store_scopes(client):
    reader = _issue("store:read")
    assert _call(client, reader, "store.save_product", name="Mug", price=1, stock=1).status_code == 404
    assert _call(client, reader, "store.products").status_code == 200


def test_uptime_monitor_round_trip(client, monkeypatch):
    from core import net

    monkeypatch.setattr(net, "check_public", lambda url: None)
    headers = _issue("uptime:read", "uptime:manage")
    monitor = _result(client, headers, "uptime.save", name="Tool site", target="https://example.com")["monitor"]
    changed = _result(client, headers, "uptime.save", id=monitor["id"], enabled=False)["monitor"]
    assert changed["enabled"] is False
    assert _result(client, headers, "uptime.get", id=monitor["id"])["monitor"]["name"] == "Tool site"
    assert _result(client, headers, "uptime.targets") == {"apps": []}
    assert _result(client, headers, "uptime.delete", ids=[monitor["id"]])["confirm_required"] is True
    assert _result(client, headers, "uptime.delete", ids=[monitor["id"]], confirm=True) == {"deleted": [monitor["id"]]}
    assert _result(client, headers, "uptime.list")["monitors"] == []


def test_org_calendar_and_leetcode_settings(client, restore_soda_config):
    headers = _issue("org:read", "settings:write", "calendar:read", "calendar:manage")
    before = _result(client, headers, "org.settings")
    changed = _result(client, headers, "org.update_settings", points_per_message=3)
    assert changed["points_per_message"] == 3
    assert _call(client, headers, "org.update_settings", prefix="new").status_code == 400
    _result(client, headers, "org.update_settings", points_per_message=before["points_per_message"])

    calendar = _result(client, headers, "calendar.settings")["settings"]
    assert calendar["notion_database_id"] == "notion-db-soda"
    toggled = _result(client, headers, "calendar.update_settings", calendar_sync_enabled=True)["settings"]
    assert toggled["calendar_sync_enabled"] is True
    _result(client, headers, "calendar.update_settings", calendar_sync_enabled=bool(calendar["calendar_sync_enabled"]))

    saved = _result(client, headers, "leetcode.update_settings", channel_id="123456789", daily_time="09:30")
    assert saved["settings"]["daily_time"] == "09:30"
    assert _call(client, headers, "leetcode.update_settings", daily_time="9am").status_code == 400
    assert _result(client, headers, "leetcode.settings")["settings"]["channel_id"] == "123456789"
    assert _result(client, headers, "ci.set_repos", repos=["asusoda/platform"]) == {"repos": ["asusoda/platform"]}


def test_secrets_are_write_only(client, monkeypatch):
    monkeypatch.setenv("SECRETS_KEY", Fernet.generate_key().decode())
    headers = _issue("secrets:manage")
    value = "secret_value_for_tool_test"
    assert _result(client, headers, "secrets.set", name="notion_api_key", value=value)["confirm_required"] is True
    assert _result(client, headers, "secrets.set", name="notion_api_key", value=value, confirm=True)["set"] is True
    listing = _result(client, headers, "secrets.list")
    assert value not in json.dumps(listing)
    assert next(s for s in listing["secrets"] if s["name"] == "notion_api_key")["set"] is True
    assert _call(client, headers, "secrets.set", name="not_a_secret", value="x", confirm=True).status_code == 400
    deleted = _result(client, headers, "secrets.delete", names=["notion_api_key", "notion_api_key"], confirm=True)
    assert deleted == {"deleted": ["notion_api_key"], "not_set": []}


def test_tokens_get_only_the_callers_scopes(client):
    headers = _issue("tokens:manage", "org:read")
    listed = _result(client, headers, "tokens.list")
    assert "tokens" in listed and "org:read" in listed["scopes"]
    assert all("token" not in t for t in listed["tokens"])

    wider = _call(client, headers, "tokens.create", name="child", kind="agent", scopes=["points:write"], confirm=True)
    assert wider.status_code == 403
    pending = _result(client, headers, "tokens.create", name="child", kind="agent", scopes=["org:read"])
    assert pending["confirm_required"] is True and "token" not in pending

    child = _result(client, headers, "tokens.create", name="child", kind="agent", scopes=["org:read"], confirm=True)
    assert child["token"].startswith("plat_") and child["scopes"] == ["org:read"]
    child_headers = {"Authorization": f"Bearer {child['token']}"}
    assert _call(client, child_headers, "org.info").status_code == 200
    assert child["token"] not in json.dumps(_result(client, headers, "tokens.list"))

    assert _call(client, headers, "tokens.revoke", ids=[999999], confirm=True).status_code == 404
    assert _result(client, headers, "tokens.revoke", ids=[child["id"]], confirm=True) == {"revoked": [child["id"]]}
    assert _call(client, child_headers, "org.info").status_code == 401


def test_child_token_expires_with_its_parent(client):
    import datetime

    from core.time import utcnow
    from modules.auth import machine_tokens

    db = db_connect.SessionLocal()
    try:
        value, row = machine_tokens.issue_oauth(
            db,
            organization_id=1,
            name="oauth-client",
            scopes=["tokens:manage", "org:read"],
            created_by="officer",
            expires_seconds=3600,
        )
        db.commit()
        parent_expiry = row.expires_at
    finally:
        db.close()
    assert parent_expiry is not None
    headers = {"Authorization": f"Bearer {value}"}
    forever = _result(client, headers, "tokens.create", name="child", kind="agent", scopes=["org:read"], confirm=True)
    assert forever["expires_at"] is not None
    assert datetime.datetime.fromisoformat(forever["expires_at"]) <= parent_expiry
    longer = _result(
        client, headers, "tokens.create", name="child", kind="agent", scopes=["org:read"], expires_days=30, confirm=True
    )
    assert datetime.datetime.fromisoformat(longer["expires_at"]) <= parent_expiry
    assert parent_expiry < utcnow() + datetime.timedelta(days=1)


def test_webhook_tools(client, sent):
    headers = _issue("webhooks:manage")
    url = "https://discord.com/api/webhooks/1/tool-test"
    hook = _result(client, headers, "webhooks.save", name="Tools", url=url, events=["member.joined"])["webhook"]
    assert url not in json.dumps(_result(client, headers, "webhooks.list"))
    assert _result(client, headers, "webhooks.save", id=hook["id"], enabled=False)["webhook"]["enabled"] is False
    assert _result(client, headers, "webhooks.test", id=hook["id"])["ok"] is True
    assert sent[-1][0] == url
    assert _call(client, headers, "webhooks.delete", ids=[hook["id"], 999999], confirm=True).status_code == 404
    assert _result(client, headers, "webhooks.delete", ids=[hook["id"]], confirm=True) == {"deleted": [hook["id"]]}


def test_notification_and_error_deletes_need_confirm(client):
    headers = _issue("settings:write")
    pending = _result(client, headers, "notifications.delete", ids=["event-999999"])
    assert pending["confirm_required"] is True
    assert "notifications" in _result(client, headers, "notifications.delete", ids=["event-999999"], confirm=True)
    assert _result(client, headers, "errors.delete", ids=[999999])["confirm_required"] is True
    assert _result(client, headers, "errors.delete", ids=[999999], confirm=True) == {"deleted": 0}
    assert "changed" in _result(client, headers, "errors.reopen", ids=[999999])


def test_create_pod_waits_for_confirm(client, monkeypatch):
    from modules.godfather import service as godfather

    monkeypatch.setattr(godfather, "create_pod", lambda *a, **k: pytest.fail("create_pod ran without confirm"))
    headers = _issue("godfather:manage")
    pending = _result(client, headers, "godfather.create_pod", name="gpu-1", use_cpu_only=True)
    assert pending["confirm_required"] is True
    assert _call(client, headers, "godfather.create_pod", name="gpu-1", allowed_users=["abc"]).status_code == 400


def test_app_templates_and_providers(client):
    headers = _issue("apps:read")
    assert isinstance(_result(client, headers, "apps.templates")["templates"], list)
    assert all("configured" in p for p in _result(client, headers, "hosting.providers")["providers"])
