"""Uptime monitors: check public addresses on a schedule, keep each result, and send an event on each change of state.

A monitor checks a URL, or the health URL of one of the org's Hosting apps. A check is up when the response
status matches expected_status. The first check that is down, and each change between up and down after it,
saves a notification and sends monitor.down or monitor.up to the org's webhooks. A first check that is up
sends nothing. probe.fetch reads only public addresses. No Flask here.
"""

import datetime
import json
import os
import re
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlsplit

from sqlalchemy import case, func

from core import hosting, limits, net, webhooks
from core.errors import ServiceError
from core.log import get_logger
from core.time import iso, utcnow
from modules.auth import scopes
from modules.organizations import service as organizations
from modules.organizations.models import Organization
from modules.runpod.models import App

from . import probe
from .models import UptimeCheck, UptimeMonitor

logger = get_logger(__name__)

scopes.declare("uptime:read", "List uptime monitors, their state, uptime, checks and the apps they can check")
scopes.declare("uptime:manage", "Add, change and delete uptime monitors, and check them now")
webhooks.declare("monitor.down", "Monitors down", "An uptime monitor finds its address down.", "uptime")
webhooks.declare("monitor.up", "Monitors up", "An uptime monitor that was down finds its address up again.", "uptime")

KINDS = ("url", "app")
STATUS_PATTERN = re.compile(r"^([1-5]xx|[1-5][0-9]{2})$")
MAX_IDS = 100  # ids in one bulk call
MAX_NAME = 100
MAX_URL = 500
TIMEOUT_RANGE = (1, 30)
INTERVAL_RANGE = (1, 1440)
RECENT = 30  # checks in the bar of each monitor in a list
HISTORY = 100  # checks in the answer for one monitor
WORKERS = 8  # checks that run at the same time
# A check is due this much before its interval ends, so that a monitor with a 1 minute interval runs on each tick
DUE_EARLY = datetime.timedelta(seconds=15)
RETENTION_DAYS = int(os.environ.get("UPTIME_RETENTION_DAYS", "30"))


class UptimeError(ServiceError):
    pass


MONITORS_LIMIT = "uptime.monitors"
limits.declare(
    MONITORS_LIMIT,
    "uptime",
    "Uptime monitors",
    50,
    unit="monitors",
    usage=lambda db, org_id: db.query(UptimeMonitor).filter_by(organization_id=org_id).count(),
)


def _find(db, org_id: int, monitor_id: int) -> UptimeMonitor:
    monitor = db.query(UptimeMonitor).filter_by(organization_id=org_id, id=monitor_id).first()
    if monitor is None:
        raise UptimeError("No monitor with this id", 404)
    return monitor


def _int(body: dict, name: str, default: int, bounds: tuple[int, int]) -> int:
    value = body.get(name, default)
    if isinstance(value, bool) or not isinstance(value, int) or not bounds[0] <= value <= bounds[1]:
        raise UptimeError(f"{name} must be an integer from {bounds[0]} to {bounds[1]}")
    return value


def _check_url(url: object) -> str:
    if not isinstance(url, str) or not url.strip() or len(url.strip()) > MAX_URL:
        raise UptimeError(f"target must be an http or https URL of {MAX_URL} characters or fewer")
    url = url.strip()
    if urlsplit(url).scheme not in ("http", "https"):
        raise UptimeError("target must be an http or https URL")
    try:
        net.check_public(url)
    except net.NotPublic as e:
        raise UptimeError(str(e)) from e
    except net.NoHost:
        # A host that does not resolve now can resolve later. Each check reports it as down.
        pass
    return url


def _fields(db, org_id: int, body: dict, monitor: UptimeMonitor | None) -> dict:
    """The checked fields of a new or changed monitor. A missing field keeps its value."""
    old = monitor
    name = body.get("name", old.name if old else None)
    if not isinstance(name, str) or not name.strip() or len(name.strip()) > MAX_NAME:
        raise UptimeError(f"name must have 1 to {MAX_NAME} characters")
    kind = body.get("target_kind", old.target_kind if old else "url")
    if kind not in KINDS:
        raise UptimeError(f"target_kind must be one of {', '.join(KINDS)}")
    target = body.get("target", old.target if old else None)
    if kind == "url":
        target = _check_url(target)
    elif not isinstance(target, str) or db.query(App).filter_by(organization_id=org_id, name=target).first() is None:
        raise UptimeError("target must be the name of an app on the Hosting page")
    expected = body.get("expected_status", old.expected_status if old else "2xx")
    if not isinstance(expected, str) or not STATUS_PATTERN.match(expected):
        raise UptimeError("expected_status must be a status class such as 2xx, or a status code such as 204")
    enabled = body.get("enabled", old.enabled if old else True)
    if not isinstance(enabled, bool):
        raise UptimeError("enabled must be true or false")
    return {
        "name": name.strip(),
        "target_kind": kind,
        "target": target,
        "expected_status": expected,
        "timeout_seconds": _int(body, "timeout_seconds", old.timeout_seconds if old else 10, TIMEOUT_RANGE),
        "interval_minutes": _int(body, "interval_minutes", old.interval_minutes if old else 5, INTERVAL_RANGE),
        "enabled": enabled,
    }


def _name_taken(db, org_id: int, name: str, monitor_id: int | None) -> bool:
    query = db.query(UptimeMonitor.id).filter_by(organization_id=org_id, name=name)
    if monitor_id is not None:
        query = query.filter(UptimeMonitor.id != monitor_id)
    return query.first() is not None


def _check_dict(check: UptimeCheck) -> dict:
    return {
        "checked_at": iso(check.checked_at),
        "up": check.up,
        "status_code": check.status_code,
        "latency_ms": check.latency_ms,
        "error": check.error,
    }


def _uptime(db, ids: list[int], since: datetime.datetime) -> dict[int, float]:
    """The percent of checks that were up since a time, for each monitor that has checks in that time."""
    if not ids:
        return {}
    rows = (
        db.query(
            UptimeCheck.monitor_id,
            func.count(UptimeCheck.id),
            func.sum(case((UptimeCheck.up.is_(True), 1), else_=0)),
        )
        .filter(UptimeCheck.monitor_id.in_(ids), UptimeCheck.checked_at >= since)
        .group_by(UptimeCheck.monitor_id)
        .all()
    )
    return {int(monitor_id): round(100 * int(up or 0) / int(total), 2) for monitor_id, total, up in rows if total}


def _recent(db, monitor_id: int, limit: int) -> list[UptimeCheck]:
    """The last checks of a monitor, oldest first."""
    rows = (
        db.query(UptimeCheck)
        .filter_by(monitor_id=monitor_id)
        .order_by(UptimeCheck.checked_at.desc(), UptimeCheck.id.desc())
        .limit(limit)
        .all()
    )
    return rows[::-1]


def _describe(monitor: UptimeMonitor, recent: list[UptimeCheck], day: float | None, week: float | None) -> dict:
    last = recent[-1] if recent else None
    return {
        "id": monitor.id,
        "name": monitor.name,
        "target_kind": monitor.target_kind,
        "target": monitor.target,
        "expected_status": monitor.expected_status,
        "timeout_seconds": monitor.timeout_seconds,
        "interval_minutes": monitor.interval_minutes,
        "enabled": monitor.enabled,
        "state": monitor.state,
        "state_since": iso(monitor.state_since),
        "last_checked_at": iso(monitor.last_checked_at),
        "last_check": _check_dict(last) if last else None,
        "uptime_24h": day,
        "uptime_7d": week,
        "recent": [_check_dict(c) for c in recent],
    }


def _describe_all(db, monitors: list[UptimeMonitor], limit: int, now: datetime.datetime | None = None) -> list[dict]:
    now = now or utcnow()
    ids = [m.id for m in monitors]
    day = _uptime(db, ids, now - datetime.timedelta(days=1))
    week = _uptime(db, ids, now - datetime.timedelta(days=7))
    return [_describe(m, _recent(db, m.id, limit), day.get(m.id), week.get(m.id)) for m in monitors]


def list_monitors(db, org_id: int) -> list[dict]:
    """The org's monitors by name, each with its state, uptime over 24 hours and 7 days, and its last checks."""
    monitors = db.query(UptimeMonitor).filter_by(organization_id=org_id).order_by(UptimeMonitor.name).all()
    return _describe_all(db, monitors, RECENT)


def get_monitor(db, org_id: int, monitor_id: int) -> dict:
    """One monitor with its last HISTORY checks."""
    return _describe_all(db, [_find(db, org_id, monitor_id)], HISTORY)[0]


def targets(db, org_id: int) -> list[dict]:
    """The org's Hosting apps that a monitor can check, and the address a check reads for each."""
    apps = db.query(App).filter_by(organization_id=org_id).order_by(App.name).all()
    return [{"name": app.name, "url": _app_url(app)[0]} for app in apps]


def create_monitor(db, org_id: int, body: dict) -> dict:
    """Add a monitor. Commits."""
    limits.check(db, org_id, MONITORS_LIMIT)
    fields = _fields(db, org_id, body, None)
    if _name_taken(db, org_id, fields["name"], None):
        raise UptimeError("A monitor with this name exists", 409)
    monitor = UptimeMonitor(organization_id=org_id, **fields)
    db.add(monitor)
    db.commit()
    return _describe_all(db, [monitor], RECENT)[0]


def watch_app(db, org_id: int, name: str) -> None:
    """Add a monitor of a new Hosting app when the org has uptime on and no monitor checks the app. Commits."""
    org = db.get(Organization, org_id)
    if org is None or not organizations.module_enabled(org, "uptime"):
        return
    monitors = db.query(UptimeMonitor).filter_by(organization_id=org_id)
    limit = limits.value(db, org_id, MONITORS_LIMIT)
    if (limit is not None and monitors.count() >= limit) or _name_taken(db, org_id, name, None):
        return
    if monitors.filter_by(target_kind="app", target=name).first() is not None:
        return
    fields = _fields(db, org_id, {"name": name, "target_kind": "app", "target": name}, None)
    db.add(UptimeMonitor(organization_id=org_id, **fields))
    db.commit()


def forget_app(db, org_id: int, name: str) -> None:
    """Delete the monitors of a Hosting app and their checks. The caller commits."""
    ids = [
        i for (i,) in db.query(UptimeMonitor.id).filter_by(organization_id=org_id, target_kind="app", target=name).all()
    ]
    if ids:
        db.query(UptimeCheck).filter(UptimeCheck.monitor_id.in_(ids)).delete(synchronize_session=False)
        db.query(UptimeMonitor).filter(UptimeMonitor.id.in_(ids)).delete(synchronize_session=False)


def update_monitor(db, org_id: int, monitor_id: int, body: dict) -> dict:
    """Change a monitor. A new target, a new expected status or a resume clears the state. Commits."""
    monitor = _find(db, org_id, monitor_id)
    fields = _fields(db, org_id, body, monitor)
    if _name_taken(db, org_id, fields["name"], monitor_id):
        raise UptimeError("A monitor with this name exists", 409)
    reset = (
        fields["target_kind"] != monitor.target_kind
        or fields["target"] != monitor.target
        or fields["expected_status"] != monitor.expected_status
        or (fields["enabled"] and not monitor.enabled)
    )
    for key, value in fields.items():
        setattr(monitor, key, value)
    if reset:
        monitor.state = None
        monitor.state_since = None
    monitor.updated_at = utcnow()
    db.commit()
    return _describe_all(db, [monitor], RECENT)[0]


def delete_monitor(db, org_id: int, monitor_id: int) -> None:
    """Delete a monitor and its checks. Commits."""
    monitor = _find(db, org_id, monitor_id)
    db.query(UptimeCheck).filter_by(monitor_id=monitor.id).delete()
    db.delete(monitor)
    db.commit()


def delete_monitors(db, org_id: int, monitor_ids: list[int]) -> dict:
    """Delete monitors and their checks in one commit. If one id is missing, nothing changes."""
    monitors = [_find(db, org_id, monitor_id) for monitor_id in dict.fromkeys(monitor_ids)]
    for monitor in monitors:
        db.query(UptimeCheck).filter_by(monitor_id=monitor.id).delete()
        db.delete(monitor)
    db.commit()
    return {"deleted": [m.id for m in monitors]}


def _app_url(app: App) -> tuple[str | None, str | None]:
    """The health URL of the app's pod, else the public url of its manifest. Returns (url, error)."""
    manifest = json.loads(str(app.manifest))
    health = manifest.get("health") or {}
    if app.pod_id and health.get("port") and str(health.get("path", "")).startswith("/"):
        try:
            provider = hosting.get(str(app.provider or hosting.DEFAULT))
            return provider.proxy_url(str(app.pod_id), int(health["port"]), str(health["path"])), None
        except hosting.ProviderError as e:
            return None, e.message
        except hosting.HostingError as e:
            if not manifest.get("url"):
                return None, e.message
    if manifest.get("url"):
        return str(manifest["url"]), None
    return None, f"The app {app.name} has no pod and no url yet"


# A check: ("url", url, error) for an HTTP probe, or ("app", provider, pod_id, port, check) for the app's own
# health check through its provider
Job = tuple


def _target(db, monitor: UptimeMonitor) -> Job:
    """What a check of the monitor runs. An app on This server has a private address, which the HTTP probe refuses,
    so its provider runs the app's own health check: an HTTP path, a TCP connect, or its running state."""
    if monitor.target_kind == "url":
        return ("url", str(monitor.target), None)
    app = db.query(App).filter_by(organization_id=monitor.organization_id, name=monitor.target).first()
    if app is None:
        return ("url", None, f"No app named {monitor.target} on the Hosting page")
    health = json.loads(str(app.manifest)).get("health") or {}
    if app.pod_id and app.provider == "server":
        check = "running" if health.get("running") else health.get("path")
        return ("app", hosting.get("server"), str(app.pod_id), int(health.get("port") or 0), check)
    return ("url", *_app_url(app))


def status_matches(expected: str, status: int) -> bool:
    """Whether a status code matches a status class such as 2xx, or one status code."""
    if expected.endswith("xx"):
        return status // 100 == int(expected[0])
    return status == int(expected)


def _run(job: tuple[Job, int]) -> probe.Result:
    target, timeout = job
    if target[0] == "app":
        return probe.provider_check(*target[1:])
    _, url, error = target
    if url is None:
        return probe.Result(error=error or "No address to check")
    return probe.fetch(url, timeout)


def _announce(monitor: UptimeMonitor, check: UptimeCheck) -> None:
    """Send monitor.down or monitor.up for a monitor whose state changed. emit() also saves the notification."""
    up = bool(check.up)
    fields = [("Target", str(monitor.target))]
    if check.status_code is not None:
        fields.append(("Status", str(check.status_code)))
    if check.latency_ms is not None:
        fields.append(("Latency", f"{check.latency_ms} ms"))
    if check.error:
        fields.append(("Error", str(check.error)))
    message = webhooks.Message(
        title=f"Monitor {monitor.name} is {'up' if up else 'down'}",
        fields=tuple(fields),
        color=webhooks.GREEN if up else webhooks.RED,
    )
    webhooks.emit(monitor.organization_id, "monitor.up" if up else "monitor.down", message)


def check(db, monitors: list[UptimeMonitor], now: datetime.datetime | None = None) -> list[dict]:
    """Check each monitor, save each result and send an event for each change of state. Commits.

    The HTTP requests run in WORKERS threads. The database work stays in this thread.
    """
    now = now or utcnow()
    jobs = []
    for monitor in monitors:
        jobs.append((_target(db, monitor), monitor.timeout_seconds))
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        results = list(pool.map(_run, jobs))
    changed = []
    out = []
    for monitor, result in zip(monitors, results, strict=True):
        error = result.error
        up = bool(result.ok)
        if result.ok is None and result.status_code is not None:
            up = status_matches(str(monitor.expected_status), result.status_code)
            if not up:
                error = f"Status {result.status_code}, expected {monitor.expected_status}"
        row = UptimeCheck(
            monitor_id=monitor.id,
            checked_at=now,
            up=up,
            status_code=result.status_code,
            latency_ms=result.latency_ms,
            error=error[:500] if error else None,
        )
        db.add(row)
        state = "up" if up else "down"
        if state != monitor.state:
            if monitor.state is not None or state == "down":
                changed.append((monitor, row))
            monitor.state = state
            monitor.state_since = now
        monitor.last_checked_at = now
        out.append({"id": monitor.id, "name": monitor.name, **_check_dict(row)})
    db.commit()
    for monitor, row in changed:
        _announce(monitor, row)
    return out


def check_now(db, org_id: int, monitor_id: int) -> dict:
    """Check one monitor now, enabled or not. Returns the check and the monitor. Commits."""
    monitor = _find(db, org_id, monitor_id)
    result = check(db, [monitor])[0]
    found = {key: value for key, value in result.items() if key not in ("id", "name")}
    return {"check": found, "monitor": get_monitor(db, org_id, monitor_id)}


def due(db, now: datetime.datetime | None = None) -> list[UptimeMonitor]:
    """Enabled monitors whose interval has passed, in active orgs that have the uptime module on."""
    now = now or utcnow()
    rows = (
        db.query(UptimeMonitor, Organization)
        .join(Organization, Organization.id == UptimeMonitor.organization_id)
        .filter(UptimeMonitor.enabled.is_(True), Organization.is_active.is_(True))
        .order_by(UptimeMonitor.id)
        .all()
    )
    found = []
    for monitor, org in rows:
        if not organizations.module_enabled(org, "uptime"):
            continue
        last = monitor.last_checked_at
        if last is None or last <= now - datetime.timedelta(minutes=int(monitor.interval_minutes)) + DUE_EARLY:
            found.append(monitor)
    return found


def check_due(db, now: datetime.datetime | None = None) -> dict:
    """Check every due monitor. Commits."""
    monitors = due(db, now)
    if not monitors:
        return {"checked": 0, "down": 0}
    results = check(db, monitors, now)
    counts = {"checked": len(results), "down": sum(1 for r in results if not r["up"])}
    logger.info("uptime checks %s", counts)
    return counts


def prune(db, now: datetime.datetime | None = None) -> int:
    """Delete checks older than RETENTION_DAYS. Returns the number deleted. Commits."""
    cutoff = (now or utcnow()) - datetime.timedelta(days=RETENTION_DAYS)
    deleted = db.query(UptimeCheck).filter(UptimeCheck.checked_at < cutoff).delete(synchronize_session=False)
    db.commit()
    return int(deleted)
