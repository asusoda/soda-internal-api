"""Outbound webhooks: the officer routes, the test message, and the fan-out of events to the org's webhooks."""

import uuid

import pytest

from core import net, webhooks

BASE = "/api/dashboard/ais/webhooks"
URL = "https://discord.com/api/webhooks/1234567890/secret-TOKEN"
OTHER_URL = "https://discord.com/api/webhooks/1111111111/other-TOKEN"


def _create(client, headers, name="Ops", events=("errors",), url=URL, **body):
    return client.post(BASE, json={"name": name, "url": url, "events": list(events), **body}, headers=headers)


def _ais_id() -> int:
    from core.db import db_connect
    from modules.organizations.models import Organization

    db = db_connect.SessionLocal()
    try:
        return db.query(Organization).filter_by(prefix="ais").one().id
    finally:
        db.close()


def test_listing_names_events_kinds_and_feeds(client, officer_headers, sent):
    body = client.get(BASE, headers=officer_headers).get_json()
    keys = {e["key"] for e in body["events"]}
    expected = {"errors", "job.failed", "pod.started", "pod.stopped", "app.deployed", "order.created"}
    assert expected | {"member.joined", "knowledge.crawl_failed", "monitor.down", "monitor.up"} <= keys
    assert body["kinds"] == [{"key": "discord", "label": "Discord", "example": "https://discord.com/api/webhooks/..."}]
    assert body["webhooks"] == []
    assert body["feeds"] == []
    assert body["secrets_key"] is True


def test_webhook_lifecycle(client, officer_headers, sent):
    created = _create(client, officer_headers, events=["order.created", "errors"])
    assert created.status_code == 201
    hook = created.get_json()
    assert hook["url_hint"] == "discord.com ...7890"
    assert hook["events"] == ["errors", "order.created"]
    assert hook["enabled"] is True
    listing = client.get(BASE, headers=officer_headers)
    assert "secret-TOKEN" not in listing.get_data(as_text=True)
    assert [w["name"] for w in listing.get_json()["webhooks"]] == ["Ops"]

    assert _create(client, officer_headers).status_code == 409
    changed = client.put(
        f"{BASE}/{hook['id']}", json={"enabled": False, "events": ["job.failed"]}, headers=officer_headers
    )
    assert changed.get_json()["enabled"] is False
    assert changed.get_json()["events"] == ["job.failed"]
    moved = client.put(f"{BASE}/{hook['id']}", json={"url": OTHER_URL}, headers=officer_headers)
    assert moved.get_json()["url_hint"] == "discord.com ...1111"

    assert client.delete(f"{BASE}/{hook['id']}", headers=officer_headers).get_json() == {"deleted": True}
    assert client.delete(f"{BASE}/{hook['id']}", headers=officer_headers).status_code == 404


def test_bad_input_is_refused(client, officer_headers, sent, monkeypatch):
    assert _create(client, officer_headers, url="https://example.com/hook").status_code == 400
    assert _create(client, officer_headers, events=["nope"]).status_code == 400
    assert _create(client, officer_headers, events=[]).status_code == 400
    assert _create(client, officer_headers, name="").status_code == 400
    assert _create(client, officer_headers, kind="smoke").status_code == 400

    def private(url):
        raise net.NotPublic("discord.com resolves to a non-public address")

    monkeypatch.setattr(net, "check_public", private)
    assert _create(client, officer_headers).status_code == 400
    monkeypatch.setattr(net, "check_public", lambda url: None)
    monkeypatch.delenv("SECRETS_KEY")
    refused = _create(client, officer_headers)
    assert refused.status_code == 400
    assert "SECRETS_KEY" in refused.get_json()["error"]


def test_webhooks_of_another_org_are_hidden(client, officer_headers, sent):
    hook = _create(client, officer_headers).get_json()
    other = f"/api/dashboard/soda/webhooks/{hook['id']}"
    assert client.put(other, json={"enabled": False}, headers=officer_headers).status_code == 404
    assert client.post(f"{other}/test", headers=officer_headers).status_code == 404
    assert client.get("/api/dashboard/soda/webhooks", headers=officer_headers).get_json()["webhooks"] == []


def test_send_test(client, officer_headers, sent):
    hook = _create(client, officer_headers, events=["errors", "pod.started"]).get_json()
    result = client.post(f"{BASE}/{hook['id']}/test", headers=officer_headers).get_json()
    assert result["ok"] is True
    url, payload = sent[-1]
    assert url == URL
    assert payload["embeds"][0]["title"] == "Test from AI Society"
    assert "Errors, Pods started" in payload["embeds"][0]["description"]
    assert payload["allowed_mentions"] == {"parse": []}

    sent.status = 404
    failed = client.post(f"{BASE}/{hook['id']}/test", headers=officer_headers).get_json()
    assert failed == {"ok": False, "message": "Discord refused the message with status 404"}
    listed = client.get(BASE, headers=officer_headers).get_json()["webhooks"][0]
    assert listed["last_error"] == failed["message"]
    assert "secret-TOKEN" not in failed["message"]


def test_events_go_only_to_webhooks_that_take_them(client, officer_headers, sent):
    _create(client, officer_headers, name="Store", events=["order.created"])
    _create(client, officer_headers, name="Errors", events=["errors"], url=OTHER_URL)
    off = _create(client, officer_headers, name="Off", events=["order.created"]).get_json()
    client.put(f"{BASE}/{off['id']}", json={"enabled": False}, headers=officer_headers)

    webhooks.emit("ais", "order.created", webhooks.Message(title="New store order #1"))
    assert [url for url, _ in sent] == [URL]
    webhooks.emit(_ais_id(), "errors", webhooks.Message(title="RuntimeError"))
    assert [url for url, _ in sent] == [URL, OTHER_URL]
    webhooks.emit("soda", "order.created", webhooks.Message(title="Another org"))
    webhooks.emit("ais", "undeclared.event", webhooks.Message(title="Nothing"))
    assert len(sent) == 2


def test_alerts_is_core_and_a_destination_that_is_off_gets_nothing(client, officer_headers, sent):
    hook = _create(client, officer_headers, events=["order.created"]).get_json()
    switch = f"/api/organizations/{_ais_id()}/modules"
    assert client.put(switch, json={"modules": {"alerts": False}}, headers=officer_headers).status_code == 400

    client.put(f"{BASE}/{hook['id']}", json={"enabled": False}, headers=officer_headers)
    webhooks.emit("ais", "order.created", webhooks.Message(title="New store order #1"))
    assert sent == []

    client.put(f"{BASE}/{hook['id']}", json={"enabled": True}, headers=officer_headers)
    webhooks.emit("ais", "order.created", webhooks.Message(title="New store order #2"))
    assert [url for url, _ in sent] == [URL]


def test_hourly_limit(client, officer_headers, sent, monkeypatch):
    monkeypatch.setattr(webhooks, "LIMIT_PER_HOUR", 2)
    _create(client, officer_headers, events=["order.created"])
    for i in range(3):
        webhooks.emit("ais", "order.created", webhooks.Message(title=f"Order {i}"))
    assert len(sent) == 2


def test_failed_job_of_an_org_sends_job_failed(client, officer_headers, sent):
    from core import jobs

    _create(client, officer_headers, events=["job.failed"])

    def broken(org_prefix: str) -> None:
        raise RuntimeError("the source is down")

    entry = jobs.Job(name="tests.broken", func=broken, cron=None, retry=0, audit=False)
    with pytest.raises(RuntimeError):
        jobs._execute(entry, {"org_prefix": "ais"})
    embed = sent[-1][1]["embeds"][0]
    assert embed["title"] == "Job tests.broken failed"
    assert embed["description"] == "RuntimeError: the source is down"

    entry = jobs.Job(name="tests.global", func=lambda: broken("x"), cron=None, retry=0, audit=False)
    with pytest.raises(RuntimeError):
        jobs._execute(entry, {})
    assert len(sent) == 1


def test_failed_crawl_sends_knowledge_crawl_failed(client, officer_headers, sent):
    from core.db import db_connect
    from modules.knowledge import runs
    from modules.knowledge.models import KnowledgeRun

    _create(client, officer_headers, events=["knowledge.crawl_failed"])
    key = f"docs-{uuid.uuid4().hex[:8]}"
    db = db_connect.SessionLocal()
    try:
        runs.record(db, _ais_id(), key, "upload", runs.Timer(), error="bad file")
        runs.record(db, _ais_id(), key, "crawl", runs.Timer(), changed=True, chunks=3)
        runs.record(db, _ais_id(), key, "crawl", runs.Timer(), error="404 Not Found")
        db.rollback()
    finally:
        db.query(KnowledgeRun).filter_by(source_key=key).delete()
        db.commit()
        db.close()
    assert len(sent) == 1
    assert sent[0][1]["embeds"][0]["title"] == f"Crawl of {key} failed"


def test_new_member_sends_member_joined(client, officer_headers, sent):
    from core.db import db_connect
    from modules.users import service as users
    from modules.users.models import User, UserOrganizationMembership

    _create(client, officer_headers, events=["member.joined"])
    username = f"wh{uuid.uuid4().hex[:8]}"
    db = db_connect.SessionLocal()
    try:
        user, ok, _ = users.manage_user_in_organization(db, _ais_id(), {"name": "Webhook Tester", "username": username})
        assert ok and user is not None
        users.manage_user_in_organization(db, _ais_id(), {"name": "Webhook Tester", "username": username})
    finally:
        found = db.query(User).filter_by(username=username).first()
        if found is not None:
            db.query(UserOrganizationMembership).filter_by(user_id=found.id).delete()
            db.delete(found)
        db.commit()
        db.close()
    assert len(sent) == 1
    embed = sent[0][1]["embeds"][0]
    assert embed["title"] == "Webhook Tester joined"
    assert embed["fields"][0]["value"] == username


def test_pod_and_deploy_messages(client, officer_headers, sent):
    from modules.godfather import service as godfather
    from modules.runpod import service as apps
    from modules.runpod.models import App, AppDeployment

    _create(client, officer_headers, events=["pod.started", "pod.stopped", "app.deployed"])
    godfather.announce(_ais_id(), "gpu-1", "pod123", "start", "the session schedule")
    godfather.announce(_ais_id(), "gpu-1", "pod123", "terminate", "an officer or a tool")
    app = App(organization_id=_ais_id(), name="site")
    apps._announce(app, AppDeployment(tag="v2", status="failed", error="The health path did not answer in time"))
    titles = [payload["embeds"][0]["title"] for _, payload in sent]
    assert titles == ["Pod gpu-1 started", "Pod gpu-1 terminated", "App site deploy failed"]


def test_listing_names_alert_feeds(client, officer_headers, sent):
    from core.db import db_connect
    from modules.feeds.models import AlertFeed

    db = db_connect.SessionLocal()
    db.add(AlertFeed(organization_id=_ais_id(), key="webhook-test-feed", kind="hackathons", config={}))
    db.commit()
    try:
        feeds = client.get(BASE, headers=officer_headers).get_json()["feeds"]
        assert feeds[0]["key"] == "webhook-test-feed"
        assert set(feeds[0]) == {"key", "kind", "enabled", "destination_id", "webhook_set", "last_run_at", "last_error"}
    finally:
        db.query(AlertFeed).filter_by(key="webhook-test-feed").delete()
        db.commit()
        db.close()


def test_officers_only(client):
    assert client.get(BASE).status_code in (401, 403)
    assert client.post(BASE, json={}).status_code in (401, 403)
