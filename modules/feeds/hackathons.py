"""Upcoming hackathons from public listings: Hack Club, Euro-Hackathons and Hackalist.

MLH and Devpost refuse automated requests, so they are not sources.
"""

import datetime
import json
import re

from dateutil import parser as date_parser

from modules.feeds.types import Fetch, Item, SourceError

SOURCES = ("hackclub", "euro_hackathons", "hackalist")
SOURCE_NAMES = {"hackclub": "Hack Club", "euro_hackathons": "Euro-Hackathons", "hackalist": "Hackalist"}


def validate(config: dict) -> dict:
    """The feed config with defaults filled in. Raises ValueError on a bad value."""
    sources = config.get("sources", list(SOURCES))
    if not isinstance(sources, list) or not sources or any(s not in SOURCES for s in sources):
        raise ValueError(f"sources must be a list drawn from {', '.join(SOURCES)}")
    min_days, max_days = config.get("min_days_ahead", 0), config.get("max_days_ahead", 90)
    if not all(isinstance(d, int) for d in (min_days, max_days)) or not 0 <= min_days <= max_days <= 365:
        raise ValueError("min_days_ahead and max_days_ahead must be integers with 0 <= min <= max <= 365")
    return {"sources": sources, "min_days_ahead": min_days, "max_days_ahead": max_days}


def fetch(config: dict, get: Fetch, now: datetime.datetime) -> list[Item]:
    """Hackathons that start inside the configured window, one per name, earliest first.

    Raises SourceError only when every source fails.
    """
    found: list[dict] = []
    failures = []
    for source in config["sources"]:
        try:
            found.extend(READERS[source](get, now))
        except (SourceError, ValueError, TypeError, KeyError) as e:
            failures.append(f"{source}: {e}")
    if failures and len(failures) == len(config["sources"]):
        raise SourceError("; ".join(failures))
    start = now + datetime.timedelta(days=config["min_days_ahead"])
    end = now + datetime.timedelta(days=config["max_days_ahead"])
    unique: dict[str, dict] = {}
    for event in sorted(found, key=lambda e: e["start"]):
        key = name_key(event["name"])
        if key and key not in unique and start <= event["start"] <= end:
            unique[key] = event
    return [_item(key, event) for key, event in unique.items()]


def name_key(name: str) -> str:
    """Lowercase name with spaces collapsed, used to match the same event across sources."""
    return " ".join(name.lower().split())[:255]


def _naive(value: str) -> datetime.datetime:
    parsed = date_parser.parse(value)
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(datetime.UTC).replace(tzinfo=None)
    return parsed


def _json(get: Fetch, url: str):
    try:
        return json.loads(get(url))
    except json.JSONDecodeError as e:
        raise SourceError(f"{url} did not return JSON") from e


def read_hackclub(get: Fetch, now: datetime.datetime) -> list[dict]:
    events = []
    for event in _json(get, "https://hackathons.hackclub.com/api/events/upcoming"):
        try:
            start, end = _naive(event["start"]), _naive(event["end"])
        except (KeyError, ValueError, OverflowError):
            continue
        if event.get("virtual"):
            kind = "Online"
        elif event.get("hybrid"):
            kind = "Hybrid"
        else:
            kind = "In person" if event.get("city") else "Online"
        place = ", ".join(str(event[k]) for k in ("city", "state", "country") if event.get(k)) or "Online"
        events.append(_event(event.get("name"), start, end, place, kind, event.get("website"), "hackclub"))
    return events


def read_euro_hackathons(get: Fetch, now: datetime.datetime) -> list[dict]:
    data = _json(get, "https://euro-hackathons.com/api/hackathons?status=upcoming")
    events = []
    for event in data if isinstance(data, list) else data.get("hackathons", []):
        start_text = event.get("startDate") or event.get("start_date") or event.get("date")
        end_text = event.get("endDate") or event.get("end_date")
        try:
            start = _naive(start_text)
            end = _naive(end_text) if end_text else start + datetime.timedelta(days=2)
        except (TypeError, ValueError, OverflowError):
            continue
        mode = str(event.get("mode") or event.get("type") or "").lower()
        kind = "Online" if ("online" in mode or "virtual" in mode) else "Hybrid" if "hybrid" in mode else "In person"
        place = event.get("location") or event.get("city") or "Europe"
        link = event.get("website") or event.get("url") or event.get("link")
        events.append(_event(event.get("name") or event.get("title"), start, end, place, kind, link, "euro_hackathons"))
    return events


def read_hackalist(get: Fetch, now: datetime.datetime) -> list[dict]:
    events = []
    first = datetime.date(now.year, now.month, 1)
    for offset in range(5):
        month_index = first.month - 1 + offset
        year, month = first.year + month_index // 12, month_index % 12 + 1
        try:
            data = _json(get, f"https://www.hackalist.org/api/1.0/{year}/{month:02d}.json")
        except SourceError:
            continue
        for month_events in data.values() if isinstance(data, dict) else []:
            for event in month_events if isinstance(month_events, list) else []:
                event_year = event.get("year", year)
                try:
                    start = _naive(f"{event.get('startDate', '')} {event_year}")
                    end = _naive(f"{event.get('endDate', '')} {event_year}")
                except (ValueError, OverflowError):
                    continue
                city = event.get("city")
                kind = "In person" if city else "Online"
                events.append(
                    _event(event.get("title"), start, end, city or "Online", kind, event.get("url"), "hackalist")
                )
    return events


READERS = {"hackclub": read_hackclub, "euro_hackathons": read_euro_hackathons, "hackalist": read_hackalist}


def _event(name, start, end, place, kind, url, source) -> dict:
    link = str(url or "")
    return {
        "name": str(name or "").strip(),
        "start": start,
        "end": end,
        "place": str(place)[:100],
        "kind": kind,
        "url": link if re.match(r"^https?://", link) else "",
        "source": SOURCE_NAMES[source],
    }


def _item(key: str, event: dict) -> Item:
    start, end = event["start"].strftime("%b %d, %Y"), event["end"].strftime("%b %d, %Y")
    return Item(
        key=key,
        title=f"New hackathon: {event['name']}",
        url=event["url"],
        fields=[
            ("Dates", start if start == end else f"{start} to {end}"),
            ("Location", event["place"]),
            ("Type", event["kind"]),
        ],
        footer=f"Source: {event['source']}",
    )
