"""The calendar table. The event dataclass is in events.py."""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.db import Base


class CalendarEventLink(Base):
    """Table kept for schema compatibility; no code reads it."""

    __tablename__ = "calendar_event_links"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime | None] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC)
    )
    event_metadata: Mapped[Any | None] = mapped_column(JSON)

    organization_id: Mapped[int] = mapped_column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    organization = relationship("Organization", backref="calendar_events")

    notion_page_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    google_calendar_event_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)

    # The Notion database the event came from and the Google Calendar it is in
    notion_database_id: Mapped[str] = mapped_column(String(255), nullable=False)
    google_calendar_id: Mapped[str] = mapped_column(String(255), nullable=False)

    def __repr__(self):
        return f"<CalendarEventLink(org_id={self.organization_id}, notion_id={self.notion_page_id})>"

    def to_dict(self):
        """The row as a dict with ISO timestamps."""
        return {
            "id": self.id,
            "organization_id": self.organization_id,
            "notion_page_id": self.notion_page_id,
            "google_calendar_event_id": self.google_calendar_event_id,
            "notion_database_id": self.notion_database_id,
            "google_calendar_id": self.google_calendar_id,
            "event_metadata": self.event_metadata,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
