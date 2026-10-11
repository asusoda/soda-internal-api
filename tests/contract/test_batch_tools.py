"""The batch tool: each call has its own scope check, confirm step and audit entry; at most 25 calls; no nesting."""

from core.db import db_connect


def _issue(*scopes):
    from modules.auth import machine_tokens

    db = db_connect.SessionLocal()
    try:
        value, _ = machine_tokens.issue(db, organization_id=1, name="batcher", kind="agent", scopes=list(scopes))
        return {"Authorization": f"Bearer {value}"}
    finally:
        db.close()


def _batch(client, headers, calls, **extra):
    return client.post("/api/tools/batch", json={"calls": calls, **extra}, headers=headers)


def _names(client, headers):
    return [t["name"] for t in client.get("/api/tools", headers=headers).get_json()["tools"]]


def test_batch_is_listed_only_with_other_tools(client):
    assert "batch" in _names(client, _issue("org:read"))
    assert _names(client, _issue("agents:read")) == []


def test_each_call_needs_its_own_scope(client):
    headers = _issue("org:read")
    calls = [
        {"tool": "org.info"},
        {"tool": "points.leaderboard", "arguments": {"limit": 3}},
        {"tool": "org.set_modules", "arguments": {"modules": {"feeds": False}, "confirm": True}},
        {"tool": "org.info", "arguments": {"nope": 1}},
    ]
    response = _batch(client, headers, calls)
    assert response.status_code == 200, response.get_json()
    results = response.get_json()["result"]["results"]
    assert [(r["tool"], r["ok"], r["status"]) for r in results] == [
        ("org.info", True, 200),
        ("points.leaderboard", False, 404),
        ("org.set_modules", False, 404),
        ("org.info", False, 400),
    ]
    assert results[0]["result"]["prefix"] == "soda"
    assert "error" in results[1] and "result" not in results[1]


def test_confirm_tools_return_their_preview_in_a_batch(client, restore_soda_config):
    headers = _issue("settings:write", "org:read")
    change = {"tool": "org.set_modules", "arguments": {"modules": {"feeds": False}}}
    pending = _batch(client, headers, [change, {"tool": "org.info"}]).get_json()["result"]["results"]
    assert pending[0]["ok"] is True and pending[0]["result"]["confirm_required"] is True
    assert pending[1]["result"]["modules"]["feeds"] is True

    confirmed = {"tool": "org.set_modules", "arguments": {"modules": {"feeds": False}, "confirm": True}}
    done = _batch(client, headers, [confirmed, {"tool": "org.info"}]).get_json()["result"]["results"]
    assert done[1]["result"]["modules"]["feeds"] is False


def test_stop_on_error_stops_at_the_first_failure(client):
    headers = _issue("org:read")
    calls = [{"tool": "org.info"}, {"tool": "nope"}, {"tool": "org.branding"}]
    assert len(_batch(client, headers, calls).get_json()["result"]["results"]) == 3
    stopped = _batch(client, headers, calls, stop_on_error=True).get_json()["result"]["results"]
    assert [r["tool"] for r in stopped] == ["org.info", "nope"]


def test_batch_size_and_nesting(client):
    headers = _issue("org:read")
    assert _batch(client, headers, [{"tool": "org.info"}] * 25).status_code == 200
    assert _batch(client, headers, [{"tool": "org.info"}] * 26).status_code == 400
    assert _batch(client, headers, []).status_code == 400
    assert _batch(client, headers, [{"tool": "org.info", "extra": 1}]).status_code == 400
    nested = {"tool": "batch", "arguments": {"calls": [{"tool": "org.info"}]}}
    result = _batch(client, headers, [nested]).get_json()["result"]["results"][0]
    assert result == {"tool": "batch", "ok": False, "error": "A batch cannot hold a batch", "status": 400}


def test_each_call_in_a_batch_is_audited(client):
    from core.audit import AuditEntry

    headers = _issue("org:read")
    db = db_connect.SessionLocal()
    try:
        last = db.query(AuditEntry.id).order_by(AuditEntry.id.desc()).limit(1).scalar() or 0
        _batch(client, headers, [{"tool": "org.info"}, {"tool": "org.branding"}])
        actions = [e.action for e in db.query(AuditEntry).filter(AuditEntry.id > last).order_by(AuditEntry.id)]
        assert actions == ["tool org.info", "tool org.branding", "tool batch"]
    finally:
        db.close()
