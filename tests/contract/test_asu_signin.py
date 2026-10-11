"""The ASU sign-in: the officer routes, the saved session, the asu.* tools and the expiry notification.

A fake browser stands in for Chromium, so no test opens a browser or reaches ASU.
"""

import json
import logging
import threading
import time
from pathlib import Path

import pytest
from cryptography.fernet import Fernet

from modules.submodules.types import Fetched
from submodules.asu.signin import browser as browsers
from submodules.asu.signin import service, sso, sundevil_central
from submodules.asu.signin.browser import Loaded

BASE = "/api/dashboard/soda/submodules/asu/signin"
NETID = "sparky1"
PASSWORD = "pw-for-tests-only-7Q"  # nosec B105 - a fake password for the fake browser
COOKIE = "cookie-for-tests-only"
FIXTURES = Path(__file__).parent / "asu_fixtures"
LOGIN_PAGE = f"{sso.SERVICE_LOGIN_URL}?msg=LOGIN_REQUIRED"


class FakeBrowser:
    """Signs in when the password is PASSWORD and shows a Duo code. Answers loads from pages, by URL prefix."""

    def __init__(self) -> None:
        self.loads: list[str] = []
        self.pages: dict[str, Loaded] = {}
        self.duo_seen = threading.Event()
        self.approve = threading.Event()
        self.approve.set()

    def sign_in(self, netid, password, report):
        if password != PASSWORD:
            raise sso.BadPassword("Invalid NetID or password")
        report("Password accepted. Approve the Duo push on your phone.", None)
        report("Enter the code 482916 in the Duo app.", "482916")
        self.duo_seen.set()
        if not self.approve.wait(timeout=10):
            raise sso.SignInFailed("Duo was not approved within 10 seconds")
        return {"cookies": [{"name": "session", "value": COOKIE, "domain": "sundevilcentral.eoss.asu.edu"}]}

    def load(self, state, url):
        assert state["cookies"][0]["value"] == COOKIE
        self.loads.append(url)
        for prefix, loaded in self.pages.items():
            if url.startswith(prefix):
                return loaded
        return Loaded(url=url, status=404, html="")


@pytest.fixture
def fake(monkeypatch):
    found = FakeBrowser()
    monkeypatch.setattr(service, "browser", lambda: found)
    monkeypatch.setattr(browsers, "missing", lambda: None)
    return found


@pytest.fixture
def soda(client, officer_headers, monkeypatch, clean_submodules):
    monkeypatch.setenv("SECRETS_KEY", Fernet.generate_key().decode())
    orgs = client.get("/api/organizations/", headers=officer_headers).get_json()
    org_id = next(o["id"] for o in orgs if o["prefix"] == "soda")
    _subscription(org_id, True)
    yield org_id
    client.delete(BASE, headers=officer_headers)
    service._attempts.pop(org_id, None)


def _subscription(org_id: int, on: bool) -> None:
    from core.db import db_connect
    from modules.submodules import service as submodules

    db = db_connect.SessionLocal()
    try:
        if on:
            submodules.subscribe(db, org_id, "asu", actor="test")
        elif "asu" in submodules.subscribed_names(db, org_id):
            submodules.unsubscribe(db, org_id, "asu")
    finally:
        db.close()


def _wait(client, officer_headers, states, seconds=10.0):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        body = client.get(BASE, headers=officer_headers).get_json()
        if body["attempt"] and body["attempt"]["state"] in states:
            return body
        time.sleep(0.02)
    raise AssertionError(f"the attempt did not reach {states}")


def _sign_in(client, officer_headers):
    started = client.post(BASE, json={"netid": NETID, "password": PASSWORD}, headers=officer_headers)
    assert started.status_code == 202, started.get_json()
    return _wait(client, officer_headers, ("done", "failed"))


def _token(client, officer_headers, org_id, scopes):
    body = {"name": "asu-agent", "kind": "agent", "scopes": scopes}
    response = client.post(f"/api/organizations/{org_id}/tokens", json=body, headers=officer_headers)
    assert response.status_code == 201, response.get_json()
    return {"Authorization": f"Bearer {response.get_json()['token']}"}


def _tools(client, headers):
    return [t["name"] for t in client.get("/api/tools", headers=headers).get_json()["tools"]]


def _page(name: str, url: str) -> Loaded:
    return Loaded(url=url, status=200, html=(FIXTURES / name).read_text(encoding="utf-8"))


def test_sign_in_shows_the_duo_code_and_saves_only_the_cookies(client, officer_headers, soda, fake, caplog):
    from core import secrets
    from core.audit import AuditEntry
    from core.db import db_connect

    caplog.set_level(logging.DEBUG)
    fake.approve.clear()
    started = client.post(BASE, json={"netid": NETID, "password": PASSWORD}, headers=officer_headers)
    assert started.status_code == 202, started.get_json()
    assert fake.duo_seen.wait(timeout=10)
    waiting = _wait(client, officer_headers, ("duo_code",))
    assert waiting["attempt"]["code"] == "482916" and "482916" in waiting["attempt"]["message"]
    again = client.post(BASE, json={"netid": NETID, "password": PASSWORD}, headers=officer_headers)
    assert again.status_code == 409
    fake.approve.set()
    done = _wait(client, officer_headers, ("done", "failed"))
    assert done["attempt"]["state"] == "done", done
    assert done["signed_in"] is True and done["signed_in_by"] and done["signed_in_at"]
    assert done["attempt"]["code"] is None
    listed = client.get(BASE, headers=officer_headers).get_json()
    assert listed["signed_in"] is True

    db = db_connect.SessionLocal()
    try:
        raw = secrets.get_secret(db, soda, service.SECRET)
        assert raw is not None and COOKIE in raw
        assert PASSWORD not in raw and NETID not in json.dumps(json.loads(raw)["state"])
        audit = [row.to_dict() for row in db.query(AuditEntry).filter(AuditEntry.action.like("%asu%")).all()]
    finally:
        db.close()
    assert audit and all(PASSWORD not in json.dumps(row) for row in audit)
    assert PASSWORD not in caplog.text
    assert PASSWORD not in json.dumps([waiting, done, listed])


def test_a_bad_password_fails_cleanly(client, officer_headers, soda, fake):
    started = client.post(BASE, json={"netid": NETID, "password": "wrong-password"}, headers=officer_headers)
    assert started.status_code == 202
    failed = _wait(client, officer_headers, ("done", "failed"))
    assert failed["attempt"]["state"] == "failed"
    assert failed["attempt"]["reason"] == "ASU did not accept the NetID or the password"
    assert failed["signed_in"] is False
    assert "wrong-password" not in json.dumps(failed)
    retry = client.post(BASE, json={"netid": NETID, "password": PASSWORD}, headers=officer_headers)
    assert retry.status_code == 202


def test_sign_in_checks_its_input(client, officer_headers, soda, fake):
    for body in ({}, {"netid": NETID}, {"password": PASSWORD}, {"netid": " ", "password": PASSWORD}):
        assert client.post(BASE, json=body, headers=officer_headers).status_code == 400, body


def test_officers_only(client, soda, fake):
    assert client.get(BASE).status_code in (401, 403)
    assert client.post(BASE, json={"netid": NETID, "password": PASSWORD}).status_code in (401, 403)
    assert client.delete(BASE).status_code in (401, 403)


def test_without_playwright_the_sign_in_is_blocked(client, officer_headers, soda, monkeypatch):
    monkeypatch.setattr(browsers, "PACKAGE", "no_such_package_for_platform_tests")
    status = client.get(BASE, headers=officer_headers).get_json()
    assert status["blocked"] == browsers.INSTALL
    refused = client.post(BASE, json={"netid": NETID, "password": PASSWORD}, headers=officer_headers)
    assert refused.status_code == 409 and refused.get_json()["error"] == browsers.INSTALL


def test_tools_show_only_with_a_session(client, officer_headers, soda, fake):
    headers = _token(client, officer_headers, soda, ["asu:read"])
    assert not [n for n in _tools(client, headers) if n.startswith("asu.")]
    assert client.post("/api/tools/asu.clubs", json={"keywords": "robotics"}, headers=headers).status_code == 404
    _sign_in(client, officer_headers)
    assert [n for n in _tools(client, headers) if n.startswith("asu.")] == ["asu.clubs", "asu.events"]
    signed_out = client.delete(BASE, headers=officer_headers).get_json()
    assert signed_out["signed_in"] is False
    assert not [n for n in _tools(client, headers) if n.startswith("asu.")]


def test_tools_need_the_asu_scope(client, officer_headers, soda, fake):
    _sign_in(client, officer_headers)
    headers = _token(client, officer_headers, soda, ["knowledge:read"])
    assert not [n for n in _tools(client, headers) if n.startswith("asu.")]
    assert client.post("/api/tools/asu.clubs", json={"keywords": "robotics"}, headers=headers).status_code == 404
    assert fake.loads == []


def test_clubs_and_events_read_sun_devil_central(client, officer_headers, soda, fake, monkeypatch):
    from submodules.asu.queries import events as public_events

    _sign_in(client, officer_headers)
    fake.pages[sundevil_central.CLUBS_URL] = _page("sundevil_clubs.html", sundevil_central.clubs_url("robotics"))
    fake.pages[sundevil_central.EVENTS_URL] = _page("sundevil_events.html", sundevil_central.EVENTS_URL)
    monkeypatch.setattr(public_events, "public", lambda k: ("https://asuevents.asu.edu/home", "Fall Welcome | Sep 1"))
    headers = _token(client, officer_headers, soda, ["asu:read"])
    clubs = client.post("/api/tools/asu.clubs", json={"keywords": "robotics clubs"}, headers=headers)
    assert clubs.status_code == 200, clubs.get_json()
    result = clubs.get_json()["result"]
    assert result["citation"] == sundevil_central.clubs_url("robotics")
    assert "Robotics Club | Tempe - Academic, Special Interest" in result["text"]
    events = client.post("/api/tools/asu.events", json={"keywords": "career"}, headers=headers).get_json()["result"]
    assert events["text"].startswith("Sun Devil Central\n1 upcoming events shown of 3025")
    assert "ASU Events\nFall Welcome" in events["text"]
    assert fake.loads[-1] == sundevil_central.events_url("career")


def test_tool_results_are_not_indexed(client, officer_headers, soda, fake):
    from core.db import db_connect
    from modules.knowledge.models import KnowledgeSource

    _sign_in(client, officer_headers)
    fake.pages[sundevil_central.CLUBS_URL] = _page("sundevil_clubs.html", sundevil_central.clubs_url("robotics"))
    headers = _token(client, officer_headers, soda, ["asu:read"])
    assert client.post("/api/tools/asu.clubs", json={"keywords": "robotics"}, headers=headers).status_code == 200
    db = db_connect.SessionLocal()
    try:
        keys = [k for (k,) in db.query(KnowledgeSource.key).filter_by(organization_id=soda).all()]
    finally:
        db.close()
    assert not [k for k in keys if "sundevil" in k or k.startswith("asu-live/")]


def test_an_expired_session_gives_an_error_and_one_notification(client, officer_headers, soda, fake, sent):
    from core import webhooks
    from core.db import db_connect

    _sign_in(client, officer_headers)
    fake.pages[sundevil_central.BASE] = Loaded(url=LOGIN_PAGE, status=200, html="<a>SSO Login</a>")
    headers = _token(client, officer_headers, soda, ["asu:read"])
    try:
        first = client.post("/api/tools/asu.clubs", json={"keywords": "robotics"}, headers=headers)
        assert first.status_code == 409 and first.get_json()["error"] == service.EXPIRED
        loads = len(fake.loads)
        second = client.post("/api/tools/asu.clubs", json={"keywords": "robotics"}, headers=headers)
        assert second.status_code == 409 and len(fake.loads) == loads
        status = client.get(BASE, headers=officer_headers).get_json()
        assert status["signed_in"] is False and status["expired_at"]
        db = db_connect.SessionLocal()
        rows = db.query(webhooks.Notification).filter_by(organization_id=soda, event="asu.session_expired").all()
        db.close()
        assert len(rows) == 1 and rows[0].color == webhooks.AMBER
        notices = client.get("/api/dashboard/soda/notifications", headers=officer_headers).get_json()
        expired = [n for n in notices["notifications"] if n["subject"] == "ASU sign-in expired"]
        assert len(expired) == 1 and expired[0]["link"] == "explore?tab=submodules"
        _sign_in(client, officer_headers)
        assert client.get(BASE, headers=officer_headers).get_json()["signed_in"] is True
    finally:
        db = db_connect.SessionLocal()
        db.query(webhooks.Notification).delete()
        db.commit()
        db.close()


def test_events_keep_the_calendar_when_the_session_expired(client, officer_headers, soda, fake, sent, monkeypatch):
    from core import webhooks
    from core.db import db_connect
    from submodules.asu.queries import events as public_events

    _sign_in(client, officer_headers)
    fake.pages[sundevil_central.BASE] = Loaded(url=LOGIN_PAGE, status=200, html="")
    monkeypatch.setattr(public_events, "public", lambda k: ("https://asuevents.asu.edu/home", "Fall Welcome | Sep 1"))
    headers = _token(client, officer_headers, soda, ["asu:read"])
    try:
        result = client.post("/api/tools/asu.events", json={}, headers=headers).get_json()["result"]
        assert result["citation"] == "https://asuevents.asu.edu/home"
        assert f"Sun Devil Central was not read: {service.EXPIRED}." in result["text"]
        assert "ASU Events\nFall Welcome" in result["text"]
    finally:
        db = db_connect.SessionLocal()
        db.query(webhooks.Notification).delete()
        db.commit()
        db.close()


def _fixture(name: str, url: str = "https://sundevilcentral.eoss.asu.edu/") -> Fetched:
    return Fetched(url=url, body=(FIXTURES / name).read_bytes(), content_type="text/html")


def test_login_pages_are_recognized():
    assert sso.is_login_url("https://weblogin.asu.edu/cas/login?service=x")
    assert sso.is_login_url(LOGIN_PAGE)
    assert not sso.is_login_url(sundevil_central.EVENTS_URL)
    assert not sso.is_login_url(sundevil_central.CLUBS_URL)
    assert sso.on_host("https://api-1.duosecurity.com/frame", ("duosecurity.com",))
    assert not sso.on_host("https://duosecurity.com.example.org/", ("duosecurity.com",))


def test_clubs_become_one_entry_each():
    text = sundevil_central.extract_clubs(_fixture("sundevil_clubs.html"))
    assert text.startswith("1 matching groups of 786")
    assert "https://sundevilcentral.eoss.asu.edu/student_community?club_id=101" in text
    assert "contact Pat Example" in text and "Mission: We build robots together." in text
    assert "Membership Benefits: Lab access." in text and "Register new" not in text


def test_events_become_one_line_each():
    lines = sundevil_central.extract_events(_fixture("sundevil_events.html")).splitlines()
    assert lines[0] == "1 upcoming events shown of 3025"
    assert lines[1].startswith("Career Soda Social | Mon, Sep 21, 2026 11 AM")
    assert "Flex Space, Fusion on First | 3 going | FREE | tags Social, In-Person Event" in lines[1]
    assert lines[1].endswith("https://sundevilcentral.eoss.asu.edu/rsvp_boot?id=555")


def test_filler_words_are_not_searched():
    assert sundevil_central.keywords("robotics clubs ASU") == "robotics"
    assert sundevil_central.keywords("upcoming events Sun Devil Central") == ""
    assert sundevil_central.clubs_url("ASU robotics club").endswith("search=robotics")
    assert sundevil_central.events_url("career fair") == f"{sundevil_central.EVENTS_URL}?search_word=career+fair"


def test_empty_and_changed_listings():
    groups = Fetched(url="x", body=b"<h1>Groups (786)</h1><ul></ul>", content_type="text/html")
    assert sundevil_central.extract_clubs(groups).startswith("No groups match")
    none = Fetched(url="x", body=b"<h1>Events (0)</h1><p>No result found</p>", content_type="text/html")
    assert sundevil_central.extract_events(none).startswith("No upcoming")
    changed = Fetched(url="x", body=b"<main><p>New layout event</p></main>", content_type="text/html")
    assert "New layout event" in sundevil_central.extract_events(changed)
    assert "New layout event" in sundevil_central.extract_clubs(changed)


def test_only_an_org_that_subscribes_to_asu_signs_in(client, officer_headers, soda, fake):
    _sign_in(client, officer_headers)
    _subscription(soda, False)
    assert client.get(BASE, headers=officer_headers).status_code == 404
    refused = client.post(BASE, json={"netid": NETID, "password": PASSWORD}, headers=officer_headers)
    assert refused.status_code == 404 and "Subscribe" in refused.get_json()["error"]
    agent = _token(client, officer_headers, soda, ["asu:read"])
    assert "asu.clubs" not in _tools(client, agent)
    # Signing out stays allowed, so the saved session can go
    assert client.delete(BASE, headers=officer_headers).status_code == 200
    _subscription(soda, True)
