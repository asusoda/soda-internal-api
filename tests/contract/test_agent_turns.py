"""Agent turns: one context read and one atomic commit, for members Discord says are in the org."""

import random
import uuid

import pytest

from core.integrations.discord import DiscordUnavailable
from tests.contract.conftest import FakeBot


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


def _turn(cid, **extra):
    return {"conversation_id": cid, "channel_id": "chan-1", "visibility": "private", **extra}


def test_commit_then_context(client, agent, member):
    cid = str(uuid.uuid4())
    token = str(uuid.uuid4())
    body = _turn(
        cid,
        messages=[{"role": "user", "content": "I take CSE 310"}, {"role": "assistant", "content": "Noted."}],
        memories=[{"kind": "semantic", "content": "Takes CSE 310", "confidence": 0.9}],
        facts=[
            {
                "subject": {"kind": "person", "label": "me"},
                "relation": "takes",
                "object": {"kind": "course", "label": "CSE 310"},
                "confidence": 0.8,
            }
        ],
        pending=[{"token": token, "action": {"tool": "canvas.submit"}, "payload_hash": "abc"}],
    )
    response = client.post(f"{member}/turn/commit", json=body, headers=agent)
    assert response.status_code == 201, response.get_json()
    result = response.get_json()
    assert result["conversation_id"] == cid and len(result["seqs"]) == 2
    assert len(result["memory_ids"]) == 1 and result["facts"] == 1 and result["pending"] == 1

    context = client.post(f"{member}/turn/context", json=_turn(cid), headers=agent).get_json()
    assert context["member"]["display_name"] == "officer" and context["member"]["officer"] is True
    assert context["conversation"] == {"id": cid, "owned": True}
    assert [m["content"] for m in context["messages"]] == ["I take CSE 310", "Noted."]
    assert context["memories"][0]["content"] == "Takes CSE 310"
    assert context["profile"]["relations"][0]["relation"] == "takes"

    claimed = client.post(f"{member}/pending/{token}/claim", json={"approved": True}, headers=agent)
    assert claimed.get_json()["action"] == {"tool": "canvas.submit"}


def test_summary_and_limits(client, agent, member):
    cid = str(uuid.uuid4())
    seqs = client.post(
        f"{member}/turn/commit",
        json=_turn(cid, messages=[{"role": "user", "content": f"m{i}"} for i in range(3)]),
        headers=agent,
    ).get_json()["seqs"]
    client.post(
        f"{member}/turn/commit",
        json=_turn(cid, summary={"content": "first two", "covers": seqs[1]}),
        headers=agent,
    )
    context = client.post(
        f"{member}/turn/context", json=_turn(cid, memory_limit=0, profile_limit=0), headers=agent
    ).get_json()
    assert [m["role"] for m in context["messages"]] == ["summary", "user"]
    assert context["memories"] == [] and context["profile"] == {"nodes": [], "relations": [], "similar": []}


def test_a_bad_part_writes_nothing(client, agent, member):
    cid = str(uuid.uuid4())
    body = _turn(
        cid,
        messages=[{"role": "user", "content": "hello"}],
        memories=[{"kind": "not-a-kind", "content": "x"}],
    )
    assert client.post(f"{member}/turn/commit", json=body, headers=agent).status_code == 400
    context = client.post(f"{member}/turn/context", json=_turn(cid), headers=agent).get_json()
    assert context["conversation"]["owned"] is False and context["messages"] == []
    assert client.post(f"{member}/turn/commit", json=_turn(cid), headers=agent).status_code == 400


def test_another_members_conversation_is_refused(client, agent, member):
    cid = str(uuid.uuid4())
    client.post(f"{member}/turn/commit", json=_turn(cid, messages=[{"role": "user", "content": "a"}]), headers=agent)
    other = f"/api/agents/members/{random.randint(10**17, 10**18)}"
    body = _turn(cid, messages=[{"role": "user", "content": "b"}])
    assert client.post(f"{other}/turn/commit", json=body, headers=agent).status_code == 409
    context = client.post(f"{other}/turn/context", json=_turn(cid), headers=agent).get_json()
    assert context["conversation"]["owned"] is False and context["messages"] == []


class _NotInServer(FakeBot):
    def get_member(self, guild_id, user_id):
        return None


class _Down(FakeBot):
    def get_member(self, guild_id, user_id):
        raise DiscordUnavailable("down")


@pytest.mark.parametrize(("directory", "status"), [(_NotInServer(), 403), (_Down(), 503), (None, 503)])
def test_membership_is_checked(client, agent, member, monkeypatch, app, directory, status):
    monkeypatch.setattr(app, "discord_directory", directory)
    cid = str(uuid.uuid4())
    assert client.post(f"{member}/turn/context", json=_turn(cid), headers=agent).status_code == status
    body = _turn(cid, messages=[{"role": "user", "content": "a"}])
    assert client.post(f"{member}/turn/commit", json=body, headers=agent).status_code == status


def test_scopes(client, member):
    reader = _issue("soda", "agents:read")
    cid = str(uuid.uuid4())
    body = _turn(cid, messages=[{"role": "user", "content": "a"}])
    assert client.post(f"{member}/turn/commit", json=body, headers=reader).status_code == 403
    assert client.post(f"{member}/turn/context", json=_turn(cid), headers=reader).status_code == 200


class WordEmbedder:
    """One dimension per word, so texts that share words are near each other."""

    model = "words"
    query_prefix = ""

    def __init__(self):
        self.calls = 0

    def _vector(self, text):
        import zlib

        vector = [0.0] * 1024
        for word in text.lower().replace(":", " ").split():
            vector[zlib.crc32(word.encode()) % 1024] += 1.0
        return vector

    def embed(self, texts):
        self.calls += 1
        return [self._vector(t) for t in texts]

    def embed_query(self, text):
        return self._vector(text)


def _fact(kind, label, relation="takes"):
    return {
        "subject": {"kind": "person", "label": "me"},
        "relation": relation,
        "object": {"kind": kind, "label": label},
        "confidence": 0.9,
    }


def test_profile_nodes_are_embedded_and_searchable(client, agent, member, monkeypatch):
    from modules.knowledge import embedder as embedder_module

    fake = WordEmbedder()
    monkeypatch.setattr(embedder_module, "configured", lambda: fake)
    facts = [_fact("course", "CSE 310 data structures"), _fact("club", "Robotics club", "joined")]
    assert client.post(f"{member}/profile/facts", json={"facts": facts}, headers=agent).get_json()["stored"] == 2
    client.post(f"{member}/profile/facts", json={"facts": facts[:1]}, headers=agent)
    assert fake.calls == 1  # nodes that already have a vector from this model are not embedded again

    found = client.get(f"{member}/profile/similar?text=data structures homework&limit=2", headers=agent).get_json()
    assert found["nodes"][0]["label"] == "CSE 310 data structures"
    assert found["nodes"][0]["distance"] < found["nodes"][1]["distance"]

    cid = str(uuid.uuid4())
    context = client.post(
        f"{member}/turn/context", json=_turn(cid, profile_query="robotics meeting"), headers=agent
    ).get_json()
    assert context["profile"]["similar"][0]["label"] == "Robotics club"


def test_similar_needs_an_embedder_and_facts_survive_a_failed_one(client, agent, member, monkeypatch):
    from modules.knowledge import embedder as embedder_module
    from modules.knowledge.embedder import EmbeddingError

    monkeypatch.setattr(embedder_module, "configured", lambda: None)
    assert client.get(f"{member}/profile/similar?text=x", headers=agent).status_code == 503

    class Broken(WordEmbedder):
        def embed(self, texts):
            raise EmbeddingError("down")

    monkeypatch.setattr(embedder_module, "configured", lambda: Broken())
    stored = client.post(f"{member}/profile/facts", json={"facts": [_fact("course", "MAT 343")]}, headers=agent)
    assert stored.status_code == 200
    labels = [n["label"] for n in client.get(f"{member}/profile", headers=agent).get_json()["nodes"]]
    assert "MAT 343" in labels
    assert client.get(f"{member}/profile/similar?text=MAT 343", headers=agent).get_json()["nodes"] == []


def test_an_org_over_its_embeddings_limit_still_commits_turns(client, agent, member, monkeypatch):
    from core import limits
    from modules.knowledge import embedder as embedder_module

    class OverLimit(WordEmbedder):
        def embed(self, texts):
            raise limits.LimitError("over the limit", 429)

        def embed_query(self, text):
            raise limits.LimitError("over the limit", 429)

    monkeypatch.setattr(embedder_module, "configured", lambda: OverLimit())
    cid = str(uuid.uuid4())
    body = _turn(cid, messages=[{"role": "user", "content": "hi"}], facts=[_fact("course", "CSE 340")])
    response = client.post(f"{member}/turn/commit", json=body, headers=agent)
    assert response.status_code == 201, response.get_json()
    context = client.post(f"{member}/turn/context", json=_turn(cid, profile_query="CSE 340"), headers=agent)
    assert context.status_code == 200, context.get_json()
    assert context.get_json()["profile"]["similar"] == []
    assert "CSE 340" in [n["label"] for n in context.get_json()["profile"]["nodes"]]
