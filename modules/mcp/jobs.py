"""MCP OAuth housekeeping."""

from core.db import db_connect
from core.jobs import job


@job("mcp.cleanup_oauth", cron="15 * * * *", audit=False)
def cleanup_oauth() -> None:
    """Delete expired OAuth requests, finished grants, unused clients and the jti of expired assertions. Runs hourly."""
    from core.log import get_logger
    from modules.mcp import client_auth, oauth

    db = db_connect.SessionLocal()
    try:
        result = oauth.cleanup(db) | {"assertions": client_auth.cleanup(db)}
        get_logger("mcp").info("mcp oauth cleanup %s", result)
    finally:
        db.close()
