"""Feeds an org posts to Discord, the items each feed has already posted, and each run of a feed."""

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from core.db import Base
from core.time import utcnow


class AlertFeed(Base):
    """One feed, such as a jobs list or hackathon listings, posted to one Discord alert destination."""

    __tablename__ = "alert_feeds"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(Integer, ForeignKey("organizations.id"), nullable=False)
    key: Mapped[str] = mapped_column(String(63), nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    config: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    every_hours: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # The alert destination (a row of webhooks) it posts to. Null for an older feed with an alert_webhook_<key> secret
    destination_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("webhooks.id"), nullable=True)
    # first run, which records items without posting them
    seeded_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_error: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)

    __table_args__ = (UniqueConstraint("organization_id", "key", name="uq_alert_feed_key"),)


class AlertPost(Base):
    """An item a feed has posted, or recorded on its first run. Items are never posted twice."""

    __tablename__ = "alert_posts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    feed_id: Mapped[int] = mapped_column(Integer, ForeignKey("alert_feeds.id", ondelete="CASCADE"), nullable=False)
    item_key: Mapped[str] = mapped_column(String(255), nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    posted: Mapped[bool] = mapped_column(Boolean, nullable=False)  # false when recorded by the first run
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)

    __table_args__ = (UniqueConstraint("feed_id", "item_key", name="uq_alert_post_item"),)


class AlertRun(Base):
    """One run of a feed: what the source listed, what was new, what was posted, and the error if it failed."""

    __tablename__ = "alert_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    feed_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("alert_feeds.id", ondelete="CASCADE"), nullable=False, index=True
    )
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    found: Mapped[int | None] = mapped_column(Integer, nullable=True)  # null when the source could not be read
    new: Mapped[int | None] = mapped_column(Integer, nullable=True)
    posted: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # first run: new items recorded, not posted
    recorded: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    error: Mapped[str | None] = mapped_column(String(1000), nullable=True)
