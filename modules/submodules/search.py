"""Settings that submodule queries read, and the SearXNG integration for web search. No Flask here.

Web search goes through SearXNG. An org sets its own SearXNG on the Integrations page; else SEARXNG_URL
and SEARXNG_ENGINES in Doppler give the deployment default. query_scope() sets the org's SearXNG and
Firecrawl for the live query it wraps.
"""

import os
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from types import SimpleNamespace
from typing import Any

import requests

from core import net
from core.integrations.registry import Field, Integration, IntegrationError, org_values, register, use
from modules.knowledge import fetch

URL_SECRET = "searxng_url"  # nosec B105 - the name of an org secret, not its value
ENGINES_SECRET = "searxng_engines"  # nosec B105 - the name of an org secret, not its value
DEFAULT_ENGINES = "google,brave,bing"
TIMEOUT_SECONDS = 20


def _int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return default


def _deployment_search() -> SimpleNamespace:
    return SimpleNamespace(
        base_url=os.environ.get("SEARXNG_URL", "").strip(),
        engines=os.environ.get("SEARXNG_ENGINES", DEFAULT_ENGINES),
        public_only=False,
    )


def search_for(db, org_id: int) -> SimpleNamespace:
    """The org's own SearXNG, else the deployment default. base_url is empty when there is none."""
    saved = org_values(db, org_id, "searxng")
    if saved is None:
        return _deployment_search()
    return SimpleNamespace(
        base_url=saved[URL_SECRET], engines=saved.get(ENGINES_SECRET) or DEFAULT_ENGINES, public_only=True
    )


_SEARCH: ContextVar[SimpleNamespace | None] = ContextVar("searxng", default=None)


@contextmanager
def query_scope(db, org_id: int) -> Iterator[None]:
    """Live queries inside the block use the org's SearXNG and Firecrawl."""
    token = _SEARCH.set(search_for(db, org_id))
    try:
        with fetch.firecrawl_scope(fetch.firecrawl_for(db, org_id)):
            yield
    finally:
        _SEARCH.reset(token)


def settings() -> SimpleNamespace:
    search = _SEARCH.get() or _deployment_search()
    return SimpleNamespace(
        scraper=SimpleNamespace(query_max_chars=_int("SUBMODULE_QUERY_MAX_CHARS", _int("ASU_QUERY_MAX_CHARS", 30_000))),
        search=SimpleNamespace(
            base_url=search.base_url,
            engines=search.engines,
            public_only=search.public_only,
            language="en-US",
            safesearch=1,
            max_results=8,
            snippet_chars=300,
        ),
    )


def search_json(url: str, public_only: bool) -> dict[str, Any]:
    """GET a SearXNG JSON answer. An org's own server must be on a public address."""
    if public_only:
        try:
            net.check_public(url)
        except ValueError as e:
            raise fetch.FetchRejected(str(e)) from e
    try:
        response = requests.get(url, timeout=TIMEOUT_SECONDS, allow_redirects=False)
    except requests.RequestException as e:
        raise fetch.FetchError("SearXNG could not be reached") from e
    if response.status_code != 200:
        raise fetch.FetchError(f"SearXNG returned {response.status_code}")
    try:
        found = response.json()
    except ValueError as e:
        raise fetch.FetchError("SearXNG did not return JSON. Turn on the json format in its settings.yml") from e
    if not isinstance(found, dict):
        raise fetch.FetchError("SearXNG sent an answer that is not an object")
    return found


def _test(db, org_id: int) -> str:
    search = search_for(db, org_id)
    if not search.base_url:
        raise IntegrationError("Set a SearXNG server first")
    try:
        found = search_json(f"{search.base_url.rstrip('/')}/search?q=test&format=json", search.public_only)
    except (fetch.FetchError, fetch.FetchRejected) as e:
        raise IntegrationError(str(e)) from e
    return f"Connected. A test search found {len(found.get('results') or [])} results."


register(
    Integration(
        key="searxng",
        title="Web search (SearXNG)",
        description="Connect a SearXNG server for live web search.",
        fields=(
            Field(
                URL_SECRET,
                "Server URL",
                "A SearXNG server with the json format on, on a public address.",
                kind="url",
                secret=False,
            ),
            Field(
                ENGINES_SECRET,
                "Engines",
                f"Comma-separated. Leave empty for {DEFAULT_ENGINES}.",
                secret=False,
                optional=True,
            ),
        ),
        docs="modules/submodules",
        deployment=lambda: bool(_deployment_search().base_url),
        test=_test,
    )
)
use("searxng", "submodules")
