"""Feeds an org posts to Discord, the items each feed has already posted, and each run of a feed."""

from sqlalchemy import JSON, Boolean, Column, DateTime, ForeignKey, Integer, String, UniqueConstraint

from core.db import Base
from core.time import utcnow


class AlertFeed(Base):
    """One feed, such as a jobs list or hackathon listings, posted to one Discord alert destination."""

    __tablename__ = "alert_feeds"

    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    key = Column(String(63), nullable=False)
    kind = Column(String(32), nullable=False)
    config = Column(JSON, nullable=False, default=dict)
    every_hours = Column(Integer, nullable=False, default=3)
    enabled = Column(Boolean, nullable=False, default=True)
    # The alert destination (a row of webhooks) it posts to. Null for an older feed with an alert_webhook_<key> secret
    destination_id = Column(Integer, ForeignKey("webhooks.id"), nullable=True)
    seeded_at = Column(DateTime, nullable=True)  # first run, which records items without posting them
    last_run_at = Column(DateTime, nullable=True)
    last_error = Column(String(1000), nullable=True)
    created_at = Column(DateTime, nullable=False, default=utcnow)

    __table_args__ = (UniqueConstraint("organization_id", "key", name="uq_alert_feed_key"),)


class AlertPost(Base):
    """An item a feed has posted, or recorded on its first run. Items are never posted twice."""

    __tablename__ = "alert_posts"

    id = Column(Integer, primary_key=True)
    feed_id = Column(Integer, ForeignKey("alert_feeds.id", ondelete="CASCADE"), nullable=False)
    item_key = Column(String(255), nullable=False)
    title = Column(String(300), nullable=False)
    posted = Column(Boolean, nullable=False)  # false when recorded by the first run
    created_at = Column(DateTime, nullable=False, default=utcnow)

    __table_args__ = (UniqueConstraint("feed_id", "item_key", name="uq_alert_post_item"),)


class AlertRun(Base):
    """One run of a feed: what the source listed, what was new, what was posted, and the error if it failed."""

    __tablename__ = "alert_runs"

    id = Column(Integer, primary_key=True)
    feed_id = Column(Integer, ForeignKey("alert_feeds.id", ondelete="CASCADE"), nullable=False, index=True)
    started_at = Column(DateTime, nullable=False, default=utcnow)
    duration_ms = Column(Integer, nullable=False, default=0)
    found = Column(Integer, nullable=True)  # null when the source could not be read
    new = Column(Integer, nullable=True)
    posted = Column(Integer, nullable=False, default=0)
    recorded = Column(Boolean, nullable=False, default=False)  # first run: new items recorded, not posted
    error = Column(String(1000), nullable=True)
