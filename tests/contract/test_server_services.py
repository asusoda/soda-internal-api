"""The services table of the superadmin Server card: the host agent's file, owners from labels, and owners the
superadmin sets. No network."""

import json
import time

import pytest

from .test_access import SUPERADMIN_ID, headers_for

SERVICES = "/api/superadmin/server/services"


def _service(name, **fields):
    return {
        "name": name,
        "kind": "container",
        "state": "running",
        "status": "Up 2 weeks",
        "image": "docker.io/library/nginx:latest",
        "project": None,
        "platform": False,
        "org": None,
        "memory_used": 1_000_000,
        "memory_limit": None,
        "cpu_percent": 0.5,
        "ports": [],
        "domains": [],
    } | fields


@pytest.fixture
def superadmin(monkeypatch):
    from core.config import config

    monkeypatch.setattr(config, "SUPERADMIN_USER_ID", SUPERADMIN_ID)
    return headers_for(SUPERADMIN_ID)


@pytest.fixture
def agent_file(tmp_path, monkeypatch):
    from core import host

    monkeypatch.setattr(host, "DATA_DIR", str(tmp_path))

    def write(services, age=5, version=1):
        data = {"version": version, "generated_at": int(time.time()) - age, "services": services}
        (tmp_path / host.AGENT_FILE).write_text(json.dumps(data))

    return write


@pytest.fixture
def owners(app):
    yield
    from core.db import db_connect
    from modules.superadmin.models import ServiceOwner

    db = db_connect.SessionLocal()
    db.query(ServiceOwner).delete()
    db.commit()
    db.close()


def _by_name(response):
    assert response.status_code == 200, response.get_json()
    return {s["name"]: s for s in response.get_json()["services"]}


def test_no_agent_file_shows_no_services(client, superadmin, agent_file):
    body = client.get(SERVICES, headers=superadmin).get_json()
    assert body == {"agent": None, "services": []}


def test_owners_come_from_labels(client, superadmin, agent_file):
    agent_file(
        [
            _service("soda-internal-api", project="soda-internal-api", platform=True, domains=["api.thesoda.io"]),
            _service("bot-ais", org="ais"),
            _service("bot-gone", org="no-such-org"),
            _service("vaultwarden", kind="container", ports=[8081], domains=["vault.thesoda.io"]),
        ]
    )
    response = client.get(SERVICES, headers=superadmin)
    services = _by_name(response)
    assert response.get_json()["agent"] == {"age_seconds": 5, "stale": False}
    assert services["soda-internal-api"]["owner"] == "platform"
    assert services["bot-ais"]["owner"] == "org" and services["bot-ais"]["org"]["prefix"] == "ais"
    assert services["bot-gone"]["owner"] is None
    assert services["vaultwarden"]["owner"] is None and services["vaultwarden"]["domains"] == ["vault.thesoda.io"]
    assert not any(s["set"] for s in services.values())


def test_an_old_file_is_stale_and_an_unknown_format_is_ignored(client, superadmin, agent_file):
    agent_file([_service("a")], age=600)
    assert client.get(SERVICES, headers=superadmin).get_json()["agent"]["stale"] is True
    agent_file([_service("a")], version=99)
    assert client.get(SERVICES, headers=superadmin).get_json()["agent"] is None


def test_superadmin_sets_and_clears_an_owner(client, superadmin, agent_file, owners):
    agent_file([_service("vaultwarden"), _service("nginx-proxy-manager"), _service("soda-bot", platform=True)])
    soda = client.get("/api/superadmin/limits", headers=superadmin).get_json()["orgs"]
    soda_id = next(o["org"]["id"] for o in soda if o["org"]["prefix"] == "soda")

    put = client.put(f"{SERVICES}/vaultwarden", json={"owner": "org", "organization_id": soda_id}, headers=superadmin)
    assert put.status_code == 200, put.get_json()
    client.put(f"{SERVICES}/nginx-proxy-manager", json={"owner": "infrastructure"}, headers=superadmin)
    client.put(f"{SERVICES}/soda-bot", json={"owner": "infrastructure", "organization_id": soda_id}, headers=superadmin)
    services = _by_name(client.get(SERVICES, headers=superadmin))
    assert services["vaultwarden"]["owner"] == "org" and services["vaultwarden"]["org"]["prefix"] == "soda"
    assert services["vaultwarden"]["set"] is True
    assert services["nginx-proxy-manager"]["owner"] == "infrastructure"
    # A set owner wins over the labels, and only an org owner keeps an org
    assert services["soda-bot"]["owner"] == "infrastructure" and services["soda-bot"]["org"] is None

    assert client.put(f"{SERVICES}/soda-bot", json={"owner": None}, headers=superadmin).status_code == 200
    services = _by_name(client.get(SERVICES, headers=superadmin))
    assert services["soda-bot"]["owner"] == "platform" and services["soda-bot"]["set"] is False


@pytest.mark.parametrize(
    "body",
    [
        None,
        {},
        {"owner": "someone"},
        {"owner": "org"},
        {"owner": "org", "organization_id": 99999},
        {"owner": "org", "organization_id": True},
    ],
)
def test_a_bad_owner_is_refused(client, superadmin, owners, body):
    assert client.put(f"{SERVICES}/vaultwarden", json=body, headers=superadmin).status_code == 400


def test_only_a_superadmin_reads_or_sets_services(client, officer_headers, agent_file):
    agent_file([_service("vaultwarden")])
    assert client.get(SERVICES, headers=officer_headers).status_code == 403
    assert (
        client.put(f"{SERVICES}/vaultwarden", json={"owner": "infrastructure"}, headers=officer_headers).status_code
        == 403
    )
