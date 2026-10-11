"""Officer dashboard: one overview of an organization, and GitHub Actions runs. No network."""

import pytest


@pytest.fixture
def clean(app):
    from core.db import db_connect
    from modules.dashboard import ci
    from modules.feeds.models import AlertFeed

    ci.clear_cache()
    yield
    ci.clear_cache()
    db = db_connect.SessionLocal()
    db.query(AlertFeed).delete()
    db.commit()
    db.close()


def test_overview_covers_every_module(client, officer_headers, clean):
    from core.db import db_connect
    from modules.feeds.models import AlertFeed
    from modules.organizations.models import Organization

    db = db_connect.SessionLocal()
    org = db.query(Organization).filter_by(prefix="soda").one()
    db.add(
        AlertFeed(organization_id=org.id, key="jobs", kind="github_jobs", config={}, last_error="README unreachable")
    )
    db.commit()
    db.close()

    response = client.get("/api/dashboard/soda/overview", headers=officer_headers)
    assert response.status_code == 200
    body = response.get_json()
    assert body["organization"]["prefix"] == "soda"
    assert {m["name"] for m in body["modules"]} >= {"points", "godfather", "feeds"}
    assert set(body["sections"]) == {
        "members",
        "points",
        "storefront",
        "godfather",
        "feeds",
        "apps",
        "knowledge",
        "agents",
        "accounts",
        "tokens",
    }
    assert body["sections"]["members"]["total"] >= 1
    assert body["problems"] == [{"module": "feeds", "subject": "jobs", "message": "README unreachable"}]
    assert "content" not in str(body["sections"]["agents"])


def test_overview_needs_an_officer(client):
    assert client.get("/api/dashboard/soda/overview").status_code == 401
    assert client.get("/api/dashboard/nope/overview", headers={"Authorization": "Bearer x"}).status_code == 401


class FakeGitHub:
    def __init__(self):
        self.calls = []

    def __call__(self, url, params=None, headers=None, timeout=None):
        self.calls.append((url, headers))
        return self

    status_code = 200

    def json(self):
        return {
            "workflow_runs": [
                {
                    "name": "Check",
                    "head_branch": "main",
                    "event": "push",
                    "status": "completed",
                    "conclusion": "success",
                    "display_title": "Add alerts",
                    "html_url": "https://github.com/a/b/actions/runs/1",
                    "run_started_at": "2026-10-08T04:00:00Z",
                }
            ]
        }


def test_ci_runs_for_listed_repos(client, officer_headers, clean, restore_soda_config, monkeypatch):
    from modules.dashboard import ci

    fake = FakeGitHub()
    monkeypatch.setattr(ci.requests, "get", fake)
    assert client.get("/api/dashboard/soda/ci", headers=officer_headers).get_json() == {"repos": []}

    for bad in ({"repos": "a/b"}, {"repos": ["../x"]}, {"repos": [f"o/r{i}" for i in range(21)]}):
        assert client.put("/api/dashboard/soda/ci/repos", json=bad, headers=officer_headers).status_code == 400
    saved = client.put("/api/dashboard/soda/ci/repos", json={"repos": ["a/b", "a/b"]}, headers=officer_headers)
    assert saved.get_json() == {"repos": ["a/b"]}

    body = client.get("/api/dashboard/soda/ci", headers=officer_headers).get_json()
    assert body["repos"][0]["runs"][0]["conclusion"] == "success" and body["repos"][0]["error"] is None
    client.get("/api/dashboard/soda/ci", headers=officer_headers)
    assert len(fake.calls) == 1
    assert "Authorization" not in fake.calls[0][1]


def test_trends_count_each_day(client, officer_headers, clean):
    from datetime import UTC, datetime

    from core.db import db_connect
    from modules.organizations.models import Organization
    from modules.points.models import Points

    db = db_connect.SessionLocal()
    org = db.query(Organization).filter_by(prefix="soda").one()
    point = Points(organization_id=org.id, points=7.5, event="trend test", timestamp=datetime.now(UTC))
    db.add(point)
    db.commit()
    try:
        response = client.get("/api/dashboard/soda/trends?days=7", headers=officer_headers)
        assert response.status_code == 200
        body = response.get_json()
        assert body["days"] == 7
        series = {item["key"]: item for item in body["series"]}
        assert {"actions", "jobs"} <= set(series)
        assert len(series["actions"]["days"]) == 7
        today = series["points"]["days"][-1]
        assert today["date"] == datetime.now(UTC).date().isoformat()
        assert today["value"] >= 7.5
    finally:
        db.delete(point)
        db.commit()
        db.close()


def test_trends_need_an_officer(client):
    assert client.get("/api/dashboard/soda/trends").status_code == 401
