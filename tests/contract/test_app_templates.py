"""App templates: the catalog in apps/, and new apps made from a template. No network."""

import uuid
from pathlib import Path

import pytest
import yaml
from cryptography.fernet import Fernet

from core import secrets
from core.db import db_connect
from modules.runpod import service, templates

from .test_runpod_apps import _issue


@pytest.fixture
def manager(app):
    return _issue("ais", "apps:read", "apps:manage")


@pytest.fixture
def reader(app):
    return _issue("ais", "apps:read")


@pytest.fixture
def secrets_key(monkeypatch):
    monkeypatch.setenv("SECRETS_KEY", Fernet.generate_key().decode())


@pytest.fixture
def cleanup():
    names: list[str] = []
    yield names
    db = db_connect.SessionLocal()
    try:
        org_id = _org_id()
        for name in names:
            if db.query(service.App).filter_by(organization_id=org_id, name=name).first() is not None:
                service.delete_app(db, org_id, name)
            for secret in secrets.list_secrets(db, org_id):
                if secret["name"].startswith(templates._secret_name(name, "")):
                    secrets.delete_secret(db, org_id, secret["name"])
    finally:
        db.close()


def _org_id() -> int:
    from modules.organizations.models import Organization

    db = db_connect.SessionLocal()
    try:
        return int(db.query(Organization.id).filter_by(prefix="ais").scalar())
    finally:
        db.close()


def _name(cleanup):
    name = "tpl-" + uuid.uuid4().hex[:8]
    cleanup.append(name)
    return name


# A template whose image the org builds itself, so the image is an input
OWN_IMAGE = """
template:
  title: Own image
  summary: An app the org builds itself.
  inputs:
    - {kind: image, label: Image}
    - {kind: env, key: API_URL, label: API URL}
    - {kind: secret, key: BOT_TOKEN, label: Bot token}
kind: agent
description: An app from the org's own image
cpu: {id: cpu3c, vcpuCount: 2}
cloud: SECURE
disk: 20
ports: ["8080/http"]
health: {port: 8080, path: /health}
"""


@pytest.fixture
def own_image(monkeypatch):
    """The templates in apps/ plus own-image, a template with an image input."""
    real = templates._load()
    extra = {"own-image": templates._check("own-image", yaml.safe_load(OWN_IMAGE))}
    monkeypatch.setattr(templates, "_load", lambda root=templates.ROOT: {**real, **extra})


VAULTWARDEN = {
    "values": {"volume": "vol_abc", "data_center": "US-KS-2"},
    "secrets": {"ADMIN_TOKEN": "admin-value"},
}


def test_every_template_loads_and_lists_its_inputs(client, reader):
    response = client.get("/api/apps/templates", headers=reader)
    assert response.status_code == 200
    listed = {t["name"]: t for t in response.get_json()["templates"]}
    assert "vaultwarden" in listed
    folders = {p.parent.name for p in templates.ROOT.glob(f"*/{templates.FILE}")}
    assert set(listed) == folders
    for name in folders:
        assert (templates.ROOT / name / "README.md").exists(), f"{name} has no README.md"

    vault = listed["vaultwarden"]
    assert vault["tag"] == "1.37.4" and vault["manifest"]["image"] == "ghcr.io/dani-garcia/vaultwarden"
    assert vault["manifest"]["env"]["SIGNUPS_ALLOWED"] == "false" and vault["manifest"]["ports"] == ["80/http"]
    assert {"key": "ADMIN_TOKEN", "kind": "secret", "label": "Admin token", "required": True} in vault["inputs"]
    assert "template" not in vault["manifest"]


def test_a_template_can_take_the_image_as_an_input(client, reader, own_image):
    listed = {t["name"]: t for t in client.get("/api/apps/templates", headers=reader).get_json()["templates"]}
    own = listed["own-image"]
    assert "image" not in own["manifest"] and own["tag"] is None
    assert {i["key"] for i in own["inputs"]} >= {"image", "API_URL", "BOT_TOKEN"}


def test_no_template_uses_docker_hub():
    for template in templates.list_templates():
        image = template["manifest"].get("image")
        assert image is None or image.startswith("ghcr.io/"), template["name"]


def test_create_from_template_saves_secrets_and_registers_inline(client, manager, secrets_key, cleanup):
    name = _name(cleanup)
    response = client.post("/api/apps/templates/vaultwarden", json={"name": name, **VAULTWARDEN}, headers=manager)
    assert response.status_code == 201, response.get_json()
    body = response.get_json()
    assert body["name"] == name and body["template"] == "vaultwarden" and body["suggested_tag"] == "1.37.4"
    assert body["repo"] is None and body["kind"] == "site"
    manifest = body["manifest"]
    secret = f"app_{name.replace('-', '_')}_admin_token"
    assert manifest["secret_env"] == {"ADMIN_TOKEN": secret}
    assert manifest["mounts"] == {"network": [{"path": "/data", "volumeId": "vol_abc"}]}
    assert manifest["dataCenterIds"] == ["US-KS-2"] and "DOMAIN" not in manifest["env"]
    assert "admin-value" not in response.get_data(as_text=True)

    db = db_connect.SessionLocal()
    try:
        assert secrets.get_secret(db, _org_id(), secret) == "admin-value"
    finally:
        db.close()

    dry = client.post(
        f"/api/apps/{name}/deploy", json={"tag": "1.37.4", "dry_run": True}, headers=_issue("ais", "apps:deploy")
    )
    assert dry.status_code == 200
    assert dry.get_json()["request"]["body"]["image"] == "ghcr.io/dani-garcia/vaultwarden:1.37.4"
    assert dry.get_json()["request"]["body"]["env"]["ADMIN_TOKEN"] == service.REDACTED

    again = client.post("/api/apps/templates/vaultwarden", json={"name": name, **VAULTWARDEN}, headers=manager)
    assert again.status_code == 409


def test_create_needs_required_inputs(client, manager, secrets_key, cleanup, own_image):
    name = _name(cleanup)
    no_secret = client.post(
        "/api/apps/templates/vaultwarden", json={"name": name, "values": VAULTWARDEN["values"]}, headers=manager
    )
    assert no_secret.status_code == 400 and "Admin token" in no_secret.get_json()["error"]
    no_image = client.post("/api/apps/templates/own-image", json={"name": name, "values": {}}, headers=manager)
    assert no_image.status_code == 400 and "Image" in no_image.get_json()["error"]
    bad_image = client.post(
        "/api/apps/templates/own-image",
        json={
            "name": name,
            "values": {"image": "Not An Image", "API_URL": "https://example.org/api"},
            "secrets": {"BOT_TOKEN": "x"},
        },
        headers=manager,
    )
    assert bad_image.status_code == 400 and "Invalid manifest" in bad_image.get_json()["error"]
    assert client.post("/api/apps/templates/none", json={"name": name}, headers=manager).status_code == 404
    reserved = client.post(
        "/api/apps/templates/vaultwarden", json={"name": "templates", **VAULTWARDEN}, headers=manager
    )
    assert reserved.status_code == 400
    db = db_connect.SessionLocal()
    try:
        assert db.query(service.App).filter_by(name=name).first() is None
    finally:
        db.close()


def test_create_needs_manage_scope(client, reader):
    response = client.post("/api/apps/templates/vaultwarden", json={"name": "x", **VAULTWARDEN}, headers=reader)
    assert response.status_code == 403


def test_officer_lists_and_creates_from_template(client, officer_headers, secrets_key, cleanup):
    listed = client.get("/api/dashboard/ais/apps/templates", headers=officer_headers)
    assert listed.status_code == 200 and listed.get_json()["templates"]
    name = _name(cleanup)
    created = client.post(
        "/api/dashboard/ais/apps/templates/vaultwarden",
        json={
            "name": name,
            "values": {**VAULTWARDEN["values"], "DOMAIN": "https://vault.example.org"},
            "secrets": VAULTWARDEN["secrets"],
        },
        headers=officer_headers,
    )
    assert created.status_code == 201, created.get_json()
    assert created.get_json()["manifest"]["env"]["DOMAIN"] == "https://vault.example.org"
    assert client.get(f"/api/dashboard/ais/apps/{name}", headers=officer_headers).status_code == 200
    assert client.get("/api/dashboard/ais/apps/templates").status_code == 401


def test_app_name_templates_is_reserved(client, manager):
    from .test_runpod_apps import MANIFEST

    assert client.put("/api/apps/templates", json={"manifest": MANIFEST}, headers=manager).status_code == 400


def test_a_bad_template_file_fails_on_load(tmp_path: Path):
    folder = tmp_path / "broken"
    folder.mkdir()
    (folder / templates.FILE).write_text("template: {title: X, summary: Y, inputs: []}\ncpu: {id: c, vcpuCount: 2}\n")
    with pytest.raises(ValueError, match="broken"):
        templates._load.__wrapped__(tmp_path)
