"""Successful API writes and job runs are recorded in audit_log; reads and refused writes are not."""

import pytest

from tests.contract.conftest import OFFICER_DISCORD_ID
from tests.contract.test_access import SUPERADMIN_ID, headers_for


@pytest.fixture
def entries(app):
    """Read audit rows written during the test."""
    from core.audit import AuditEntry
    from core.db import db_connect

    db = db_connect.SessionLocal()
    start = db.query(AuditEntry.id).order_by(AuditEntry.id.desc()).limit(1).scalar() or 0
    db.close()

    def read():
        session = db_connect.SessionLocal()
        try:
            rows = session.query(AuditEntry).filter(AuditEntry.id > start).order_by(AuditEntry.id).all()
            return [row.to_dict() for row in rows]
        finally:
            session.close()

    return read


@pytest.fixture
def soda_id(client, officer_headers, restore_soda_config):
    orgs = client.get("/api/organizations/", headers=officer_headers).get_json()
    return next(o["id"] for o in orgs if o["prefix"] == "soda")


def test_write_is_recorded(client, officer_headers, soda_id, entries):
    body = {"modules": {"calendar": True}}
    assert client.put(f"/api/organizations/{soda_id}/modules", json=body, headers=officer_headers).status_code == 200
    [entry] = entries()
    assert entry["action"] == "PUT /api/organizations/<int:org_id>/modules"
    assert entry["org"] == "soda"
    assert entry["source"] == "api"
    assert entry["actor_id"] == OFFICER_DISCORD_ID
    assert entry["status"] == 200


def test_reads_and_refused_writes_are_not_recorded(client, officer_headers, soda_id, entries):
    client.get(f"/api/organizations/{soda_id}/modules", headers=officer_headers)
    client.put(f"/api/organizations/{soda_id}/modules", json={"modules": {"nope": True}}, headers=officer_headers)
    assert entries() == []


def test_job_runs_are_recorded(entries):
    from core import jobs

    jobs.job("test.audited")(lambda org_prefix, blob: None)
    try:
        thread = jobs.defer("test.audited", org_prefix="soda", blob="x" * 500)
        assert thread is not None
        thread.join(timeout=5)
    finally:
        jobs.JOBS.pop("test.audited")
    [entry] = entries()
    assert entry["action"] == "job test.audited"
    assert entry["org"] == "soda"
    assert entry["details"] == {"result": "succeeded", "args": {"org_prefix": "soda"}}


def test_org_audit_shows_only_that_org(client, officer_headers, soda_id):
    from core import audit

    audit.record("POST /api/points/<string:org_prefix>/users", source="api", org="ais")
    audit.record("POST /api/points/<string:org_prefix>/users", source="api", org="soda")
    response = client.get(f"/api/organizations/{soda_id}/audit", headers=officer_headers)
    assert response.status_code == 200
    orgs = {e["org"] for e in response.get_json()["entries"]}
    assert orgs == {"soda"}


def test_superadmin_audit_needs_the_superadmin(client, monkeypatch, app):
    from core.config import config
    from modules.auth import access
    from tests.contract.test_access import ScopedBot

    access.clear_cache()
    monkeypatch.setattr(app, "discord_directory", ScopedBot())
    monkeypatch.setattr(config, "SUPERADMIN_USER_ID", SUPERADMIN_ID)
    monkeypatch.setattr(config, "ACCESS_ENFORCE", True)
    try:
        assert client.get("/api/superadmin/audit", headers=headers_for(OFFICER_DISCORD_ID)).status_code == 403
        response = client.get("/api/superadmin/audit?org=ais", headers=headers_for(SUPERADMIN_ID))
        assert response.status_code == 200
        assert all(e["org"] == "ais" for e in response.get_json()["entries"])
    finally:
        access.clear_cache()
