"""Hosting providers: the provider list, and pods and apps that run on the provider they name."""

import uuid

import pytest
from cryptography.fernet import Fernet

from core import hosting
from core.integrations.runpod import RunPodProvider

from .test_godfather import FakeRunPod
from .test_runpod_apps import MANIFEST


class FakeProvider(RunPodProvider):
    """A second provider that keeps its pods in memory, configured for every org. It builds RunPod requests."""

    name = "fakecloud"
    title = "Fake Cloud"
    integration = "fakecloud"

    def __init__(self):
        self.pods = FakeRunPod()
        self.checked: list[str] = []

    def configured(self, db, org_id):
        return True

    def client(self, db, org_id):
        return self.pods

    def status(self, pod):
        return "GONE" if pod is None else str(pod.get("status"))

    def machine(self, pod):
        return {"gpuTypeId": "fake-gpu"} if pod else None

    def ssh_address(self, pod):
        return ("198.51.100.7", 2222)

    def proxy_url(self, pod_id, port, path):
        return f"https://{pod_id}.fakecloud.example:{port}{path}"

    def healthy(self, pod_id, port, path):
        self.checked.append(self.proxy_url(pod_id, port, path))
        return True


@pytest.fixture
def fakecloud(app, monkeypatch):
    from core.db import db_connect
    from modules.godfather.models import ComputeKey, ComputePod

    monkeypatch.setenv("SECRETS_KEY", Fernet.generate_key().decode())
    provider = FakeProvider()
    monkeypatch.setitem(hosting.PROVIDERS, provider.name, provider)
    yield provider
    db = db_connect.SessionLocal()
    db.query(ComputePod).delete()
    db.query(ComputeKey).delete()
    db.commit()
    db.close()


@pytest.fixture
def runpod_key(app):
    from core import secrets
    from core.db import db_connect
    from modules.organizations.models import Organization

    db = db_connect.SessionLocal()
    org_id = db.query(Organization.id).filter_by(prefix="soda").scalar()
    db.close()

    def set_key(value):
        db = db_connect.SessionLocal()
        if value is None:
            secrets.delete_secret(db, org_id, "runpod_api_key")
        else:
            secrets.set_secret(db, org_id, "runpod_api_key", value)
        db.commit()
        db.close()

    yield set_key
    set_key(None)


def test_providers_say_whether_the_org_configured_them(client, officer_headers, runpod_key, monkeypatch):
    monkeypatch.setenv("SECRETS_KEY", Fernet.generate_key().decode())
    url = "/api/dashboard/soda/hosting/providers"
    before = client.get(url, headers=officer_headers).get_json()["providers"]
    assert {"name": "runpod", "title": "RunPod", "integration": "runpod", "configured": False} in before
    runpod_key("rp-test")
    after = client.get(url, headers=officer_headers).get_json()["providers"]
    assert next(p for p in after if p["name"] == "runpod")["configured"] is True


def test_a_pod_runs_on_the_provider_it_names(client, officer_headers, fakecloud):
    created = client.post(
        "/api/compute/soda/pods", json={"name": "lab", "provider": "fakecloud"}, headers=officer_headers
    )
    assert created.status_code == 201, created.get_json()
    pod = created.get_json()["pod"]
    assert (pod["id"], pod["provider"], pod["machine"]) == ("pod1", "fakecloud", {"gpuTypeId": "fake-gpu"})
    assert fakecloud.pods.calls[0][0] == "create"

    listed = client.get("/api/compute/soda/pods", headers=officer_headers).get_json()["pods"]
    assert [(p["id"], p["provider"], p["status"]) for p in listed] == [("pod1", "fakecloud", "RUNNING")]
    client.post("/api/compute/soda/pods/pod1/action", json={"action": "stop"}, headers=officer_headers)
    assert fakecloud.pods.calls[-1] == ("stop", "pod1")

    unknown = client.post("/api/compute/soda/pods", json={"provider": "nope"}, headers=officer_headers)
    assert unknown.status_code == 400 and "provider must be one of" in unknown.get_json()["error"]


def test_an_app_runs_on_the_provider_it_names(client, officer_headers, fakecloud):
    from modules.runpod import service as apps

    name = "app-" + uuid.uuid4().hex[:8]
    base = f"/api/dashboard/ais/apps/{name}"
    registered = client.put(base, json={"manifest": MANIFEST, "provider": "fakecloud"}, headers=officer_headers)
    assert registered.status_code == 200
    assert (registered.get_json()["provider"], registered.get_json()["host"]) == ("fakecloud", "fakecloud")

    assert client.post(f"{base}/deploy", json={"tag": "v1"}, headers=officer_headers).status_code == 202
    assert fakecloud.pods.calls[-1][0] == "create"
    from core.db import db_connect

    db = db_connect.SessionLocal()
    apps.check_deployments(db)
    db.close()
    assert "https://pod1.fakecloud.example:8080/health" in fakecloud.checked

    moved = client.put(base, json={"manifest": MANIFEST, "provider": "runpod"}, headers=officer_headers)
    assert moved.status_code == 409
    bad = client.put(f"{base}-x", json={"manifest": MANIFEST, "provider": "nope"}, headers=officer_headers)
    assert bad.status_code == 400
    client.delete(base, headers=officer_headers)


def test_existing_rows_default_to_runpod(client, officer_headers, monkeypatch):
    from modules.runpod import service as apps

    from .test_runpod_apps import FakeRunPod as FakeApps

    monkeypatch.setattr(apps, "client_for", lambda db, org_id, provider="runpod": FakeApps())
    name = "app-" + uuid.uuid4().hex[:8]
    base = f"/api/dashboard/ais/apps/{name}"
    body = client.put(base, json={"manifest": MANIFEST}, headers=officer_headers).get_json()
    assert (body["provider"], body["host"]) == ("runpod", "runpod")
    client.delete(base, headers=officer_headers)
