"""Controls of a running app (start, stop, restart, logs) for its org, the runner's command, working folder and
group network, and the superadmin's controls of the server's services. The runner runs on a temporary socket with
a fake podman (tests/runner_fake.py). No network."""

import json
import time
import uuid

import pytest

from core import host
from core.integrations import server
from tests import runner_fake

from .test_access import SUPERADMIN_ID, headers_for
from .test_server_hosting import VAULT

CRM_DB = {
    "kind": "service",
    "image": "docker.io/library/postgres",
    "memory": 128,
    "group": "crm",
    "alias": "db",
    "command": ["postgres", "-c", "max_connections=50"],
    "workdir": "/var/lib/postgresql",
    "health": {"port": 5432, "path": "/"},
}


@pytest.fixture
def runner(tmp_path, monkeypatch):
    path = str(tmp_path / "runner.sock")
    monkeypatch.setattr(server, "SOCKET", path)
    fake = runner_fake.start(path, monkeypatch)
    runner_fake.runner.Handler.policy["data_root"] = str(tmp_path / "apps")
    yield fake
    fake.server.shutdown()
    fake.server.server_close()


@pytest.fixture
def apps(app):
    names: list[str] = []
    yield names
    from core.db import db_connect
    from modules.runpod.models import App, AppDeployment
    from modules.uptime import service as uptime

    db = db_connect.SessionLocal()
    for row in db.query(App).filter(App.name.in_(names)).all():
        db.query(AppDeployment).filter_by(app_id=row.id).delete()
        uptime.forget_app(db, int(row.organization_id), str(row.name))
        db.delete(row)
    db.commit()
    db.close()


def _deployed(client, officer_headers, apps, manifest) -> str:
    name = "ctl-" + uuid.uuid4().hex[:8]
    apps.append(name)
    base = f"/api/dashboard/soda/apps/{name}"
    assert (
        client.put(base, json={"manifest": manifest, "provider": "server"}, headers=officer_headers).status_code == 200
    )
    deployed = client.post(f"{base}/deploy", json={"tag": "1"}, headers=officer_headers)
    assert deployed.status_code == 202, deployed.get_json()
    return name


def test_an_org_starts_stops_restarts_and_reads_logs(client, officer_headers, runner, apps):
    name = _deployed(client, officer_headers, apps, VAULT)
    base = f"/api/dashboard/soda/apps/{name}"
    stopped = client.post(f"{base}/action", json={"action": "stop"}, headers=officer_headers)
    assert stopped.status_code == 200 and stopped.get_json()["pod"]["state"] == "exited"
    restarted = client.post(f"{base}/action", json={"action": "restart"}, headers=officer_headers)
    assert restarted.get_json()["pod"]["state"] == "running"
    assert ("restart", f"app-soda-{name}") in runner.calls
    logs = client.get(f"{base}/logs?lines=50", headers=officer_headers).get_json()["logs"]
    assert f"app-soda-{name}" in logs and ("logs", "--tail", "50", f"app-soda-{name}") in [c[1:] for c in runner.calls]
    assert client.post(f"{base}/action", json={"action": "delete"}, headers=officer_headers).status_code == 400


def test_an_app_that_is_not_deployed_has_no_controls(client, officer_headers, runner, apps):
    name = "ctl-" + uuid.uuid4().hex[:8]
    apps.append(name)
    base = f"/api/dashboard/soda/apps/{name}"
    client.put(base, json={"manifest": VAULT, "provider": "server"}, headers=officer_headers)
    assert client.post(f"{base}/action", json={"action": "start"}, headers=officer_headers).status_code == 409
    assert client.get(f"{base}/logs", headers=officer_headers).status_code == 409


def test_the_parts_of_an_app_share_a_group_network(client, officer_headers, runner, apps):
    name = _deployed(client, officer_headers, apps, CRM_DB)
    info = runner.containers[f"app-soda-{name}"]
    assert info["Extra"]["--network"] == "platform-soda-crm" and info["Extra"]["--network-alias"] == "db"
    assert info["Extra"]["--workdir"] == "/var/lib/postgresql"
    assert info["Config"]["Image"] == "docker.io/library/postgres:1"
    assert info["Config"]["Cmd"] == ["postgres", "-c", "max_connections=50"]
    assert info["Config"]["Labels"]["platform.group"] == "crm"


@pytest.fixture
def superadmin(monkeypatch, tmp_path):
    from core.config import config

    monkeypatch.setattr(config, "SUPERADMIN_USER_ID", SUPERADMIN_ID)
    monkeypatch.setattr(host, "DATA_DIR", str(tmp_path))
    services = [
        {"name": "twenty_db_1", "kind": "container", "status": "Up"},
        {"name": "nginx-proxy-manager", "kind": "container", "status": "Up"},
        {"name": "react-website", "kind": "process", "status": "systemd react-website.service"},
        {"name": "pid 42", "kind": "process", "status": "not in a systemd unit"},
    ]
    (tmp_path / host.AGENT_FILE).write_text(
        json.dumps({"version": 1, "generated_at": int(time.time()), "services": services})
    )
    return headers_for(SUPERADMIN_ID)


def test_the_superadmin_controls_only_the_services_the_policy_lists(client, superadmin, runner, monkeypatch):
    runner.containers["twenty_db_1"] = {"Name": "twenty_db_1", "Config": {"Labels": {}}, "State": {"Status": "running"}}
    base = "/api/superadmin/server/services"
    restarted = client.post(f"{base}/twenty_db_1/action", json={"action": "restart"}, headers=superadmin)
    assert restarted.status_code == 200 and ("restart", "twenty_db_1") in runner.calls
    assert "twenty_db_1" in client.get(f"{base}/twenty_db_1/logs", headers=superadmin).get_json()["logs"]

    refused = client.post(f"{base}/nginx-proxy-manager/action", json={"action": "stop"}, headers=superadmin)
    assert refused.status_code == 403 and "host_control" in refused.get_json()["error"]
    no_unit = client.post(f"{base}/pid 42/action", json={"action": "restart"}, headers=superadmin)
    assert no_unit.status_code == 409
    assert client.post(f"{base}/unknown/action", json={"action": "restart"}, headers=superadmin).status_code == 404

    ran = []
    monkeypatch.setattr(runner_fake.runner.subprocess, "run", lambda args, **kw: ran.append(args))
    unit = client.post(f"{base}/react-website/action", json={"action": "restart"}, headers=superadmin)
    assert unit.status_code == 200 and ran[0][-2:] == ["restart", "react-website.service"]


def test_officers_cannot_control_server_services(client, officer_headers, runner):
    refused = client.post(
        "/api/superadmin/server/services/twenty_db_1/action", json={"action": "stop"}, headers=officer_headers
    )
    assert refused.status_code == 403
