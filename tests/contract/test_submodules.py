"""Submodules: subscribe to the ASU submodule's shared pages, crawl with its extractors, live queries and their indexing."""

from pathlib import Path

import pytest

from core.db import db_connect
from modules.knowledge import crawl, fetch
from modules.knowledge.models import KnowledgeSource
from modules.submodules import queries, service
from submodules.asu import SUBMODULE
from submodules.asu.sources import SOURCES

QUERIES = {q.key: q for q in SUBMODULE.queries}


def _issue(prefix, *scopes):
    from modules.auth import machine_tokens
    from modules.organizations.models import Organization

    db = db_connect.SessionLocal()
    try:
        org_id = db.query(Organization.id).filter_by(prefix=prefix).scalar()
        value, _ = machine_tokens.issue(db, organization_id=org_id, name="asu", kind="app", scopes=list(scopes))
        return {"Authorization": f"Bearer {value}"}, org_id
    finally:
        db.close()


@pytest.fixture
def writer(app, clean_submodules):
    headers, org_id = _issue("ais", "knowledge:read", "knowledge:write", "submodules:read", "submodules:manage")
    yield headers, org_id
    # Synced sources are due at once and would crowd other tests' crawl batches
    from modules.knowledge.service import delete_source

    db = db_connect.SessionLocal()
    try:
        keys = [
            s.key
            for s in db.query(KnowledgeSource).filter(
                KnowledgeSource.organization_id == org_id,
                KnowledgeSource.key.like("asu/%") | KnowledgeSource.key.like("asu-live/%"),
            )
        ]
        for key in keys:
            delete_source(db, org_id, key)
    finally:
        db.close()


@pytest.fixture
def queued(monkeypatch):
    calls: list = []
    monkeypatch.setattr(service, "defer", lambda name, **kwargs: calls.append((name, kwargs)))
    return calls


@pytest.fixture
def pages(monkeypatch):
    served: dict = {}

    def fake_fetch(url):
        page = served.get(url, fetch.FetchError(f"{url} is not served in this test"))
        if isinstance(page, Exception):
            raise page
        return page

    monkeypatch.setattr(fetch, "fetch", fake_fetch)
    return served


def _sources():
    """The ASU submodule's shared sources: no org, the submodule's id."""
    db = db_connect.SessionLocal()
    try:
        rows = db.query(KnowledgeSource).filter(
            KnowledgeSource.submodule_id.isnot(None), KnowledgeSource.key.like("asu/%")
        )
        return {s.key: (s.url, s.enabled, s.extractor, s.fetch_every_hours, s.organization_id) for s in rows}
    finally:
        db.close()


def test_subscribe_shares_every_page_and_retires_removed_ones(client, writer):
    headers, org_id = writer
    first = client.put("/api/submodules/asu/subscription", headers=headers).get_json()
    assert first["added"] == len(SOURCES) and first["subscribed"] is True
    rows = _sources()
    assert len(rows) == len(SOURCES)
    url, enabled, extractor, every, owner = rows["asu/library_hours"]
    assert url == SOURCES["library_hours"].url and enabled and extractor == "asu.library_hours"
    assert every == SOURCES["library_hours"].fetch_every_hours and owner is None

    db = db_connect.SessionLocal()
    try:
        submodule_id = (
            db.query(KnowledgeSource.submodule_id).filter(KnowledgeSource.key == "asu/library_hours").scalar()
        )
        db.add(KnowledgeSource(submodule_id=submodule_id, key="asu/removed", url="https://asu.edu/x", category="c"))
        db.commit()
    finally:
        db.close()
    # The older sync route subscribes again; a second org shares the same pages
    again = client.post("/api/asu/sync", headers=headers).get_json()
    assert again["added"] == 0 and again["retired"] == 1
    assert _sources()["asu/removed"][1] is False
    soda_headers, _ = _issue("soda", "submodules:manage")
    assert client.put("/api/submodules/asu/subscription", headers=soda_headers).get_json()["added"] == 0
    assert len(_sources()) == len(SOURCES) + 1


def test_subscription_needs_the_manage_scope(client, app, clean_submodules):
    reader, _ = _issue("ais", "submodules:read", "knowledge:write")
    assert client.put("/api/submodules/asu/subscription", headers=reader).status_code == 403
    listed = client.post("/api/tools/submodules.list", headers=reader).get_json()["result"]["submodules"]
    assert next(p for p in listed if p["name"] == "asu")["subscribed"] is False


def test_only_subscribers_search_a_submodule(client, writer):
    from modules.knowledge import service as knowledge

    headers, _ = writer
    client.put("/api/submodules/asu/subscription", headers=headers)
    db = db_connect.SessionLocal()
    try:
        source = db.query(KnowledgeSource).filter(KnowledgeSource.key == "asu/library_hours").one()
        rows = [
            {
                "ordinal": 0,
                "level": 0,
                "parent_ordinal": None,
                "content": "Hayden Library opens at 7.",
                "embedding": None,
            }
        ]
        knowledge._write_version(db, source, rows, "h1", None)
        db.commit()
    finally:
        db.close()
    found = client.post("/api/knowledge/search", json={"query": "Hayden Library"}, headers=headers).get_json()
    assert any("Hayden Library opens" in r["content"] for r in found["results"])
    read = client.post("/api/tools/knowledge.read_source", json={"key": "asu/library_hours"}, headers=headers)
    assert read.status_code == 200 and "Hayden Library opens" in str(read.get_json()["result"])
    soda_headers, _ = _issue("soda", "knowledge:read")
    other = client.post("/api/knowledge/search", json={"query": "Hayden Library"}, headers=soda_headers).get_json()
    assert not any("Hayden Library opens" in r["content"] for r in other["results"])
    client.delete("/api/submodules/asu/subscription", headers=headers)
    gone = client.post("/api/knowledge/search", json={"query": "Hayden Library"}, headers=headers).get_json()
    assert not any("Hayden Library opens" in r["content"] for r in gone["results"])


def test_sync_needs_write_scope(client, app, clean_submodules):
    reader, _ = _issue("ais", "knowledge:read")
    assert client.post("/api/asu/sync", headers=reader).status_code == 403


def test_crawl_uses_the_asu_extractor(client, writer, pages):
    headers, org_id = writer
    client.put("/api/submodules/asu/subscription", headers=headers)
    url = SOURCES["library_hours"].url
    markdown = (Path(__file__).parent / "asu_fixtures" / "library_hours.md").read_text()
    pages[url] = fetch.Fetched(url=url, body=markdown.encode(), content_type="text/markdown", text=markdown)
    db = db_connect.SessionLocal()
    try:
        source = db.query(KnowledgeSource).filter(KnowledgeSource.key == "asu/library_hours").one()
        result = crawl.crawl(db, source, None)
    finally:
        db.close()
    assert result["changed"] is True
    found = client.post("/api/knowledge/search", json={"query": "Hayden Library"}, headers=headers).get_json()
    hayden = [r for r in found["results"] if "Hayden Library" in r["content"]]
    assert hayden and "|" not in hayden[0]["content"].split("\n", 1)[1]


def test_live_query_answers_then_queues_indexing(client, writer, pages, queued):
    headers, org_id = writer
    url = queries.url_for(QUERIES["news"], {"keywords": "robotics"})
    pages[url] = fetch.Fetched(url=url, body=b"", content_type="text/markdown", text="Robotics team wins title.")
    response = client.post(
        "/api/submodules/asu/query", json={"source": "news", "params": {"keywords": "robotics"}}, headers=headers
    )
    assert response.status_code == 200, response.get_json()
    body = response.get_json()
    assert body["url"] == url and "Robotics team wins title." in body["text"]
    assert queued[0][0] == "submodules.index_result" and queued[0][1]["org_id"] == org_id

    db = db_connect.SessionLocal()
    try:
        first = service.index_result(db, **queued[0][1], embedder=None)
        again = service.index_result(db, **queued[0][1], embedder=None)
    finally:
        db.close()
    assert first["changed"] is True and first["key"].startswith("asu-live/news-")
    assert again == {"key": first["key"], "changed": False}
    found = client.post("/api/knowledge/search", json={"query": "Robotics"}, headers=headers).get_json()
    assert any("Robotics team wins title." in r["content"] for r in found["results"])


def test_live_result_never_writes_into_a_shared_page(client, writer):
    headers, org_id = writer
    client.put("/api/submodules/asu/subscription", headers=headers)
    db = db_connect.SessionLocal()
    try:
        url = SOURCES["library_hours"].url
        result = service.index_result(db, org_id, "ais", "asu", "library_hours", url, "Hayden opens at 7am.", None)
        shared = db.query(KnowledgeSource).filter(KnowledgeSource.key == "asu/library_hours").one()
    finally:
        db.close()
    assert result["key"].startswith("asu-live/library_hours-") and shared.current_version_id is None


def test_query_errors(client, writer, pages, queued, monkeypatch):
    headers, _ = writer
    post = lambda body: client.post("/api/submodules/asu/query", json=body, headers=headers)  # noqa: E731
    assert post({"source": "nope"}).status_code == 404
    assert post({"source": "courses", "params": {"keywords": "CSE 310"}}).status_code == 422
    assert post({"source": "courses", "params": ["x"]}).status_code == 400
    assert post({"source": "library_hours"}).status_code == 502
    monkeypatch.delenv("SEARXNG_URL", raising=False)
    assert post({"source": "web", "params": {"query": "asu"}}).status_code == 503
    assert queued == []


def test_query_list_and_tool(client, writer, pages, queued):
    headers, _ = writer
    listed = client.get("/api/submodules/asu/queries", headers=headers).get_json()["queries"]
    courses = next(q for q in listed if q["key"] == "courses")
    assert any(p["name"] == "term" and p["required"] for p in courses["params"])

    url = queries.url_for(QUERIES["library_hours"], {})
    pages[url] = fetch.Fetched(url=url, body=b"", content_type="text/markdown", text="Hayden Library\nOpen 24 hours")
    result = client.post(
        "/api/tools/submodules.query", json={"submodule": "asu", "source": "library_hours"}, headers=headers
    ).get_json()
    assert result["result"]["url"] == url
    bad = client.post("/api/tools/submodules.query", json={"submodule": "nope", "source": "x"}, headers=headers)
    assert bad.status_code == 400


def test_submodule_list_and_unknown_submodule(client, writer):
    headers, _ = writer
    listed = client.get("/api/submodules", headers=headers).get_json()["submodules"]
    asu = next(p for p in listed if p["name"] == "asu")
    assert asu["key_prefix"] == "asu/" and asu["pages"] == len(SOURCES) and "courses" in asu["queries"]
    assert client.get("/api/submodules/nope/queries", headers=headers).status_code == 404
    assert client.post("/api/submodules/nope/sync", headers=headers).status_code == 404


def test_old_asu_routes_still_answer(client, writer, pages, queued):
    headers, _ = writer
    listed = client.get("/api/asu/queries", headers=headers).get_json()["queries"]
    assert any(q["key"] == "courses" for q in listed)
    url = queries.url_for(QUERIES["library_hours"], {})
    pages[url] = fetch.Fetched(url=url, body=b"", content_type="text/markdown", text="Hayden Library\nOpen 24 hours")
    body = client.post("/api/asu/query", json={"source": "library_hours"}, headers=headers).get_json()
    assert body["url"] == url and body["source"] == "library_hours"
    assert client.post("/api/asu/sync", headers=headers).get_json()["added"] == len(SOURCES)


def test_every_submodule_feed_is_a_valid_alert_feed():
    from modules.feeds import service as alerts
    from modules.submodules import catalog

    for submodule in catalog.SUBMODULES.values():
        for feed in submodule.feeds:
            assert alerts.KEY_PATTERN.match(feed.key), f"{submodule.name}/{feed.key}"
            assert feed.kind in alerts.KINDS, f"{submodule.name}/{feed.key}"
            alerts.KINDS[feed.kind].validate(dict(feed.config))


def test_alert_presets_come_from_subscribed_submodules(client, officer_headers, clean_submodules, monkeypatch):
    monkeypatch.setattr(crawl, "start_crawl_due", lambda: None)
    presets = client.get("/api/feeds/ais/presets", headers=officer_headers).get_json()["presets"]
    assert not [p for p in presets if p["submodule"] == "careers"]
    assert client.put("/api/dashboard/ais/submodules/careers/subscription", headers=officer_headers).status_code == 200
    presets = client.get("/api/feeds/ais/presets", headers=officer_headers).get_json()["presets"]
    internships = next(p for p in presets if p["key"] == "internships")
    assert internships["submodule"] == "careers" and internships["kind"] == "github_jobs"
    assert internships["config"]["repo"] == "vanshb03/Summer2026-Internships" and internships["added"] is False
    assert client.get("/api/feeds/ais/presets").status_code == 401


def test_canvas_url_comes_from_the_submodule(monkeypatch):
    from modules.accounts import providers

    monkeypatch.setenv("ACCOUNTS_BASE_URL", "https://api.test")
    monkeypatch.setenv("ACCOUNTS_CANVAS_CLIENT_ID", "id")
    monkeypatch.setenv("ACCOUNTS_CANVAS_CLIENT_SECRET", "secret")
    monkeypatch.delenv("ACCOUNTS_CANVAS_URL", raising=False)
    canvas = providers.get("canvas")
    assert canvas is not None and canvas.token_url == "https://canvas.asu.edu/login/oauth2/token"
    monkeypatch.setenv("ACCOUNTS_CANVAS_URL", "https://canvas.example.edu/")
    canvas = providers.get("canvas")
    assert canvas is not None and canvas.authorize_url == "https://canvas.example.edu/login/oauth2/auth"
