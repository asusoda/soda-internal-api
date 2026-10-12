"""Notifications for officers: the problems an org has now, the events it had, and which ones an officer resolved.

A problem is a current state: an enabled feed whose last run failed, an app whose latest deploy failed,
or a crawled knowledge source whose last fetch failed. Its id is a hash of the module, the subject and the
message, so a new error on the same subject is a new notification. An event is one webhook event of the org
(core/webhooks.py saves each one): an error, a failed job, a pod started or stopped, a deploy, a store order,
a new member. Its id is event-<row id>. Resolved ids are in the org config key dashboard.resolved. When a
problem goes away or an event is dropped or deleted, its id is removed at the next resolve or reopen.
"""

import hashlib
from typing import cast

from sqlalchemy.orm.attributes import flag_modified

from core import webhooks
from core.errors import ServiceError
from core.time import iso, utcnow
from modules.feeds import service as feeds
from modules.feeds.models import AlertFeed
from modules.knowledge.models import KnowledgeSource
from modules.organizations.models import Organization
from modules.runpod.models import App, AppDeployment

MAX_KNOWLEDGE = 200
MAX_EVENTS = 200
# The page that shows each event, relative to /<org>/
EVENT_LINKS = {
    "errors": "activity?tab=errors",
    "job.failed": "activity?tab=knowledge",
    "knowledge.crawl_failed": "activity?tab=knowledge",
    "pod.started": "godfather",
    "pod.stopped": "godfather",
    "app.deployed": "hosting",
    "order.created": "store",
    "member.joined": "points",
    "asu.session_expired": "explore?tab=shared",
    "monitor.down": "uptime",
    "monitor.up": "uptime",
}
# The module label of each event in the dashboard
EVENT_MODULES = {
    "errors": "errors",
    "job.failed": "jobs",
    "pod.started": "godfather",
    "pod.stopped": "godfather",
    "monitor.down": "uptime",
    "monitor.up": "uptime",
}
# The dashboard page of each kind of feed
FEED_PAGES = {"github_jobs": "job-alerts", "hackathons": "hackathons"}
ERROR_COLORS = (webhooks.RED, webhooks.AMBER)
MAX_IDS = 500


class NoticeError(ServiceError):
    """A refused change to notifications."""


def notice_id(module: str, subject: str, message: str) -> str:
    """The id of a notification: the same problem with the same message keeps its id."""
    return hashlib.sha256(f"{module}\0{subject}\0{message}".encode()).hexdigest()[:20]


def _notice(module: str, subject: str, message: str, link: str) -> dict:
    return {
        "id": notice_id(module, subject, message),
        "module": module,
        "subject": subject,
        "message": message,
        "link": link,
        "kind": "problem",
        "level": "error",
        "at": None,
    }


def _event(row: webhooks.Notification) -> dict:
    event = str(row.event)
    module = EVENT_MODULES.get(event) or event.split(".")[0]
    return {
        "id": f"event-{row.id}",
        "module": module,
        "subject": str(row.title),
        "message": str(row.text or ""),
        "link": EVENT_LINKS.get(event, ""),
        "kind": "event",
        "level": "error" if row.color in ERROR_COLORS else "info",
        "at": iso(row.created_at),
    }


def events(db, org_id: int) -> list[dict]:
    """The org's saved webhook events, newest first."""
    rows = (
        db.query(webhooks.Notification)
        .filter_by(organization_id=org_id)
        .order_by(webhooks.Notification.id.desc())
        .limit(MAX_EVENTS)
    )
    return [_event(row) for row in rows]


def current(db, org_id: int) -> list[dict]:
    """Every notification of the org: problems first, then events, newest first."""
    return problems(db, org_id) + events(db, org_id)


def problems(db, org_id: int) -> list[dict]:
    """Every current problem of the org, feeds first, then apps, then knowledge."""
    found = []
    on = feeds.kinds_on(db, org_id)
    rows = (
        db.query(AlertFeed)
        .filter_by(organization_id=org_id, enabled=True)
        .filter(AlertFeed.last_error.isnot(None))
        .order_by(AlertFeed.key)
    )
    for f in rows:
        if f.kind in on:
            module = feeds.KIND_MODULES[str(f.kind)]
            found.append(_notice(module, cast(str, f.key), cast(str, f.last_error), FEED_PAGES[str(f.kind)]))
    for app in db.query(App).filter_by(organization_id=org_id).order_by(App.name):
        latest = db.query(AppDeployment).filter_by(app_id=app.id).order_by(AppDeployment.started_at.desc()).first()
        if latest and latest.status == "failed":
            found.append(_notice("apps", cast(str, app.name), cast(str, latest.error or "Deploy failed"), "apps"))
    sources = (
        db.query(KnowledgeSource)
        .filter_by(organization_id=org_id)
        .filter(KnowledgeSource.fetch_every_hours.isnot(None), KnowledgeSource.last_error.isnot(None))
        .order_by(KnowledgeSource.key)
        .limit(MAX_KNOWLEDGE)
    )
    found += [_notice("knowledge", cast(str, s.key), (s.last_error or "")[:300], "knowledge") for s in sources]
    return found


def _resolved(org: Organization) -> dict[str, dict]:
    config = cast(dict, org.config) or {}
    entries = (config.get("dashboard") or {}).get("resolved") or []
    return {e["id"]: e for e in entries if isinstance(e, dict) and "id" in e}


def unresolved(org: Organization, found: list[dict]) -> list[dict]:
    """The notifications in found that no officer marked resolved."""
    resolved = _resolved(org)
    return [p for p in found if p.get("id", notice_id(p["module"], p["subject"], p["message"])) not in resolved]


def listing(db, org: Organization) -> dict:
    """Open and resolved notifications of the org, with who resolved each one and when."""
    resolved = _resolved(org)
    notices = []
    for p in current(db, org.id):
        entry = resolved.get(p["id"])
        notices.append(
            p | {"resolved_at": entry.get("at") if entry else None, "resolved_by": entry.get("by") if entry else None}
        )
    return {"notifications": notices, "open": sum(1 for n in notices if not n["resolved_at"])}


def _ids(value: object) -> list[str]:
    if not isinstance(value, list) or not value or len(value) > MAX_IDS or not all(isinstance(i, str) for i in value):
        raise NoticeError(f"ids must be a list of 1 to {MAX_IDS} notification ids")
    return cast(list[str], value)


def _save(db, org: Organization, kept: dict[str, dict], ids: set[str]) -> None:
    config = dict(cast(dict, org.config) or {})
    entries = [e for i, e in kept.items() if i in ids]
    config["dashboard"] = {**(config.get("dashboard") or {}), "resolved": entries}
    org.config = config
    flag_modified(org, "config")
    db.commit()


def resolve(db, org: Organization, ids: object, actor: str) -> dict:
    """Mark notifications resolved. Ids that match no current problem are ignored."""
    wanted = set(_ids(ids))
    ids = {p["id"] for p in current(db, org.id)}
    kept = _resolved(org)
    at = iso(utcnow())
    for i in wanted & ids:
        kept.setdefault(i, {"id": i, "by": actor, "at": at})
    _save(db, org, kept, ids)
    return listing(db, org)


def delete(db, org: Organization, ids: object) -> dict:
    """Delete events by id. A problem cannot be deleted, so its id is ignored; resolve it instead."""
    rows = [int(i[6:]) for i in _ids(ids) if i.startswith("event-") and i[6:].isdigit()]
    if rows:
        db.query(webhooks.Notification).filter(
            webhooks.Notification.organization_id == org.id, webhooks.Notification.id.in_(rows)
        ).delete(synchronize_session=False)
        db.commit()
    return listing(db, org)


def reopen(db, org: Organization, ids: object) -> dict:
    """Mark resolved notifications open again."""
    wanted = set(_ids(ids))
    ids = {p["id"] for p in current(db, org.id)}
    kept = {i: e for i, e in _resolved(org).items() if i not in wanted}
    _save(db, org, kept, ids)
    return listing(db, org)
