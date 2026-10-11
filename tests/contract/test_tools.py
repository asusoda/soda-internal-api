"""Tools over HTTP (/api/tools) and MCP: filtered by token scopes and org module switches, audited."""

import pytest


@pytest.fixture
def soda_id(client, officer_headers, restore_soda_config):
    orgs = client.get("/api/organizations/", headers=officer_headers).get_json()
    return next(o["id"] for o in orgs if o["prefix"] == "soda")


@pytest.fixture
def token_for(client, officer_headers, soda_id):
    def issue(*scopes):
        body = {"name": "test-agent", "kind": "agent", "scopes": list(scopes)}
        response = client.post(f"/api/organizations/{soda_id}/tokens", json=body, headers=officer_headers)
        assert response.status_code == 201, response.get_json()
        return {"Authorization": f"Bearer {response.get_json()['token']}"}

    return issue


def _names(client, headers):
    return [t["name"] for t in client.get("/api/tools", headers=headers).get_json()["tools"]]


def test_tools_follow_scopes(client, token_for):
    org_read = ["batch", "leetcode.settings", "org.branding", "org.info", "org.limits", "org.settings"]
    assert _names(client, token_for("org:read")) == org_read
    assert _names(client, token_for("org:read", "points:read", "calendar:read")) == [
        "batch",
        "calendar.settings",
        "events.list",
        "leetcode.settings",
        "org.branding",
        "org.info",
        "org.limits",
        "org.settings",
        "points.leaderboard",
    ]


def test_tools_follow_module_switches(client, officer_headers, soda_id, token_for):
    headers = token_for("points:read")
    client.put(f"/api/organizations/{soda_id}/modules", json={"modules": {"points": False}}, headers=officer_headers)
    assert _names(client, headers) == []
    assert client.post("/api/tools/points.leaderboard", json={}, headers=headers).status_code == 404


def test_call_org_info_and_leaderboard(client, token_for):
    headers = token_for("org:read", "points:read")
    info = client.post("/api/tools/org.info", headers=headers)
    assert info.status_code == 200
    assert info.get_json()["result"]["prefix"] == "soda"
    board = client.post("/api/tools/points.leaderboard", json={"limit": 5}, headers=headers).get_json()["result"]
    assert all(set(row) == {"rank", "name", "total_points"} for row in board["leaderboard"])


def test_bad_calls(client, token_for):
    headers = token_for("points:read")
    assert client.post("/api/tools/points.leaderboard", json={"limit": 0}, headers=headers).status_code == 400
    assert client.post("/api/tools/points.leaderboard", json={"x": 1}, headers=headers).status_code == 400
    assert client.post("/api/tools/org.info", headers=headers).status_code == 404  # scope missing
    assert client.post("/api/tools/nope", headers=headers).status_code == 404
    assert client.get("/api/tools").status_code == 401


def test_tool_calls_are_audited(client, token_for):
    from core.audit import AuditEntry
    from core.db import db_connect

    client.post("/api/tools/org.info", headers=token_for("org:read"))
    db = db_connect.SessionLocal()
    try:
        entry = db.query(AuditEntry).order_by(AuditEntry.id.desc()).first()
        assert entry.action == "tool org.info"
        assert entry.source == "api"
        assert entry.org == "soda"
        assert entry.actor_id.startswith("agent:test-agent#")
    finally:
        db.close()


@pytest.fixture
def mcp_client(app):
    from starlette.testclient import TestClient

    from modules.mcp.server import build_app

    with TestClient(build_app(host="testserver")) as test_client:
        yield test_client


def _rpc(mcp_client, headers, method, params=None):
    body = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}}
    response = mcp_client.post("/mcp", json=body, headers={**headers, "Accept": "application/json, text/event-stream"})
    return response


def test_mcp_lists_and_calls_tools(mcp_client, token_for):
    headers = token_for("org:read")
    init = _rpc(
        mcp_client,
        headers,
        "initialize",
        {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "test", "version": "0"}},
    )
    assert init.status_code == 200, init.text
    listed = _rpc(mcp_client, headers, "tools/list")
    assert listed.status_code == 200, listed.text
    tools = listed.json()["result"]["tools"]
    assert [t["name"] for t in tools] == [
        "batch",
        "leetcode.settings",
        "org.branding",
        "org.info",
        "org.limits",
        "org.settings",
    ]
    assert tools[3]["annotations"] == {"readOnlyHint": True, "destructiveHint": False}
    called = _rpc(mcp_client, headers, "tools/call", {"name": "org.info", "arguments": {}})
    result = called.json()["result"]
    assert result.get("isError") in (None, False)
    assert result["structuredContent"]["prefix"] == "soda"


def test_mcp_refuses_without_a_token(mcp_client):
    called = _rpc(mcp_client, {}, "tools/call", {"name": "org.info", "arguments": {}})
    assert called.json()["result"]["isError"] is True
