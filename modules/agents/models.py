"""Conversations, messages, memories, the profile graph and pending actions of any agent.

Rows are scoped by organization and the member's Discord id. Ids are UUID strings so they work on
SQLite and Postgres alike.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from core.db import Base, new_uuid
from core.time import utcnow
from modules.knowledge.models import Embedding


class AgentConversation(Base):
    __tablename__ = "agent_conversations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    organization_id: Mapped[int] = mapped_column(Integer, ForeignKey("organizations.id"), nullable=False)
    discord_id: Mapped[str] = mapped_column(String(32), nullable=False)
    channel_id: Mapped[str] = mapped_column(String(255), nullable=False)
    visibility: Mapped[str] = mapped_column(String(10), nullable=False, default="public")  # public, private
    agent_token_id: Mapped[int | None] = mapped_column(Integer, nullable=True)  # machine token that started it
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    __table_args__ = (
        Index("ix_agent_conversations_owner", "organization_id", "discord_id", "channel_id", "updated_at"),
    )


class AgentMessage(Base):
    __tablename__ = "agent_messages"

    seq: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)  # write order
    conversation_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("agent_conversations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(10), nullable=False)  # system, user, assistant, tool, summary
    content: Mapped[Any] = mapped_column(JSON, nullable=False)
    # a summary stands in for messages up to this seq
    covers_seq: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)


class AgentMemory(Base):
    __tablename__ = "agent_memories"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    organization_id: Mapped[int] = mapped_column(Integer, ForeignKey("organizations.id"), nullable=False)
    discord_id: Mapped[str] = mapped_column(String(32), nullable=False)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)  # episodic, semantic, profile, task
    content: Mapped[str] = mapped_column(Text, nullable=False)  # encrypted when sensitivity is sensitive
    sensitivity: Mapped[str] = mapped_column(String(20), nullable=False, default="normal")
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    source_seq: Mapped[int | None] = mapped_column(Integer, nullable=True)
    agent_token_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    __table_args__ = (Index("ix_agent_memories_owner", "organization_id", "discord_id", "kind"),)


class AgentProfileNode(Base):
    __tablename__ = "agent_profile_nodes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    organization_id: Mapped[int] = mapped_column(Integer, ForeignKey("organizations.id"), nullable=False)
    discord_id: Mapped[str] = mapped_column(String(32), nullable=False)
    kind: Mapped[str] = mapped_column(String(100), nullable=False)
    label: Mapped[str] = mapped_column(String(500), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    embedding: Mapped[list[float] | None] = mapped_column(Embedding(), nullable=True)  # of "kind: label"
    embedding_model: Mapped[str | None] = mapped_column(String(200), nullable=True)
    agent_token_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)

    __table_args__ = (
        UniqueConstraint("organization_id", "discord_id", "kind", "label", name="uq_agent_profile_node"),
        Index("ix_agent_profile_nodes_owner", "organization_id", "discord_id"),
    )


class AgentProfileEdge(Base):
    __tablename__ = "agent_profile_edges"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    organization_id: Mapped[int] = mapped_column(Integer, ForeignKey("organizations.id"), nullable=False)
    from_node: Mapped[str] = mapped_column(
        String(36), ForeignKey("agent_profile_nodes.id", ondelete="CASCADE"), nullable=False
    )
    to_node: Mapped[str] = mapped_column(
        String(36), ForeignKey("agent_profile_nodes.id", ondelete="CASCADE"), nullable=False
    )
    relation: Mapped[str] = mapped_column(String(200), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)

    __table_args__ = (UniqueConstraint("from_node", "to_node", "relation", name="uq_agent_profile_edge"),)


class AgentPendingAction(Base):
    __tablename__ = "agent_pending_actions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)  # the confirmation token the agent chose
    organization_id: Mapped[int] = mapped_column(Integer, ForeignKey("organizations.id"), nullable=False)
    discord_id: Mapped[str] = mapped_column(String(32), nullable=False)
    action: Mapped[Any] = mapped_column(JSON, nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    # pending, confirmed, denied, expired
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="pending")
    agent_token_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
