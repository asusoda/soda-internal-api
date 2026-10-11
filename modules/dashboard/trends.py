"""Daily counts of an org's activity for the dashboard charts. Each series counts one day per UTC date."""

import datetime
from collections.abc import Iterable
from typing import cast

from core.audit import AuditEntry
from core.time import utcnow
from modules.agents.models import AgentConversation, AgentMessage
from modules.feeds.models import AlertFeed, AlertRun
from modules.knowledge.models import KnowledgeRun
from modules.organizations import service as organizations
from modules.organizations.models import Organization
from modules.points.models import Points
from modules.storefront.models import Order

DEFAULT_DAYS = 30
MAX_DAYS = 90


def _day(value: datetime.datetime | None) -> str | None:
    return value.date().isoformat() if value else None


def _series(
    key: str, title: str, unit: str, dates: list[str], rows: Iterable[tuple[datetime.datetime | None, float, bool]]
) -> dict:
    """Sums values per day. A row is (time, value, failed); failed rows also count in the day's failed total."""
    values = dict.fromkeys(dates, 0.0)
    failed = dict.fromkeys(dates, 0.0)
    for when, value, bad in rows:
        day = _day(when)
        if day not in values:
            continue
        values[day] += value
        if bad:
            failed[day] += value
    return {
        "key": key,
        "title": title,
        "unit": unit,
        "total": sum(values.values()),
        "failed": sum(failed.values()),
        "days": [{"date": d, "value": values[d], "failed": failed[d]} for d in dates],
    }


def trends(db, org: Organization, days: int = DEFAULT_DAYS) -> dict:
    """One series per chart for the last days days, only for modules the org has on."""
    org_id = cast(int, org.id)
    prefix = cast(str, org.prefix)
    days = max(7, min(int(days), MAX_DAYS))
    today = utcnow().date()
    dates = [(today - datetime.timedelta(days=n)).isoformat() for n in range(days - 1, -1, -1)]
    since = datetime.datetime.combine(today - datetime.timedelta(days=days - 1), datetime.time.min)

    def on(name: str) -> bool:
        return organizations.module_enabled(org, name)

    audit_rows = (
        db.query(AuditEntry.created_at, AuditEntry.source, AuditEntry.status, AuditEntry.details)
        .filter(AuditEntry.org == prefix, AuditEntry.created_at >= since)
        .all()
    )
    series = [
        _series(
            "actions",
            "Officer and app actions",
            "actions",
            dates,
            ((when, 1, False) for when, source, _, _ in audit_rows if source != "job"),
        ),
        _series(
            "jobs",
            "Job runs",
            "runs",
            dates,
            (
                (when, 1, (details or {}).get("result") == "failed")
                for when, source, _, details in audit_rows
                if source == "job"
            ),
        ),
    ]

    if on("points"):
        rows = db.query(Points.timestamp, Points.points).filter(
            Points.organization_id == org_id, Points.timestamp >= since, Points.points > 0
        )
        series.append(_series("points", "Points given", "points", dates, ((t, p or 0, False) for t, p in rows)))
    if on("storefront"):
        rows = db.query(Order.created_at).filter(Order.organization_id == org_id, Order.created_at >= since)
        series.append(_series("orders", "Store orders", "orders", dates, ((t, 1, False) for (t,) in rows)))
    # Agents and knowledge are always on, so their charts show only when the window has data.
    rows = (
        db.query(AgentMessage.created_at)
        .join(AgentConversation, AgentConversation.id == AgentMessage.conversation_id)
        .filter(
            AgentConversation.organization_id == org_id,
            AgentMessage.created_at >= since,
            AgentMessage.role == "user",
        )
    )
    series.append(_series("questions", "Questions to agents", "questions", dates, ((t, 1, False) for (t,) in rows)))
    rows = db.query(KnowledgeRun.started_at, KnowledgeRun.error).filter(
        KnowledgeRun.organization_id == org_id, KnowledgeRun.started_at >= since
    )
    series.append(_series("knowledge", "Knowledge runs", "runs", dates, ((t, 1, bool(err)) for t, err in rows)))
    if on("feeds"):
        rows = (
            db.query(AlertRun.started_at, AlertRun.posted, AlertRun.error)
            .join(AlertFeed, AlertFeed.id == AlertRun.feed_id)
            .filter(AlertFeed.organization_id == org_id, AlertRun.started_at >= since)
        )
        series.append(_series("feed_posts", "Webhook posts", "posts", dates, ((t, p or 0, False) for t, p, _ in rows)))
    always_on = {"questions", "knowledge"}
    series = [item for item in series if item["key"] not in always_on or item["total"]]
    return {"days": days, "series": series, "generated_at": utcnow().isoformat()}
