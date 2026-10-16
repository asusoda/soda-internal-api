"""The sync keeps the Google events of current Notion pages and copies Notion dates as Google reads them."""

import logging
from typing import cast

from sentry_sdk import start_transaction

from modules.calendar.clients import GoogleCalendarClient
from modules.calendar.events import CalendarEventDTO
from modules.calendar.sync import update_google_calendar


def _page(page_id, date):
    return {"id": page_id, "properties": {"Name": {"title": [{"plain_text": page_id}]}, "Date": {"date": date}}}


def _managed(page_id):
    return {"id": f"evt-{page_id}", "extendedProperties": {"private": {"notionPageId": page_id}}}


class FakeGcal:
    def __init__(self, events):
        self.events = events
        self.deleted = []
        self.created = []

    def get_all_events(self, calendar_id, time_min=None, parent_transaction=None):
        return self.events

    def update_event(self, calendar_id, gcal_event_id, event_data, notion_page_id, parent_transaction=None):
        return {"id": gcal_event_id}

    def create_event(self, calendar_id, event_data, notion_page_id, parent_transaction=None):
        self.created.append(notion_page_id)
        return f"https://calendar.google.com/event?{notion_page_id}", f"evt-{notion_page_id}"

    def batch_delete_events(self, calendar_id, event_ids, op, parent_transaction=None):
        self.deleted.extend(event_ids)
        return len(event_ids), 0


def _event(page_id, date) -> CalendarEventDTO:
    event = CalendarEventDTO.from_notion(_page(page_id, date))
    assert event is not None
    return event


def _dto(page_id):
    return _event(page_id, {"start": "2026-10-20", "end": None})


def test_sync_deletes_only_events_of_pages_that_are_gone():
    gcal = FakeGcal([_managed("kept"), _managed("gone"), _managed("kept") | {"id": "evt-kept-copy"}])

    results = update_google_calendar(
        cast(GoogleCalendarClient, gcal),
        [_dto("kept"), _dto("new")],
        "cal-1",
        start_transaction(op="test"),
        logging.getLogger(),
    )

    assert sorted(gcal.deleted) == ["evt-gone", "evt-kept-copy"]
    created = next(result for result in results if result["status"] == "created")
    assert created["gcal_event_id"] == "evt-new"
    assert created["jump_url"] == "https://calendar.google.com/event?new"


def test_a_time_with_no_offset_is_in_the_notion_time_zone():
    event = _event("p", {"start": "2026-10-20T18:00:00.000", "end": None, "time_zone": "America/New_York"})

    assert event.start == {"dateTime": "2026-10-20T18:00:00", "timeZone": "America/New_York"}
    assert event.end["timeZone"] == "America/New_York"


def test_an_all_day_range_includes_its_last_day():
    event = _event("p", {"start": "2026-10-17", "end": "2026-10-19"})

    assert event.start == {"date": "2026-10-17"}
    assert event.end == {"date": "2026-10-20"}
