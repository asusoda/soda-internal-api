"""The This server provider: apps deployed as capped containers through the runner, the runner's policy, the
This server limits, and the providers that Godfather refuses. The runner runs on a temporary socket with a fake
podman (tests/runner_fake.py). No network."""

import uuid

import pytest

from core.integrations import server
from tests import runner_fake

from .test_runpod_apps import MANIFEST

VAULT = {
    "kind": "service",
    "description": "Password manager",
    "url": "https://vault.example.org",
    "image": "docker.io/vaultwarden/server",
    "memory": 256,
    "ports": ["80/http"],
    "publish": {"80": 8081},
    "volumes": [{"host": "/var/www/vaultwarden/data", "path": "/data"}],
    "env": {"SIGNUPS_ALLOWED": "false"},
    "health": {"port": 80, "path": "/alive"},
}


@pytest.fixture
def runner(tmp_path, monkeypatch):
    path = str(tmp_path / "runner.sock")
    monkeypatch.setattr(server, "SOCKET", path)
    fake = runner_fake.start(path, monkeypatch)
    runner_fake.runner.Handler.policy["data_root"] = str(tmp_path / "apps")
    yield fake
    assert fake.server is not None
    fake.server.shutdown()
    fake.server.server_close()


@pytest.fixture
def apps_cleanup(app):
    names: list[str] = []
    yield names
    from core.db import db_connect
    from modules.runpod.models import App, AppDeployment
    from modules.uptime import service as uptime

    db = db_connect.SessionLocal()
    for app_row in db.query(App).filter(App.name.in_(names)).all():
        db.query(AppDeployment).filter_by(app_id=app_row.id).delete()
        assert app_row.organization_id is not None
        uptime.forget_app(db, app_row.organization_id, str(app_row.name))
        db.delete(app_row)
    db.commit()
    db.close()


def _name(cleanup) -> str:
    name = "srv-" + uuid.uuid4().hex[:8]
    cleanup.append(name)
    return name


def _check_deployments():
    from core.db import db_connect
    from modules.runpod import service

    db = db_connect.SessionLocal()
    try:
        return service.check_deployments(db)
    finally:
        db.close()


def test_this_server_is_a_provider_when_the_runner_is_there(client, officer_headers, runner):
    providers = client.get("/api/dashboard/soda/hosting/providers", headers=officer_headers).get_json()["providers"]
    found = {p["name"]: p for p in providers}
    assert found["server"]["title"] == "This server" and found["server"]["configured"] is True


def test_an_app_deploys_to_a_capped_container_and_becomes_healthy(client, officer_headers, runner, apps_cleanup):
    name = _name(apps_cleanup)
    base = f"/api/dashboard/soda/apps/{name}"
    registered = client.put(base, json={"manifest": VAULT, "provider": "server"}, headers=officer_headers)
    assert registered.status_code == 200, registered.get_json()

    dry = client.post(f"{base}/deploy", json={"tag": "1.32.0", "dry_run": True}, headers=officer_headers)
    body = dry.get_json()["request"]["body"]
    assert body["memory_mb"] == 256 and body["ports"] == [{"container": 80, "host": 8081}]

    deployed = client.post(f"{base}/deploy", json={"tag": "1.32.0"}, headers=officer_headers)
    assert deployed.status_code == 202, deployed.get_json()
    container = f"app-soda-{name}"
    info = runner.containers[container]
    assert info["HostConfig"]["Memory"] == 256 * 1024 * 1024
    assert info["Config"]["Image"] == "docker.io/vaultwarden/server:1.32.0"
    # Published only on localhost and the podman gateway, never on a public address
    assert [b["HostIp"] for b in info["HostConfig"]["PortBindings"]["80/tcp"]] == ["127.0.0.1", "10.88.0.1"]
    assert "/var/www/vaultwarden/data:/data:rw" in info["Mounts"]
    assert info["Config"]["Labels"]["platform.org"] == "soda"

    assert _check_deployments()["healthy"] >= 1
    pod = client.get(f"{base}/pod", headers=officer_headers).get_json()["pod"]
    assert pod["state"] == "running" and pod["memory_mb"] == 256

    deleted = client.delete(base, headers=officer_headers).get_json()
    assert deleted["pod_id"] is None and container not in runner.containers


def test_the_runner_refuses_what_its_policy_does_not_allow(client, officer_headers, runner, apps_cleanup):
    base = f"/api/dashboard/soda/apps/{_name(apps_cleanup)}"
    for change, message in [
        ({"volumes": [{"host": "/var/www/soda-internal-api", "path": "/x"}]}, "not allowed"),
        ({"publish": {"80": 8000}}, "host port 8000 is not allowed"),
        ({"image": "quay.io/someone/app"}, "must come from"),
    ]:
        client.put(base, json={"manifest": {**VAULT, **change}, "provider": "server"}, headers=officer_headers)
        refused = client.post(f"{base}/deploy", json={"tag": "1"}, headers=officer_headers)
        assert refused.status_code == 502 and message in refused.get_json()["error"], refused.get_json()
    assert not runner.containers

    # Another org may not use SoDA's host paths or ports
    ais = f"/api/dashboard/ais/apps/{_name(apps_cleanup)}"
    client.put(ais, json={"manifest": VAULT, "provider": "server"}, headers=officer_headers)
    refused = client.post(f"{ais}/deploy", json={"tag": "1"}, headers=officer_headers)
    assert refused.status_code == 502 and "not allowed for ais" in refused.get_json()["error"]


def test_manifest_fields_must_fit_the_provider(client, officer_headers, runner, apps_cleanup):
    base = f"/api/dashboard/soda/apps/{_name(apps_cleanup)}"
    gpu = client.put(
        base, json={"manifest": {**VAULT, "gpu": {"id": "A40"}}, "provider": "server"}, headers=officer_headers
    )
    assert gpu.status_code == 400 and "gpu" in gpu.get_json()["error"]
    no_memory = {k: v for k, v in VAULT.items() if k != "memory"}
    missing = client.put(base, json={"manifest": no_memory, "provider": "server"}, headers=officer_headers)
    assert missing.status_code == 400 and "memory" in missing.get_json()["error"]
    on_runpod = client.put(base, json={"manifest": {**MANIFEST, "memory": 256}}, headers=officer_headers)
    assert on_runpod.status_code == 400 and "This server" in on_runpod.get_json()["error"]


def test_this_server_limits_apps_and_memory(client, officer_headers, runner, apps_cleanup):
    def put(name, memory):
        body = {"manifest": {**VAULT, "memory": memory}, "provider": "server"}
        return client.put(f"/api/dashboard/soda/apps/{name}", json=body, headers=officer_headers)

    assert put(_name(apps_cleanup), 600).status_code == 200
    over = put(_name(apps_cleanup), 600)
    assert over.status_code == 409 and "memory of the apps on this server" in over.get_json()["error"]
    assert put(apps_cleanup[-1], 300).status_code == 200
    third = put(_name(apps_cleanup), 64)
    assert third.status_code == 409 and "apps on this server" in third.get_json()["error"]


def test_godfather_refuses_this_server(client, officer_headers, runner):
    refused = client.post("/api/compute/soda/pods", json={"provider": "server"}, headers=officer_headers)
    assert refused.status_code == 400 and "cannot run Godfather pods" in refused.get_json()["error"]
