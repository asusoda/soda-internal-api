"""Linked apps: services that run outside Platform, listed on Hosting and checked by Uptime, never deployed."""

import uuid

import pytest

BASE = "/api/dashboard/soda/apps"
MANIFEST = {
    "kind": "bot",
    "image": "ghcr.io/example/bot",
    "cpu": {"id": "cpu3c", "vcpuCount": 2},
    "health": {"port": 8080, "path": "/health"},
}


@pytest.fixture
def name(app):
    """A fresh app name; its app and monitor are removed after the test."""
    value = "linked-" + uuid.uuid4().hex[:8]
    yield value
    from core.db import db_connect
    from modules.runpod.models import App
    from modules.uptime.models import UptimeMonitor

    db = db_connect.SessionLocal()
    db.query(UptimeMonitor).filter(UptimeMonitor.target == value).delete(synchronize_session=False)
    db.query(App).filter(App.name == value).delete(synchronize_session=False)
    db.commit()
    db.close()


def test_a_linked_app_is_listed_watched_and_never_deployed(client, officer_headers, name):
    body = {
        "url": "https://vault.example.org",
        "description": "Password manager",
        "kind": "service",
        "runs_as": ["vaultwarden"],
    }
    linked = client.put(f"{BASE}/{name}/link", json=body, headers=officer_headers)
    assert linked.status_code == 200, linked.get_json()
    app = linked.get_json()
    assert app["linked"] is True and app["provider"] == "linked" and app["runs_as"] == ["vaultwarden"]
    assert app["url"] == "https://vault.example.org" and app["pod_id"] is None

    listed = {a["name"]: a for a in client.get(BASE, headers=officer_headers).get_json()["apps"]}
    assert listed[name]["linked"] is True
    monitors = client.get("/api/uptime/soda/monitors", headers=officer_headers).get_json()["monitors"]
    assert any(m["target"] == name and m["target_kind"] == "app" for m in monitors)
    targets = {
        t["name"]: t["url"] for t in client.get("/api/uptime/soda/targets", headers=officer_headers).get_json()["apps"]
    }
    assert targets[name] == "https://vault.example.org"

    deploy = client.post(f"{BASE}/{name}/deploy", json={"tag": "v1"}, headers=officer_headers)
    assert deploy.status_code == 409 and "linked app" in deploy.get_json()["error"]
    assert client.post(f"{BASE}/{name}/rollback", json={}, headers=officer_headers).status_code == 409
    assert client.put(f"{BASE}/{name}", json={"manifest": MANIFEST}, headers=officer_headers).status_code == 409

    again = client.put(f"{BASE}/{name}/link", json={"url": None, "kind": "site"}, headers=officer_headers)
    assert again.status_code == 200 and again.get_json()["url"] is None and again.get_json()["kind"] == "site"
    assert client.delete(f"{BASE}/{name}", headers=officer_headers).get_json()["deleted"] is True


def test_a_deployed_app_cannot_become_linked(client, officer_headers, name):
    assert client.put(f"{BASE}/{name}", json={"manifest": MANIFEST}, headers=officer_headers).status_code == 200
    refused = client.put(f"{BASE}/{name}/link", json={"url": "https://x.example.org"}, headers=officer_headers)
    assert refused.status_code == 409


@pytest.mark.parametrize(
    "body",
    [
        {"url": "http://plain.example.org"},
        {"url": "https://x.example.org", "kind": "rocket"},
        {"description": "x" * 201},
        {"runs_as": "vaultwarden"},
        {"runs_as": ["x" * 101]},
    ],
)
def test_link_checks_its_fields(client, officer_headers, name, body):
    assert client.put(f"{BASE}/{name}/link", json=body, headers=officer_headers).status_code == 400


def test_linked_apps_count_against_no_limit(client, officer_headers, name):
    from core import limits
    from core.db import db_connect
    from modules.organizations.models import Organization

    db = db_connect.SessionLocal()
    try:
        soda = db.query(Organization.id).filter_by(prefix="soda").scalar()
        before = limits.used(db, soda, "runpod.apps")
    finally:
        db.close()
    client.put(f"{BASE}/{name}/link", json={"url": "https://site.example.org"}, headers=officer_headers)
    db = db_connect.SessionLocal()
    try:
        assert limits.used(db, soda, "runpod.apps") == before
    finally:
        db.close()


def test_link_tool_and_cli(client, app, officer_headers, name):
    from core.db import db_connect
    from modules.organizations.models import Organization

    db = db_connect.SessionLocal()
    try:
        soda = db.query(Organization.id).filter_by(prefix="soda").scalar()
    finally:
        db.close()
    made = client.post(
        f"/api/organizations/{soda}/tokens",
        json={"name": "linker", "kind": "agent", "scopes": ["apps:manage"]},
        headers=officer_headers,
    )
    headers = {"Authorization": f"Bearer {made.get_json()['token']}"}
    called = client.post(
        "/api/tools/apps.link", json={"name": name, "url": "https://wiki.example.org", "kind": "site"}, headers=headers
    )
    assert called.status_code == 200 and called.get_json()["result"]["linked"] is True

    result = app.test_cli_runner().invoke(
        args=["apps", "link", "soda", name, "--url", "https://crm.example.org", "--runs-as", "crm_server,crm_db"]
    )
    assert result.exit_code == 0, result.output
    assert "linked, url=https://crm.example.org, runs as crm_server, crm_db" in result.output
    bad = app.test_cli_runner().invoke(args=["apps", "link", "nope", name])
    assert bad.exit_code != 0 and "No organization" in bad.output
