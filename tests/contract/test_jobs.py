"""Jobs run inline on SQLite and through the Procrastinate queue on Postgres."""

import io
import threading

import pytest

from tests.contract.conftest import MEMBER_EMAIL


def _wait_for_jobs():
    for thread in threading.enumerate():
        if thread.name.startswith("job-") and thread.name != "job-scheduler":
            thread.join(timeout=10)


def test_modules_register_their_jobs(app):
    from core import jobs

    assert jobs.JOBS["auth.cleanup_tokens"].cron == "0 * * * *"
    assert jobs.JOBS["points.import_event_csv"].cron is None
    assert "calendar.sync_all" in jobs.JOBS


def test_inline_defer_runs_the_job():
    from core import jobs

    seen = []
    jobs.job("test.inline")(lambda value: seen.append(value))
    try:
        thread = jobs.defer("test.inline", value=3)
        assert thread is not None
        thread.join(timeout=5)
    finally:
        jobs.JOBS.pop("test.inline")
    assert seen == [3]


def _csv_points():
    from core.db import db_connect
    from modules.points.models import Points

    db = db_connect.SessionLocal()
    try:
        total = 0.0
        for row in db.query(Points).filter_by(event="CSV Night").all():
            assert row.points is not None
            total += row.points
        return total
    finally:
        db.close()


def test_csv_upload_awards_points_through_a_job(client, officer_headers):
    csv_body = f"First Name,Last Name,Email,Checked-In Date\nAlice,A,{MEMBER_EMAIL},2026-10-01\n"
    response = client.post(
        "/api/points/soda/uploadEventCSV",
        data={"file": (io.BytesIO(csv_body.encode()), "event.csv"), "event_name": "CSV Night", "event_points": "4"},
        headers=officer_headers,
        content_type="multipart/form-data",
    )
    assert response.status_code == 202, response.get_data(as_text=True)
    _wait_for_jobs()
    assert _csv_points() == 4


@pytest.fixture
def procrastinate_backend(monkeypatch):
    from core.db import db_connect

    if db_connect.engine.dialect.name != "postgresql":
        pytest.skip("Procrastinate needs Postgres (set TEST_DATABASE_URL)")
    from core import jobs

    monkeypatch.setenv("JOBS_BACKEND", "procrastinate")
    monkeypatch.setattr(jobs, "_app", None)
    monkeypatch.setattr(jobs, "_app_open", False)
    yield jobs
    if jobs._app is not None:
        jobs._app.close()


def test_queued_job_runs_in_the_worker(procrastinate_backend):
    jobs = procrastinate_backend
    seen = []
    jobs.job("test.queued", retry=1)(lambda value: seen.append(value))
    try:
        app = jobs.procrastinate_app()
        jobs._open_app()
        app.schema_manager.apply_schema()
        jobs.defer("test.queued", value=7)
        app.run_worker(wait=False, install_signal_handlers=False, listen_notify=False)
    finally:
        jobs.JOBS.pop("test.queued")
    assert seen == [7]


def test_periodic_jobs_do_not_wait_for_each_other():
    from datetime import UTC, datetime, timedelta

    from core import jobs

    release = threading.Event()
    fast_ran = threading.Event()
    slow_runs = []

    def slow():
        slow_runs.append(1)
        release.wait(timeout=10)

    slow_entry = jobs.Job(name="test.slow", func=slow, cron="* * * * *", retry=0, audit=False)
    fast_entry = jobs.Job(name="test.fast", func=fast_ran.set, cron="* * * * *", retry=0, audit=False)
    periodic = [(slow_entry, "* * * * *"), (fast_entry, "* * * * *")]
    past = datetime.now(UTC) - timedelta(minutes=1)
    due = {"test.slow": past, "test.fast": past}
    active: dict[str, threading.Thread] = {}
    try:
        jobs._start_due(periodic, due, active)
        assert fast_ran.wait(timeout=5)
        # The slow job is due again while its first run still runs; no second run starts
        due["test.slow"] = past
        jobs._start_due(periodic, due, active)
        assert len(slow_runs) == 1
    finally:
        release.set()
        for thread in active.values():
            thread.join(timeout=10)


def test_scheduler_starts_when_the_api_serves_not_on_import(tmp_path):
    import os
    import subprocess  # nosec B404 - runs this repo's Python in a child process
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    script = (
        "import sys, threading\n"
        f"sys.path.insert(0, {str(root)!r})\n"
        "import main\n"
        "names = lambda: [t.name for t in threading.enumerate()]\n"
        "print('import', 'job-scheduler' in names())\n"
        "main.app.test_client().get('/health')\n"
        "print('serve', 'job-scheduler' in names())\n"
    )
    env = {**os.environ, "JOBS_SCHEDULER": "true", "JOBS_BACKEND": "inline"}
    env["DATABASE_URL"] = f"sqlite:///{tmp_path / 'user.db'}"
    result = subprocess.run(  # nosec B603 - fixed arguments, no user input
        [sys.executable, "-c", script], cwd=tmp_path, env=env, capture_output=True, text=True, timeout=120
    )
    assert result.returncode == 0, result.stderr
    assert "import False" in result.stdout
    assert "serve True" in result.stdout
