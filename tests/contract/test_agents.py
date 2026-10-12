"""Agent storage: conversations, memories, profile graph and pending actions, scoped by token org and member."""

import datetime
import random
import uuid
from typing import Any

import pytest
from cryptography.fernet import Fernet

from tests.contract.conftest import MEMBER_DISCORD_ID


@pytest.fixture
def soda_id(client, officer_headers):
    orgs = client.get("/api/organizations/", headers=officer_headers).get_json()
    return next(o["id"] for o in orgs if o["prefix"] == "soda")


def _issue(prefix, *scopes):
    from core.db import db_connect
    from modules.auth import machine_tokens
    from modules.organizations.models import Organization

    db = db_connect.SessionLocal()
    try:
        org_id = db.query(Organization.id).filter_by(prefix=prefix).scalar()
        value, _ = machine_tokens.issue(
            db, organization_id=org_id, name="club-agent", kind="agent", scopes=list(scopes)
        )
        return {"Authorization": f"Bearer {value}"}
    finally:
        db.close()


@pytest.fixture
def agent(app):
    return _issue("soda", "agents:read", "agents:write")


@pytest.fixture
def member():
    return f"/api/agents/members/{random.randint(10**17, 10**18)}"


def _conversation(client, agent, member, channel="chan-1", visibility="public"):
    cid = str(uuid.uuid4())
    response = client.put(
        f"{member}/conversations/{cid}", json={"channel_id": channel, "visibility": visibility}, headers=agent
    )
    assert response.status_code == 200, response.get_json()
    return cid


def test_conversation_round_trip(client, agent, member):
    cid = _conversation(client, agent, member)
    messages = [{"role": "user", "content": {"text": f"m{i}"}} for i in range(4)]
    seqs = client.post(f"{member}/conversations/{cid}/messages", json={"messages": messages}, headers=agent)
    assert seqs.status_code == 201
    seqs = seqs.get_json()["seqs"]
    assert seqs == sorted(seqs)

    loaded = client.get(f"{member}/conversations/{cid}/messages?limit=2", headers=agent).get_json()["messages"]
    assert [m["content"]["text"] for m in loaded] == ["m2", "m3"]

    summary = {"content": {"text": "summary of m0 m1 m2"}, "covers": seqs[2]}
    assert client.post(f"{member}/conversations/{cid}/summary", json=summary, headers=agent).status_code == 201
    loaded = client.get(f"{member}/conversations/{cid}/messages", headers=agent).get_json()["messages"]
    assert [m["role"] for m in loaded] == ["summary", "user"]
    assert loaded[0]["position"] == seqs[2]
    assert loaded[1]["content"]["text"] == "m3"

    assert client.get(f"{member}/conversations/{cid}?visibility=public", headers=agent).get_json()["owned"] is True
    assert client.get(f"{member}/conversations/{cid}?visibility=private", headers=agent).get_json()["owned"] is False


def test_ensure_refuses_another_members_conversation(client, agent, member):
    cid = _conversation(client, agent, member)
    other = f"/api/agents/members/{random.randint(10**17, 10**18)}"
    body = {"channel_id": "chan-1", "visibility": "public"}
    assert client.put(f"{other}/conversations/{cid}", json=body, headers=agent).status_code == 409
    moved = {"channel_id": "chan-2", "visibility": "public"}
    assert client.put(f"{member}/conversations/{cid}", json=moved, headers=agent).status_code == 409
    write = {"messages": [{"role": "user", "content": "x"}]}
    assert client.post(f"{other}/conversations/{cid}/messages", json=write, headers=agent).status_code == 409
    assert client.get(f"{other}/conversations/{cid}/messages", headers=agent).get_json()["messages"] == []


def test_latest_and_end(client, agent, member):
    first = _conversation(client, agent, member, channel="dm")
    second = _conversation(client, agent, member, channel="dm")
    client.post(
        f"{member}/conversations/{first}/messages", json={"messages": [{"role": "user", "content": "x"}]}, headers=agent
    )
    assert client.get(f"{member}/channels/dm/latest", headers=agent).get_json()["id"] == first
    assert client.post(f"{member}/channels/dm/end", headers=agent).get_json()["ended"] == 2
    assert client.get(f"{member}/channels/dm/latest", headers=agent).get_json()["id"] is None
    assert second


def test_memories(client, agent, member, monkeypatch):
    monkeypatch.setenv("SECRETS_KEY", Fernet.generate_key().decode())
    client.post(
        f"{member}/memories", json={"kind": "semantic", "content": "likes Rust", "confidence": 0.4}, headers=agent
    )
    client.post(f"{member}/memories", json={"kind": "episodic", "content": "asked about CSE 310"}, headers=agent)
    secret = {"kind": "semantic", "content": "has a disability accommodation", "sensitivity": "sensitive"}
    assert client.post(f"{member}/memories", json=secret, headers=agent).status_code == 201

    recalled = client.get(f"{member}/memories", headers=agent).get_json()["memories"]
    assert [m["content"] for m in recalled][-1] == "likes Rust"  # lowest confidence last
    assert "has a disability accommodation" in [m["content"] for m in recalled]
    semantic = client.get(f"{member}/memories?kinds=semantic", headers=agent).get_json()["memories"]
    assert {m["kind"] for m in semantic} == {"semantic"}

    from core.db import db_connect
    from modules.agents.models import AgentMemory

    db = db_connect.SessionLocal()
    try:
        stored = db.query(AgentMemory).filter_by(sensitivity="sensitive").all()
        assert stored and all("disability" not in str(row.content) for row in stored)
    finally:
        db.close()

    monkeypatch.delenv("SECRETS_KEY")
    assert client.post(f"{member}/memories", json=secret, headers=agent).status_code == 503
    after = client.get(f"{member}/memories", headers=agent).get_json()["memories"]
    assert "has a disability accommodation" not in [m["content"] for m in after]


def test_profile_graph(client, agent, member):
    me = {"kind": "person", "label": "me"}
    facts: list[dict[str, Any]] = [
        {"subject": me, "relation": "majors_in", "object": {"kind": "major", "label": "CS"}, "confidence": 0.6},
        {"subject": me, "relation": "takes", "object": {"kind": "course", "label": "CSE 310"}},
    ]
    assert client.post(f"{member}/profile/facts", json={"facts": facts}, headers=agent).get_json()["stored"] == 2
    facts[0]["confidence"] = 0.3
    client.post(f"{member}/profile/facts", json={"facts": facts[:1]}, headers=agent)

    profile = client.get(f"{member}/profile", headers=agent).get_json()
    assert {n["label"] for n in profile["nodes"]} == {"me", "CS", "CSE 310"}
    major = next(r for r in profile["relations"] if r["relation"] == "majors_in")
    assert major["confidence"] == 0.6  # the higher confidence is kept

    found = client.get(f"{member}/profile/matching?subject=ME&relation=TAKES", headers=agent).get_json()
    assert [r["object"]["label"] for r in found["relations"]] == ["CSE 310"]

    drop = {"subject": "me", "relation": "takes", "object": "cse 310"}
    assert client.delete(f"{member}/profile/relations", json=drop, headers=agent).get_json()["deleted"] is True
    assert client.delete(f"{member}/profile/nodes?label=CS", headers=agent).get_json()["deleted"] == 1
    profile = client.get(f"{member}/profile", headers=agent).get_json()
    assert {n["label"] for n in profile["nodes"]} == {"me", "CSE 310"}
    assert profile["relations"] == []

    client.post(f"{member}/memories", json={"kind": "semantic", "content": "x"}, headers=agent)
    assert client.delete(f"{member}/data", headers=agent).get_json()["deleted"] == 3
    assert client.get(f"{member}/memories", headers=agent).get_json()["memories"] == []


def test_pending_action_claims_once(client, agent, member):
    token = str(uuid.uuid4())
    hold = {"action": {"tool": "rsvp", "args": {"event": 1}}, "payload_hash": "abc", "ttl_seconds": 60}
    assert client.put(f"{member}/pending/{token}", json=hold, headers=agent).status_code == 201
    assert client.put(f"{member}/pending/{token}", json=hold, headers=agent).status_code == 409

    other = f"/api/agents/members/{random.randint(10**17, 10**18)}"
    assert client.post(f"{other}/pending/{token}/claim", json={"approved": True}, headers=agent).status_code == 404
    claimed = client.post(f"{member}/pending/{token}/claim", json={"approved": True}, headers=agent)
    assert claimed.get_json() == {"action": hold["action"], "payload_hash": "abc"}
    assert client.post(f"{member}/pending/{token}/claim", json={"approved": True}, headers=agent).status_code == 404


def test_tokens_are_scoped(client, member, app):
    cid = str(uuid.uuid4())
    body = {"channel_id": "c", "visibility": "public"}
    assert client.put(f"{member}/conversations/{cid}", json=body).status_code == 401
    reader = _issue("soda", "agents:read")
    assert client.put(f"{member}/conversations/{cid}", json=body, headers=reader).status_code == 403
    assert client.get(f"{member}/memories", headers=reader).status_code == 200
    assert client.get("/api/agents/members/not-a-number/memories", headers=reader).status_code == 400


def test_orgs_do_not_share_agent_data(client, agent, member):
    client.post(f"{member}/memories", json={"kind": "semantic", "content": "soda only"}, headers=agent)
    ais = _issue("ais", "agents:read", "agents:write")
    assert client.get(f"{member}/memories", headers=ais).get_json()["memories"] == []


def test_member_sees_and_deletes_own_data(client, member_client, agent):
    member = f"/api/agents/members/{MEMBER_DISCORD_ID}"
    cid = _conversation(client, agent, member)
    client.post(f"{member}/memories", json={"kind": "semantic", "content": "mine"}, headers=agent)

    mine = member_client.get("/api/agents/soda/me").get_json()
    assert cid in [c["id"] for c in mine["conversations"]]
    assert "mine" in [m["content"] for m in mine["memories"]]
    assert member_client.delete(f"/api/agents/soda/me/conversations/{cid}").status_code == 200
    assert member_client.delete("/api/agents/soda/me").status_code == 200
    mine = member_client.get("/api/agents/soda/me").get_json()
    assert mine["conversations"] == [] and mine["memories"] == []
    assert client.get("/api/agents/soda/me").status_code == 401


def test_officer_token_cannot_read_agent_data(client, officer_headers, member):
    assert client.get(f"{member}/memories", headers=officer_headers).status_code == 401


def test_prune_removes_idle_conversations(client, agent, member):
    from core.db import db_connect
    from modules.agents import service
    from modules.agents.models import AgentConversation

    cid = _conversation(client, agent, member)
    later = datetime.datetime.now(datetime.UTC).replace(tzinfo=None) + datetime.timedelta(
        days=service.RETENTION_DAYS + 1
    )
    db = db_connect.SessionLocal()
    try:
        result = service.prune(db, now=later)
        assert result["conversations"] >= 1
        assert db.query(AgentConversation).filter_by(id=cid).first() is None
    finally:
        db.close()
