"""Shared submodules: one row for each submodule, and the orgs that subscribe to it.

A submodule's crawled sources belong to the submodule, not to an org (knowledge_sources.submodule_id with a null
organization_id). The deployment crawls and embeds them once, and each subscribed org searches them.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from core.db import Base
from core.time import utcnow


class Submodule(Base):
    __tablename__ = "submodules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # the package name in submodules/, such as asu
    key: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # code (submodules/) or manifest (org-made)
    origin: Mapped[str] = mapped_column(String(16), nullable=False, default="code")
    manifest: Mapped[Any | None] = mapped_column(JSON, nullable=True)
    owner_org_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True
    )
    # draft, pending, shared or retired
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="shared")
    approved_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)


class SubmoduleSubscription(Base):
    __tablename__ = "submodule_subscriptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    submodule_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("submodules.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)

    __table_args__ = (UniqueConstraint("organization_id", "submodule_id", name="uq_submodule_subscription"),)
