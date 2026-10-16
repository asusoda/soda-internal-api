"""A calendar event read from a Notion page, in the formats Google Calendar and the website take."""

from dataclasses import dataclass, field
from typing import Any, Optional

from sentry_sdk import capture_exception, set_context

from core.log import get_logger

from .dates import DateParser

logger = get_logger(__name__)


def extract_property(properties: dict, name: str, prop_type: str) -> Any | None:
    """The value of the Notion page property name read as prop_type, or None if it is missing or unreadable.

    title and rich_text give the joined plain text, select gives the option name, date gives the raw
    {"start", "end", "time_zone"} object.
    """
    try:
        prop_data = properties.get(name)
        if not prop_data:
            return None

        if prop_type == "title":
            title_array = prop_data.get("title", [])
            if not isinstance(title_array, list):
                return None
            return "".join(item.get("plain_text", "") for item in title_array).strip() or None
        elif prop_type == "rich_text":
            rt_array = prop_data.get("rich_text", [])
            if not isinstance(rt_array, list):
                return None
            return "".join(item.get("plain_text", "") for item in rt_array).strip() or None
        elif prop_type == "select":
            select_obj = prop_data.get("select")
            return select_obj.get("name") if isinstance(select_obj, dict) else None
        elif prop_type == "checkbox":
            return prop_data.get("checkbox")
        elif prop_type == "date":
            return prop_data.get("date")
        elif prop_type == "number":
            return prop_data.get("number")
        elif prop_type == "url":
            return prop_data.get("url")
        elif prop_type == "email":
            return prop_data.get("email")
        elif prop_type == "phone_number":
            return prop_data.get("phone_number")
        else:
            logger.warning(f"Unhandled property type '{prop_type}' requested for property '{name}'.")
            return None

    except Exception as e:
        capture_exception(e)
        logger.error(f"Error extracting property '{name}' of type '{prop_type}': {str(e)}")
        set_context(
            "property_error",
            {"property_name": name, "property_type": prop_type, "raw_data": properties.get(name), "error": str(e)},
        )
        return None


@dataclass
class CalendarEventDTO:
    """An event from a Notion page, on its way to Google Calendar or the website."""

    summary: str
    start: dict[str, str]
    end: dict[str, str]
    notion_page_id: str
    gcal_id: str | None = None
    location: str | None = None
    description: str | None = None
    raw_notion_properties: dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_notion(cls, notion_event: dict) -> Optional["CalendarEventDTO"]:
        """The event of a Notion page, or None without an id, a Name or a valid start date.

        Reads the properties Name (title), Location (select), Description (rich text), Date and gcal_id (rich text).
        """
        properties = notion_event.get("properties", {})
        notion_page_id = notion_event.get("id")

        if not notion_page_id:
            logger.error("Cannot create CalendarEventDTO: Notion event data missing 'id'.")
            return None

        summary = extract_property(properties, "Name", "title")
        location = extract_property(properties, "Location", "select")
        description = extract_property(properties, "Description", "rich_text")

        if not summary:
            logger.warning(
                f"Cannot create CalendarEventDTO for Notion page {notion_page_id}: Missing or empty 'Name' (title) property."
            )
            return None

        date_prop_raw = extract_property(properties, "Date", "date")
        start_str = date_prop_raw.get("start") if date_prop_raw else None
        end_str = date_prop_raw.get("end") if date_prop_raw else None
        time_zone = date_prop_raw.get("time_zone") if date_prop_raw else None

        start_dict = DateParser.parse_notion_date(start_str, time_zone)
        if not start_dict:
            logger.warning(
                "Cannot create CalendarEventDTO for Notion page %s: Invalid or missing start date.",
                notion_page_id,
            )
            return None

        end_dict_parsed = DateParser.parse_notion_date(end_str, time_zone)
        end_dict = DateParser.ensure_end_date(start_dict, DateParser.exclusive_end(end_dict_parsed))

        gcal_id_from_notion = extract_property(properties, "gcal_id", "rich_text")

        return cls(
            summary=summary,
            start=start_dict,
            end=end_dict,
            notion_page_id=notion_page_id,
            gcal_id=gcal_id_from_notion,
            location=location,
            description=description,
            raw_notion_properties=properties,
        )

    def to_gcal_format(self) -> dict[str, Any]:
        """The event body for the Google Calendar API, without None values.

        The Google client adds the notionPageId extended property.
        """
        gcal_event = {
            "summary": self.summary,
            "start": self.start,
            "end": self.end,
            "reminders": {"useDefault": True},
        }

        if self.location:
            gcal_event["location"] = self.location

        if self.description:
            gcal_event["description"] = self.description

        return {k: v for k, v in gcal_event.items() if v is not None}

    def to_frontend_format(self) -> dict[str, Any]:
        """The event as the website shows it, keyed by the Notion page id, without None values."""
        start_val = self.start.get("dateTime", self.start.get("date"))
        end_val = self.end.get("dateTime", self.end.get("date"))

        frontend_event = {
            "id": self.notion_page_id,
            "title": self.summary,
            "start": start_val,
            "end": end_val,
            "location": self.location,
            "description": self.description,
            "gcal_id": self.gcal_id,
        }

        return {k: v for k, v in frontend_event.items() if v is not None}
