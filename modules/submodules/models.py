"""Shared submodules: one row for each submodule, and the orgs that subscribe to it.

A submodule's crawled sources belong to the submodule, not to an org (knowledge_sources.submodule_id with a null
organization_id). The deployment crawls and embeds them once, and each subscribed org searches them.
"""

from sqlalchemy import JSON, Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint

from core.db import Base
from core.time import utcnow


class Submodule(Base):
    __tablename__ = "submodules"

    id = Column(Integer, primary_key=True)
    key = Column(String(64), nullable=False, unique=True)  # the package name in submodules/, such as asu
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    origin = Column(String(16), nullable=False, default="code")  # code (submodules/) or manifest (org-made)
    manifest = Column(JSON, nullable=True)
    owner_org_id = Column(Integer, ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True)
    status = Column(String(16), nullable=False, default="shared")  # draft, pending, shared or retired
    approved_by = Column(String(255), nullable=True)
    approved_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=utcnow)
    updated_at = Column(DateTime, nullable=False, default=utcnow)


class SubmoduleSubscription(Base):
    __tablename__ = "submodule_subscriptions"

    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    submodule_id = Column(Integer, ForeignKey("submodules.id", ondelete="CASCADE"), nullable=False, index=True)
    created_by = Column(String(255), nullable=True)
    created_at = Column(DateTime, nullable=False, default=utcnow)

    __table_args__ = (UniqueConstraint("organization_id", "submodule_id", name="uq_submodule_subscription"),)
