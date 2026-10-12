"""Apps on RunPod: manifests, deploys with a narrow token, health checks, rollback."""

import datetime
import uuid
from typing import Any

import pytest
from cryptography.fernet import Fernet

from core.db import db_connect
from core.integrations import runpod
from modules.runpod import service


class FakeRunPod:
    def __init__(self):
        self.calls = []
        self.fail = False

    def create_pod(self, body):
        self.calls.append(("POST", None, body))
        if self.fail:
            raise runpod.RunPodError("RunPod answered 500", 500)
        return {"id": "pod123"}

    def update_pod(self, pod_id, body):
        self.calls.append(("PATCH", pod_id, body))
        if self.fail:
            raise runpod.RunPodError("RunPod answered 500", 500)
        return {"id": pod_id}

    def get_pod(self, pod_id):
        return {"id": pod_id, "desiredStatus": "RUNNING"}


@pytest.fixture
def fake(monkeypatch):
    client = FakeRunPod()
    monkeypatch.setattr(service, "client_for", lambda db, org_id, provider="runpod": client)
    return client


@pytest.fixture
def healthy(monkeypatch):
    state: dict[str, Any] = {"up": True, "urls": []}

    def check(url):
        state["urls"].append(url)
        return state["up"]

    from core.integrations import runpod

    monkeypatch.setattr(
        runpod.RunPodProvider, "healthy", lambda self, pod_id, port, path: check(runpod.proxy_url(pod_id, port, path))
    )
    return state


def _issue(prefix, *scopes):
    from modules.auth import machine_tokens
    from modules.organizations.models import Organization

    db = db_connect.SessionLocal()
    try:
        org_id = db.query(Organization.id).filter_by(prefix=prefix).scalar()
        value, _ = machine_tokens.issue(db, organization_id=org_id, name="ci", kind="app", scopes=list(scopes))
        return {"Authorization": f"Bearer {value}"}
    finally:
        db.close()


@pytest.fixture
def manager(app):
    return _issue("ais", "apps:read", "apps:manage")


@pytest.fixture
def deployer(app):
    return _issue("ais", "apps:deploy")


MANIFEST = {
    "image": "ghcr.io/example-club/club-bot",
    "gpu": {"id": "NVIDIA RTX A5000", "count": 1},
    "cloud": "SECURE",
    "disk": 50,
    "ports": ["8080/http"],
    "env": {"BOT_MODE": "prod"},
    "health": {"port": 8080, "path": "/health"},
}


def _name():
    return "app-" + uuid.uuid4().hex[:8]


def _register(client, manager, manifest=None):
    name = _name()
    response = client.put(f"/api/apps/{name}", json={"manifest": manifest or MANIFEST}, headers=manager)
    assert response.status_code == 200, response.get_json()
    return name


def _check():
    db = db_connect.SessionLocal()
    try:
        return service.check_deployments(db)
    finally:
        db.close()


def test_first_deploy_creates_pod_then_updates_image(client, manager, deployer, fake, healthy):
    name = _register(client, manager)
    first = client.post(f"/api/apps/{name}/deploy", json={"tag": "v1"}, headers=deployer)
    assert first.status_code == 202, first.get_json()
    method, _, body = fake.calls[-1]
    assert method == "POST" and body["image"] == "ghcr.io/example-club/club-bot:v1"
    assert body["name"] == f"ais-{name}" and body["gpu"]["id"] == "NVIDIA RTX A5000"
    assert body["env"] == {"BOT_MODE": "prod"}

    assert _check()["healthy"] >= 1
    assert "https://pod123-8080.proxy.runpod.net/health" in healthy["urls"]

    digest = "sha256:" + "a" * 64
    client.post(f"/api/apps/{name}/deploy", json={"tag": digest}, headers=deployer)
    method, pod_id, body = fake.calls[-1]
    assert (method, pod_id) == ("PATCH", "pod123")
    assert body["image"] == f"ghcr.io/example-club/club-bot@{digest}"
    assert "gpu" not in body and "name" not in body

    info = client.get(f"/api/apps/{name}", headers=manager).get_json()
    assert info["current_tag"] == digest and info["pod_id"] == "pod123"
    assert (info["kind"], info["description"], info["url"], info["host"]) == ("service", None, None, "runpod")


def test_kind_and_url_are_kept_out_of_the_pod(client, manager, deployer, fake):
    name = _name()
    manifest = {**MANIFEST, "kind": "bot", "description": "Club Discord bot", "url": "https://club.example.org"}
    assert client.put(f"/api/apps/{name}", json={"manifest": manifest}, headers=manager).status_code in (200, 201)
    info = client.get(f"/api/apps/{name}", headers=manager).get_json()
    assert (info["kind"], info["description"], info["url"]) == ("bot", "Club Discord bot", "https://club.example.org")
    client.post(f"/api/apps/{name}/deploy", json={"tag": "v1"}, headers=deployer)
    _, _, body = fake.calls[-1]
    assert not {"kind", "description", "url"} & set(body)


def test_deploy_token_can_only_deploy(client, manager, deployer, fake):
    name = _register(client, manager)
    assert client.put(f"/api/apps/{name}", json={"manifest": MANIFEST}, headers=deployer).status_code == 403
    assert client.get(f"/api/apps/{name}", headers=deployer).status_code == 403
    assert client.post(f"/api/apps/{name}/rollback", headers=deployer).status_code == 403
    assert client.post(f"/api/apps/{name}/deploy", json={"tag": "v1"}, headers=manager).status_code == 403
    soda = _issue("soda", "apps:deploy")
    assert client.post(f"/api/apps/{name}/deploy", json={"tag": "v1"}, headers=soda).status_code == 404


def test_secret_env_comes_from_org_secrets_and_dry_run_redacts(client, manager, deployer, fake, monkeypatch):
    monkeypatch.setenv("SECRETS_KEY", Fernet.generate_key().decode())
    manifest = {**MANIFEST, "secret_env": {"DISCORD_TOKEN": "app_club_bot_discord_token"}}
    name = _register(client, manager, manifest)

    dry = client.post(f"/api/apps/{name}/deploy", json={"tag": "v1", "dry_run": True}, headers=deployer)
    assert dry.status_code == 200
    assert dry.get_json()["request"]["body"]["env"]["DISCORD_TOKEN"] == service.REDACTED
    assert fake.calls == []

    assert client.post(f"/api/apps/{name}/deploy", json={"tag": "v1"}, headers=deployer).status_code == 409

    from core import secrets
    from modules.organizations.models import Organization

    db = db_connect.SessionLocal()
    try:
        org_id = db.query(Organization.id).filter_by(prefix="ais").scalar()
        secrets.set_secret(db, org_id, "app_club_bot_discord_token", "real-token")
    finally:
        db.close()
    assert client.post(f"/api/apps/{name}/deploy", json={"tag": "v1"}, headers=deployer).status_code == 202
    assert fake.calls[-1][2]["env"]["DISCORD_TOKEN"] == "real-token"


def test_failed_health_and_rollback(client, manager, deployer, fake, healthy):
    name = _register(client, manager)
    client.post(f"/api/apps/{name}/deploy", json={"tag": "v1"}, headers=deployer)
    _check()
    healthy["up"] = False
    client.post(f"/api/apps/{name}/deploy", json={"tag": "v2"}, headers=deployer)
    later = datetime.datetime.now(datetime.UTC).replace(tzinfo=None) + service.HEALTH_TIMEOUT
    db = db_connect.SessionLocal()
    try:
        service.check_deployments(db, now=later)
    finally:
        db.close()

    history = client.get(f"/api/apps/{name}/deployments", headers=manager).get_json()["deployments"]
    assert [(d["tag"], d["status"]) for d in history] == [("v2", "failed"), ("v1", "healthy")]

    back = client.post(f"/api/apps/{name}/rollback", headers=manager)
    assert back.status_code == 202, back.get_json()
    assert fake.calls[-1][2]["image"].endswith(":v1")


def test_newer_deploy_replaces_a_running_one(client, manager, deployer, fake, healthy):
    name = _register(client, manager)
    healthy["up"] = False
    client.post(f"/api/apps/{name}/deploy", json={"tag": "v1"}, headers=deployer)
    client.post(f"/api/apps/{name}/deploy", json={"tag": "v2"}, headers=deployer)
    history = client.get(f"/api/apps/{name}/deployments", headers=manager).get_json()["deployments"]
    assert [(d["tag"], d["status"]) for d in history] == [("v2", "deploying"), ("v1", "failed")]


def test_runpod_failure_is_recorded(client, manager, deployer, fake):
    name = _register(client, manager)
    fake.fail = True
    assert client.post(f"/api/apps/{name}/deploy", json={"tag": "v1"}, headers=deployer).status_code == 502
    history = client.get(f"/api/apps/{name}/deployments", headers=manager).get_json()["deployments"]
    assert history[0]["status"] == "failed" and "500" in history[0]["error"]
    assert client.get(f"/api/apps/{name}", headers=manager).get_json()["pod_id"] is None


@pytest.mark.parametrize(
    "manifest",
    [
        {k: v for k, v in MANIFEST.items() if k != "health"},
        {k: v for k, v in MANIFEST.items() if k != "gpu"},
        {**MANIFEST, "cpu": {"id": "cpu5c", "vcpuCount": 4}},
        {**MANIFEST, "image": "ghcr.io/x/y:latest"},
        {**MANIFEST, "ports": ["8080"]},
        {**MANIFEST, "unknown": 1},
        {**MANIFEST, "kind": "game"},
        {**MANIFEST, "url": "http://club.example.org"},
        {**MANIFEST, "description": "x" * 201},
    ],
)
def test_rejects_bad_manifests(client, manager, manifest):
    assert client.put(f"/api/apps/{_name()}", json={"manifest": manifest}, headers=manager).status_code == 400


def test_rejects_bad_tags_and_names(client, manager, deployer, fake):
    name = _register(client, manager)
    for tag in ("", "v1 v2", "../x", None, "-x"):
        assert client.post(f"/api/apps/{name}/deploy", json={"tag": tag}, headers=deployer).status_code == 400
    assert client.put("/api/apps/Bad_Name", json={"manifest": MANIFEST}, headers=manager).status_code == 400


def test_no_runpod_key(client, manager, deployer):
    name = _register(client, manager)
    response = client.post(f"/api/apps/{name}/deploy", json={"tag": "v1"}, headers=deployer)
    assert response.status_code == 503


def test_list_tool_and_delete(client, manager, fake):
    name = _register(client, manager)
    tools = client.post("/api/tools/apps.list", json={}, headers=manager).get_json()["result"]["apps"]
    assert name in [a["name"] for a in tools] and "manifest" not in tools[0]
    assert client.delete(f"/api/apps/{name}", headers=manager).get_json()["deleted"] is True
    assert client.get(f"/api/apps/{name}", headers=manager).status_code == 404


def test_app_secrets_need_the_prefix(monkeypatch):
    from core import secrets

    monkeypatch.setenv("SECRETS_KEY", Fernet.generate_key().decode())
    db = db_connect.SessionLocal()
    try:
        with pytest.raises(secrets.SecretsError):
            secrets.set_secret(db, 1, "anything_else", "x")
        with pytest.raises(secrets.SecretsError):
            secrets.set_secret(db, 1, "app_", "x")
        secrets.set_secret(db, 1, "app_listed", "x")
        listed = {s["name"]: s for s in secrets.list_secrets(db, 1)}
        assert listed["app_listed"]["set"] is True and listed[runpod.SECRET_NAME]["set"] is False
    finally:
        secrets.delete_secret(db, 1, "app_listed")
        db.close()


class _GitHubFile:
    def __init__(self, status, text=""):
        self.status_code = status
        self.text = text
        self.content = text.encode()


@pytest.fixture
def github(monkeypatch):
    """(repo, path, ref) -> YAML text served instead of GitHub. Records each request."""
    files: dict = {}
    seen: list = []

    def get(url, params=None, headers=None, timeout=None):
        prefix = "https://api.github.com/repos/"
        assert url.startswith(prefix)
        repo_and_path = url[len(prefix) :]
        owner, repo, _, path = repo_and_path.split("/", 3)
        ref = (params or {}).get("ref")
        seen.append((f"{owner}/{repo}", path, ref, headers or {}))
        text = files.get((f"{owner}/{repo}", path, ref))
        return _GitHubFile(404) if text is None else _GitHubFile(200, text)

    monkeypatch.setattr(service.requests, "get", get)
    return files, seen


def _yaml(**changes):
    import yaml

    return yaml.safe_dump({**MANIFEST, **changes})


def test_manifest_from_the_repo_at_the_deployed_ref(client, manager, deployer, fake, github):
    files, seen = github
    files[("example-club/club-bot", "platform.app.yaml", None)] = _yaml()
    files[("example-club/club-bot", "platform.app.yaml", "abc123")] = _yaml(env={"BOT_MODE": "canary"})
    name = _name()
    registered = client.put(f"/api/apps/{name}", json={"repo": "example-club/club-bot"}, headers=manager)
    assert registered.status_code == 200, registered.get_json()
    assert registered.get_json()["repo"] == "example-club/club-bot"

    dry = client.post(
        f"/api/apps/{name}/deploy", json={"tag": "v2", "ref": "abc123", "dry_run": True}, headers=deployer
    )
    assert dry.get_json()["manifest"]["env"] == {"BOT_MODE": "canary"} and fake.calls == []

    response = client.post(f"/api/apps/{name}/deploy", json={"tag": "v2", "ref": "abc123"}, headers=deployer)
    assert response.status_code == 202, response.get_json()
    assert fake.calls[-1][2]["env"] == {"BOT_MODE": "canary"}
    assert response.get_json()["deployment"]["manifest_ref"] == "abc123"
    assert client.get(f"/api/apps/{name}", headers=manager).get_json()["manifest"]["env"] == {"BOT_MODE": "canary"}
    assert "Authorization" not in seen[-1][3]


def test_repo_manifest_errors(client, manager, deployer, fake, github):
    files, _ = github
    name = _name()
    missing = client.put(f"/api/apps/{name}", json={"repo": "ais/none"}, headers=manager)
    assert missing.status_code == 422 and "github_token" in missing.get_json()["error"]
    files[("ais/bad", "platform.app.yaml", None)] = "image: [unclosed"
    assert client.put(f"/api/apps/{name}", json={"repo": "ais/bad"}, headers=manager).status_code == 422
    files[("ais/bad", "deploy/app.yaml", None)] = _yaml(image="ghcr.io/x/y:latest")
    body = {"repo": "ais/bad", "manifest_path": "deploy/app.yaml"}
    assert client.put(f"/api/apps/{name}", json=body, headers=manager).status_code == 422
    for body in (
        {"repo": "../x"},
        {"repo": "ais/x", "manifest_path": "../secrets"},
        {"repo": "a/b", "manifest": MANIFEST},
    ):
        assert client.put(f"/api/apps/{name}", json=body, headers=manager).status_code == 400

    files[("ais/ok", "platform.app.yaml", None)] = _yaml()
    client.put(f"/api/apps/{name}", json={"repo": "ais/ok"}, headers=manager)
    assert (
        client.post(f"/api/apps/{name}/deploy", json={"tag": "v1", "ref": "nope"}, headers=deployer).status_code == 422
    )
    assert (
        client.post(f"/api/apps/{name}/deploy", json={"tag": "v1", "ref": "a..b"}, headers=deployer).status_code == 400
    )
    plain = _register(client, manager)
    assert (
        client.post(f"/api/apps/{plain}/deploy", json={"tag": "v1", "ref": "main"}, headers=deployer).status_code == 400
    )


def test_private_repo_uses_the_github_secret_and_rollback_reuses_the_old_manifest(
    client, manager, deployer, fake, github, healthy, monkeypatch
):
    from core import secrets
    from modules.organizations.models import Organization

    monkeypatch.setenv("SECRETS_KEY", Fernet.generate_key().decode())
    files, seen = github
    db = db_connect.SessionLocal()
    try:
        org_id = db.query(Organization.id).filter_by(prefix="ais").scalar()
        secrets.set_secret(db, org_id, service.GITHUB_SECRET, "ghp_test")
    finally:
        db.close()
    try:
        files[("ais/private", "platform.app.yaml", None)] = _yaml()
        files[("ais/private", "platform.app.yaml", "v1")] = _yaml(env={"V": "1"})
        files[("ais/private", "platform.app.yaml", "v2")] = _yaml(env={"V": "2"})
        name = _name()
        client.put(f"/api/apps/{name}", json={"repo": "ais/private"}, headers=manager)
        assert seen[-1][3]["Authorization"] == "Bearer ghp_test"
        client.post(f"/api/apps/{name}/deploy", json={"tag": "v1", "ref": "v1"}, headers=deployer)
        _check()
        client.post(f"/api/apps/{name}/deploy", json={"tag": "v2", "ref": "v2"}, headers=deployer)
        assert fake.calls[-1][2]["env"] == {"V": "2"}
        assert client.post(f"/api/apps/{name}/rollback", headers=manager).status_code == 202
        assert fake.calls[-1][2]["env"] == {"V": "1"} and fake.calls[-1][2]["image"].endswith(":v1")
    finally:
        db = db_connect.SessionLocal()
        try:
            secrets.delete_secret(db, org_id, service.GITHUB_SECRET)
        finally:
            db.close()


def test_deploy_tool_previews_a_dry_run_until_confirmed(client, manager, deployer, fake, healthy):
    name = _register(client, manager)
    pending = client.post("/api/tools/apps.deploy", json={"name": name, "tag": "v1"}, headers=deployer).get_json()
    assert pending["result"]["confirm_required"] is True
    assert pending["result"]["preview"]["request"]["body"]["image"].endswith(":v1")
    assert fake.calls == []

    done = client.post("/api/tools/apps.deploy", json={"name": name, "tag": "v1", "confirm": True}, headers=deployer)
    assert done.status_code == 200, done.get_json()
    assert fake.calls[-1][0] == "POST"
    app = client.post("/api/tools/apps.get", json={"name": name}, headers=manager).get_json()["result"]
    assert app["deployments"][0]["tag"] == "v1"


def _monitors(name):
    from modules.uptime.models import UptimeMonitor

    db = db_connect.SessionLocal()
    try:
        return [(m.name, m.target_kind) for m in db.query(UptimeMonitor).filter_by(target=name).all()]
    finally:
        db.close()


def test_uptime_watches_a_new_app_and_forgets_a_deleted_one(client, manager):
    name = _register(client, manager)
    assert _monitors(name) == [(name, "app")]
    again = client.put(f"/api/apps/{name}", json={"manifest": MANIFEST}, headers=manager)
    assert again.status_code == 200
    assert len(_monitors(name)) == 1
    deleted = client.delete(f"/api/apps/{name}", headers=manager)
    assert deleted.get_json()["deleted"] is True
    assert _monitors(name) == []
