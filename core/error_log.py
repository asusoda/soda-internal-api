"""Error log: the errors of the API, bot, job worker, MCP server and dashboard, grouped and stored in the database.

ErrorLogHandler on the root logger records each log line at ERROR or above. Lines with the same fingerprint
(the source, the exception type and the first frame in this repo, or the logger and its message template)
add to one group. A new group, or a resolved group that comes back, calls the handlers added with
on_new_group(). Groups not seen for ERROR_RETENTION_DAYS (default 90) are deleted daily by error_log.prune.
No Flask here.
"""

import contextvars
import hashlib
import logging
import os
import platform
import socket
import sys
import threading
import traceback
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast

from sqlalchemy import JSON, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from core.db import Base, session
from core.jobs import current_job, job
from core.log import get_logger

logger = get_logger("error_log")

SOURCES = ("api", "bot", "worker", "mcp", "browser")
MAX_MESSAGE = 1000
MAX_STACK = 20_000
REPO_ROOT = str(Path(__file__).resolve().parent.parent)

# The org and route of the current API request, set by core/http/request_log.py
current_org: contextvars.ContextVar[str | None] = contextvars.ContextVar("error_log_org", default=None)
current_route: contextvars.ContextVar[str | None] = contextvars.ContextVar("error_log_route", default=None)
# The method and path of the current API request, without the query string
current_request: contextvars.ContextVar[str | None] = contextvars.ContextVar("error_log_request", default=None)

_new_group_handlers: list[Callable[[dict], None]] = []
_org_resolver: list[Callable[[str | None], str | None]] = []
_guard = threading.local()


class ErrorGroup(Base):
    __tablename__ = "error_groups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    source: Mapped[str] = mapped_column(String(20), nullable=False)  # api, bot, worker, mcp, browser
    # org prefix, or null for the whole server
    org: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    kind: Mapped[str] = mapped_column(String(200), nullable=False)  # exception type, or the logger name
    message: Mapped[str] = mapped_column(Text, nullable=False)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)  # file:function, or the dashboard page
    route: Mapped[str | None] = mapped_column(String(255), nullable=True)
    stack: Mapped[str | None] = mapped_column(Text, nullable=True)
    count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    first_seen: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=lambda: datetime.now(UTC))
    last_seen: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=lambda: datetime.now(UTC), index=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    resolved_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # where the last event ran: request, job, logger, line, host, release
    context: Mapped[Any | None] = mapped_column(JSON, nullable=True)

    def to_dict(self, stack: bool = True) -> dict:
        return {
            "id": self.id,
            "source": self.source,
            "org": self.org,
            "kind": self.kind,
            "message": self.message,
            "location": self.location,
            "route": self.route,
            "stack": self.stack if stack else None,
            "count": self.count,
            "first_seen": _iso(self.first_seen),
            "last_seen": _iso(self.last_seen),
            "resolved_at": _iso(self.resolved_at),
            "resolved_by": self.resolved_by,
            "context": self.context or {},
        }


def _iso(value: object) -> str | None:
    return value.isoformat() if isinstance(value, datetime) else None


def on_new_group(handler: Callable[[dict], None]) -> None:
    """Call handler with the group dict when a group is new or comes back after it was resolved."""
    if handler not in _new_group_handlers:
        _new_group_handlers.append(handler)


def set_org_resolver(resolver: Callable[[str | None], str | None]) -> None:
    """Map the org value of a request (a prefix, an org id or a guild id) to the org prefix."""
    _org_resolver[:] = [resolver]


def _fingerprint(*parts: str | None) -> str:
    return hashlib.sha256("\x1f".join(p or "" for p in parts).encode()).hexdigest()


def _repo_frame(tb: list[traceback.FrameSummary]) -> str | None:
    """file:function of the innermost frame in this repo, outside .venv, else of the innermost frame."""
    inside = [f for f in tb if f.filename.startswith(REPO_ROOT) and "/.venv/" not in f.filename]
    frame = (inside or tb or [None])[-1]
    if frame is None:
        return None
    return f"{os.path.relpath(frame.filename, REPO_ROOT)}:{frame.name}"


def _context(extra: dict | None) -> dict:
    """The process facts of the current event, and extra. Values are short strings; empty values are left out."""
    values = {
        "request": current_request.get(),
        "job": current_job.get(),
        "host": socket.gethostname(),
        "pid": os.getpid(),
        "thread": threading.current_thread().name,
        "release": (os.environ.get("GIT_COMMIT_HASH") or "")[:12],
        "python": platform.python_version(),
    } | (extra or {})
    return {k: v if isinstance(v, int) else str(v)[:255] for k, v in values.items() if v not in (None, "")}


def capture(
    *,
    source: str,
    kind: str,
    message: str,
    location: str | None = None,
    stack: str | None = None,
    org: str | None = None,
    route: str | None = None,
    group_key: str | None = None,
    context: dict | None = None,
) -> dict | None:
    """Add one error to its group and return the group, or None when the write fails. Never raises.

    group_key replaces the message in the fingerprint, so messages with ids in them still group together.
    """
    if getattr(_guard, "active", False):
        return None
    _guard.active = True
    try:
        source = source if source in SOURCES else "api"
        if org and _org_resolver:
            org = _org_resolver[0](org)
        fingerprint = _fingerprint(source, org, kind, location, group_key if group_key is not None else message)
        now = datetime.now(UTC)
        with session() as db:
            group = db.query(ErrorGroup).filter(ErrorGroup.fingerprint == fingerprint).first()
            fresh = group is None or group.resolved_at is not None
            if group is None:
                group = ErrorGroup(fingerprint=fingerprint, source=source, org=org, kind=kind[:200], count=0)
                group.first_seen = now
                db.add(group)
            group.count = cast(int, group.count or 0) + 1
            group.message = message[:MAX_MESSAGE]
            group.location = location[:255] if location else None
            group.route = route[:255] if route else None
            group.stack = stack[-MAX_STACK:] if stack else None
            group.last_seen = now
            group.resolved_at = None
            group.resolved_by = None
            group.context = _context(context)
            db.flush()
            result = group.to_dict()
        if fresh:
            for handler in list(_new_group_handlers):
                try:
                    handler(result)
                except Exception:
                    logger.warning("error_log handler failed handler=%s", getattr(handler, "__name__", handler))
        return result
    except Exception:
        logger.warning("error_log write failed kind=%s", kind)
        return None
    finally:
        _guard.active = False


class ErrorLogHandler(logging.Handler):
    """Records each log line at ERROR or above for one process."""

    def __init__(self, source: str) -> None:
        super().__init__(level=logging.ERROR)
        self.source = source

    def emit(self, record: logging.LogRecord) -> None:
        if record.name == logger.name:
            return
        try:
            message = record.getMessage()
            # logger.error inside an except block has no exc_info; the exception being handled is still known
            exc_info = record.exc_info if record.exc_info and record.exc_info[1] is not None else sys.exc_info()
            if exc_info[1] is not None:
                error = exc_info[1]
                tb = traceback.extract_tb(exc_info[2])
                kind = type(error).__name__
                location = _repo_frame(tb)
                stack = "".join(traceback.format_exception(*exc_info))
                text = f"{message}: {error}" if message else str(error)
                group_key = None if location else text
            else:
                kind = record.name
                location = f"{os.path.relpath(record.pathname, REPO_ROOT)}:{record.funcName}"
                stack = None
                text = message
                group_key = str(record.msg)
            capture(
                source=self.source,
                kind=kind,
                message=text,
                location=location,
                stack=stack,
                org=current_org.get(),
                route=current_route.get(),
                group_key=group_key,
                context={
                    "logger": record.name,
                    "line": f"{os.path.relpath(record.pathname, REPO_ROOT)}:{record.lineno}",
                },
            )
        except Exception:
            self.handleError(record)


def install(source: str) -> None:
    """Add the handler to the root logger once per process."""
    root = logging.getLogger()
    if not any(isinstance(h, ErrorLogHandler) for h in root.handlers):
        root.addHandler(ErrorLogHandler(source))


def list_groups(db, *, org: str | None = None, everything: bool = False, status: str = "open", limit: int = 50):
    """Groups newest first. org limits to one org; everything=True lists every org and the server-wide groups."""
    query = db.query(ErrorGroup)
    if not everything:
        query = query.filter(ErrorGroup.org == org)
    elif org:
        query = query.filter(ErrorGroup.org == org)
    if status == "open":
        query = query.filter(ErrorGroup.resolved_at.is_(None))
    elif status == "resolved":
        query = query.filter(ErrorGroup.resolved_at.isnot(None))
    rows = query.order_by(ErrorGroup.last_seen.desc()).limit(max(1, min(limit, 200))).all()
    return [row.to_dict() for row in rows]


def counts(db, *, org: str | None) -> dict:
    """Open groups and their events for one org."""
    rows = db.query(ErrorGroup).filter(ErrorGroup.org == org, ErrorGroup.resolved_at.is_(None)).all()
    return {"open": len(rows), "events": sum(cast(int, r.count or 0) for r in rows)}


def set_resolved(db, ids: list[int], *, resolved: bool, actor: str | None, org: str | None = None) -> int:
    """Resolve or reopen groups by id. With org, only that org's groups change. Returns the number changed."""
    query = db.query(ErrorGroup).filter(ErrorGroup.id.in_(ids))
    if org is not None:
        query = query.filter(ErrorGroup.org == org)
    changed = 0
    now = datetime.now(UTC)
    for group in query.all():
        group.resolved_at = now if resolved else None
        group.resolved_by = actor if resolved else None
        changed += 1
    db.commit()
    return changed


def delete_groups(db, ids: list[int], *, org: str | None = None) -> int:
    """Delete groups by id. With org, only that org's groups go. Returns the number deleted."""
    query = db.query(ErrorGroup).filter(ErrorGroup.id.in_(ids))
    if org is not None:
        query = query.filter(ErrorGroup.org == org)
    deleted = query.delete(synchronize_session=False)
    db.commit()
    return deleted


RETENTION_DAYS = int(os.environ.get("ERROR_RETENTION_DAYS", "90"))


@job("error_log.prune", cron="40 3 * * *", audit=False)
def prune() -> None:
    """Delete groups not seen for ERROR_RETENTION_DAYS."""
    cutoff = datetime.now(UTC) - timedelta(days=RETENTION_DAYS)
    with session() as db:
        deleted = db.query(ErrorGroup).filter(ErrorGroup.last_seen < cutoff).delete()
    logger.info("error_log pruned groups=%s", deleted)
