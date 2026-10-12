"""Agent conversations and their messages, scoped to one member. No Flask here."""

from typing import Any

from core import limits
from core.time import iso, utcnow
from modules.agents import service
from modules.agents.models import AgentConversation, AgentMessage
from modules.agents.service import ROLES, VISIBILITIES, AgentError, Owner


def _owned(db, who: Owner, conversation_id: str) -> AgentConversation | None:
    return (
        db.query(AgentConversation)
        .filter_by(id=conversation_id, organization_id=who.organization_id, discord_id=who.discord_id)
        .first()
    )


def ensure(
    db, who: Owner, conversation_id: object, channel_id: object, visibility: object, *, commit: bool = True
) -> str:
    """Create the conversation, or confirm the caller already owns it with this channel and visibility.

    An id held by another member, channel or visibility raises AgentError 409. Commits.
    """
    cid = service.uuid_text(conversation_id)
    channel = service.text(channel_id, "channel_id", 255)
    if visibility not in VISIBILITIES:
        raise AgentError(f"visibility must be one of {', '.join(VISIBILITIES)}")
    row = db.query(AgentConversation).filter_by(id=cid).first()
    if row is None:
        limits.check(db, who.organization_id, service.CONVERSATIONS_LIMIT)
        db.add(
            AgentConversation(
                id=cid,
                organization_id=who.organization_id,
                discord_id=who.discord_id,
                channel_id=channel,
                visibility=visibility,
                agent_token_id=who.token_id,
            )
        )
        service.save(db, commit)
        return cid
    same = (
        row.organization_id == who.organization_id
        and row.discord_id == who.discord_id
        and row.channel_id == channel
        and row.visibility == visibility
    )
    if not same:
        raise AgentError("Conversation is not owned by this member", 409)
    return cid


def owns(db, who: Owner, conversation_id: object, visibility: object) -> bool:
    cid = service.uuid_text(conversation_id)
    row = _owned(db, who, cid)
    return bool(row is not None and row.visibility == visibility)


def load(db, who: Owner, conversation_id: object, limit: object = None) -> list[dict]:
    """The newest summary, then up to limit messages after what it covers, oldest first.

    Each item is {"position", "role", "content"}. A summary's position is the seq it covers.
    An unknown or unowned conversation loads as empty.
    """
    count = service.limit(limit, 50)
    cid = service.uuid_text(conversation_id)
    if _owned(db, who, cid) is None:
        return []
    summary = (
        db.query(AgentMessage)
        .filter(AgentMessage.conversation_id == cid, AgentMessage.role == "summary")
        .order_by(AgentMessage.seq.desc())
        .first()
    )
    start = 0
    out = []
    if summary is not None:
        start = int(summary.covers_seq or summary.seq)
        out.append({"position": start, "role": "summary", "content": summary.content})
    recent = (
        db.query(AgentMessage)
        .filter(AgentMessage.conversation_id == cid, AgentMessage.role != "summary", AgentMessage.seq > start)
        .order_by(AgentMessage.seq.desc())
        .limit(count)
        .all()
    )
    out.extend({"position": m.seq, "role": m.role, "content": m.content} for m in reversed(recent))
    return out


def _write(
    db, who: Owner, conversation_id: object, rows: list[tuple[str, object, int | None]], commit: bool = True
) -> list[int]:
    cid = service.uuid_text(conversation_id)
    conversation = _owned(db, who, cid)
    if conversation is None:
        raise AgentError("Conversation is not owned by this member", 409)
    conversation.updated_at = utcnow()
    messages = [
        AgentMessage(conversation_id=cid, role=role, content=content, covers_seq=covers)
        for role, content, covers in rows
    ]
    db.add_all(messages)
    service.save(db, commit)
    return [m.seq for m in messages]


def append(db, who: Owner, conversation_id: object, messages: Any, *, commit: bool = True) -> list[int]:
    """Append messages in one transaction. Each is {"role", "content"}; content is any JSON. Returns their seqs."""
    if not isinstance(messages, list) or not messages:
        raise AgentError("messages must be a non-empty list")
    rows: list[tuple[str, object, int | None]] = []
    for m in messages:
        if not isinstance(m, dict) or m.get("role") not in ROLES or "content" not in m:
            raise AgentError(f"each message needs a role ({', '.join(ROLES)}) and content")
        rows.append((m["role"], m["content"], None))
    return _write(db, who, conversation_id, rows, commit)


def append_summary(
    db, who: Owner, conversation_id: object, content: object, covers: object, *, commit: bool = True
) -> int:
    """Store a summary that stands in for every message up to seq covers."""
    if not isinstance(covers, int) or isinstance(covers, bool) or covers < 1:
        raise AgentError("covers must be a message seq")
    if content is None:
        raise AgentError("content is required")
    return _write(db, who, conversation_id, [("summary", content, covers)], commit)[0]


def latest(db, who: Owner, channel_id: object, visibility: object) -> str | None:
    """The member's most recently updated open conversation in a channel."""
    channel = service.text(channel_id, "channel_id", 255)
    row = (
        db.query(AgentConversation)
        .filter_by(
            organization_id=who.organization_id,
            discord_id=who.discord_id,
            channel_id=channel,
            visibility=visibility,
            ended_at=None,
        )
        .order_by(AgentConversation.updated_at.desc())
        .first()
    )
    return str(row.id) if row else None


def end(db, who: Owner, channel_id: object) -> int:
    """End the member's open conversations in a channel. Returns how many ended. Commits."""
    channel = service.text(channel_id, "channel_id", 255)
    ended = (
        db.query(AgentConversation)
        .filter_by(organization_id=who.organization_id, discord_id=who.discord_id, channel_id=channel, ended_at=None)
        .update({"ended_at": utcnow()})
    )
    db.commit()
    return int(ended)


def conversation_dict(row: AgentConversation) -> dict:
    return {
        "id": row.id,
        "channel_id": row.channel_id,
        "visibility": row.visibility,
        "created_at": iso(row.created_at),
        "updated_at": iso(row.updated_at),
        "ended_at": iso(row.ended_at),
    }


def list_conversations(db, who: Owner, limit: object = None) -> list[dict]:
    rows = (
        db.query(AgentConversation)
        .filter_by(organization_id=who.organization_id, discord_id=who.discord_id)
        .order_by(AgentConversation.updated_at.desc())
        .limit(service.limit(limit, 100))
        .all()
    )
    return [conversation_dict(row) for row in rows]


def delete_conversation(db, who: Owner, conversation_id: object) -> bool:
    row = _owned(db, who, service.uuid_text(conversation_id))
    if row is None:
        return False
    db.query(AgentMessage).filter_by(conversation_id=row.id).delete()
    db.delete(row)
    db.commit()
    return True
