"""Per-org limits: the values, count and rate checks, the modules that use them, the superadmin and officer routes,
the MCP tool, one heavy job per org, the fair crawl batch, the server page and the request size cap. No network."""

import datetime
import threading
import uuid
from typing import cast

import pytest

from core import limits

from .test_access import SUPERADMIN_ID, headers_for

UPTIME = "/api/uptime/soda/monitors"
NOW = datetime.datetime(2026, 10, 11, 12, 30)


def _org_id(prefix: str) -> int:
    from core.db import db_connect
    from modules.organizations.models import Organization

    db = db_connect.SessionLocal()
    try:
        return cast(int, db.query(Organization.id).filter_by(prefix=prefix).scalar())
    finally:
        db.close()


@pytest.fixture
def db(app):
    from core.db import db_connect

    session = db_connect.SessionLocal()
    yield session
    session.close()


@pytest.fixture
def clean_limits(app):
    """Removes every override and counter after the test."""
    yield
    from core.db import db_connect

    db = db_connect.SessionLocal()
    db.query(limits.OrgLimit).delete()
    db.query(limits.UsageCounter).delete()
    db.commit()
    db.close()


@pytest.fixture
def superadmin(monkeypatch):
    from core.config import config

    monkeypatch.setattr(config, "SUPERADMIN_USER_ID", SUPERADMIN_ID)
    return headers_for(SUPERADMIN_ID)


@pytest.fixture
def monitors(app):
    yield
    from core.db import db_connect
    from modules.uptime.models import UptimeMonitor

    db = db_connect.SessionLocal()
    db.query(UptimeMonitor).delete()
    db.commit()
    db.close()


def test_value_comes_from_override_then_env_then_default(db, clean_limits, monkeypatch):
    soda = _org_id("soda")
    assert limits.value(db, soda, "uptime.monitors") == 50
    monkeypatch.setenv("LIMIT_UPTIME_MONITORS", "7")
    assert limits.value(db, soda, "uptime.monitors") == 7
    monkeypatch.setenv("LIMIT_UPTIME_MONITORS", "unlimited")
    assert limits.value(db, soda, "uptime.monitors") is None
    limits.set_values(db, soda, {"uptime.monitors": 3})
    assert limits.value(db, soda, "uptime.monitors") == 3
    limits.set_values(db, soda, {"uptime.monitors": None})
    assert limits.value(db, soda, "uptime.monitors") is None
    limits.set_values(db, soda, {"uptime.monitors": "default"})
    assert limits.value(db, soda, "uptime.monitors") is None  # LIMIT_UPTIME_MONITORS=unlimited again
    assert limits.env_name("knowledge.embeddings_per_day") == "LIMIT_KNOWLEDGE_EMBEDDINGS_PER_DAY"


@pytest.mark.parametrize("bad", [-1, 1.5, True, "ten", 10**13])
def test_set_values_refuses_bad_values(db, clean_limits, bad):
    with pytest.raises(limits.LimitError) as refused:
        limits.set_values(db, _org_id("soda"), {"uptime.monitors": bad})
    assert refused.value.status == 400


def test_unknown_limit_is_404(db, clean_limits):
    with pytest.raises(limits.LimitError) as refused:
        limits.set_values(db, _org_id("soda"), {"nope.things": 1})
    assert refused.value.status == 404


def test_rate_limit_counts_per_window_and_refuses_without_counting(db, clean_limits):
    soda, ais = _org_id("soda"), _org_id("ais")
    limits.set_values(db, soda, {"knowledge.uploads_per_day": 5})
    limits.consume(db, soda, "knowledge.uploads_per_day", 3, now=NOW)
    db.commit()
    with pytest.raises(limits.LimitError) as refused:
        limits.consume(db, soda, "knowledge.uploads_per_day", 3, now=NOW)
    assert refused.value.status == 429 and "5 files a day" in refused.value.message
    db.rollback()
    assert limits.used(db, soda, "knowledge.uploads_per_day", now=NOW) == 3
    limits.consume(db, soda, "knowledge.uploads_per_day", 2, now=NOW)
    db.commit()
    assert limits.used(db, soda, "knowledge.uploads_per_day", now=NOW) == 5
    # Another org and the next day have their own counters
    assert limits.used(db, ais, "knowledge.uploads_per_day", now=NOW) == 0
    assert limits.used(db, soda, "knowledge.uploads_per_day", now=NOW + datetime.timedelta(days=1)) == 0


def test_count_limit_refuses_the_next_monitor(client, officer_headers, db, clean_limits, monitors, monkeypatch):
    from core import net

    monkeypatch.setattr(net, "check_public", lambda url: None)
    limits.set_values(db, _org_id("soda"), {"uptime.monitors": 1})
    first = client.post(UPTIME, json={"name": "One", "target": "https://example.org"}, headers=officer_headers)
    assert first.status_code == 201, first.get_json()
    second = client.post(UPTIME, json={"name": "Two", "target": "https://example.org/b"}, headers=officer_headers)
    assert second.status_code == 409
    assert "limit of 1 monitors" in second.get_json()["error"]


def test_knowledge_source_and_passage_limits(client, officer_headers, db, clean_limits):
    from modules.knowledge import service

    ais = _org_id("ais")
    key = "limits-" + uuid.uuid4().hex[:8]
    chunks = [{"ordinal": i, "content": f"passage {i}"} for i in range(3)]
    limits.set_values(db, ais, {"knowledge.sources": service.source_count(db, ais)})
    with pytest.raises(limits.LimitError) as refused:
        service.put_source(db, ais, "ais", key, {"category": "test", "chunks": chunks}, None)
    assert refused.value.status == 409
    db.rollback()

    limits.set_values(
        db, ais, {"knowledge.sources": "default", "knowledge.passages": service.passage_count(db, ais) + 2}
    )
    with pytest.raises(limits.LimitError):
        service.put_source(db, ais, "ais", key, {"category": "test", "chunks": chunks}, None)
    db.rollback()
    limits.set_values(db, ais, {"knowledge.passages": service.passage_count(db, ais) + 3})
    assert service.put_source(db, ais, "ais", key, {"category": "test", "chunks": chunks}, None)["changed"] is True
    assert limits.used(db, ais, "knowledge.passages") == service.passage_count(db, ais)
    service.delete_source(db, ais, key)


def test_embeddings_are_metered_and_search_falls_back_to_text(db, clean_limits, monkeypatch):
    from modules.knowledge import embedder, search
    from modules.knowledge.models import DIMENSIONS

    real = embedder.Embedder(url="http://embed.invalid/v1", model="test-model")
    monkeypatch.setattr(embedder, "configured", lambda: real)
    posted: list[int] = []

    def post(self, batch):
        posted.append(len(batch))
        return [[0.0] * DIMENSIONS for _ in batch]

    monkeypatch.setattr(embedder.Embedder, "_post", post)
    ais = _org_id("ais")
    metered = embedder.for_org(db, ais)
    assert metered is not None
    metered.embed(["a", "b"])
    db.commit()
    assert limits.used(db, ais, embedder.EMBEDDINGS_LIMIT) == 2

    limits.set_values(db, ais, {embedder.EMBEDDINGS_LIMIT: 2})
    result = search.search(db, ais, "anything", embedder=embedder.for_org(db, ais))
    assert result["dense"] is False and posted == [2]


def test_mcp_calls_per_minute(client, officer_headers, db, clean_limits):
    soda = _org_id("soda")
    body = {"name": "limit-agent", "kind": "agent", "scopes": ["org:read"]}
    made = client.post(f"/api/organizations/{soda}/tokens", json=body, headers=officer_headers)
    headers = {"Authorization": f"Bearer {made.get_json()['token']}"}
    limits.set_values(db, soda, {"mcp.calls_per_minute": 2})
    assert client.post("/api/tools/org.info", headers=headers).status_code == 200
    batch = {"calls": [{"tool": "org.info"}, {"tool": "org.settings"}]}
    results = client.post("/api/tools/batch", json=batch, headers=headers).get_json()["result"]["results"]
    assert [r["status"] for r in results] == [200, 429]
    assert client.post("/api/tools/org.info", headers=headers).status_code == 429


def test_org_limits_tool_and_officer_route_show_modules_that_are_on(client, officer_headers, clean_limits):
    soda = _org_id("soda")
    made = client.post(
        f"/api/organizations/{soda}/tokens",
        json={"name": "limit-reader", "kind": "agent", "scopes": ["org:read"]},
        headers=officer_headers,
    )
    headers = {"Authorization": f"Bearer {made.get_json()['token']}"}
    tool = client.post("/api/tools/org.limits", headers=headers).get_json()["result"]["limits"]
    route = client.get(f"/api/organizations/{soda}/limits", headers=officer_headers).get_json()["limits"]
    assert tool == route
    keys = {row["key"] for row in route}
    assert "mcp.calls_per_minute" in keys and all(row["enabled"] for row in route)
    row = next(r for r in route if r["key"] == "uptime.monitors")
    assert row["value"] == 50 and row["override"] is False and row["window"] is None and isinstance(row["used"], int)


def test_superadmin_reads_and_sets_limits(client, superadmin, officer_headers, clean_limits):
    ais = _org_id("ais")
    everything = client.get("/api/superadmin/limits", headers=superadmin).get_json()
    assert {"knowledge.sources", "godfather.pods", "runpod.apps"} <= {c["key"] for c in everything["catalog"]}
    assert {o["org"]["prefix"] for o in everything["orgs"]} >= {"soda", "ais"}

    changed = client.put(
        f"/api/superadmin/limits/{ais}",
        json={"limits": {"godfather.pods": 0, "knowledge.sources": None}},
        headers=superadmin,
    )
    assert changed.status_code == 200, changed.get_json()
    body = changed.get_json()
    by_key = {row["key"]: row for row in body["limits"]}
    assert by_key["godfather.pods"]["value"] == 0 and by_key["godfather.pods"]["override"] is True
    assert by_key["knowledge.sources"]["value"] is None
    assert {o["key"] for o in body["overrides"]} == {"godfather.pods", "knowledge.sources"}
    assert body["overrides"][0]["updated_by"] == f"superadmin:{SUPERADMIN_ID}"

    assert (
        client.put(
            f"/api/superadmin/limits/{ais}", json={"limits": {"godfather.pods": -2}}, headers=superadmin
        ).status_code
        == 400
    )
    assert client.put(f"/api/superadmin/limits/{ais}", json={}, headers=superadmin).status_code == 400
    assert (
        client.put(
            "/api/superadmin/limits/999999", json={"limits": {"godfather.pods": 1}}, headers=superadmin
        ).status_code
        == 404
    )
    assert client.get(f"/api/superadmin/limits/{ais}", headers=superadmin).get_json()["org"]["prefix"] == "ais"
    # An officer reads their own limits but cannot set them
    assert client.get("/api/superadmin/limits", headers=officer_headers).status_code == 403
    assert (
        client.put(
            f"/api/superadmin/limits/{ais}", json={"limits": {"godfather.pods": 9}}, headers=officer_headers
        ).status_code
        == 403
    )


def test_superadmin_server_health(client, superadmin):
    server = client.get("/api/superadmin/server", headers=superadmin)
    assert server.status_code == 200, server.get_json()
    body = server.get_json()
    from core import jobs
    from core.db import db_connect

    assert body["cpus"] >= 1 and body["database"] == db_connect.engine.dialect.name
    assert body["jobs"]["backend"] == jobs.queue_backend()
    assert (body["jobs"]["queue"] is None) == (jobs.queue_backend() == "inline")
    assert set(body["container"]) == {"memory_used", "memory_limit", "cpu_limit", "process_uptime_seconds"}
    assert body["disk"]["total"] >= body["disk"]["used"]


def test_a_heavy_job_runs_once_per_org(app):
    from core import jobs

    release = threading.Event()
    started = threading.Event()

    @jobs.job("test.limits_heavy", once=("org_id",), audit=False)
    def heavy(org_id: int) -> None:
        started.set()
        release.wait(5)

    try:
        thread = jobs.defer("test.limits_heavy", org_id=1)
        assert started.wait(5)
        with pytest.raises(jobs.JobBusy) as busy:
            jobs.defer("test.limits_heavy", org_id=1)
        assert busy.value.status == 409
        other = jobs.defer("test.limits_heavy", org_id=2)  # another org is not blocked
        release.set()
        for t in (thread, other):
            assert t is not None
            t.join(5)
        again = jobs.defer("test.limits_heavy", org_id=1)
        assert again is not None
        again.join(5)
    finally:
        release.set()
        jobs.JOBS.pop("test.limits_heavy", None)


def test_crawl_batch_is_fair_and_skips_orgs(db):
    from modules.knowledge import crawl
    from modules.knowledge.models import KnowledgeSource

    soda, ais = _org_id("soda"), _org_id("ais")
    tag = "fair-" + uuid.uuid4().hex[:6]
    old = datetime.datetime(2000, 1, 1)
    rows = [
        KnowledgeSource(
            organization_id=org,
            key=f"{tag}-{org}-{i}",
            url="https://example.invalid/",
            category="x",
            fetch_every_hours=1,
            last_attempt_at=old + datetime.timedelta(minutes=i),
        )
        for org, count in ((soda, 6), (ais, 2))
        for i in range(count)
    ]
    db.add_all(rows)
    db.commit()
    try:
        others = {
            cast(int, s.organization_id)
            for s in db.query(KnowledgeSource).filter(~KnowledgeSource.key.like(f"{tag}%")).all()
        } - {soda, ais}
        batch = [s for s in crawl.due(db, limit=4, skip=others) if str(s.key).startswith(tag)]
        assert [s.organization_id for s in batch][:4].count(ais) == 2
        alone = crawl.due(db, limit=50, skip=others | {soda})
        assert all(s.organization_id != soda for s in alone)
    finally:
        db.query(KnowledgeSource).filter(KnowledgeSource.key.like(f"{tag}%")).delete(synchronize_session=False)
        db.commit()


def test_request_body_cap(client, officer_headers, monkeypatch, app):
    monkeypatch.setitem(app.config, "MAX_CONTENT_LENGTH", 1000)
    big = client.post(UPTIME, data=b"x" * 2000, headers=officer_headers | {"Content-Type": "application/json"})
    assert big.status_code == 413


def test_limits_say_who_pays(client, officer_headers, clean_limits):
    from modules.knowledge.embedder import EMBEDDINGS_LIMIT

    catalog = {entry["key"]: entry for entry in limits.catalog()}
    assert catalog["knowledge.sources"]["paid_by"] == "org"
    assert catalog[EMBEDDINGS_LIMIT]["paid_by"] == "metered" and catalog[EMBEDDINGS_LIMIT]["integrations"] == [
        "embeddings"
    ]
    assert limits.metering("embeddings") == [{"key": EMBEDDINGS_LIMIT, "label": catalog[EMBEDDINGS_LIMIT]["label"]}]
    with pytest.raises(ValueError):
        limits.declare("test.bad", "test", "Bad", 1, window="day", paid_by="shared")

    modules = client.get("/api/dashboard/soda/modules", headers=officer_headers).get_json()["modules"]
    knowledge = next(m for m in modules if m["name"] == "knowledge")
    assert {"key": "knowledge.sources", "label": "Sources", "window": None, "paid_by": "org"} in knowledge["limits"]


def test_submodule_parts_say_who_pays(client, officer_headers):
    listed = client.get("/api/dashboard/soda/submodules", headers=officer_headers).get_json()["submodules"]
    asu = next(s for s in listed if s["name"] == "asu")
    careers = next(s for s in listed if s["name"] == "careers")
    assert {p["kind"]: p["paid_by"] for p in asu["parts"]} == {"pages": "shared", "queries": "org"}
    assert {p["kind"]: p["paid_by"] for p in careers["parts"]} == {"feeds": "org"}
    assert "submodules" not in asu["modules"]


def test_shared_keys_say_which_limits_they_count_against(client, officer_headers, monkeypatch):
    from modules.knowledge.embedder import EMBEDDINGS_LIMIT

    monkeypatch.setenv("EMBEDDINGS_URL", "http://embed.invalid/v1")
    found = client.get("/api/dashboard/soda/integrations", headers=officer_headers).get_json()["integrations"]
    embeddings = next(i for i in found if i["key"] == "embeddings")
    assert embeddings["source"] == "deployment"
    assert [m["key"] for m in embeddings["metered_by"]] == [EMBEDDINGS_LIMIT]
    monkeypatch.delenv("EMBEDDINGS_URL")
    found = client.get("/api/dashboard/soda/integrations", headers=officer_headers).get_json()["integrations"]
    assert next(i for i in found if i["key"] == "embeddings")["metered_by"] == []
