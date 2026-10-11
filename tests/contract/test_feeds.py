"""Alert feeds: job tables and hackathon listings posted to Discord webhooks. No network."""

import datetime
import json
from typing import cast

import pytest
from cryptography.fernet import Fernet

WEBHOOK = "https://discord.com/api/webhooks/123/abc-DEF_1"

ROW = '| {company} | {role} | {location} | <a href="{url}"><img src="https://i.imgur.com/x.png" alt="Apply"></a> | {date} |'


def _readme(*rows: str) -> str:
    header = "| Company | Role | Location | Application/Link | Date Posted |\n| ------- | ---- | -------- | --- | --- |"
    return "# Jobs\n\n" + header + "\n" + "\n".join(rows) + "\n\nFooter text\n"


def _row(company, role, url, date="Oct 07", location="Tempe, AZ"):
    return ROW.format(company=company, role=role, location=location, url=url, date=date)


def test_job_table_parsing():
    from modules.feeds import github_jobs as jobs_table

    markdown = _readme(
        _row("Acme", "Software Intern \U0001f6c2", "https://jobs.acme.com/1?utm_source=list"),
        _row("↳", "Data Intern \U0001f1fa\U0001f1f8", "https://jobs.acme.com/2"),
        _row("Closed Co", "ML Intern \U0001f512", "https://jobs.closed.com/3"),
        _row("**Bold**", "Infra Intern", "https://jobs.bold.com/4", location="Austin, TX</br>Remote"),
        "| NoLink | Intern | Tempe | none | Oct 07 |",
    )
    rows = jobs_table.parse(markdown)
    assert [(r["company"], r["role"]) for r in rows] == [
        ("Acme", "Software Intern"),
        ("Acme", "Data Intern"),
        ("Closed Co", "ML Intern"),
        ("Bold", "Infra Intern"),
    ]
    assert rows[0]["no_sponsorship"] and rows[1]["requires_citizenship"] and rows[2]["closed"]
    assert rows[3]["location"] == "Austin, TX / Remote"
    assert jobs_table.item_key(rows[0]) == jobs_table.item_key({**rows[0], "url": "https://jobs.acme.com/1"})

    config = jobs_table.validate({"repo": "someone/jobs"})
    items = jobs_table.fetch(config, lambda url: markdown, datetime.date(2026, 10, 8))
    assert [i.title for i in items] == ["New Job: Acme", "New Job: Acme", "New Job: Bold"]
    assert ("Requirements", "No visa sponsorship") in items[0].fields

    old = _readme(_row("Old", "Intern", "https://x.com/1", date="Sep 01"))
    assert jobs_table.fetch(config, lambda url: old, datetime.date(2026, 10, 8)) == []
    assert len(jobs_table.fetch({**config, "max_age_days": 0}, lambda url: old, datetime.date(2026, 10, 8))) == 1
    # A date after today is last year's
    assert jobs_table.posted_within("Dec 30", 5, datetime.date(2027, 1, 2))
    assert not jobs_table.posted_within("Dec 30", 1, datetime.date(2027, 1, 2))


@pytest.mark.parametrize(
    "config",
    [
        {},
        {"repo": "../etc"},
        {"repo": "a/b", "path": "../x.md"},
        {"repo": "a/b", "path": "x.txt"},
        {"repo": "a/b", "max_age_days": -1},
    ],
)
def test_job_table_config_is_checked(config):
    from modules.feeds import github_jobs as jobs_table

    with pytest.raises(ValueError):
        jobs_table.validate(config)


def test_hackathon_sources():
    from modules.feeds import hackathons

    now = datetime.datetime(2026, 10, 8, 12)
    responses = {
        "https://hackathons.hackclub.com/api/events/upcoming": [
            {
                "name": "Desert Hacks",
                "start": "2026-10-20T16:00:00Z",
                "end": "2026-10-21T20:00:00Z",
                "city": "Tempe",
                "state": "AZ",
                "website": "https://deserthacks.dev",
            },
            {"name": "Far Future", "start": "2027-06-01T00:00:00Z", "end": "2027-06-02T00:00:00Z", "virtual": True},
        ],
        "https://euro-hackathons.com/api/hackathons?status=upcoming": {
            "hackathons": [
                {"name": "desert  hacks", "startDate": "2026-10-19", "mode": "online", "url": "javascript:x"}
            ]
        },
    }

    def get(url):
        if url in responses:
            return json.dumps(responses[url])
        if "hackalist" in url:
            return json.dumps(
                {
                    "October": [
                        {
                            "title": "Lab Jam",
                            "startDate": "October 30",
                            "endDate": "October 31",
                            "year": "2026",
                            "url": "https://labjam.org",
                        }
                    ]
                }
            )
        raise hackathons.SourceError("offline")

    items = hackathons.fetch(hackathons.validate({}), get, now)
    # Same name from two sources is one event; the earliest listing wins; Far Future is past the window
    assert [i.key for i in items] == ["desert hacks", "lab jam"]
    assert items[0].url == "" and dict(items[0].fields)["Type"] == "Online"
    assert dict(items[1].fields)["Dates"] == "Oct 30, 2026 to Oct 31, 2026"

    def down(url):
        raise hackathons.SourceError("offline")

    with pytest.raises(hackathons.SourceError):
        hackathons.fetch(hackathons.validate({"sources": ["hackclub"]}), down, now)
    with pytest.raises(ValueError):
        hackathons.validate({"sources": ["mlh"]})


@pytest.fixture
def alerts(app, monkeypatch):
    from core.db import db_connect
    from core.secrets import OrgSecret
    from modules.feeds import service
    from modules.feeds.models import AlertFeed, AlertPost, AlertRun

    monkeypatch.setenv("SECRETS_KEY", Fernet.generate_key().decode())
    monkeypatch.setattr(service, "POST_GAP_SECONDS", 0)
    state: dict = {"readme": _readme(_row("Acme", "Intern", "https://jobs.acme.com/1")), "sent": []}
    monkeypatch.setattr(service, "http_get", lambda url: state["readme"])
    monkeypatch.setattr(service, "post_webhook", lambda url, payload: state["sent"].append((url, payload)))
    monkeypatch.setattr(service, "utcnow", lambda: datetime.datetime(2026, 10, 8, 12))
    yield state
    db = db_connect.SessionLocal()
    db.query(AlertRun).delete()
    db.query(AlertPost).delete()
    db.query(AlertFeed).delete()
    db.query(OrgSecret).filter(OrgSecret.name.like("alert_webhook_%")).delete(synchronize_session=False)
    db.commit()
    db.close()


def _put(client, headers, key="internships", **body):
    payload = {"kind": "github_jobs", "config": {"repo": "someone/jobs"}, "webhook_url": WEBHOOK, **body}
    return client.put(f"/api/feeds/soda/feeds/{key}", json=payload, headers=headers)


def _run(key="internships", **kwargs):
    from core.db import db_connect
    from modules.feeds import service
    from modules.organizations.models import Organization

    db = db_connect.SessionLocal()
    try:
        org = db.query(Organization).filter_by(prefix="soda").one()
        return service.run_now(db, cast(int, org.id), key, **kwargs)
    finally:
        db.close()


def test_feed_lifecycle(client, officer_headers, alerts):
    created = _put(client, officer_headers)
    assert created.status_code == 201
    feed = created.get_json()["feed"]
    assert feed["webhook_set"] is True and feed["every_hours"] == 3
    assert "webhook" not in json.dumps(feed).replace("webhook_set", "")

    # First run records what is listed without posting it
    assert _run() == {"key": "internships", "found": 1, "new": 1, "posted": 0, "recorded": True}
    assert alerts["sent"] == []

    alerts["readme"] = _readme(
        _row("Acme", "Intern", "https://jobs.acme.com/1"), _row("Beta", "ML Intern \U0001f6c2", "https://beta.io/7")
    )
    assert _run()["posted"] == 1
    url, payload = alerts["sent"][0]
    assert url == WEBHOOK
    assert payload["embeds"][0]["title"] == "New Job: Beta" and payload["embeds"][0]["url"] == "https://beta.io/7"
    assert _run()["posted"] == 0

    listed = client.get("/api/feeds/soda/feeds", headers=officer_headers).get_json()["feeds"]
    assert [(f["key"], f["posted"]) for f in listed] == [("internships", 1)]

    updated = _put(client, officer_headers, every_hours=6, webhook_url=None)
    assert updated.status_code == 200 and updated.get_json()["feed"]["every_hours"] == 6
    deleted = client.delete("/api/feeds/soda/feeds/internships", headers=officer_headers)
    assert deleted.get_json() == {"deleted": True}
    assert client.get("/api/feeds/soda/feeds/internships", headers=officer_headers).status_code == 404


def test_post_existing_and_failures(client, officer_headers, alerts, monkeypatch):
    from modules.feeds import service

    _put(client, officer_headers)
    assert _run(post_existing=True)["posted"] == 1

    def broken(url, payload):
        raise service.requests.HTTPError("500")

    monkeypatch.setattr(service, "post_webhook", broken)
    alerts["readme"] = _readme(_row("Gamma", "Intern", "https://g.io/1"))
    result = _run()
    assert result["posted"] == 0 and "Discord webhook failed" in result["error"]

    # The unposted item goes out on the next run
    monkeypatch.setattr(service, "post_webhook", lambda url, payload: alerts["sent"].append(payload))
    assert _run()["posted"] == 1

    def offline(url):
        raise service.SourceError("README unreachable")

    monkeypatch.setattr(service, "http_get", offline)
    assert _run() == {"key": "internships", "error": "README unreachable"}
    feed = client.get("/api/feeds/soda/feeds/internships", headers=officer_headers).get_json()["feed"]
    assert feed["last_error"] == "README unreachable"

    history = client.get("/api/feeds/soda/feeds/internships/history", headers=officer_headers).get_json()
    runs = history["runs"]
    assert [(r["found"], r["posted"], r["error"]) for r in runs] == [
        (None, 0, "README unreachable"),
        (1, 1, None),
        (1, 0, "Discord webhook failed: 500"),
        (1, 1, None),
    ]
    assert [(i["title"], i["posted"]) for i in history["items"]][0] == ("New Job: Gamma", True)
    assert client.get("/api/feeds/soda/feeds/nope/history", headers=officer_headers).status_code == 404


def test_runs_are_pruned(client, officer_headers, alerts, monkeypatch):
    from modules.feeds import service

    monkeypatch.setattr(service, "RUNS_KEPT", 3)
    _put(client, officer_headers)
    for _ in range(5):
        _run()
    assert len(client.get("/api/feeds/soda/feeds/internships/history", headers=officer_headers).get_json()["runs"]) == 3


@pytest.mark.parametrize(
    "body",
    [
        {"kind": "rss"},
        {"webhook_url": "https://example.com/hook"},
        {"webhook_url": "http://discord.com/api/webhooks/1/a"},
        {"every_hours": 0},
        {"enabled": "yes"},
        {"config": {"repo": "nope"}},
    ],
)
def test_bad_feeds_are_refused(client, officer_headers, alerts, body):
    assert _put(client, officer_headers, **body).status_code == 400


def test_feed_rules(client, officer_headers, alerts):
    assert _put(client, officer_headers, key="Bad Key").status_code == 400
    no_hook = client.put(
        "/api/feeds/soda/feeds/new", json={"kind": "hackathons", "config": {}}, headers=officer_headers
    )
    assert no_hook.status_code == 400
    _put(client, officer_headers)
    assert _put(client, officer_headers, kind="hackathons", config={}).status_code == 409
    assert client.get("/api/feeds/soda/feeds").status_code == 401


def test_due_feeds_respect_schedule_and_switch(client, officer_headers, alerts, restore_soda_config):
    from core.db import db_connect
    from modules.feeds import service

    _put(client, officer_headers)
    _put(client, officer_headers, key="paused", enabled=False)
    db = db_connect.SessionLocal()
    try:
        now = datetime.datetime(2026, 10, 8, 12)
        assert [f.key for f in service.due(db, now)] == ["internships"]
        assert service.run_due(db, now) == {"ran": 1, "failed": 0}
        assert service.due(db, now + datetime.timedelta(hours=2)) == []
        assert [f.key for f in service.due(db, now + datetime.timedelta(hours=3))] == ["internships"]
    finally:
        db.close()

    orgs = client.get("/api/organizations/", headers=officer_headers).get_json()
    soda_id = next(o["id"] for o in orgs if o["prefix"] == "soda")
    client.put(f"/api/organizations/{soda_id}/modules", json={"modules": {"feeds": False}}, headers=officer_headers)
    assert client.get("/api/feeds/soda/feeds", headers=officer_headers).get_json()["feeds"] == []
    assert client.get("/api/feeds/soda/feeds/internships", headers=officer_headers).status_code == 404
    db = db_connect.SessionLocal()
    try:
        assert service.due(db, datetime.datetime(2026, 10, 9)) == []
    finally:
        db.close()
