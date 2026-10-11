"""Outbound webhooks: the events that modules send, the webhooks that officers add, and the delivery of each event.

A module declares its events with declare() and sends one with emit(). emit() returns at once: a daemon thread
saves the event as a notification of the org, then finds the enabled webhooks of the org that take the event
and posts the message to each. The org keeps the notifications of the last KEEP_DAYS days, at most KEEP_COUNT. A kind (Discord now)
checks the URL and formats the message. URLs are encrypted with SECRETS_KEY, and no log line or error has one.
Each process sends at most LIMIT_PER_HOUR messages for each org and event in an hour. No Flask here.
"""

import re
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from typing import cast

import requests
from sqlalchemy import JSON, Boolean, Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, column
from sqlalchemy import table as sql_table

from core import secrets
from core.db import Base, session
from core.log import get_logger
from core.time import utcnow

logger = get_logger("webhooks")

LIMIT_PER_HOUR = 30
KEEP_DAYS = 30
KEEP_COUNT = 200
TIMEOUT_SECONDS = 10
RED = 0xE5484D
GREEN = 0x30A46C
BLUE = 0x3E63DD
AMBER = 0xF5A524


@dataclass(frozen=True)
class Event:
    key: str
    label: str
    description: str
    # The optional module that sends the event. The event is listed only when the org has the module on.
    module: str | None = None


@dataclass(frozen=True)
class Message:
    """One event as text. Each kind turns it into the body its service reads."""

    title: str
    text: str = ""
    fields: tuple[tuple[str, str], ...] = ()
    url: str | None = None
    color: int = BLUE
    footer: str | None = None


@dataclass(frozen=True)
class Kind:
    key: str
    label: str
    pattern: re.Pattern
    example: str
    format: Callable[[Message], dict]
    hint: Callable[[str], str]


EVENTS: dict[str, Event] = {}


def declare(key: str, label: str, description: str, module: str | None = None) -> None:
    """Add an event that officers can pick for a webhook."""
    EVENTS[key] = Event(key, label, description, module)


def _discord(message: Message) -> dict:
    embed: dict = {
        "title": message.title[:256],
        "description": message.text[:1500],
        "color": message.color,
        "fields": [{"name": n[:256], "value": (v or "-")[:1024], "inline": len(v) < 40} for n, v in message.fields],
    }
    if message.url:
        embed["url"] = message.url
    if message.footer:
        embed["footer"] = {"text": message.footer[:2048]}
    return {"embeds": [embed], "allowed_mentions": {"parse": []}}


def _discord_hint(url: str) -> str:
    """The host and the last 4 digits of the webhook id. The token is not in it."""
    match = re.match(r"^https://([\w.]+)/api/webhooks/(\d+)/", url)
    return f"{match.group(1)} ...{match.group(2)[-4:]}" if match else "discord.com"


KINDS: dict[str, Kind] = {
    "discord": Kind(
        key="discord",
        label="Discord",
        pattern=re.compile(r"^https://(?:discord|discordapp)\.com/api/webhooks/\d+/[\w-]+$"),
        example="https://discord.com/api/webhooks/...",
        format=_discord,
        hint=_discord_hint,
    ),
}


class Webhook(Base):
    """One destination of an org and the events it gets. The URL is encrypted with SECRETS_KEY."""

    __tablename__ = "webhooks"

    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    kind = Column(String(20), nullable=False)
    url_ciphertext = Column(Text, nullable=False)
    url_hint = Column(String(100), nullable=False)
    events = Column(JSON, nullable=False, default=list)
    enabled = Column(Boolean, nullable=False, default=True)
    last_sent_at = Column(DateTime, nullable=True)
    last_error = Column(String(500), nullable=True)
    created_at = Column(DateTime, nullable=False, default=utcnow)
    created_by = Column(String(255), nullable=True)

    __table_args__ = (UniqueConstraint("organization_id", "name", name="uq_webhook_name"),)


class Notification(Base):
    """One event that an org's officers see in Notifications, whether or not a webhook takes it."""

    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    event = Column(String(50), nullable=False)
    title = Column(String(256), nullable=False)
    text = Column(Text, nullable=False, default="")
    color = Column(Integer, nullable=False, default=BLUE)
    created_at = Column(DateTime, nullable=False, default=utcnow, index=True)


declare("job.failed", "Failed job runs", "A background job for the org fails, such as a crawl or a reindex.")

_organizations = sql_table("organizations", column("id"), column("prefix"), column("config", JSON))
_sent: dict[tuple[int | str, str], list[float]] = {}
_sent_lock = threading.Lock()


def _allow(org: int | str, event: str) -> bool:
    now = time.monotonic()
    with _sent_lock:
        times = [t for t in _sent.get((org, event), []) if now - t < 3600]
        allowed = len(times) < LIMIT_PER_HOUR
        if allowed:
            times.append(now)
        _sent[(org, event)] = times
        return allowed


def _thread(target: Callable, *args) -> threading.Thread:
    thread = threading.Thread(target=target, args=args, name="webhooks", daemon=True)
    thread.start()
    return thread


# Starts the delivery. Tests replace it to deliver in the test thread.
spawn: Callable[..., object] = _thread


def emit(org: int | str | None, event: str, message: Message) -> None:
    """Send the event to the org's webhooks in the background. org is an org id or prefix. Never raises."""
    if org is None or org == "":
        return
    if event not in EVENTS:
        logger.warning("webhook event not declared event=%s", event)
        return
    try:
        spawn(save, org, event, message)
    except Exception:
        logger.warning("notification save did not start event=%s", event)
    if not _allow(org, event):
        logger.info("webhook event over the hourly limit org=%s event=%s", org, event)
        return
    try:
        spawn(deliver, org, event, message)
    except Exception:
        logger.warning("webhook delivery did not start event=%s", event)


def _org_id(db, org: int | str) -> int | None:
    if isinstance(org, int):
        return org
    row = db.execute(_organizations.select().where(_organizations.c.prefix == org)).first()
    return int(row.id) if row is not None else None


def save(org: int | str, event: str, message: Message) -> None:
    """Save the event as a notification of the org and drop the org's old ones. Never raises."""
    try:
        with session() as db:
            org_id = _org_id(db, org)
            if org_id is None:
                return
            text = "\n".join([message.text, *(f"{name}: {value}" for name, value in message.fields)]).strip()
            db.add(
                Notification(
                    organization_id=org_id,
                    event=event,
                    title=message.title[:256],
                    text=text[:2000],
                    color=message.color,
                )
            )
            db.flush()
            mine = db.query(Notification).filter_by(organization_id=org_id)
            mine.filter(Notification.created_at < utcnow() - timedelta(days=KEEP_DAYS)).delete()
            kept = [
                i for (i,) in mine.order_by(Notification.id.desc()).with_entities(Notification.id).limit(KEEP_COUNT)
            ]
            mine.filter(Notification.id.notin_(kept)).delete(synchronize_session=False)
            db.commit()
    except Exception:
        logger.warning("notification save failed event=%s", event)


def post(kind: str, url: str, message: Message) -> str | None:
    """Send one message. Returns None when the service took it, else an error with no URL in it."""
    destination = KINDS.get(kind)
    if destination is None:
        return f"Unknown webhook kind {kind}"
    try:
        response = requests.post(url, json=destination.format(message), timeout=TIMEOUT_SECONDS, allow_redirects=False)
    except requests.RequestException as e:
        return f"Could not reach {destination.label}: {type(e).__name__}"
    if response.status_code >= 400:
        return f"{destination.label} refused the message with status {response.status_code}"
    return None


def deliver(org: int | str, event: str, message: Message) -> int:
    """Post the message to each enabled webhook of the org that takes the event. Returns the number sent."""
    try:
        with session() as db:
            org_id = _org_id(db, org)
            if org_id is None:
                return 0
            rows = db.query(Webhook).filter_by(organization_id=org_id, enabled=True).all()
            targets = [
                (cast(int, row.id), str(row.kind), url)
                for row in rows
                if event in (row.events or []) and (url := secrets.decrypt(str(row.url_ciphertext)))
            ]
        results = {webhook_id: post(kind, url, message) for webhook_id, kind, url in targets}
        if results:
            record(results)
        return sum(1 for error in results.values() if error is None)
    except Exception:
        logger.warning("webhook delivery failed event=%s", event)
        return 0


def record(results: dict[int, str | None]) -> None:
    """Save the time and the error of the last message of each webhook."""
    with session() as db:
        for row in db.query(Webhook).filter(Webhook.id.in_(list(results))).all():
            error = results[cast(int, row.id)]
            row.last_sent_at = utcnow()
            row.last_error = error[:500] if error else None
            if error:
                logger.warning("webhook send failed webhook=%s error=%s", row.id, error)
