"""Alerts: the org's destinations (outbound webhooks) and the events each one gets. No Flask here.

core/webhooks.py has the table, the events and the delivery. A URL must match its kind and name a public
host. It is encrypted with SECRETS_KEY and no route returns it. Feeds post to a destination too; the listing
names them, so officers see every place that Platform sends to.
"""

from datetime import datetime
from typing import cast

from core import limits, net, secrets, webhooks
from core.errors import ServiceError
from core.time import utcnow
from modules.feeds import service as feeds
from modules.feeds.models import AlertFeed
from modules.organizations import service as organizations
from modules.organizations.models import Organization

WEBHOOKS_LIMIT = "alerts.destinations"
limits.declare(
    WEBHOOKS_LIMIT,
    "alerts",
    "Alert destinations",
    20,
    unit="destinations",
    usage=lambda db, org_id: db.query(webhooks.Webhook).filter_by(organization_id=org_id).count(),
)
MAX_IDS = 100  # ids in one bulk call
MAX_NAME = 100


class WebhookError(ServiceError, ValueError):
    pass


def _iso(value: object) -> str | None:
    return value.isoformat() if isinstance(value, datetime) else None


def _dict(row: webhooks.Webhook) -> dict:
    return {
        "id": row.id,
        "name": row.name,
        "kind": row.kind,
        "url_hint": row.url_hint,
        "events": list(cast(list[str], row.events) or []),
        "enabled": bool(row.enabled),
        "last_sent_at": _iso(row.last_sent_at),
        "last_error": row.last_error,
        "created_at": _iso(row.created_at),
        "created_by": row.created_by,
    }


def events(org: Organization) -> list[dict]:
    """The events an officer can pick: each event whose module is on for the org."""
    return [
        {"key": e.key, "label": e.label, "description": e.description, "module": e.module}
        for e in webhooks.EVENTS.values()
        if e.module is None or organizations.module_enabled(org, e.module)
    ]


def _feeds(db, org: Organization) -> list[dict]:
    return [
        {
            "key": f["key"],
            "kind": f["kind"],
            "enabled": f["enabled"],
            "destination_id": f["destination_id"],
            "webhook_set": f["webhook_set"],
            "last_run_at": f["last_run_at"],
            "last_error": f["last_error"],
        }
        for f in feeds.list_feeds(db, org.id)
    ]


def listing(db, org: Organization) -> dict:
    """The org's destinations, the events and kinds to pick from, and the org's feeds."""
    rows = db.query(webhooks.Webhook).filter_by(organization_id=org.id).order_by(webhooks.Webhook.name).all()
    return {
        "webhooks": [_dict(row) for row in rows],
        "events": events(org),
        "kinds": [{"key": k.key, "label": k.label, "example": k.example} for k in webhooks.KINDS.values()],
        "feeds": _feeds(db, org),
        "secrets_key": secrets.configured(),
    }


def _find(db, org: Organization, webhook_id: int) -> webhooks.Webhook:
    row = db.query(webhooks.Webhook).filter_by(organization_id=org.id, id=webhook_id).first()
    if row is None:
        raise WebhookError("No webhook with that id", 404)
    return row


def _name(value: object) -> str:
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > MAX_NAME:
        raise WebhookError(f"name must be text of 1 to {MAX_NAME} characters")
    return value.strip()


def _events(org: Organization, value: object) -> list[str]:
    known = [e["key"] for e in events(org)]
    if not isinstance(value, list) or not value or not all(isinstance(v, str) for v in value):
        raise WebhookError("events must be a list of one or more event keys")
    unknown = sorted(set(cast(list[str], value)) - set(known))
    if unknown:
        raise WebhookError(f"Unknown events: {', '.join(unknown)}")
    return [key for key in known if key in value]


def _url(kind: str, value: object) -> tuple[str, str]:
    """The encrypted URL and its hint. Raises when the URL does not match the kind or is not public."""
    destination = webhooks.KINDS[kind]
    if not isinstance(value, str) or not destination.pattern.match(value.strip()):
        raise WebhookError(f"Use a {destination.label} webhook URL: {destination.example}")
    url = value.strip()
    try:
        net.check_public(url)
    except ValueError as e:
        raise WebhookError(str(e)) from e
    ciphertext = secrets.encrypt(url)
    if ciphertext is None:
        raise WebhookError("SECRETS_KEY is not configured on this server")
    return ciphertext, destination.hint(url)


def _unique(db, org: Organization, name: str, webhook_id: int | None = None) -> None:
    other = db.query(webhooks.Webhook).filter_by(organization_id=org.id, name=name).first()
    if other is not None and other.id != webhook_id:
        raise WebhookError("Another webhook has that name", 409)


def create(db, org: Organization, body: dict, actor: str | None) -> dict:
    """Add a webhook. Commits."""
    kind = body.get("kind", "discord")
    if kind not in webhooks.KINDS:
        raise WebhookError(f"kind must be one of {', '.join(webhooks.KINDS)}")
    name = _name(body.get("name"))
    chosen = _events(org, body.get("events"))
    _unique(db, org, name)
    limits.check(db, org.id, WEBHOOKS_LIMIT)
    ciphertext, hint = _url(kind, body.get("url"))
    row = webhooks.Webhook(
        organization_id=org.id,
        name=name,
        kind=kind,
        url_ciphertext=ciphertext,
        url_hint=hint,
        events=chosen,
        enabled=body.get("enabled", True) is not False,
        created_by=actor,
    )
    db.add(row)
    db.commit()
    return _dict(row)


def update(db, org: Organization, webhook_id: int, body: dict) -> dict:
    """Change the name, URL, events or switch of a webhook. A missing key keeps its value. Commits."""
    row = _find(db, org, webhook_id)
    if "name" in body:
        name = _name(body["name"])
        _unique(db, org, name, webhook_id)
        row.name = name
    if "events" in body:
        row.events = _events(org, body["events"])
    if "enabled" in body:
        if not isinstance(body["enabled"], bool):
            raise WebhookError("enabled must be true or false")
        row.enabled = body["enabled"]
    if body.get("url") is not None:
        row.url_ciphertext, row.url_hint = _url(str(row.kind), body["url"])
        row.last_error = None
    db.commit()
    return _dict(row)


def delete(db, org: Organization, webhook_id: int) -> None:
    """Delete a destination. Refuses while a feed posts to it. Commits."""
    row = _find(db, org, webhook_id)
    used = [key for (key,) in db.query(AlertFeed.key).filter_by(organization_id=org.id, destination_id=webhook_id)]
    if used:
        raise WebhookError(f"Feeds post here: {', '.join(sorted(used))}. Give them another destination first", 409)
    db.delete(row)
    db.commit()


def send_test(db, org: Organization, webhook_id: int) -> dict:
    """Post a test message to the webhook now and save the result. Commits."""
    row = _find(db, org, webhook_id)
    url = secrets.decrypt(str(row.url_ciphertext))
    if url is None:
        return {"ok": False, "message": "The URL cannot be read with SECRETS_KEY. Save the URL again."}
    labels = {e.key: e.label for e in webhooks.EVENTS.values()}
    message = webhooks.Message(
        title=f"Test from {org.name}",
        text="This webhook works. It sends: " + ", ".join(labels.get(k, k) for k in row.events or []) + ".",
        color=webhooks.GREEN,
    )
    error = webhooks.post(str(row.kind), url, message)
    row.last_sent_at = utcnow()
    row.last_error = error
    db.commit()
    return {"ok": error is None, "message": error or "Sent. Look for the message in the channel."}
