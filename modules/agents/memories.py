"""Agent memories of one member. Sensitive memories are encrypted with the org secret keys (SECRETS_KEY).

No Flask here.
"""

import datetime

from sqlalchemy import or_

from core import limits, secrets
from core.time import iso, utcnow
from modules.agents import service
from modules.agents.models import AgentMemory
from modules.agents.service import MEMORY_KINDS, SENSITIVITIES, AgentError, Owner


def _seal(text: str) -> str:
    sealed = secrets.encrypt(text)
    if sealed is None:
        raise AgentError("Sensitive memories need SECRETS_KEY on this server", 503)
    return sealed


def _open(row: AgentMemory) -> str | None:
    if row.sensitivity != "sensitive":
        return str(row.content)
    return secrets.decrypt(str(row.content))


def memory_dict(row: AgentMemory, content: str | None) -> dict:
    return {
        "id": row.id,
        "kind": row.kind,
        "content": content,
        "sensitivity": row.sensitivity,
        "confidence": row.confidence,
        "source_seq": row.source_seq,
        "created_at": iso(row.created_at),
        "expires_at": iso(row.expires_at),
    }


def remember(
    db,
    who: Owner,
    *,
    kind: object,
    content: object,
    sensitivity: object = "normal",
    confidence: object = None,
    source_seq: object = None,
    expires_in_days: object = None,
    commit: bool = True,
) -> dict:
    """Store one memory. Commits unless commit is false."""
    if kind not in MEMORY_KINDS:
        raise AgentError(f"kind must be one of {', '.join(MEMORY_KINDS)}")
    if sensitivity not in SENSITIVITIES:
        raise AgentError(f"sensitivity must be one of {', '.join(SENSITIVITIES)}")
    text = service.text(content, "content", 20000)
    if source_seq is not None and (not isinstance(source_seq, int) or isinstance(source_seq, bool)):
        raise AgentError("source_seq must be a message seq")
    if expires_in_days is not None and (not isinstance(expires_in_days, int) or expires_in_days < 1):
        raise AgentError("expires_in_days must be a positive integer")
    limits.check(db, who.organization_id, service.MEMORIES_LIMIT)
    row = AgentMemory(
        organization_id=who.organization_id,
        discord_id=who.discord_id,
        kind=kind,
        content=_seal(text) if sensitivity == "sensitive" else text,
        sensitivity=sensitivity,
        confidence=service.confidence(confidence),
        source_seq=source_seq,
        agent_token_id=who.token_id,
        expires_at=utcnow() + datetime.timedelta(days=expires_in_days) if expires_in_days else None,
    )
    db.add(row)
    service.save(db, commit)
    return memory_dict(row, text)


def recall(db, who: Owner, kinds: object = None, limit: object = None) -> list[dict]:
    """Unexpired memories, most confident first, then newest. Sensitive ones that cannot be decrypted are left out."""
    if kinds is not None and (not isinstance(kinds, list) or any(k not in MEMORY_KINDS for k in kinds)):
        raise AgentError(f"kinds must be a list of {', '.join(MEMORY_KINDS)}")
    query = db.query(AgentMemory).filter(
        AgentMemory.organization_id == who.organization_id,
        AgentMemory.discord_id == who.discord_id,
        or_(AgentMemory.expires_at.is_(None), AgentMemory.expires_at > utcnow()),
    )
    if kinds:
        query = query.filter(AgentMemory.kind.in_(kinds))
    rows = (
        query.order_by(AgentMemory.confidence.desc(), AgentMemory.created_at.desc())
        .limit(service.limit(limit, 20))
        .all()
    )
    out = []
    for row in rows:
        content = _open(row)
        if content is not None:
            out.append(memory_dict(row, content))
    return out


def forget_memory(db, who: Owner, memory_id: object) -> bool:
    deleted = (
        db.query(AgentMemory)
        .filter_by(id=str(memory_id), organization_id=who.organization_id, discord_id=who.discord_id)
        .delete()
    )
    db.commit()
    return bool(deleted)
