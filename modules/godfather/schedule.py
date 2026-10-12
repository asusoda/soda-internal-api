"""Pod sessions: windows when a pod should run. No Flask here.

The godfather.schedule job starts a pod a few minutes before a session and stops it when the
session ends, unless another session on the same pod is still running. A pod already running
when its session begins is also stopped when the session ends. Pods without sessions are never
started or stopped by the job.
"""

import datetime
from collections.abc import Callable
from typing import Any, cast

from core import hosting
from core.log import get_logger
from core.time import utcnow
from modules.godfather import service
from modules.godfather.models import ComputePod, ComputeSession

logger = get_logger("godfather.schedule")

START_LEAD = datetime.timedelta(minutes=10)
MAX_LENGTH = datetime.timedelta(hours=24)
MAX_UPCOMING = 100


def _time(data: dict, key: str) -> datetime.datetime:
    value = data.get(key)
    if not isinstance(value, str):
        raise service.GodfatherError(f"{key} must be an ISO 8601 time with a timezone")
    try:
        parsed = datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as e:
        raise service.GodfatherError(f"{key} must be an ISO 8601 time with a timezone") from e
    if parsed.tzinfo is None:
        raise service.GodfatherError(f"{key} needs a timezone, such as -07:00 or Z")
    return parsed.astimezone(datetime.UTC).replace(tzinfo=None)


def _iso(value: Any) -> str:
    return cast(datetime.datetime, value).replace(tzinfo=datetime.UTC).isoformat()


def session_dict(row: ComputeSession) -> dict:
    return {
        "id": row.id,
        "pod_id": row.pod_id,
        "title": row.title,
        "start_at": _iso(row.start_at),
        "stop_at": _iso(row.stop_at),
        "started": bool(row.started),
        "finished": bool(row.finished),
        "created_by": row.created_by,
    }


def list_sessions(db, org_id: int, pod_id: str) -> list[dict]:
    service._find(db, org_id, pod_id)
    rows = (
        db.query(ComputeSession)
        .filter_by(organization_id=org_id, pod_id=pod_id)
        .order_by(ComputeSession.start_at)
        .all()
    )
    return [session_dict(row) for row in rows]


def add_session(db, org_id: int, pod_id: str, data: object, creator: str | None, now=None) -> dict:
    """Schedule a window for a pod. Commits."""
    service._find(db, org_id, pod_id)
    if not isinstance(data, dict):
        raise service.GodfatherError("Send start_at and stop_at")
    data = cast(dict, data)
    start, stop = _time(data, "start_at"), _time(data, "stop_at")
    now = now or utcnow()
    if stop <= start:
        raise service.GodfatherError("stop_at must be after start_at")
    if stop - start > MAX_LENGTH:
        raise service.GodfatherError("A session can be at most 24 hours long")
    if stop <= now:
        raise service.GodfatherError("stop_at is in the past")
    title = data.get("title")
    if title is not None and (not isinstance(title, str) or len(title) > 200):
        raise service.GodfatherError("title must be text of at most 200 characters")
    upcoming = db.query(ComputeSession).filter_by(organization_id=org_id, pod_id=pod_id, finished=False).count()
    if upcoming >= MAX_UPCOMING:
        raise service.GodfatherError(f"A pod can have at most {MAX_UPCOMING} upcoming sessions")
    row = ComputeSession(
        organization_id=org_id, pod_id=pod_id, title=title, start_at=start, stop_at=stop, created_by=creator
    )
    db.add(row)
    db.commit()
    return session_dict(row)


def delete_session(db, org_id: int, pod_id: str, session_id: int) -> None:
    """Remove a session. A pod the job already started for it is stopped at the next run. Commits."""
    row = db.query(ComputeSession).filter_by(organization_id=org_id, pod_id=pod_id, id=session_id).first()
    if row is None:
        raise service.GodfatherError("Session not found", 404)
    if row.started and not row.finished:
        # Ending it now lets the next run stop the pod
        row.stop_at = utcnow()
    else:
        db.delete(row)
    db.commit()


def delete_pod_sessions(db, org_id: int, pod_id: str) -> None:
    db.query(ComputeSession).filter_by(organization_id=org_id, pod_id=pod_id).delete()


def run(db, now=None, client_for: Callable[[Any, int, str], hosting.HostingClient] | None = None) -> dict:
    """Start pods whose session is about to begin and stop pods whose sessions have ended. Commits.

    client_for takes the db, the org id and the provider name.
    """
    now = now or utcnow()
    client_for = client_for or service._client
    due = (
        db.query(ComputeSession)
        .filter(ComputeSession.finished.is_(False), ComputeSession.start_at <= now + START_LEAD)
        .order_by(ComputeSession.organization_id, ComputeSession.pod_id)
        .all()
    )
    pods: dict[tuple[int, str], list[ComputeSession]] = {}
    for row in due:
        pods.setdefault((int(row.organization_id), str(row.pod_id)), []).append(row)
    clients: dict[tuple[int, str], hosting.HostingClient] = {}
    result = {"started": [], "stopped": [], "failed": []}
    for (org_id, pod_id), rows in pods.items():
        active = [r for r in rows if r.stop_at > now]
        ended = [r for r in rows if r.stop_at <= now]
        try:
            pod = db.query(ComputePod).filter_by(organization_id=org_id, pod_id=pod_id).first()
            if pod is None:
                for r in rows:
                    r.finished = True
                continue
            provider = str(pod.provider)
            if (org_id, provider) not in clients:
                clients[(org_id, provider)] = client_for(db, org_id, provider)
            client = clients[(org_id, provider)]
            if active and not all(r.started for r in active):
                if service._status(service._call(client.get_pod, pod_id), provider) != "RUNNING":
                    service._call(client.start_pod, pod_id)
                    result["started"].append(pod_id)
                    service.announce(org_id, str(pod.name), pod_id, "start", "the session schedule")
                for r in active:
                    r.started = True
            if ended and not active and any(r.started for r in ended):
                service._call(client.stop_pod, pod_id)
                result["stopped"].append(pod_id)
                service.announce(org_id, str(pod.name), pod_id, "stop", "the session schedule")
            for r in ended:
                r.finished = True
        except service.GodfatherError as e:
            logger.warning("godfather schedule failed org=%s pod=%s: %s", org_id, pod_id, e.message)
            result["failed"].append(pod_id)
        db.commit()
    if result["started"] or result["stopped"]:
        logger.info("godfather schedule started=%s stopped=%s", result["started"], result["stopped"])
    return result
