"""Make a Google Calendar match the events read from Notion."""

from .clients import GoogleCalendarClient
from .events import CalendarEventDTO
from .tracing import operation_span


def _notion_page_id(event: dict):
    return event.get("extendedProperties", {}).get("private", {}).get("notionPageId")


def event_links(gcal: GoogleCalendarClient, calendar_id: str, time_min: str, parent_transaction=None) -> dict[str, str]:
    """The Google Calendar link of each event that the sync made and that ends after time_min, by Notion page id.

    Empty if Google fails.
    """
    links: dict[str, str] = {}
    events = gcal.get_all_events(calendar_id, time_min=time_min, parent_transaction=parent_transaction)
    for event in events or []:
        notion_page_id = _notion_page_id(event)
        link = event.get("htmlLink")
        if notion_page_id and link:
            links.setdefault(notion_page_id, link)
    return links


def update_google_calendar(
    gcal: GoogleCalendarClient,
    parsed_events: list[CalendarEventDTO],
    calendar_id: str,
    parent_transaction,
    logger,
) -> list[dict]:
    """Create or update a Google event for each Notion event, then delete duplicates and orphans.

    Only Google events with a notionPageId extended property are managed. Of several events for one
    Notion page, the first is kept. Returns one result per created or updated event, or [] when the
    Google events cannot be read.
    """
    results = []
    op_name = "update_organization_google_calendar"
    logger.info(f"Starting {op_name} with {len(parsed_events)} parsed Notion events for calendar {calendar_id}.")

    with operation_span(
        parent_transaction, op="fetch_gcal", description="fetch_existing_gcal_events", logger=logger
    ) as span:
        all_gcal_events_raw = gcal.get_all_events(calendar_id, time_min=None, parent_transaction=parent_transaction)
        if all_gcal_events_raw is None:
            logger.error(f"{op_name}: Failed to fetch existing Google Calendar events. Aborting update.")
            return []

        managed_gcal_events = [ev for ev in all_gcal_events_raw if _notion_page_id(ev)]
        span.set_data("fetched_total_gcal_event_count", len(all_gcal_events_raw))
        span.set_data("fetched_managed_gcal_event_count", len(managed_gcal_events))
        logger.info(
            f"Fetched {len(managed_gcal_events)} managed GCal events (out of {len(all_gcal_events_raw)} total)."
        )

    gcal_events_by_gcal_id: dict[str, dict] = {}
    gcal_events_by_notion_id: dict[str, dict] = {}
    duplicates_to_delete: set[str] = set()

    with operation_span(
        parent_transaction,
        op="process_gcal",
        description="build_gcal_lookups_handle_duplicates",
        logger=logger,
    ) as span:
        temp_gcal_by_notion_id: dict[str, list[dict]] = {}

        for event in managed_gcal_events:
            gcal_id = event.get("id")
            notion_page_id = _notion_page_id(event)

            if gcal_id:
                gcal_events_by_gcal_id[gcal_id] = event

            if notion_page_id:
                temp_gcal_by_notion_id.setdefault(notion_page_id, []).append(event)

        for notion_id, events in temp_gcal_by_notion_id.items():
            if len(events) > 1:
                logger.warning(f"Found {len(events)} duplicate events for Notion page {notion_id}")
                gcal_events_by_notion_id[notion_id] = events[0]
                for duplicate_event in events[1:]:
                    duplicates_to_delete.add(duplicate_event["id"])
            else:
                gcal_events_by_notion_id[notion_id] = events[0]

        span.set_data("duplicates_found", len(duplicates_to_delete))

    for event_dto in parsed_events:
        result = _write_event(gcal, event_dto, gcal_events_by_notion_id, calendar_id, parent_transaction)
        if result:
            results.append(result)

    if duplicates_to_delete:
        with operation_span(
            parent_transaction, op="cleanup", description="delete_duplicate_events", logger=logger
        ) as span:
            deleted_count, failed_count = gcal.batch_delete_events(
                calendar_id, list(duplicates_to_delete), "delete_duplicates", parent_transaction
            )
            span.set_data("duplicates_deleted", deleted_count)
            span.set_data("duplicates_failed", failed_count)
            logger.info(f"Cleaned up {deleted_count} duplicate events, {failed_count} failed.")

    # Managed Google events whose Notion page is not in the parsed events
    synced_page_ids = {event_dto.notion_page_id for event_dto in parsed_events}
    orphaned_events = {
        gcal_id for gcal_id, event in gcal_events_by_gcal_id.items() if _notion_page_id(event) not in synced_page_ids
    } - duplicates_to_delete
    if orphaned_events:
        with operation_span(
            parent_transaction, op="cleanup", description="delete_orphaned_events", logger=logger
        ) as span:
            deleted_count, failed_count = gcal.batch_delete_events(
                calendar_id, list(orphaned_events), "delete_orphaned", parent_transaction
            )
            span.set_data("orphaned_deleted", deleted_count)
            span.set_data("orphaned_failed", failed_count)
            logger.info(f"Cleaned up {deleted_count} orphaned events, {failed_count} failed.")

    return results


def _write_event(
    gcal: GoogleCalendarClient,
    event_dto: CalendarEventDTO,
    gcal_events_by_notion_id: dict[str, dict],
    calendar_id: str,
    parent_transaction,
) -> dict | None:
    """Update the Google event of this Notion page, or create one. The result, or None if the write failed."""
    notion_page_id = event_dto.notion_page_id
    existing_gcal_event = gcal_events_by_notion_id.get(notion_page_id)

    event_data = event_dto.to_gcal_format()

    if existing_gcal_event:
        gcal_event_id = existing_gcal_event["id"]
        result = gcal.update_event(calendar_id, gcal_event_id, event_data, notion_page_id, parent_transaction)
        if result:
            return {
                "notion_page_id": notion_page_id,
                "gcal_event_id": gcal_event_id,
                "status": "updated",
                "summary": event_dto.summary,
            }
    else:
        result = gcal.create_event(calendar_id, event_data, notion_page_id, parent_transaction)
        if result:
            jump_url, gcal_event_id = result
            return {
                "notion_page_id": notion_page_id,
                "gcal_event_id": gcal_event_id,
                "status": "created",
                "summary": event_dto.summary,
                "jump_url": jump_url,
            }

    return None
