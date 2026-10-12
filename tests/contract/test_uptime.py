"""Uptime monitors: the officer routes, the checks, the events on a change of state, and the probe. No network."""

import datetime
import json

import pytest
import requests

from core import net

BASE = "/api/uptime/soda/monitors"
HOOK = "https://discord.com/api/webhooks/1234567890/uptime-TOKEN"
NOW = datetime.datetime(2026, 10, 9, 12)


def _soda_id() -> int:
    from core.db import db_connect
    from modules.organizations.models import Organization

    db = db_connect.SessionLocal()
    try:
        return db.query(Organization).filter_by(prefix="soda").one().id
    finally:
        db.close()


@pytest.fixture
def uptime(app, monkeypatch):
    """probe.fetch answers from state["answers"] by URL and records each URL. Removes every monitor after the test."""
    from core import webhooks
    from core.db import db_connect
    from modules.runpod.models import App
    from modules.uptime import probe
    from modules.uptime.models import UptimeCheck, UptimeMonitor

    state: dict = {"answers": {}, "urls": []}

    def fetch(url, timeout):
        state["urls"].append(url)
        return state["answers"].get(url, probe.Result(status_code=200, latency_ms=42))

    monkeypatch.setattr(probe, "fetch", fetch)
    monkeypatch.setattr(net, "check_public", lambda url: None)
    yield state
    db = db_connect.SessionLocal()
    db.query(UptimeCheck).delete()
    db.query(UptimeMonitor).delete()
    db.query(App).filter(App.name.like("uptime-%")).delete(synchronize_session=False)
    db.query(webhooks.Notification).filter(webhooks.Notification.event.like("monitor.%")).delete(
        synchronize_session=False
    )
    db.commit()
    db.close()


def _create(client, headers, **body):
    payload = {"name": "Website", "target": "https://example.org/health", **body}
    return client.post(BASE, json=payload, headers=headers)


def _check_due(now):
    from core.db import db_connect
    from modules.uptime import service

    db = db_connect.SessionLocal()
    try:
        return service.check_due(db, now)
    finally:
        db.close()


def test_monitor_lifecycle(client, officer_headers, uptime):
    created = _create(client, officer_headers)
    assert created.status_code == 201
    monitor = created.get_json()["monitor"]
    assert monitor["target_kind"] == "url"
    assert monitor["expected_status"] == "2xx"
    assert (monitor["timeout_seconds"], monitor["interval_minutes"]) == (10, 5)
    assert monitor["enabled"] is True and monitor["state"] is None
    assert monitor["uptime_24h"] is None and monitor["recent"] == []
    url = f"{BASE}/{monitor['id']}"

    assert _create(client, officer_headers).status_code == 409
    listed = client.get(BASE, headers=officer_headers).get_json()["monitors"]
    assert [m["name"] for m in listed] == ["Website"]

    paused = client.put(url, json={"enabled": False, "interval_minutes": 1}, headers=officer_headers)
    assert paused.status_code == 200
    assert paused.get_json()["monitor"]["enabled"] is False
    assert paused.get_json()["monitor"]["interval_minutes"] == 1

    checked = client.post(f"{url}/check", headers=officer_headers).get_json()
    assert checked["check"]["up"] is True and checked["check"]["status_code"] == 200
    assert checked["monitor"]["state"] == "up"
    assert checked["monitor"]["last_check"]["latency_ms"] == 42

    assert client.delete(url, headers=officer_headers).get_json() == {"deleted": True}
    assert client.get(url, headers=officer_headers).status_code == 404
    assert client.delete(url, headers=officer_headers).status_code == 404
    assert client.get(BASE).status_code == 401


@pytest.mark.parametrize(
    "body",
    [
        {"name": ""},
        {"target": "ftp://example.org"},
        {"target": ""},
        {"target_kind": "pod"},
        {"target_kind": "app", "target": "no-such-app"},
        {"expected_status": "ok"},
        {"expected_status": "600"},
        {"interval_minutes": 0},
        {"interval_minutes": 1441},
        {"timeout_seconds": 31},
        {"timeout_seconds": True},
        {"enabled": "yes"},
    ],
)
def test_bad_monitors_are_refused(client, officer_headers, uptime, body):
    assert _create(client, officer_headers, **body).status_code == 400


def test_private_addresses_are_refused(client, officer_headers, uptime, monkeypatch):
    def private(url):
        raise net.NotPublic("example.org resolves to a non-public address")

    monkeypatch.setattr(net, "check_public", private)
    refused = _create(client, officer_headers)
    assert refused.status_code == 400
    assert "non-public" in refused.get_json()["error"]


def test_state_changes_send_events(client, officer_headers, uptime, sent):
    from core import webhooks
    from core.db import db_connect
    from modules.uptime import probe

    hook = client.post(
        "/api/dashboard/soda/webhooks",
        json={"name": "Uptime", "url": HOOK, "events": ["monitor.down", "monitor.up"]},
        headers=officer_headers,
    )
    assert hook.status_code == 201
    monitor = _create(client, officer_headers, interval_minutes=1).get_json()["monitor"]
    target = monitor["target"]

    assert _check_due(NOW) == {"checked": 1, "down": 0}
    assert sent == []
    # Not due again within the interval
    assert _check_due(NOW + datetime.timedelta(seconds=20)) == {"checked": 0, "down": 0}

    uptime["answers"][target] = probe.Result(status_code=503, latency_ms=80)
    assert _check_due(NOW + datetime.timedelta(minutes=1)) == {"checked": 1, "down": 1}
    assert _check_due(NOW + datetime.timedelta(minutes=2)) == {"checked": 1, "down": 1}
    assert len(sent) == 1
    embed = sent[0][1]["embeds"][0]
    assert embed["title"] == "Monitor Website is down"
    assert {"name": "Error", "value": "Status 503, expected 2xx", "inline": True} in embed["fields"]

    uptime["answers"][target] = probe.Result(error="No answer in 10 seconds")
    _check_due(NOW + datetime.timedelta(minutes=3))
    assert len(sent) == 1
    del uptime["answers"][target]
    _check_due(NOW + datetime.timedelta(minutes=4))
    assert len(sent) == 2
    assert sent[1][1]["embeds"][0]["title"] == "Monitor Website is up"

    db = db_connect.SessionLocal()
    try:
        events = [
            n.event
            for n in db.query(webhooks.Notification)
            .filter_by(organization_id=_soda_id())
            .filter(webhooks.Notification.event.like("monitor.%"))
            .order_by(webhooks.Notification.id)
        ]
    finally:
        db.close()
    assert events == ["monitor.down", "monitor.up"]

    notices = client.get("/api/dashboard/soda/notifications", headers=officer_headers).get_json()["notifications"]
    down = next(n for n in notices if n["subject"] == "Monitor Website is down")
    assert down["module"] == "uptime" and down["link"] == "uptime" and down["level"] == "error"

    listed = client.get(BASE, headers=officer_headers).get_json()["monitors"][0]
    assert listed["state"] == "up"
    assert [c["up"] for c in listed["recent"]] == [True, False, False, False, True]
    assert listed["recent"][1]["status_code"] == 503
    assert listed["recent"][3]["error"] == "No answer in 10 seconds"


def test_uptime_percent_and_prune(client, officer_headers, uptime, monkeypatch):
    from core.db import db_connect
    from modules.uptime import service
    from modules.uptime.models import UptimeCheck

    monitor = _create(client, officer_headers).get_json()["monitor"]
    db = db_connect.SessionLocal()
    try:
        now = service.utcnow()
        rows = [(now - datetime.timedelta(hours=1), True), (now - datetime.timedelta(hours=2), False)]
        rows += [(now - datetime.timedelta(days=3), True), (now - datetime.timedelta(days=3), True)]
        rows += [(now - datetime.timedelta(days=40), False)]
        for at, up in rows:
            db.add(UptimeCheck(monitor_id=monitor["id"], checked_at=at, up=up, status_code=200 if up else 500))
        db.commit()
        found = client.get(f"{BASE}/{monitor['id']}", headers=officer_headers).get_json()["monitor"]
        assert found["uptime_24h"] == 50.0
        assert found["uptime_7d"] == 75.0
        assert len(found["recent"]) == 5
        assert service.prune(db) == 1
        assert db.query(UptimeCheck).filter_by(monitor_id=monitor["id"]).count() == 4
    finally:
        db.close()


def test_app_targets_use_the_health_url(client, officer_headers, uptime):
    from core.db import db_connect
    from modules.runpod.models import App

    manifest = {
        "image": "ghcr.io/club/bot",
        "cpu": {"id": "cpu3c", "vcpuCount": 2},
        "health": {"port": 8080, "path": "/healthz"},
    }
    db = db_connect.SessionLocal()
    try:
        db.add(App(organization_id=_soda_id(), name="uptime-bot", manifest=json.dumps(manifest), pod_id="pod123"))
        site = {**manifest, "url": "https://club.example.org"}
        db.add(App(organization_id=_soda_id(), name="uptime-site", manifest=json.dumps(site)))
        db.commit()
    finally:
        db.close()

    apps = client.get("/api/uptime/soda/targets", headers=officer_headers).get_json()["apps"]
    by_name = {a["name"]: a["url"] for a in apps}
    assert by_name["uptime-bot"] == "https://pod123-8080.proxy.runpod.net/healthz"
    assert by_name["uptime-site"] == "https://club.example.org"

    bot = _create(client, officer_headers, name="Bot", target_kind="app", target="uptime-bot").get_json()["monitor"]
    _create(client, officer_headers, name="Site", target_kind="app", target="uptime-site")
    client.post(f"{BASE}/{bot['id']}/check", headers=officer_headers)
    assert uptime["urls"] == ["https://pod123-8080.proxy.runpod.net/healthz"]


def test_due_monitors_respect_the_switch(client, officer_headers, uptime, restore_soda_config):
    from core.db import db_connect
    from modules.uptime import service

    _create(client, officer_headers)
    paused = _create(client, officer_headers, name="Paused").get_json()["monitor"]
    client.put(f"{BASE}/{paused['id']}", json={"enabled": False}, headers=officer_headers)
    db = db_connect.SessionLocal()
    try:
        assert [m.name for m in service.due(db, NOW)] == ["Website"]
    finally:
        db.close()
    client.put(f"/api/organizations/{_soda_id()}/modules", json={"modules": {"uptime": False}}, headers=officer_headers)
    db = db_connect.SessionLocal()
    try:
        assert service.due(db, NOW) == []
    finally:
        db.close()
    assert client.get(BASE, headers=officer_headers).status_code == 404


def test_uptime_list_tool(client, uptime):
    from core.db import db_connect
    from modules.auth import machine_tokens

    _create_direct()
    db = db_connect.SessionLocal()
    try:
        value, _ = machine_tokens.issue(
            db, organization_id=_soda_id(), name="uptime", kind="agent", scopes=["uptime:read"]
        )
    finally:
        db.close()
    headers = {"Authorization": f"Bearer {value}"}
    result = client.post("/api/tools/uptime.list", json={}, headers=headers).get_json()["result"]
    assert [m["name"] for m in result["monitors"]] == ["Tool site"]
    assert "recent" not in result["monitors"][0]


def _create_direct():
    from core.db import db_connect
    from modules.uptime import service

    db = db_connect.SessionLocal()
    try:
        service.create_monitor(db, _soda_id(), {"name": "Tool site", "target": "https://example.org"})
    finally:
        db.close()


class _Response:
    def __init__(self, status, location=None):
        self.status_code = status
        self.headers = {"location": location} if location else {}
        self.is_redirect = location is not None

    def close(self):
        pass


def test_probe_checks_each_redirect(monkeypatch):
    from modules.uptime import probe

    hops = {
        "https://a.example.org/": _Response(301, "/next"),
        "https://a.example.org/next": _Response(204),
        "https://b.example.org/": _Response(302, "http://10.0.0.5/admin"),
    }
    checked = []

    def check_public(url):
        checked.append(url)
        if "10.0.0.5" in url:
            raise net.NotPublic("10.0.0.5 resolves to a non-public address")

    def get(url, **kwargs):
        assert kwargs["allow_redirects"] is False
        return hops[url]

    monkeypatch.setattr(net, "check_public", check_public)
    monkeypatch.setattr(probe.requests, "get", get)
    result = probe.fetch("https://a.example.org/", 5)
    assert result.status_code == 204 and result.error is None and result.latency_ms is not None
    assert checked == ["https://a.example.org/", "https://a.example.org/next"]

    refused = probe.fetch("https://b.example.org/", 5)
    assert refused.status_code is None and "non-public" in (refused.error or "")

    def slow(url, **kwargs):
        raise requests.Timeout()

    monkeypatch.setattr(probe.requests, "get", slow)
    assert probe.fetch("https://a.example.org/", 5).error == "No answer in 5 seconds"


def test_status_matches():
    from modules.uptime.service import status_matches

    assert status_matches("2xx", 204) and not status_matches("2xx", 301)
    assert status_matches("301", 301) and not status_matches("301", 302)
