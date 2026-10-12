"""Uptime monitors of an org and the result of each check."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from core.db import Base
from core.time import utcnow


class UptimeMonitor(Base):
    """One address that the org checks on a schedule: a public URL, or the health URL of a Hosting app."""

    __tablename__ = "uptime_monitors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(Integer, ForeignKey("organizations.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    target_kind: Mapped[str] = mapped_column(String(16), nullable=False)  # url or app
    target: Mapped[str] = mapped_column(String(500), nullable=False)  # the URL, or the name of an app in runpod_apps
    # 2xx, or one status code such as 204
    expected_status: Mapped[str] = mapped_column(String(8), nullable=False, default="2xx")
    timeout_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    interval_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    state: Mapped[str | None] = mapped_column(String(8), nullable=True)  # up, down, or null before the first check
    state_since: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)

    __table_args__ = (UniqueConstraint("organization_id", "name", name="uq_uptime_monitor_name"),)


class UptimeCheck(Base):
    """One check of a monitor. The uptime.prune job deletes checks older than UPTIME_RETENTION_DAYS."""

    __tablename__ = "uptime_checks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    monitor_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("uptime_monitors.id", ondelete="CASCADE"), nullable=False
    )
    checked_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)
    up: Mapped[bool] = mapped_column(Boolean, nullable=False)
    status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)  # null when no response came back
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error: Mapped[str | None] = mapped_column(String(500), nullable=True)

    __table_args__ = (
        Index("ix_uptime_checks_monitor", "monitor_id", "checked_at"),
        Index("ix_uptime_checks_checked_at", "checked_at"),
    )
