"""Shared apps: the superadmin deploys an app that the deployment owns on This server, and orgs subscribe to it.
The vault's subscription invites emails through a fake Vaultwarden admin page. The runner runs on a temporary socket
with a fake podman (tests/runner_fake.py). No network."""

import pytest
from cryptography.fernet import Fernet

from core.integrations import server
from modules.runpod import shared
from tests import runner_fake

from .test_access import SUPERADMIN_ID, headers_for

VAULT = {
    "kind": "service",
    "description": "Password manager for every org",
    "url": "https://vault.example.org",
    "image": "docker.io/vaultwarden/server",
    "memory": 256,
    "ports": ["80/http"],
    "publish": {"80": 8082},
    "volumes": [{"host": "/srv/shared/vault", "path": "/data"}],
    "env": {"SIGNUPS_ALLOWED": "false"},
    "secret_env": {"ADMIN_TOKEN": "shared_vault_admin_token"},
    "access": {"kind": "vaultwarden"},
    "health": {"port": 80, "path": "/alive"},
}
ADMIN = "/api/superadmin/shared-apps"


class FakeVault:
    """The Vaultwarden admin page: POST /admin signs in with the token, POST /admin/invite invites an email."""

    def __init__(self):
        self.invited: list[str] = []
        self.token = "admin-token-for-tests"  # nosec B105 - a fake token

    def session(self):
        vault = self

        class Response:
            def __init__(self, status, text=""):
                self.status_code, self.text = status, text

        class Session:
            def __init__(self):
                self.headers: dict = {}
                self.cookies: dict = {}

            def post(self, url, data=None, json=None, **kwargs):
                if url.endswith("/admin"):
                    if data and data.get("token") == vault.token:
                        self.cookies["VW_ADMIN"] = "1"
                        return Response(303)
                    return Response(401)
                assert self.cookies.get("VW_ADMIN"), "invite without the admin cookie"
                email = (json or {})["email"]
                if email in vault.invited:
                    return Response(409, "User already exists")
                vault.invited.append(email)
                return Response(200)

        return Session


@pytest.fixture
def superadmin(monkeypatch):
    from core.config import config

    monkeypatch.setattr(config, "SUPERADMIN_USER_ID", SUPERADMIN_ID)
    monkeypatch.setenv("SECRETS_KEY", Fernet.generate_key().decode())
    return headers_for(SUPERADMIN_ID)


@pytest.fixture
def runner(tmp_path, monkeypatch):
    path = str(tmp_path / "runner.sock")
    monkeypatch.setattr(server, "SOCKET", path)
    fake = runner_fake.start(path, monkeypatch)
    yield fake
    fake.server.shutdown()
    fake.server.server_close()


@pytest.fixture
def vault(monkeypatch):
    fake = FakeVault()
    monkeypatch.setattr(shared.requests, "Session", fake.session())
    return fake


@pytest.fixture
def cleanup(app):
    yield
    from core import secrets
    from core.db import db_connect
    from modules.runpod.models import App, AppDeployment, SharedAppSubscription

    db = db_connect.SessionLocal()
    for row in db.query(App).filter(App.organization_id.is_(None)).all():
        db.query(SharedAppSubscription).filter_by(app_id=row.id).delete()
        db.query(AppDeployment).filter_by(app_id=row.id).delete()
        db.delete(row)
    db.query(secrets.DeploymentSecret).delete()
    db.commit()
    db.close()


def _deploy(client, superadmin, vault):
    assert client.put(f"{ADMIN}/vault", json={"manifest": VAULT}, headers=superadmin).status_code == 200
    saved = client.put(f"{ADMIN}/vault/secrets", json={"secrets": {"ADMIN_TOKEN": vault.token}}, headers=superadmin)
    assert saved.status_code == 200 and saved.get_json() == {"secrets": ["admin_token"]}
    deployed = client.post(f"{ADMIN}/vault/deploy", json={"tag": "1.32.0"}, headers=superadmin)
    assert deployed.status_code == 202, deployed.get_json()


def test_the_superadmin_deploys_a_shared_app_owned_by_no_org(client, superadmin, runner, vault, cleanup):
    _deploy(client, superadmin, vault)
    info = runner.containers["shared-vault"]
    labels = info["Config"]["Labels"]
    assert labels["platform.shared"] == "1" and "platform.org" not in labels
    assert f"ADMIN_TOKEN={vault.token}" in info["Config"]["Env"]
    assert "/srv/shared/vault:/data:rw" in info["Mounts"]

    listed = client.get(ADMIN, headers=superadmin).get_json()["apps"]
    assert [(a["name"], a["provider"], a["current_tag"]) for a in listed] == [("vault", "server", "1.32.0")]
    detail = client.get(f"{ADMIN}/vault", headers=superadmin).get_json()
    assert detail["secrets"] == ["admin_token"] and vault.token not in str(detail)
    assert client.get(f"{ADMIN}/vault/pod", headers=superadmin).get_json()["pod"]["shared"] is True

    deleted = client.delete(f"{ADMIN}/vault", headers=superadmin)
    assert deleted.status_code == 200 and "shared-vault" not in runner.containers


def test_an_org_subscribes_and_its_officers_are_invited(client, superadmin, officer_headers, runner, vault, cleanup):
    _deploy(client, superadmin, vault)
    base = "/api/dashboard/soda/shared-apps"
    listed = client.get(base, headers=officer_headers).get_json()["apps"]
    assert [(a["name"], a["access"], a["subscribed"]) for a in listed] == [("vault", "vaultwarden", False)]

    emails = {"emails": ["Ada@Example.org", "grace@example.org"]}
    subscribed = client.put(f"{base}/vault/subscription", json=emails, headers=officer_headers)
    assert subscribed.status_code == 200, subscribed.get_json()
    assert subscribed.get_json()["results"] == {"ada@example.org": "invited", "grace@example.org": "invited"}
    assert vault.invited == ["ada@example.org", "grace@example.org"]

    again = client.put(f"{base}/vault/subscription", json={"emails": ["ada@example.org"]}, headers=officer_headers)
    assert again.get_json()["results"] == {"ada@example.org": "already has an account"}
    mine = client.get(base, headers=officer_headers).get_json()["apps"][0]
    assert mine["subscribed"] is True and mine["invited"] == ["ada@example.org", "grace@example.org"]

    bad = client.put(f"{base}/vault/subscription", json={"emails": ["not-an-email"]}, headers=officer_headers)
    assert bad.status_code == 400
    assert client.delete(f"{base}/vault/subscription", headers=officer_headers).get_json()["subscribed"] is False


def test_a_wrong_admin_token_is_a_clear_error(client, superadmin, officer_headers, runner, vault, cleanup):
    _deploy(client, superadmin, vault)
    client.put(f"{ADMIN}/vault/secrets", json={"secrets": {"ADMIN_TOKEN": "wrong"}}, headers=superadmin)
    refused = client.put(
        "/api/dashboard/soda/shared-apps/vault/subscription",
        json={"emails": ["a@example.org"]},
        headers=officer_headers,
    )
    assert refused.status_code == 502 and "admin token" in refused.get_json()["error"]


def test_only_the_superadmin_manages_shared_apps_and_orgs_cannot_use_access(client, officer_headers, runner, cleanup):
    assert client.get(ADMIN, headers=officer_headers).status_code == 403
    assert client.put(f"{ADMIN}/vault", json={"manifest": VAULT}, headers=officer_headers).status_code == 403
    own = client.put(
        "/api/dashboard/soda/apps/my-vault", json={"manifest": VAULT, "provider": "server"}, headers=officer_headers
    )
    assert own.status_code == 400 and "only for shared apps" in own.get_json()["error"]
    # A shared app that is not deployed is not offered to orgs
    assert client.get("/api/dashboard/soda/shared-apps", headers=officer_headers).get_json() == {"apps": []}
