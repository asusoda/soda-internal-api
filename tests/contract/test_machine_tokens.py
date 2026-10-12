"""Machine tokens: one org, explicit scopes, hashed at rest, revocable, refused on officer routes."""

import datetime

import pytest
from flask import Flask, g, jsonify


@pytest.fixture
def soda_id(client, officer_headers):
    orgs = client.get("/api/organizations/", headers=officer_headers).get_json()
    return next(o["id"] for o in orgs if o["prefix"] == "soda")


def _issue(client, headers, org_id, **body):
    payload = {"name": "club-agent", "kind": "agent", "scopes": ["calendar:read"], **body}
    return client.post(f"/api/organizations/{org_id}/tokens", json=payload, headers=headers)


def _bearer(token):
    return {"Authorization": f"Bearer {token}"}


def test_issue_list_whoami_revoke(client, officer_headers, soda_id):
    response = _issue(client, officer_headers, soda_id)
    assert response.status_code == 201
    body = response.get_json()
    token = body["token"]
    assert token.startswith("plat_")

    listing = client.get(f"/api/organizations/{soda_id}/tokens", headers=officer_headers).get_json()
    assert token not in str(listing)
    assert any(t["id"] == body["id"] for t in listing["tokens"])
    assert "calendar:read" in listing["scopes"]

    whoami = client.get("/api/auth/machine/whoami", headers=_bearer(token))
    assert whoami.get_json() == {"org": "soda", "name": "club-agent", "kind": "agent", "scopes": ["calendar:read"]}

    assert (
        client.delete(f"/api/organizations/{soda_id}/tokens/{body['id']}", headers=officer_headers).status_code == 200
    )
    assert client.get("/api/auth/machine/whoami", headers=_bearer(token)).status_code == 401


def test_the_list_groups_scopes_and_has_presets(client, officer_headers, soda_id):
    listing = client.get(f"/api/organizations/{soda_id}/tokens", headers=officer_headers).get_json()
    owned = {s for i in listing["integrations"] for s in i["scopes"]}
    grouped = [s for group in listing["groups"] for s in group["scopes"]]
    assert sorted(grouped) == sorted(set(listing["scopes"]) - owned)
    assert listing["groups"][0]["title"] == "Org" and "Other" not in [g["title"] for g in listing["groups"]]
    presets = {p["key"]: set(p["scopes"]) for p in listing["presets"]}
    assert set(presets) == {"read", "write", "all"}
    assert "tokens:manage" in listing["admin"]
    assert not presets["write"] & set(listing["admin"])


def test_only_the_hash_is_stored(client, officer_headers, soda_id):
    from core.db import db_connect
    from modules.auth.models import MachineToken

    token = _issue(client, officer_headers, soda_id).get_json()["token"]
    db = db_connect.SessionLocal()
    try:
        rows = db.query(MachineToken).all()
        assert all(token not in (r.token_hash, r.display) for r in rows)
    finally:
        db.close()


@pytest.mark.parametrize(
    "body",
    [{"scopes": ["nope:write"]}, {"scopes": []}, {"kind": "robot"}, {"name": ""}, {"expires_days": 0}],
)
def test_bad_requests_are_refused(client, officer_headers, soda_id, body):
    assert _issue(client, officer_headers, soda_id, **body).status_code == 400


def test_expired_token_is_refused(client, officer_headers, soda_id):
    from core.db import db_connect
    from modules.auth.models import MachineToken

    body = _issue(client, officer_headers, soda_id, expires_days=1).get_json()
    db = db_connect.SessionLocal()
    try:
        row = db.query(MachineToken).filter_by(id=body["id"]).one()
        row.expires_at = datetime.datetime(2020, 1, 1)
        db.commit()
    finally:
        db.close()
    assert client.get("/api/auth/machine/whoami", headers=_bearer(body["token"])).status_code == 401


def test_machine_token_cannot_use_officer_routes(client, officer_headers, soda_id):
    token = _issue(client, officer_headers, soda_id).get_json()["token"]
    assert client.get("/api/points/soda/users", headers=_bearer(token)).status_code == 401


@pytest.fixture
def scoped_app(app):
    from modules.auth.decorators import machine_scope_required

    probe = Flask("probe")

    @probe.route("/<org_prefix>/events")
    @machine_scope_required("calendar:read")
    def events(org_prefix):
        return jsonify({"token_id": g.machine_caller.token_id})

    return probe.test_client()


def test_scope_and_org_are_enforced(client, officer_headers, soda_id, scoped_app):
    calendar = _issue(client, officer_headers, soda_id).get_json()["token"]
    org_only = _issue(client, officer_headers, soda_id, scopes=["org:read"]).get_json()["token"]
    assert scoped_app.get("/soda/events", headers=_bearer(calendar)).status_code == 200
    assert scoped_app.get("/ais/events", headers=_bearer(calendar)).status_code == 403
    assert scoped_app.get("/soda/events", headers=_bearer(org_only)).status_code == 403
    assert scoped_app.get("/soda/events").status_code == 401
