# modules/calendar/models.py
import logging
from datetime import datetime
from dataclasses import dataclass, field # Added field
from typing import Dict, Optional, Any

from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Text, JSON
from sqlalchemy.orm import relationship
from modules.utils.base import Base

# Import helpers from the new utils module
from .utils import DateParser, extract_property, logger # Added logger import

# --- Data Transfer Object (DTO) ---

@dataclass
class CalendarEventDTO:
    """
    Model representing a calendar event for processing and API transfer.
    Uses data from Notion to prepare for Google Calendar.
    """
    summary: str
    start: Dict[str, str]
    end: Dict[str, str]
    notion_page_id: str # Made non-optional as it's crucial for linking
    gcal_id: Optional[str] = None # GCAL ID might not exist initially or be stored elsewhere
    location: Optional[str] = None
    description: Optional[str] = None
    # Add raw properties for potential debugging or future use
    raw_notion_properties: Dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_notion(cls, notion_event: Dict) -> Optional['CalendarEventDTO']:
        """Create CalendarEventDTO from raw Notion event data."""
        properties = notion_event.get('properties', {})
        notion_page_id = notion_event.get('id')

        if not notion_page_id:
             logger.error("Cannot create CalendarEventDTO: Notion event data missing 'id'.")
             return None

        # Extract core properties using the utility function
        summary = extract_property(properties, 'Name', 'title') # Assuming 'Name' is the title property
        location = extract_property(properties, 'Location', 'select') # Assuming 'Location' is a select property
        description = extract_property(properties, 'Description', 'rich_text') # Assuming 'Description' is rich text

        # Check if essential 'Name' property was extracted
        if not summary:
            logger.warning(f"Cannot create CalendarEventDTO for Notion page {notion_page_id}: Missing or empty 'Name' (title) property.")
            return None # Cannot create event without a summary/title

        # Parse dates using DateParser utility
        date_prop_raw = extract_property(properties, 'Date', 'date') # Extract the raw date object
        start_str = date_prop_raw.get('start') if date_prop_raw else None
        end_str = date_prop_raw.get('end') if date_prop_raw else None

        start_dict = DateParser.parse_notion_date(start_str)
        if not start_dict:
            logger.warning(f"Cannot create CalendarEventDTO for Notion page {notion_page_id}: Invalid or missing start date ('{start_str}').")
            return None  # Cannot create event without a valid start date

        # Parse end date string if it exists
        end_dict_parsed = DateParser.parse_notion_date(end_str)

        # Ensure a valid end date exists, calculating if necessary
        end_dict = DateParser.ensure_end_date(start_dict, end_dict_parsed)

        # Extract gcal_id if it exists in Notion (though sync logic primarily uses GCal's extended props now)
        gcal_id_from_notion = extract_property(properties, 'gcal_id', 'rich_text') # Assuming 'gcal_id' is rich text

        return cls(
            summary=summary,
            start=start_dict,
            end=end_dict,
            notion_page_id=notion_page_id,
            gcal_id=gcal_id_from_notion, # Store if found, but might not be reliable source
            location=location,
            description=description,
            raw_notion_properties=properties # Store raw properties
        )

    def to_gcal_format(self) -> Dict[str, Any]:
        """Convert to Google Calendar API event format."""
        gcal_event = {
            'summary': self.summary,
            'start': self.start,
            'end': self.end,
            'reminders': {"useDefault": True} # Add default reminders
        }

        if self.location:
            gcal_event['location'] = self.location

        if self.description:
            gcal_event['description'] = self.description

        # Note: extendedProperties (like notionPageId) are added by the GoogleCalendarClient
        # when calling create_event or update_event, not here.

        # Remove keys with None values before returning
        return {k: v for k, v in gcal_event.items() if v is not None}

    def to_frontend_format(self) -> Dict[str, Any]:
        """Convert to a format suitable for frontend display."""
        start_val = self.start.get('dateTime', self.start.get('date'))
        end_val = self.end.get('dateTime', self.end.get('date'))

        frontend_event = {
            'id': self.notion_page_id, # Use Notion page ID as the unique ID for frontend
            'title': self.summary,
            'start': start_val,
            'end': end_val,
            'location': self.location,
            'description': self.description,
            'gcal_id': self.gcal_id # Include gcal_id if available
            # Add any other fields needed by the frontend
        }

        # Remove keys with None values
        return {k: v for k, v in frontend_event.items() if v is not None}


# --- SQLAlchemy Database Models (Updated for Multi-Org Support) ---

class CalendarEventLink(Base):
    """Base model linking Notion and Google Calendar events in the DB."""
    __tablename__ = 'calendar_event_links'

    id = Column(Integer, primary_key=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    event_metadata = Column(JSON)  # Store additional metadata if needed

    # Organization relationship
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    organization = relationship("Organization", backref="calendar_events")

    # Foreign keys to link with Notion and Google Calendar specific data
    notion_page_id = Column(String(255), nullable=False, index=True)
    google_calendar_event_id = Column(String(255), nullable=True, index=True)
    
    # Calendar identifiers
    notion_database_id = Column(String(255), nullable=False)  # Which Notion database this event came from
    google_calendar_id = Column(String(255), nullable=False)  # Which Google Calendar this event is in

    def __repr__(self):
        return f"<CalendarEventLink(org_id={self.organization_id}, notion_id={self.notion_page_id})>"

    def to_dict(self):
        """Convert to dictionary."""
        return {
            "id": self.id,
            "organization_id": self.organization_id,
            "notion_page_id": self.notion_page_id,
            "google_calendar_event_id": self.google_calendar_event_id,
            "notion_database_id": self.notion_database_id,
            "google_calendar_id": self.google_calendar_id,
            "event_metadata": self.event_metadata,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }