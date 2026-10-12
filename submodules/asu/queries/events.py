"""ASU events: the public events calendar."""

from __future__ import annotations

import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag

from modules.submodules import http
from modules.submodules.params import text, url
from modules.submodules.search import settings
from modules.submodules.types import Fetched, QueryError, QueryParam, QuerySource
from submodules.asu.sources.events import extract_events

_PUBLIC = "https://asuevents.asu.edu/home"


_SPACE = re.compile(r"\s+")


def _clean(node: Tag | None) -> str:
    return _SPACE.sub(" ", node.get_text(" ", strip=True)).strip() if node else ""


def public_cards(fetched: Fetched) -> str:
    """One line per event card on the public calendar: name, date, time, place, and its page."""
    if fetched.text is not None:
        return extract_events(fetched)
    out: list[str] = []
    for card in BeautifulSoup(fetched.body, "lxml").select("li.card-event"):
        title = card.select_one("h3.card-title a")
        if title is None:
            continue
        href = title.get("href")
        parts = [
            _clean(title),
            _clean(card.select_one(".views-field-field-event-date-value-1")),
            _clean(card.select_one(".views-field-field-event-date-end-value")),
            _clean(card.select_one(".views-field-field-asu-events-location")),
            urljoin(_PUBLIC, href.split("&")[0] if isinstance(href, str) else ""),
        ]
        out.append(" | ".join(p for p in parts if p))
    return "\n".join(out) if out else extract_events(fetched)


def public(keywords: str) -> tuple[str, str]:
    """The public ASU events calendar, narrowed to a keyword when one was given."""
    target = url(_PUBLIC, [("searchText", keywords)])
    return target, public_cards(http.fetch(target, needs_js=True))


def answer(params: dict[str, str]) -> tuple[str, str]:
    """The public ASU events calendar. Sun Devil Central needs an ASU sign-in and is not read here."""
    source_url, body = public(text(params, "keywords"))
    if not body.strip():
        raise QueryError("no events found on the ASU events calendar")
    budget = settings().scraper.query_max_chars
    if len(body) > budget:
        body = body[:budget].rsplit("\n", 1)[0] + "\n[more listings not shown]"
    return source_url, body.strip()


QUERY = QuerySource(
    key="events",
    description="Search the public ASU events calendar.",
    params=(QueryParam("keywords", "What the event is about.", example="career fair"),),
    answer=answer,
    category="events",
    index=False,
)
