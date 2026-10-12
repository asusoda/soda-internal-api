"""Calendar tools."""

from core.tools import ToolError, tool
from modules.calendar import service


@tool(
    "events.list",
    description="The org's published calendar events, past and upcoming: title, start, end, location, description.",
    scope="calendar:read",
    module="calendar",
)
def events_list(db, org, caller):
    result = service.list_events(db, org)
    if isinstance(result, dict) and result.get("status") == "error":
        raise ToolError(str(result.get("message", "Calendar unavailable")), 502)
    return {"events": result.get("events", [])}


@tool(
    "calendar.settings",
    description="The org's Notion events database, Google Calendar, sync switch and last sync time.",
    scope="calendar:read",
    module="calendar",
)
def calendar_settings(db, org, caller):
    return {"settings": service.calendar_settings(org)}


@tool(
    "calendar.update_settings",
    description="Change the Notion database, the Google Calendar or the sync switch. An empty id clears it.",
    scope="calendar:manage",
    module="calendar",
    input_schema={
        "type": "object",
        "properties": {
            "notion_database_id": {"type": ["string", "null"], "maxLength": 200},
            "google_calendar_id": {"type": ["string", "null"], "maxLength": 300},
            "calendar_sync_enabled": {"type": "boolean"},
        },
        "minProperties": 1,
        "additionalProperties": False,
    },
)
def calendar_update_settings(db, org, caller, **data):
    return {"settings": service.save_calendar_settings(db, org, data)}


@tool(
    "calendar.sync",
    description="Copy the org's Notion events to its Google Calendar now.",
    scope="calendar:manage",
    module="calendar",
)
def calendar_sync(db, org, caller):
    result = service.sync_organization(db, org)
    if result.get("status") == "error":
        raise ToolError(str(result.get("message", "Calendar sync failed")), 502)
    return result


@tool(
    "calendar.setup",
    description="Make the org's Google Calendar if it has none, and return its id.",
    scope="calendar:manage",
    module="calendar",
)
def calendar_setup(db, org, caller):
    calendar_id = service.setup_calendar(db, org)
    if not calendar_id:
        raise ToolError("Failed to set up calendar", 502)
    return {"calendar_id": calendar_id}
