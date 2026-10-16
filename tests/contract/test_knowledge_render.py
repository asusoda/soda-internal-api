"""Pages rendered in the shared browser: when a page is thin, the per-org limit, shared pages, and the address guard.
No browser and no network: render.render is replaced."""

from typing import Any, cast

import pytest

from core import limits, net
from modules.knowledge import fetch, render
from modules.knowledge.fetch import Fetched

URL = "https://example.edu/hours"
THIN = Fetched(url=URL, body=b"<html><body><div id='root'></div></body></html>", content_type="text/html")
FULL_TEXT = "The library opens at 7am and closes at midnight on weekdays. " * 20
FULL = Fetched(
    url=URL, body=f"<html><body><main><p>{FULL_TEXT}</p></main></body></html>".encode(), content_type="text/html"
)
RENDERED = Fetched(
    url=URL, body=f"<html><body><main><p>{FULL_TEXT}</p></main></body></html>".encode(), content_type="text/html"
)


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
    session.rollback()
    session.close()


@pytest.fixture
def clean_limits(app):
    yield
    from core.db import db_connect

    db = db_connect.SessionLocal()
    db.query(limits.OrgLimit).delete()
    db.query(limits.UsageCounter).delete()
    db.commit()
    db.close()


@pytest.fixture
def web(monkeypatch):
    """The plain GET serves served["page"]; render.render records its calls and returns RENDERED."""
    served: dict[str, Any] = {"page": THIN, "renders": []}
    monkeypatch.setattr(fetch, "check_url", lambda url: None)
    monkeypatch.setattr(fetch, "robots_allowed", lambda url: True)
    monkeypatch.setattr(fetch, "fetch_http", lambda url: served["page"])

    def fake_render(url, server):
        served["renders"].append((url, server))
        return RENDERED

    monkeypatch.setattr(render, "render", fake_render)
    monkeypatch.setenv("BROWSER_URL", "ws://browser:3000/")
    return served


def test_a_page_with_little_text_is_thin():
    assert render.is_thin(THIN)
    assert not render.is_thin(FULL)


def test_a_page_that_asks_for_javascript_is_thin_whatever_its_length():
    body = f"<html><body><noscript>Please enable JavaScript.</noscript><main><p>{FULL_TEXT}</p></main></body></html>"
    assert render.is_thin(Fetched(url=URL, body=body.encode(), content_type="text/html"))


def test_text_and_markdown_pages_are_never_thin():
    assert not render.is_thin(Fetched(url=URL, body=b"short", content_type="text/plain"))
    assert not render.is_thin(Fetched(url=URL, body=b"# x", content_type="text/markdown", text="# x"))


def test_without_a_browser_the_get_page_is_kept(db, web, monkeypatch):
    monkeypatch.delenv("BROWSER_URL")
    with render.scope(db, None):
        assert fetch.fetch(URL) is THIN
    assert web["renders"] == []


def test_a_shared_page_renders_and_counts_against_no_org(clean_limits, db, web):
    with render.scope(db, None):
        assert fetch.fetch(URL) is RENDERED
    assert web["renders"] == [(URL, "ws://browser:3000/")]


def test_an_org_does_not_render_until_its_limit_is_raised(clean_limits, db, web):
    soda = _org_id("soda")
    assert limits.value(db, soda, render.RENDERS_LIMIT) == 0
    with render.scope(db, soda):
        assert fetch.fetch(URL) is THIN
    assert web["renders"] == []

    limits.set_values(db, soda, {render.RENDERS_LIMIT: 1})
    with render.scope(db, soda):
        assert fetch.fetch(URL) is RENDERED
        assert fetch.fetch(URL) is THIN, "the second render is over the limit of 1"
    assert len(web["renders"]) == 1
    assert limits.used(db, soda, render.RENDERS_LIMIT) == 1


def test_a_page_with_enough_text_is_not_rendered_unless_asked(clean_limits, db, web):
    web["page"] = FULL
    with render.scope(db, None):
        assert fetch.fetch(URL) is FULL
        assert fetch.fetch(URL, render=True) is RENDERED
    assert len(web["renders"]) == 1


def test_a_failed_render_keeps_the_get_page(clean_limits, db, web, monkeypatch):
    def broken(url, server):
        raise fetch.FetchError("did not load")

    monkeypatch.setattr(render, "render", broken)
    with render.scope(db, None):
        assert fetch.fetch(URL) is THIN


def test_firecrawl_takes_the_page_before_the_browser(clean_limits, db, web, monkeypatch):
    from_firecrawl = Fetched(url=URL, body=b"# hours", content_type="text/markdown", text="# hours")
    monkeypatch.setattr(fetch, "fetch_firecrawl", lambda url, firecrawl: from_firecrawl)
    with fetch.firecrawl_scope(fetch.Firecrawl("http://firecrawl:3002")), render.scope(db, None):
        assert fetch.fetch(URL) is from_firecrawl
    assert web["renders"] == []


def test_the_browser_loads_only_public_addresses(monkeypatch):
    assert render.allowed_request("data:text/plain,hi")
    assert not render.allowed_request("http://127.0.0.1:8000/health")
    assert not render.allowed_request("file:///etc/passwd")

    def no_host(url):
        raise net.NoHost("api does not resolve")

    monkeypatch.setattr(net, "check_public", no_host)
    assert not render.allowed_request("http://api:8000/")
    monkeypatch.setattr(net, "check_public", lambda url: None)
    assert render.allowed_request("https://example.edu/")
