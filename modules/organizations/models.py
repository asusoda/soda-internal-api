from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.db import Base


class Organization(Base):
    """Model representing a Discord organization/guild."""

    __tablename__ = "organizations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    # URL-friendly prefix for the organization
    prefix: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)

    guild_id: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(String(500))
    icon_url: Mapped[str | None] = mapped_column(String(255))
    is_active: Mapped[bool | None] = mapped_column(Boolean, default=True)
    config: Mapped[dict[str, Any] | None] = mapped_column(JSON, default=dict)  # Store organization-specific settings
    created_at: Mapped[datetime | None] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC)
    )
    # Changed to String since Discord role IDs are strings
    officer_role_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    points_per_message: Mapped[int | None] = mapped_column(Integer, default=1)  # Default points per message
    points_cooldown: Mapped[int | None] = mapped_column(Integer, default=60)  # Default cooldown in seconds

    # Calendar-related fields
    # Google Calendar ID for this org
    google_calendar_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Notion database ID for this org
    notion_database_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Whether calendar sync is enabled
    calendar_sync_enabled: Mapped[bool | None] = mapped_column(Boolean, default=False)
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)  # Last successful sync timestamp

    def __repr__(self):
        return f"<Organization(name='{self.name}', guild_id='{self.guild_id}')>"

    def to_dict(self):
        """Convert organization to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "prefix": self.prefix,
            "guild_id": self.guild_id,
            "description": self.description,
            "icon_url": self.icon_url,
            "is_active": self.is_active,
            "config": self.config,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "officer_role_id": self.officer_role_id,
            "points_per_message": self.points_per_message,
            "points_cooldown": self.points_cooldown,
            "google_calendar_id": self.google_calendar_id,
            "notion_database_id": self.notion_database_id,
            "calendar_sync_enabled": self.calendar_sync_enabled,
            "last_sync_at": self.last_sync_at.isoformat() if self.last_sync_at else None,
        }


class OrganizationConfig(Base):
    """Table kept for schema compatibility; no code reads it."""

    __tablename__ = "organization_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(Integer, ForeignKey("organizations.id"), nullable=False)
    key: Mapped[str] = mapped_column(String(100), nullable=False)
    value: Mapped[Any] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime | None] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC)
    )

    organization = relationship("Organization", backref="configurations")

    def __repr__(self):
        return f"<OrganizationConfig(org_id={self.organization_id}, key='{self.key}')>"

    def to_dict(self):
        """Convert config to dictionary."""
        return {
            "id": self.id,
            "organization_id": self.organization_id,
            "key": self.key,
            "value": self.value,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class Officer(Base):
    """Table kept for schema compatibility; no code reads it."""

    __tablename__ = "officers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(Integer, ForeignKey("organizations.id"), nullable=False)
    user_id: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at: Mapped[datetime | None] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC)
    )

    organization = relationship("Organization", backref="officers")
