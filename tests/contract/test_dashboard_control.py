"""Officer control of apps and knowledge from the dashboard. No network."""

import uuid

import pytest

from modules.runpod import service as apps

from .test_runpod_apps import MANIFEST, FakeRunPod


@pytest.fixture
def fake(monkeypatch):
    client = FakeRunPod()
    monkeypatch.setattr(apps, "client_for", lambda db, org_id, provider="runpod": client)
    return client


@pytest.fixture
def queued(monkeypatch):
    import core.jobs

    calls = []
    monkeypatch.setattr(core.jobs, "defer", lambda name, **kwargs: calls.append((name, kwargs)))
    return calls


def test_officer_registers_deploys_and_deletes_an_app(client, officer_headers, fake):
    name = "app-" + uuid.uuid4().hex[:8]
    base = f"/api/dashboard/ais/apps/{name}"
    assert client.put(base, json={"manifest": MANIFEST}, headers=officer_headers).status_code == 200

    dry = client.post(f"{base}/deploy", json={"tag": "v1", "dry_run": True}, headers=officer_headers)
    assert dry.status_code == 200 and dry.get_json()["request"]["method"] == "POST" and dry.get_json()["tag"] == "v1"
    assert fake.calls == []

    deployed = client.post(f"{base}/deploy", json={"tag": "v1"}, headers=officer_headers)
    assert deployed.status_code == 202
    assert deployed.get_json()["deployment"]["actor"].startswith("officer:")

    detail = client.get(base, headers=officer_headers).get_json()
    assert detail["current_tag"] == "v1" and [d["tag"] for d in detail["deployments"]] == ["v1"]
    assert client.get(f"{base}/pod", headers=officer_headers).get_json()["pod"]["desiredStatus"] == "RUNNING"
    assert name in [
        a["name"] for a in client.get("/api/dashboard/ais/apps", headers=officer_headers).get_json()["apps"]
    ]

    assert client.post(f"{base}/rollback", json={}, headers=officer_headers).status_code == 409
    assert client.delete(base, headers=officer_headers).get_json()["deleted"] is True
    assert client.get(base, headers=officer_headers).status_code == 404


def test_officer_manages_crawls(client, officer_headers, queued):
    key = "site-" + uuid.uuid4().hex[:8]
    base = "/api/dashboard/ais/knowledge"
    body = {"url": "https://example.edu/about", "category": "club", "fetch_every_hours": 12}
    scheduled = client.put(f"{base}/crawls/{key}", json=body, headers=officer_headers)
    assert scheduled.status_code == 200 and scheduled.get_json()["crawl"]["fetch_every_hours"] == 12

    listed = client.get(f"{base}/sources", headers=officer_headers).get_json()
    assert key in [s["key"] for s in listed["sources"]] and listed["can_publish"] is False

    assert client.post(f"{base}/crawls/{key}/run", json={"force": True}, headers=officer_headers).status_code == 202
    assert queued == [
        ("knowledge.crawl_source", {"org_id": queued[0][1]["org_id"], "key": key, "force": True, "org_prefix": "ais"})
    ]
    assert client.post(f"{base}/crawls/nope/run", json={}, headers=officer_headers).status_code == 404

    found = client.post(f"{base}/search", json={"query": "about"}, headers=officer_headers)
    assert found.status_code == 200

    assert client.delete(f"{base}/sources/{key}", headers=officer_headers).get_json() == {"deleted": True}
    assert client.delete(f"{base}/sources/{key}", headers=officer_headers).status_code == 404


def test_officer_subscribes_to_a_submodule(client, officer_headers, queued, clean_submodules):
    from submodules.asu.sources import SOURCES

    base = "/api/dashboard/ais"

    def _asu():
        listed = client.get(f"{base}/submodules", headers=officer_headers).get_json()["submodules"]
        return next(p for p in listed if p["name"] == "asu")

    asu = _asu()
    assert (asu["key_prefix"], asu["sources"], asu["subscribed"]) == ("asu/", 0, False)
    assert "knowledge" in asu["modules"]

    first = client.put(f"{base}/submodules/asu/subscription", headers=officer_headers)
    assert first.status_code == 200 and first.get_json()["added"] == len(SOURCES)
    assert first.get_json()["subscribed"] is True
    assert queued[-1] == ("knowledge.crawl_due", {})
    asu = _asu()
    assert (asu["sources"], asu["subscribed"], asu["subscribers"]) == (len(SOURCES), True, 1)
    # The older sync route subscribes too, and adds nothing the second time
    again = client.post(f"{base}/knowledge/submodules/asu/sync", headers=officer_headers)
    assert again.get_json()["added"] == 0
    assert client.put(f"{base}/submodules/nope/subscription", headers=officer_headers).status_code == 404
    # The pages are the submodule's, not the org's
    keys = [s["key"] for s in client.get(f"{base}/knowledge/sources", headers=officer_headers).get_json()["sources"]]
    assert not [k for k in keys if k.startswith("asu/")]

    assert client.delete(f"{base}/submodules/asu/subscription", headers=officer_headers).get_json() == {
        "subscribed": False
    }
    asu = _asu()
    assert (asu["subscribed"], asu["subscribers"], asu["sources"]) == (False, 0, len(SOURCES))


def test_control_routes_need_an_officer(client):
    assert client.get("/api/dashboard/ais/apps").status_code == 401
    assert client.put("/api/dashboard/ais/knowledge/crawls/x", json={}).status_code == 401
    assert client.post("/api/dashboard/ais/knowledge/submodules/asu/sync").status_code == 401
