"""Tools that change an org: scopes, the confirm step, write-only secrets and the audit trail."""

import json

from cryptography.fernet import Fernet

from core.db import db_connect


def _issue(*scopes):
    from modules.auth import machine_tokens

    db = db_connect.SessionLocal()
    try:
        value, _ = machine_tokens.issue(db, organization_id=1, name="test-agent", kind="agent", scopes=list(scopes))
        return {"Authorization": f"Bearer {value}"}
    finally:
        db.close()


def _call(client, headers, tool, **arguments):
    return client.post(f"/api/tools/{tool}", json=arguments, headers=headers)


def test_confirm_tools_change_nothing_until_confirmed(client, restore_soda_config):
    headers = _issue("settings:write", "org:read")
    first = _call(client, headers, "org.set_modules", modules={"feeds": False})
    assert first.status_code == 200
    result = first.get_json()["result"]
    assert result["confirm_required"] is True and result["arguments"] == {"modules": {"feeds": False}}
    info = _call(client, headers, "org.info").get_json()["result"]
    assert info["modules"]["feeds"] is True

    done = _call(client, headers, "org.set_modules", modules={"feeds": False}, confirm=True).get_json()["result"]
    assert {m["name"]: m["enabled"] for m in done["modules"]}["feeds"] is False
    assert _call(client, headers, "org.info").get_json()["result"]["modules"]["feeds"] is False


def test_write_tools_need_their_scope(client):
    headers = _issue("org:read")
    assert _call(client, headers, "org.set_modules", modules={"feeds": False}, confirm=True).status_code == 404
    assert _call(client, headers, "integrations.list").status_code == 404
    names = [t["name"] for t in client.get("/api/tools", headers=_issue("settings:write")).get_json()["tools"]]
    assert names == [
        "batch",
        "ci.set_repos",
        "errors.delete",
        "errors.reopen",
        "errors.resolve",
        "leetcode.update_settings",
        "notifications.delete",
        "notifications.reopen",
        "notifications.resolve",
        "org.set_branding",
        "org.set_modules",
        "org.update_settings",
    ]


def test_branding_and_notifications(client, restore_soda_config):
    headers = _issue("settings:write", "org:read", "activity:read")
    changed = _call(client, headers, "org.set_branding", accent_color="#1F6FEB").get_json()["result"]
    assert changed["accent_color"] == "#1f6feb"
    assert _call(client, headers, "org.branding").get_json()["result"]["accent_color"] == "#1f6feb"
    assert _call(client, headers, "org.set_branding", accent_color="blue").status_code == 400
    assert _call(client, headers, "notifications.list").status_code == 200
    assert _call(client, headers, "org.trends", days=7).get_json()["result"]["days"] == 7
    assert "entries" in _call(client, headers, "activity.log", limit=5).get_json()["result"]


def test_integration_keys_are_write_only(client, monkeypatch):
    monkeypatch.setenv("SECRETS_KEY", Fernet.generate_key().decode())
    headers = _issue("integrations:manage")
    token = "secret_notion_value_123"
    saved = _call(client, headers, "integrations.save", key="notion", fields={"notion_api_key": token}, confirm=True)
    assert saved.status_code == 200, saved.get_json()
    listing = _call(client, headers, "integrations.list").get_json()["result"]
    assert token not in json.dumps(listing)
    notion = next(i for i in listing["integrations"] if i["key"] == "notion")
    assert notion["source"] == "org"
    _call(client, headers, "integrations.save", key="notion", fields={"notion_api_key": None}, confirm=True)


def test_knowledge_document_round_trip(client):
    headers = _issue("knowledge:read", "knowledge:write")
    added = _call(client, headers, "knowledge.add_document", name="faq.md", content="# FAQ\n\nMeetings are on Friday.")
    assert added.status_code == 200, added.get_json()
    assert added.get_json()["result"]["indexed"] == 1
    keys = [s["key"] for s in _call(client, headers, "knowledge.sources").get_json()["result"]["sources"]]
    assert "agent/faq.md" in keys
    pending = _call(client, headers, "knowledge.delete_source", key="agent/faq.md").get_json()["result"]
    assert pending["confirm_required"] is True
    assert _call(client, headers, "knowledge.delete_source", key="agent/faq.md", confirm=True).status_code == 200
    keys = [s["key"] for s in _call(client, headers, "knowledge.sources").get_json()["result"]["sources"]]
    assert "agent/faq.md" not in keys


def test_pending_calls_are_audited_as_pending(client, restore_soda_config):
    from core.audit import AuditEntry

    headers = _issue("settings:write")
    _call(client, headers, "org.set_modules", modules={"feeds": False})
    db = db_connect.SessionLocal()
    try:
        entry = db.query(AuditEntry).filter_by(action="tool org.set_modules").order_by(AuditEntry.id.desc()).first()
        assert entry is not None and entry.details is not None and entry.actor_id is not None
        assert entry.details["confirm"] == "pending"
        assert entry.actor_id.startswith("agent:test-agent#")
    finally:
        db.close()
