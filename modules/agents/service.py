"""Shared parts of agent storage: the Owner, input checks, scopes and retention. No Flask here.

Every storage function is scoped to one Owner: the machine token's organization plus the Discord id of
the member the agent is talking to. The agent says who the member is; the platform checks the token,
so an agent can only reach members of its own organization.

conversations.py, memories.py, profile.py and pending.py hold the storage functions.
"""

import datetime
import os
import uuid
from dataclasses import dataclass

from core import limits
from core.errors import ServiceError
from core.time import utcnow
from modules.agents.models import AgentConversation, AgentMemory, AgentMessage, AgentPendingAction
from modules.auth import scopes

VISIBILITIES = ("public", "private")
ROLES = ("system", "user", "assistant", "tool")
MEMORY_KINDS = ("episodic", "semantic", "profile", "task")
SENSITIVITIES = ("normal", "sensitive")
MAX_LIMIT = 500

scopes.declare(
    "agents:read", "Read conversations, memories and profiles of members the agent talks to", uses=("embeddings",)
)
scopes.declare(
    "agents:write", "Write conversations, memories, profiles and pending actions for members", uses=("embeddings",)
)


class AgentError(ServiceError, ValueError):
    pass


CONVERSATIONS_LIMIT = "agents.conversations"
MEMORIES_LIMIT = "agents.memories"
limits.declare(
    CONVERSATIONS_LIMIT,
    "agents",
    "Agent conversations",
    5000,
    unit="conversations",
    usage=lambda db, org_id: db.query(AgentConversation).filter_by(organization_id=org_id).count(),
)
limits.declare(
    MEMORIES_LIMIT,
    "agents",
    "Agent memories",
    20000,
    unit="memories",
    usage=lambda db, org_id: db.query(AgentMemory).filter_by(organization_id=org_id).count(),
)


@dataclass(frozen=True)
class Owner:
    """The member an agent acts for, inside the token's organization."""

    organization_id: int
    discord_id: str
    token_id: int | None = None


def owner(organization_id: int, discord_id: object, token_id: int | None = None) -> Owner:
    """Validate the member id an agent sent. Discord ids are numeric snowflakes."""
    if not isinstance(discord_id, str) or not discord_id.isdigit() or len(discord_id) > 32:
        raise AgentError("discord_id must be a Discord user id")
    return Owner(organization_id=organization_id, discord_id=discord_id, token_id=token_id)


def save(db, commit: bool) -> None:
    """Commit, or flush when the caller commits several writes as one transaction."""
    if commit:
        db.commit()
    else:
        db.flush()


def limit(value: object, default: int) -> int:
    """A positive limit, capped at MAX_LIMIT. None gives the default."""
    if value is None:
        return default
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise AgentError("limit must be a positive integer")
    return min(value, MAX_LIMIT)


def text(value: object, name: str, max_len: int) -> str:
    """A non-empty string of at most max_len characters, stripped."""
    if not isinstance(value, str) or not value.strip():
        raise AgentError(f"{name} is required")
    if len(value) > max_len:
        raise AgentError(f"{name} is longer than {max_len} characters")
    return value.strip()


def confidence(value: object) -> float:
    """A number from 0 to 1. None gives 1.0."""
    if value is None:
        return 1.0
    if not isinstance(value, int | float) or isinstance(value, bool) or not 0 <= value <= 1:
        raise AgentError("confidence must be a number from 0 to 1")
    return float(value)


def uuid_text(value: object) -> str:
    """The value as a UUID string. Conversation ids and pending action tokens are UUIDs."""
    try:
        return str(uuid.UUID(str(value)))
    except ValueError:
        raise AgentError("conversation id must be a UUID") from None


# Retention


RETENTION_DAYS = int(os.environ.get("AGENT_RETENTION_DAYS", "180"))


def prune(db, now: datetime.datetime | None = None) -> dict:
    """Delete conversations not updated in RETENTION_DAYS, expired memories and old pending actions. Commits."""
    now = now or utcnow()
    cutoff = now - datetime.timedelta(days=RETENTION_DAYS)
    stale = [row.id for row in db.query(AgentConversation.id).filter(AgentConversation.updated_at < cutoff).all()]
    if stale:
        db.query(AgentMessage).filter(AgentMessage.conversation_id.in_(stale)).delete(synchronize_session=False)
        db.query(AgentConversation).filter(AgentConversation.id.in_(stale)).delete(synchronize_session=False)
    memories = db.query(AgentMemory).filter(AgentMemory.expires_at <= now).delete(synchronize_session=False)
    actions = (
        db.query(AgentPendingAction)
        .filter(AgentPendingAction.expires_at < now - datetime.timedelta(days=1))
        .delete(synchronize_session=False)
    )
    db.commit()
    return {"conversations": len(stale), "memories": int(memories), "pending_actions": int(actions)}
