"""Per-org limits on what each module may use, so one org cannot use up the server for the others.

A module declares its limits with declare(). There are two kinds:

- A count limit caps how many of a thing an org keeps, such as knowledge sources or pods. The module gives a
  usage function that counts them, and calls check() before it adds more.
- A rate limit caps how much an org uses in a window of a minute, an hour or a day, such as embedded texts a day.
  The module calls consume(), which adds to the org's counter for the current window in usage_counters.

The value of a limit is, in order: the org's override (the superadmin sets it), LIMIT_<KEY> in Doppler (the key in
upper case, with _ for . and -), the declared default. None means no limit. An org over a limit gets a LimitError:
409 for a count, 429 for a rate. consume() flushes and does not commit, so a call that fails later is not counted.

Each limit says who pays for what it counts (paid_by), so the dashboard can tell an org what uses its budget:
"org" for the org's own data and apps, "metered" for a shared service the org uses, such as the deployment's
embedder. Shared content, such as a submodule's pages, is "shared" and has no limit of an org.
No Flask here.
"""

import datetime
import os
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, cast

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Mapped, mapped_column

from core.db import Base, session
from core.errors import ServiceError
from core.jobs import job
from core.log import get_logger
from core.time import iso, utcnow

logger = get_logger("limits")

WINDOWS = {
    "minute": datetime.timedelta(minutes=1),
    "hour": datetime.timedelta(hours=1),
    "day": datetime.timedelta(days=1),
}
# Counters of windows that ended this long ago are deleted
KEEP = datetime.timedelta(days=8)
MAX_VALUE = 10**12
UNLIMITED = "unlimited"
PAID_BY = {
    "org": "The org's own data and apps",
    "shared": "Made once by the deployment for every org; counts against no org",
    "metered": "A shared service the org uses; counts against the org as a rate",
}


class LimitError(ServiceError):
    pass


@dataclass(frozen=True)
class Limit:
    key: str
    # The module the limit belongs to. The dashboard shows the limit when the org has the module on.
    module: str
    label: str
    default: int | None
    # minute, hour or day for a rate limit; None for a count limit
    window: str | None = None
    # The thing counted, such as "sources" or "texts"
    unit: str = ""
    # Counts what the org has now. Required for a count limit.
    usage: Callable[[Any, int], int] | None = None
    # org or metered (see PAID_BY)
    paid_by: str = "org"
    # Integrations whose deployment default this limit meters, such as ("embeddings",)
    integrations: tuple[str, ...] = ()


LIMITS: dict[str, Limit] = {}


class OrgLimit(Base):
    """A superadmin's override of one limit for one org. value None means no limit."""

    __tablename__ = "org_limits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    key: Mapped[str] = mapped_column(String(100), nullable=False)
    value: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, default=utcnow)
    updated_by: Mapped[str | None] = mapped_column(String(255), nullable=True)

    __table_args__ = (UniqueConstraint("organization_id", "key", name="uq_org_limit_key"),)


class UsageCounter(Base):
    """How much of a rate limit an org used in one window."""

    __tablename__ = "usage_counters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    key: Mapped[str] = mapped_column(String(100), nullable=False)
    window_start: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, index=True)
    count: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)

    __table_args__ = (UniqueConstraint("organization_id", "key", "window_start", name="uq_usage_counter_window"),)


def declare(
    key: str,
    module: str,
    label: str,
    default: int | None,
    *,
    window: str | None = None,
    unit: str = "",
    usage: Callable[[Any, int], int] | None = None,
    paid_by: str | None = None,
    integrations: tuple[str, ...] = (),
) -> None:
    """Add a limit. A count limit (no window) needs usage. paid_by defaults to org for a count, metered for a rate."""
    if window is not None and window not in WINDOWS:
        raise ValueError(f"window must be one of {', '.join(WINDOWS)}")
    if window is None and usage is None:
        raise ValueError(f"The count limit {key} needs a usage function")
    paid = paid_by or ("metered" if window else "org")
    if paid not in ("org", "metered"):
        raise ValueError("paid_by must be org or metered")
    LIMITS[key] = Limit(key, module, label, default, window, unit, usage, paid, integrations)


def env_name(key: str) -> str:
    return "LIMIT_" + key.upper().replace(".", "_").replace("-", "_")


def _env_value(spec: Limit) -> int | None:
    raw = os.environ.get(env_name(spec.key), "").strip()
    if not raw:
        return spec.default
    if raw.lower() == UNLIMITED:
        return None
    try:
        return max(0, int(raw))
    except ValueError:
        logger.warning("%s is not a number or %s; the default applies", env_name(spec.key), UNLIMITED)
        return spec.default


def _spec(key: str) -> Limit:
    spec = LIMITS.get(key)
    if spec is None:
        raise LimitError(f"Unknown limit: {key}", 404)
    return spec


def _overrides(db, org_id: int) -> dict[str, int | None]:
    rows = db.query(OrgLimit).filter_by(organization_id=org_id).all()
    return {cast(str, row.key): cast(int | None, row.value) for row in rows}


def value(db, org_id: int, key: str) -> int | None:
    """The limit for the org: its override, else Doppler, else the default. None means no limit."""
    spec = _spec(key)
    row = db.query(OrgLimit).filter_by(organization_id=org_id, key=key).first()
    return cast(int | None, row.value) if row is not None else _env_value(spec)


def window_start(window: str, now: datetime.datetime | None = None) -> datetime.datetime:
    now = now or utcnow()
    if window == "minute":
        return now.replace(second=0, microsecond=0)
    if window == "hour":
        return now.replace(minute=0, second=0, microsecond=0)
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


def used(db, org_id: int, key: str, now: datetime.datetime | None = None) -> int:
    """What the org uses now: the count for a count limit, the current window's counter for a rate limit."""
    spec = _spec(key)
    if spec.window is None:
        return int(cast(Callable, spec.usage)(db, org_id))
    row = (
        db.query(UsageCounter)
        .filter_by(organization_id=org_id, key=key, window_start=window_start(spec.window, now))
        .first()
    )
    return int(row.count) if row is not None else 0


def _refusal(spec: Limit, limit: int) -> str:
    unit = f" {spec.unit}" if spec.unit else ""
    if spec.window is None:
        return f"This organization has reached its limit of {limit:,}{unit} for {spec.label.lower()}"
    return f"This organization has used its limit of {limit:,}{unit} a {spec.window} for {spec.label.lower()}"


def check(db, org_id: int, key: str, add: int = 1) -> None:
    """Raise LimitError (409) when adding add more would take the org over a count limit."""
    spec = _spec(key)
    if add <= 0:
        return
    limit = value(db, org_id, key)
    if limit is not None and used(db, org_id, key) + add > limit:
        raise LimitError(_refusal(spec, limit), 409)


def consume(db, org_id: int, key: str, amount: int = 1, now: datetime.datetime | None = None) -> None:
    """Add amount to the org's counter of a rate limit. Raises LimitError (429), and counts nothing, when it is over.

    Flushes, does not commit: the caller's commit keeps the count, and a rollback drops it.
    """
    spec = _spec(key)
    if spec.window is None:
        raise ValueError(f"{key} is a count limit; use check()")
    if amount <= 0:
        return
    start = window_start(spec.window, now)
    limit = value(db, org_id, key)
    if limit is not None and used(db, org_id, key, now) + amount > limit:
        raise LimitError(_refusal(spec, limit), 429)
    values = {"organization_id": org_id, "key": key, "window_start": start, "count": amount}
    insert = pg_insert if db.get_bind().dialect.name == "postgresql" else sqlite_insert
    statement = insert(UsageCounter).values(**values)
    statement = statement.on_conflict_do_update(
        index_elements=["organization_id", "key", "window_start"],
        set_={"count": UsageCounter.count + amount},
    )
    db.execute(statement)
    db.flush()


def catalog() -> list[dict]:
    """Every declared limit with its value in Doppler or its default."""
    return [
        {
            "key": spec.key,
            "module": spec.module,
            "label": spec.label,
            "unit": spec.unit,
            "window": spec.window,
            "default": _env_value(spec),
            "paid_by": spec.paid_by,
            "integrations": list(spec.integrations),
        }
        for spec in sorted(LIMITS.values(), key=lambda s: (s.module, s.key))
    ]


def report(db, org_id: int, now: datetime.datetime | None = None) -> list[dict]:
    """Each limit for the org: the catalog fields, the org's value, whether it is an override, and what it uses."""
    overrides = _overrides(db, org_id)
    rows = []
    for entry in catalog():
        key = entry["key"]
        overridden = key in overrides
        rows.append(
            entry
            | {
                "value": overrides[key] if overridden else entry["default"],
                "override": overridden,
                "used": used(db, org_id, key, now),
            }
        )
    return rows


def set_values(db, org_id: int, changes: object, actor: str | None = None) -> list[dict]:
    """Set the org's overrides. changes maps a key to a whole number, null (no limit) or "default". Commits."""
    if not isinstance(changes, dict) or not changes:
        raise LimitError('Send "limits": an object of limit key to a number, null or "default"')
    for key, new in changes.items():
        _spec(str(key))
        if new is not None and new != "default" and (not isinstance(new, int) or isinstance(new, bool)):
            raise LimitError(f'{key} must be a whole number, null or "default"')
        if isinstance(new, int) and not 0 <= new <= MAX_VALUE:
            raise LimitError(f"{key} must be from 0 to {MAX_VALUE:,}")
    for key, new in changes.items():
        row = db.query(OrgLimit).filter_by(organization_id=org_id, key=key).first()
        if new == "default":
            if row is not None:
                db.delete(row)
            continue
        if row is None:
            row = OrgLimit(organization_id=org_id, key=key)
            db.add(row)
        row.value, row.updated_at, row.updated_by = new, utcnow(), actor
    db.commit()
    logger.info("limits changed org=%s keys=%s actor=%s", org_id, ",".join(sorted(changes)), actor)
    return report(db, org_id)


def overrides_of(db, org_id: int) -> list[dict]:
    """The org's overrides, with who set each one and when."""
    rows = db.query(OrgLimit).filter_by(organization_id=org_id).order_by(OrgLimit.key).all()
    return [
        {"key": row.key, "value": row.value, "updated_at": iso(row.updated_at), "updated_by": row.updated_by}
        for row in rows
    ]


@job("limits.prune", cron="10 4 * * *", audit=False)
def prune() -> None:
    """Delete usage counters of windows that started more than KEEP ago."""
    with session() as db:
        deleted = db.query(UsageCounter).filter(UsageCounter.window_start < utcnow() - KEEP).delete()
    logger.info("usage counters pruned rows=%s", deleted)


def metering(integration: str) -> list[dict]:
    """The limits (key and label) that meter the deployment default of the integration."""
    return [
        {"key": spec.key, "label": spec.label}
        for spec in sorted(LIMITS.values(), key=lambda s: s.key)
        if integration in spec.integrations
    ]


def for_module(module: str) -> list[dict]:
    """The module's limits from the catalog: key, label, window and paid_by."""
    return [
        {"key": e["key"], "label": e["label"], "window": e["window"], "paid_by": e["paid_by"]}
        for e in catalog()
        if e["module"] == module
    ]
