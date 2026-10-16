"""Running feeds on their schedules and on request."""

from core.db import db_connect
from core.jobs import job


@job("feeds.run_due", cron="*/15 * * * *", audit=False)
def run_due() -> None:
    """Run every enabled feed whose every_hours has passed since its last run."""
    from modules.feeds import service

    db = db_connect.SessionLocal()
    try:
        service.run_due(db)
    finally:
        db.close()


@job("feeds.run_feed", once=("org_id", "key"))
def run_feed(org_id: int, key: str, post_existing: bool = False, org_prefix: str | None = None) -> None:
    """Run one feed now, on request."""
    from modules.feeds import service

    db = db_connect.SessionLocal()
    try:
        service.run_now(db, org_id, key, post_existing=post_existing)
    finally:
        db.close()
