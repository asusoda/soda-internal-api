"""MCP OAuth housekeeping."""

from core.db import db_connect
from core.jobs import job


@job("mcp.cleanup_oauth", cron="15 * * * *", audit=False)
def cleanup_oauth() -> None:
    """Delete expired OAuth requests, finished grants and unused clients. Runs hourly."""
    from core.log import get_logger
    from modules.mcp import oauth

    db = db_connect.SessionLocal()
    try:
        get_logger("mcp").info("mcp oauth cleanup %s", oauth.cleanup(db))
    finally:
        db.close()
