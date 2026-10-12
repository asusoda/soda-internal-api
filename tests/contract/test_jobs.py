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
