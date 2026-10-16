"""Fetching for live queries: pages through the knowledge fetcher, and JSON, feeds and plain text."""

from __future__ import annotations

import html
import json
import re
import xml.etree.ElementTree as ET  # nosec B405 - types only; parsing goes through defusedxml
from typing import Any

from defusedxml import ElementTree as SafeET
from defusedxml.common import DefusedXmlException

from modules.knowledge import fetch as knowledge_fetch
from modules.knowledge.fetch import Fetched, fetch_http
from modules.submodules.types import QueryError

_TAG = re.compile(r"<[^>]+>")
_SPACE = re.compile(r"\s+")


def fetch(url: str, *, needs_js: bool = False) -> Fetched:
    """The page at url through the knowledge fetcher. needs_js pages are rendered by Firecrawl or the browser."""
    return knowledge_fetch.fetch(url, render=needs_js)


def get_text(url: str) -> str:
    """The body of url as text."""
    return fetch_http(url).body.decode("utf-8", errors="replace")


def get_json(url: str) -> Any:
    """The body of url parsed as JSON. Raises QueryError when it is not JSON."""
    body = fetch_http(url).body
    try:
        return json.loads(body)
    except ValueError as e:
        raise QueryError(f"{url} did not return JSON") from e


def get_xml(url: str) -> ET.Element:
    """The body of url parsed as XML. Raises QueryError when it is not XML."""
    body = fetch_http(url).body
    try:
        return SafeET.fromstring(body)
    except (ET.ParseError, DefusedXmlException) as e:
        raise QueryError(f"{url} did not return a feed") from e


def plain(text: str | None, limit: int) -> str:
    """text with markup removed, entities decoded, whitespace collapsed, held to limit."""
    cleaned = _SPACE.sub(" ", html.unescape(_TAG.sub(" ", text or ""))).strip()
    return cleaned if len(cleaned) <= limit else cleaned[: limit - 3].rstrip() + "..."
