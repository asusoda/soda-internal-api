"""The events route links each event that the sync copied to the org's Google Calendar."""

import pytest

from modules.calendar import service


def _page(page_id, name):
    return {
        "id": page_id,
        "properties": {
            "Name": {"title": [{"plain_text": name}]},
            "Date": {"date": {"start": "2026-10-20T18:00:00.000-07:00", "end": None}},
        },
    }


class FakeNotion:
    def fetch_events(self, database_id, parent_transaction=None):
        return [_page("page-1", "Build night"), _page("page-2", "Social")]


class FakeGcal:
    def __init__(self, events):
        self.events = events
        self.time_mins = []

    def get_all_events(self, calendar_id, time_min=None, parent_transaction=None):
        self.time_mins.append(time_min)
        return self.events


def _managed(page_id, link):
    return {"id": f"evt-{page_id}", "htmlLink": link, "extendedProperties": {"private": {"notionPageId": page_id}}}


@pytest.fixture
def soda_calendar(monkeypatch):
    from core.db import db_connect
    from modules.organizations.models import Organization

    db = db_connect.SessionLocal()
    org = db.query(Organization).filter_by(prefix="soda").one()
    before = (org.notion_database_id, org.google_calendar_id)
    org.notion_database_id, org.google_calendar_id = "notion-db", "cal-1"
    db.commit()
    calendar = service.get_service()
    monkeypatch.setattr(calendar, "notion_for", lambda db, org: FakeNotion())
    service._FRONTEND_CACHE.clear()
    yield calendar
    service._FRONTEND_CACHE.clear()
    org.notion_database_id, org.google_calendar_id = before
    db.commit()
    db.close()


def _events(client):
    response = client.get("/api/calendar/soda/events")
    assert response.status_code == 200
    return {event["id"]: event for event in response.get_json()["events"]}


def test_events_have_the_google_calendar_link(client, soda_calendar, monkeypatch):
    gcal = FakeGcal([_managed("page-1", "https://www.google.com/calendar/event?eid=abc")])
    monkeypatch.setattr(soda_calendar, "gcal_for", lambda db, org: gcal)
    events = _events(client)
    assert events["page-1"]["jump_url"] == "https://www.google.com/calendar/event?eid=abc"
    assert "jump_url" not in events["page-2"]
    # Both pages start 2026-10-20T18:00-07:00; the lookup starts one day before
    assert gcal.time_mins == ["2026-10-20T01:00:00Z"]


def test_events_load_without_links_when_google_fails(client, soda_calendar, monkeypatch):
    monkeypatch.setattr(soda_calendar, "gcal_for", lambda db, org: FakeGcal(None))
    events = _events(client)
    assert set(events) == {"page-1", "page-2"}
    assert all("jump_url" not in event for event in events.values())


def test_no_google_lookup_without_events(client, soda_calendar, monkeypatch):
    gcal = FakeGcal([])
    monkeypatch.setattr(soda_calendar, "gcal_for", lambda db, org: gcal)
    monkeypatch.setattr(FakeNotion, "fetch_events", lambda self, database_id, parent_transaction=None: [])
    assert _events(client) == {}
    assert gcal.time_mins == []
