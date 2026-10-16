"""Crawled knowledge sources: schedule, fetch, extract, chunk, index, and the guards around them."""

import datetime
import socket
import uuid

import pytest

from core.db import db_connect
from modules.knowledge import crawl, extract, fetch
from modules.knowledge.models import KnowledgeSource


def _issue(prefix, *scopes):
    from modules.auth import machine_tokens
    from modules.organizations.models import Organization

    db = db_connect.SessionLocal()
    try:
        org_id = db.query(Organization.id).filter_by(prefix=prefix).scalar()
        value, _ = machine_tokens.issue(db, organization_id=org_id, name="crawler", kind="app", scopes=list(scopes))
        return {"Authorization": f"Bearer {value}"}
    finally:
        db.close()


@pytest.fixture
def writer(app):
    return _issue("soda", "knowledge:read", "knowledge:write")


@pytest.fixture
def pages(monkeypatch):
    """url -> Fetched or exception, served instead of the network."""
    served: dict = {}

    def fake_fetch(url):
        page = served.get(url, fetch.FetchError(f"{url} is not served in this test"))
        if isinstance(page, Exception):
            raise page
        return page

    monkeypatch.setattr(fetch, "fetch", fake_fetch)
    return served


def _html(main: str, nav: str = "Home About Apply") -> bytes:
    return f"<html><head><title>Hours</title></head><body><nav>{nav}</nav><main><p>{main}</p></main></body></html>".encode()


def _schedule(client, writer, url, **extra):
    key = "crawl-" + uuid.uuid4().hex[:8]
    body = {"url": url, "category": "pages", "fetch_every_hours": 24, **extra}
    response = client.put(f"/api/knowledge/crawls/{key}", json=body, headers=writer)
    assert response.status_code == 200, response.get_json()
    return key


def _run(key, force=False):
    from modules.organizations.models import Organization

    db = db_connect.SessionLocal()
    try:
        org_id = db.query(Organization.id).filter_by(prefix="soda").scalar()
        return crawl.run(db, org_id, key, None, force=force)
    finally:
        db.close()


def _search(client, writer, query):
    return client.post("/api/knowledge/search", json={"query": query}, headers=writer).get_json()["results"]


def test_crawl_indexes_main_text(client, writer, pages):
    word = "w" + uuid.uuid4().hex[:8]
    url = f"https://example.edu/{word}"
    pages[url] = fetch.Fetched(url=url, body=_html(f"The library opens at 7am {word}."), content_type="text/html")
    key = _schedule(client, writer, url)

    assert _run(key) == {"key": key, "changed": True, "chunks": 1}
    results = _search(client, writer, word)
    assert results[0]["content"] == f"Hours\nThe library opens at 7am {word}."
    assert results[0]["title"] == "Hours"
    assert "Apply" not in results[0]["content"]

    assert _run(key)["changed"] is False
    source = client.get(f"/api/knowledge/sources/{key}", headers=writer).get_json()
    assert source["crawl"]["fetch_every_hours"] == 24 and source["crawl"]["last_error"] is None


def test_quality_floor_keeps_a_good_index(client, writer, pages):
    word = "w" + uuid.uuid4().hex[:8]
    url = f"https://example.edu/{word}"
    long_text = " ".join(f"Sentence {i} about {word}." for i in range(60))
    pages[url] = fetch.Fetched(url=url, body=_html(long_text), content_type="text/html")
    key = _schedule(client, writer, url)
    _run(key)

    pages[url] = fetch.Fetched(url=url, body=_html("Page moved."), content_type="text/html")
    result = _run(key)
    assert result["changed"] is False and "index is kept" in result["error"]
    assert _search(client, writer, word)
    assert client.get(f"/api/knowledge/sources/{key}", headers=writer).get_json()["crawl"]["last_error"]

    assert _run(key, force=True)["changed"] is True
    assert _search(client, writer, word) == []


def test_fetch_failure_is_recorded(client, writer, pages):
    url = "https://example.edu/gone"
    pages[url] = fetch.FetchRejected("https://example.edu/gone returned 404")
    key = _schedule(client, writer, url)
    assert "404" in _run(key)["error"]
    source = client.get(f"/api/knowledge/sources/{key}", headers=writer).get_json()
    assert "404" in source["crawl"]["last_error"] and source["crawl"]["last_attempt_at"]


def test_firecrawl_markdown_is_used_as_is(client, writer, pages):
    word = "w" + uuid.uuid4().hex[:8]
    url = f"https://example.edu/{word}"
    payload = {
        "success": True,
        "data": {"markdown": f"# Dining\nOpen late {word}", "metadata": {"statusCode": 200, "title": "Dining"}},
    }
    pages[url] = fetch.parse_firecrawl(url, payload)
    key = _schedule(client, writer, url)
    _run(key)
    assert _search(client, writer, word)[0]["content"] == f"Dining\n# Dining\nOpen late {word}"


def test_due_sources(client, writer, pages):
    url = "https://example.edu/due"
    pages[url] = fetch.Fetched(url=url, body=_html("Due page text here."), content_type="text/html")
    key = _schedule(client, writer, url, fetch_every_hours=2)
    db = db_connect.SessionLocal()
    try:
        assert key in [s.key for s in crawl.due(db, limit=1000)]
        result = crawl.crawl_due(db, lambda org_id: None)
        assert result["crawled"] >= 1
        assert key not in [s.key for s in crawl.due(db, limit=1000)]
        later = datetime.datetime.now(datetime.UTC).replace(tzinfo=None) + datetime.timedelta(hours=3)
        assert key in [s.key for s in crawl.due(db, later, limit=1000)]
        source = db.query(KnowledgeSource).filter_by(key=key).one()
        source.enabled = False
        db.commit()
        assert key not in [s.key for s in crawl.due(db, later, limit=1000)]
    finally:
        db.close()


def test_schedule_rules(client, writer, monkeypatch):
    bad = [
        {"url": "ftp://example.edu", "category": "c"},
        {"url": "https://example.edu", "category": "c", "fetch_every_hours": 0},
        {"url": "https://example.edu"},
    ]
    for body in bad:
        assert client.put("/api/knowledge/crawls/k1", json=body, headers=writer).status_code == 400
    public = {"url": "https://example.edu", "category": "c", "public": True}
    assert client.put("/api/knowledge/crawls/k1", json=public, headers=writer).status_code == 403

    client.put("/api/knowledge/sources/written", json={"category": "c", "chunks": [{"content": "x"}]}, headers=writer)
    assert client.post("/api/knowledge/crawls/run", json={"key": "written"}, headers=writer).status_code == 409


def test_run_endpoint_queues(client, writer, monkeypatch):
    import core.jobs

    queued = []
    monkeypatch.setattr(core.jobs, "defer", lambda name, **kwargs: queued.append((name, kwargs)))
    key = _schedule(client, writer, "https://example.edu/queued")
    assert client.post("/api/knowledge/crawls/run", json={"key": key, "force": True}, headers=writer).status_code == 202
    assert queued[0][0] == "knowledge.crawl_source" and queued[0][1]["key"] == key and queued[0][1]["force"] is True
    assert client.post("/api/knowledge/crawls/run", json={"key": "nope"}, headers=writer).status_code == 404


def _resolve_to(monkeypatch, address):
    monkeypatch.setattr(socket, "getaddrinfo", lambda host, port: [(socket.AF_INET, 0, 0, "", (address, port))])


@pytest.mark.parametrize("address", ["127.0.0.1", "10.1.2.3", "169.254.169.254", "192.168.0.5"])
def test_private_addresses_are_refused(monkeypatch, address):
    _resolve_to(monkeypatch, address)
    with pytest.raises(fetch.FetchRejected):
        fetch.check_url("https://internal.example/")


def test_redirect_to_a_private_address_is_refused(monkeypatch):
    class Redirect:
        is_redirect = True
        headers = {"location": "http://metadata.internal/latest"}

        def close(self):
            pass

    def resolve(host, port):
        address = "93.184.216.34" if host == "example.edu" else "169.254.169.254"
        return [(socket.AF_INET, 0, 0, "", (address, port))]

    monkeypatch.setattr(socket, "getaddrinfo", resolve)
    monkeypatch.setattr(fetch.net, "get", lambda *a, **k: Redirect())
    with pytest.raises(fetch.FetchRejected):
        fetch.fetch_http("https://example.edu/page")


def test_robots_rules():
    rules = fetch.robots_rules(200, "User-agent: *\nDisallow: /private")
    assert not rules.can_fetch(fetch.USER_AGENT, "https://example.edu/private/x")
    assert rules.can_fetch(fetch.USER_AGENT, "https://example.edu/public")
    assert fetch.robots_rules(404, "").can_fetch(fetch.USER_AGENT, "https://example.edu/private")
    with pytest.raises(fetch.FetchError):
        fetch.robots_rules(503, "")


def test_chunking_and_pacing():
    text = "\n".join(f"Paragraph {i} " + "word " * 40 for i in range(5))
    chunks = extract.chunk_text(text, max_chars=300, overlap_chars=0)
    assert all(len(c) <= 300 for c in chunks) and len(chunks) >= 4

    slept = []
    clock = iter([0.0, 0.5, 10.0])
    pacer = fetch.HostPacer(2, clock=lambda: next(clock), sleep=slept.append)
    pacer.wait("https://a.edu/1")
    pacer.wait("https://a.edu/2")
    pacer.wait("https://b.edu/1")
    assert slept == [1.5]
