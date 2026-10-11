"""Background jobs.

Modules declare jobs with @job in their jobs.py and start them with defer(). On Postgres the
jobs go through Procrastinate: defer() writes a row and the worker process (worker_main.py)
runs it, with retries and run history in the procrastinate_jobs table. On SQLite there is no
queue: defer() runs the job in a thread of the calling process and periodic jobs run from a
thread in the API, which is how the platform behaved before the queue existed. At most JOB_THREADS
(default 4) of those threads run a job at the same time; the others wait.

A job made with once names the arguments that make a run unique, such as ("org_id",), or () for one
run at a time. While a run with the same values is queued (or, on SQLite, running), defer() raises
JobBusy, so one org cannot queue the same heavy job again and again.
"""

import contextvars
import os
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, cast

from croniter import croniter

from core.errors import ServiceError
from core.log import get_logger

logger = get_logger("jobs")


def _database_url() -> str:
    return os.environ.get("DATABASE_URL", "sqlite:///./data/user.db")


def queue_backend() -> str:
    """'procrastinate' on Postgres, 'inline' otherwise. JOBS_BACKEND overrides it."""
    configured = os.environ.get("JOBS_BACKEND")
    if configured:
        return configured
    return "procrastinate" if _database_url().startswith("postgresql") else "inline"


def _conninfo() -> str:
    url = _database_url()
    scheme, _, rest = url.partition("://")
    return "postgresql://" + rest if scheme.startswith("postgresql") else url


@dataclass
class Job:
    name: str
    func: Callable
    cron: str | None
    retry: int
    audit: bool = True
    task: object | None = None
    once: tuple[str, ...] | None = None


class JobBusy(ServiceError):
    """The same job with the same arguments is already queued or running."""


JOBS: dict[str, Job] = {}
# The name of the job that runs in this context, for the error log
current_job: contextvars.ContextVar[str | None] = contextvars.ContextVar("current_job", default=None)

_app = None


def procrastinate_app():
    """The Procrastinate app, created on first use. Only valid with the procrastinate backend."""
    global _app
    if _app is None:
        import procrastinate

        _app = procrastinate.App(connector=procrastinate.PsycopgConnector(conninfo=_conninfo()))
    return _app


def job(name: str, *, cron: str | None = None, retry: int = 0, audit: bool = True, once: tuple[str, ...] | None = None):
    """Register a job. `cron` makes it periodic; `retry` is how many times a failure is retried;
    `audit` records each run in the audit log (turn it off for frequent housekeeping);
    `once` names the arguments that make a run unique (see the module docstring)."""

    def register(func: Callable) -> Callable:
        entry = Job(name=name, func=func, cron=cron, retry=retry, audit=audit, once=once)
        if queue_backend() == "procrastinate":
            app = procrastinate_app()
            if cron:

                def periodic(timestamp: int) -> None:
                    _execute(entry, {})

                task = app.task(name=name, retry=retry, queueing_lock=name)(periodic)
                app.periodic(cron=cron, periodic_id=name)(task)
            else:

                def queued(**kwargs) -> None:
                    _execute(entry, kwargs)

                task = app.task(name=name, retry=retry)(queued)
            entry.task = task
        JOBS[name] = entry
        return func

    return register


def _audit_args(kwargs: dict) -> dict:
    """Small scalar arguments only; file contents and long strings stay out of the audit log."""
    return {
        key: value
        for key, value in kwargs.items()
        if isinstance(value, int | float | bool) or (isinstance(value, str) and len(value) <= 100)
    }


def _execute(entry: Job, kwargs: dict) -> None:
    """Run a job, log it, and record it in the audit log. Re-raises so the queue can retry."""
    started = time.monotonic()
    status = "succeeded"
    token = current_job.set(entry.name)
    try:
        entry.func(**kwargs)
        logger.info("job finished name=%s seconds=%.2f", entry.name, time.monotonic() - started)
    except Exception as error:
        status = "failed"
        logger.exception("job failed name=%s", entry.name)
        _send_failure(entry, kwargs, error)
        raise
    finally:
        current_job.reset(token)
        if entry.audit:
            from core.audit import record

            record(
                f"job {entry.name}",
                source="job",
                org=kwargs.get("org_prefix"),
                actor_kind="job",
                actor_id=entry.name,
                details={"result": status, "args": _audit_args(kwargs)},
            )


def _send_failure(entry: Job, kwargs: dict, error: Exception) -> None:
    """Send the job.failed webhook event when the job ran for one org."""
    from core import webhooks

    org = kwargs.get("org_id") or kwargs.get("org_prefix")
    if isinstance(org, int | str):
        message = webhooks.Message(
            title=f"Job {entry.name} failed",
            text=f"{type(error).__name__}: {error}"[:500],
            fields=tuple((key, str(value)) for key, value in _audit_args(kwargs).items()),
            color=webhooks.RED,
        )
        webhooks.emit(org, "job.failed", message)


def _run(entry: Job, kwargs: dict) -> None:
    """Inline backend: nothing retries, so a failure ends here after it is logged."""
    try:
        _execute(entry, kwargs)
    except Exception:
        logger.debug("job %s ended with an error, already logged", entry.name)


_slots = threading.BoundedSemaphore(max(1, int(os.environ.get("JOB_THREADS", "4"))))
_running: set[str] = set()
_running_lock = threading.Lock()
BUSY = "This job is already queued or running for these arguments. Wait for it to finish"


def _lock_key(entry: Job, kwargs: dict) -> str | None:
    if entry.once is None:
        return None
    return entry.name + ":" + ":".join(f"{name}={kwargs.get(name)}" for name in entry.once)


def _run_in_slot(entry: Job, kwargs: dict, lock: str | None) -> None:
    try:
        with _slots:
            _run(entry, kwargs)
    finally:
        if lock is not None:
            with _running_lock:
                _running.discard(lock)


def defer(name: str, **kwargs) -> threading.Thread | None:
    """Queue a job by name. Returns the thread running it with the inline backend, else None.

    Raises JobBusy when the job has once and a run with the same arguments is queued or running.
    """
    entry = JOBS[name]
    lock = _lock_key(entry, kwargs)
    if entry.task is not None:
        _open_app()
        task = cast(Any, entry.task)
        if lock is None:
            task.defer(**kwargs)
        else:
            from procrastinate.exceptions import AlreadyEnqueued

            try:
                task.configure(queueing_lock=lock).defer(**kwargs)
            except AlreadyEnqueued as e:
                raise JobBusy(BUSY, 409) from e
        logger.info("job queued name=%s", name)
        return None
    if lock is not None:
        with _running_lock:
            if lock in _running:
                raise JobBusy(BUSY, 409)
            _running.add(lock)
    thread = threading.Thread(target=_run_in_slot, args=(entry, kwargs, lock), name=f"job-{name}", daemon=True)
    thread.start()
    return thread


_open_lock = threading.Lock()
_app_open = False


def _open_app() -> None:
    """Open the app's sync connection once per process, for defer() calls from web requests."""
    global _app_open
    with _open_lock:
        if not _app_open:
            procrastinate_app().open()
            _app_open = True


def start_inline_scheduler() -> threading.Thread | None:
    """Run periodic jobs from a thread in this process. Only for the inline backend."""
    if queue_backend() != "inline":
        return None
    periodic = [(entry, entry.cron) for entry in JOBS.values() if entry.cron]
    if not periodic:
        return None

    def loop() -> None:
        now = datetime.now(UTC)
        due = {entry.name: croniter(cron, now).get_next(datetime) for entry, cron in periodic}
        while True:
            now = datetime.now(UTC)
            for entry, cron in periodic:
                if due[entry.name] <= now:
                    _run(entry, {})
                    due[entry.name] = croniter(cron, now).get_next(datetime)
            time.sleep(30)

    thread = threading.Thread(target=loop, name="job-scheduler", daemon=True)
    thread.start()
    logger.info("inline job scheduler started jobs=%s", ",".join(entry.name for entry, _ in periodic))
    return thread


def queue_counts(db) -> dict[str, int] | None:
    """Jobs in the queue by status on Procrastinate, such as {"todo": 3, "doing": 1}. None with the inline backend."""
    if queue_backend() != "procrastinate":
        return None
    from sqlalchemy import text

    rows = db.execute(text("SELECT status, count(*) FROM procrastinate_jobs GROUP BY status")).all()
    return {str(status): int(count) for status, count in rows}
