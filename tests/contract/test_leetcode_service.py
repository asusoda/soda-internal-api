"""LeetCode links and solves, through the service the Discord cog uses."""

import datetime

import pytest


@pytest.fixture
def db(app):
    from core.db import db_connect
    from modules.leetcode.models import LeetCodeLink, LeetCodeSolve

    session = db_connect.SessionLocal()
    yield session
    session.query(LeetCodeSolve).delete()
    session.query(LeetCodeLink).delete()
    session.commit()
    session.close()


def test_link_solve_and_rank(db):
    from modules.leetcode import service

    service.link(db, "1", "alice_lc")
    service.link(db, "1", "alice_new")
    service.link(db, "2", "bob_lc")
    day = datetime.date(2026, 10, 1)
    service.record_solve(db, "1", "two-sum", day)
    service.record_solve(db, "1", "two-sum", day)  # same day counts once
    service.record_solve(db, "1", "add-two-numbers", day + datetime.timedelta(days=1))
    service.record_solve(db, "2", "two-sum", day)

    assert service.links_for(db, ["1", "2", "3"]) == {"1": "alice_new", "2": "bob_lc"}
    assert service.leaderboard(db) == [("1", "alice_new", 2), ("2", "bob_lc", 1)]
    assert service.stats(db) == {"total_linked": 2, "total_solves": 3, "distinct_solvers": 2}
    assert service.unlink(db, "2") is True
    assert service.unlink(db, "2") is False


QUESTION = {
    "title": "Two Sum",
    "titleSlug": "two-sum",
    "difficulty": "Easy",
    "acRate": 52.3,
    "frontendQuestionId": "1",
    "topicTags": [{"name": "Array"}],
}


@pytest.fixture
def daily_env(db, monkeypatch):
    from core.config import config
    from modules.leetcode.models import LeetCodeDaily

    monkeypatch.setattr(config, "LEETCODE_CHANNEL_ID", "555", raising=False)
    monkeypatch.setattr(config, "LEETCODE_ROLE_PING", "777", raising=False)
    monkeypatch.setattr(config, "LEETCODE_DAILY_TIME", "09:00", raising=False)
    monkeypatch.setattr(config, "TIMEZONE", "America/Phoenix", raising=False)
    sent: list = []

    def send(token, channel_id, payload):
        sent.append((str(channel_id), payload))
        return {"id": str(1000 + len(sent))}

    yield sent, send
    db.query(LeetCodeDaily).delete()
    db.commit()


def _at(hour, minute=0, day=8):
    from zoneinfo import ZoneInfo

    return datetime.datetime(2026, 10, day, hour, minute, tzinfo=ZoneInfo("America/Phoenix"))


def test_daily_post_happens_once_after_the_time(db, daily_env):
    from modules.leetcode import daily

    sent, send = daily_env
    reacted: list = []
    react = lambda *a: reacted.append(a)  # noqa: E731
    fetch = lambda: QUESTION  # noqa: E731

    assert daily.post_daily(db, _at(8, 59), fetch, send, react)["instance"]["reason"] == "not yet"
    assert daily.post_daily(db, _at(9, 0), fetch, send, react)["instance"]["posted"] is True
    assert daily.post_daily(db, _at(9, 5), fetch, send, react)["instance"]["reason"] == "already posted"
    assert len(sent) == 1 and reacted[0][2] == "1001"
    channel, payload = sent[0]
    assert channel == "555" and payload["content"] == "<@&777>"
    assert payload["embeds"][0]["url"] == "https://leetcode.com/problems/two-sum/"
    assert payload["embeds"][0]["fields"][3]["value"] == "||`Array`||"
    assert daily.post_daily(db, _at(9, 0, day=9), fetch, send, react)["instance"]["posted"] is True


def test_a_failed_post_gives_the_day_back(db, daily_env):
    from core.integrations.discord import DiscordUnavailable
    from modules.leetcode import daily

    _, send = daily_env

    def down(*args):
        raise DiscordUnavailable("down")

    failed = daily.post_daily(db, _at(10), lambda: QUESTION, down, lambda *a: None)
    assert failed["instance"] == {"posted": False, "reason": "discord unavailable"}
    assert daily.post_daily(db, _at(10, 5), lambda: QUESTION, send, lambda *a: None)["instance"]["posted"] is True


def test_verify_records_and_announces_each_solve_once(db, daily_env):
    from modules.leetcode import daily, service

    sent, send = daily_env
    daily.post_daily(db, _at(9), lambda: QUESTION, send, lambda *a: None)
    service.link(db, "1", "alice_lc")
    service.link(db, "2", "bob_lc")
    solved_at = int(_at(11).timestamp())
    yesterday = int(_at(11, day=7).timestamp())
    history = {
        "alice_lc": [{"titleSlug": "two-sum", "timestamp": str(solved_at)}],
        "bob_lc": [{"titleSlug": "two-sum", "timestamp": str(yesterday)}],
    }

    result = daily.verify(db, _at(12), lambda name: history[name], send)
    assert result == {"checked": 2, "verified": 1}
    reply = sent[-1][1]
    assert reply["message_reference"]["message_id"] == "1001" and "<@1>" in reply["content"]
    assert daily.verify(db, _at(12, 10), lambda name: history[name], send) == {"checked": 1, "verified": 0}
    assert service.leaderboard(db) == [("1", "alice_lc", 1)]


@pytest.mark.parametrize("error", [TimeoutError(), "client"])
def test_verify_skips_a_member_whose_read_fails(db, daily_env, error):
    import aiohttp

    from modules.leetcode import daily, service

    sent, send = daily_env
    daily.post_daily(db, _at(9), lambda: QUESTION, send, lambda *a: None)
    service.link(db, "1", "alice_lc")
    service.link(db, "2", "bob_lc")
    solved = [{"titleSlug": "two-sum", "timestamp": str(int(_at(11).timestamp()))}]

    def submissions(name):
        if name == "alice_lc":
            raise aiohttp.ClientConnectionError("reset") if error == "client" else error
        return solved

    assert daily.verify(db, _at(12), submissions, send) == {"checked": 2, "verified": 1}
    assert service.leaderboard(db) == [("2", "bob_lc", 1)]


def test_no_channel_means_no_post(db, daily_env, monkeypatch):
    from core.config import config
    from modules.leetcode import daily

    monkeypatch.setattr(config, "LEETCODE_CHANNEL_ID", None, raising=False)
    assert daily.post_daily(db, _at(10), lambda: QUESTION) == {}


@pytest.fixture
def soda(db, client, officer_headers):
    from modules.organizations.models import Organization

    org = db.query(Organization).filter_by(prefix="soda").one()
    yield org
    db.refresh(org)
    config = dict(org.config or {})
    config.pop("leetcode", None)
    config.get("modules", {}).pop("leetcode", None)
    org.config = config
    db.commit()


def _settings(client, headers, org_id, body):
    return client.put(f"/api/organizations/{org_id}/leetcode", json=body, headers=headers)


def test_officers_set_their_orgs_daily_post(client, officer_headers, soda):
    assert (
        _settings(client, officer_headers, soda.id, {"channel_id": "123456", "daily_time": "08:30"}).status_code == 200
    )
    got = client.get(f"/api/organizations/{soda.id}/leetcode", headers=officer_headers).get_json()
    assert got == {"settings": {"channel_id": "123456", "role_ping": None, "daily_time": "08:30"}, "enabled": True}
    cleared = _settings(client, officer_headers, soda.id, {"daily_time": None}).get_json()
    assert cleared["settings"] == {"channel_id": "123456", "role_ping": None, "daily_time": None}

    # Replacing the rest of the org config keeps these settings
    client.put(f"/api/organizations/{soda.id}", json={"config": {"theme": "dark"}}, headers=officer_headers)
    got = client.get(f"/api/organizations/{soda.id}/leetcode", headers=officer_headers).get_json()
    assert got["settings"]["channel_id"] == "123456"


@pytest.mark.parametrize(
    "body",
    [
        None,
        {},
        {"channel": "1"},
        {"channel_id": "abc"},
        {"channel_id": 123456},
        {"daily_time": "9am"},
        {"daily_time": "24:00"},
    ],
)
def test_bad_leetcode_settings_are_refused(client, officer_headers, soda, body):
    assert _settings(client, officer_headers, soda.id, body).status_code == 400


def test_each_org_gets_its_own_post_and_member_only_announcements(db, daily_env, client, officer_headers, soda):
    from modules.leetcode import daily, service

    sent, send = daily_env
    _settings(client, officer_headers, soda.id, {"channel_id": "999999", "role_ping": "888888", "daily_time": "10:00"})
    scope = f"org:{soda.id}"
    db.expire_all()

    first = daily.post_daily(db, _at(9), lambda: QUESTION, send, lambda *a: None)
    assert first["instance"]["posted"] is True and first[scope]["reason"] == "not yet"
    second = daily.post_daily(db, _at(10), lambda: QUESTION, send, lambda *a: None)
    assert second[scope]["posted"] is True and second["instance"]["reason"] == "already posted"
    assert [channel for channel, _ in sent] == ["555", "999999"]
    assert sent[1][1]["content"] == "<@&888888>"

    service.link(db, "1", "alice_lc")
    service.link(db, "2", "bob_lc")
    solved_at = str(int(_at(11).timestamp()))
    history = {name: [{"titleSlug": "two-sum", "timestamp": solved_at}] for name in ("alice_lc", "bob_lc")}
    members = {(str(soda.guild_id), "1")}
    result = daily.verify(db, _at(12), lambda name: history[name], send, lambda guild, user: (guild, user) in members)
    assert result == {"checked": 2, "verified": 2}
    replies = [(channel, payload["content"]) for channel, payload in sent[2:]]
    assert sorted(c for c, _ in replies) == ["555", "555", "999999"]
    assert [text for c, text in replies if c == "999999"] == ["✅ <@1> solved today's challenge as **alice_lc**!"]


def test_turning_leetcode_off_stops_the_orgs_post(db, daily_env, client, officer_headers, soda, monkeypatch):
    from core.config import config
    from modules.leetcode import daily

    monkeypatch.setattr(config, "LEETCODE_CHANNEL_ID", None, raising=False)
    _settings(client, officer_headers, soda.id, {"channel_id": "999999"})
    client.put(f"/api/organizations/{soda.id}/modules", json={"modules": {"leetcode": False}}, headers=officer_headers)
    db.expire_all()
    assert daily.post_daily(db, _at(10), lambda: QUESTION) == {}
