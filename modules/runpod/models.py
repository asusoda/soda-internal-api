"""Apps deployed to pods on a hosting provider, their deployments, and the orgs that use a shared app."""

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from core.db import Base, new_uuid
from core.time import utcnow


class App(Base):
    __tablename__ = "runpod_apps"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    # None for a shared app: the deployment owns it and orgs subscribe to it
    organization_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("organizations.id"), nullable=True)
    name: Mapped[str] = mapped_column(String(63), nullable=False)
    # The hosting provider the app runs on, a name in core.hosting.PROVIDERS
    provider: Mapped[str] = mapped_column(String(32), nullable=False, default="runpod", server_default="runpod")
    manifest: Mapped[str] = mapped_column(Text, nullable=False)  # JSON, validated by service.MANIFEST_SCHEMA
    # owner/name whose manifest file is read on each deploy
    repo: Mapped[str | None] = mapped_column(String(201), nullable=True)
    manifest_path: Mapped[str | None] = mapped_column(String(200), nullable=True)
    pod_id: Mapped[str | None] = mapped_column(String(64), nullable=True)  # set by the first deploy
    current_tag: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)

    __table_args__ = (UniqueConstraint("organization_id", "name", name="uq_runpod_app_name"),)


class AppDeployment(Base):
    __tablename__ = "runpod_deployments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    app_id: Mapped[str] = mapped_column(String(36), ForeignKey("runpod_apps.id", ondelete="CASCADE"), nullable=False)
    tag: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)  # deploying, healthy, failed
    actor: Mapped[str | None] = mapped_column(String(255), nullable=True)
    manifest: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON the deploy used, so a rollback reuses it
    manifest_ref: Mapped[str | None] = mapped_column(String(100), nullable=True)  # git ref the manifest was read at
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    __table_args__ = (
        Index("ix_runpod_deployments_app", "app_id", "started_at"),
        Index("ix_runpod_deployments_status", "status"),
    )


class SharedAppSubscription(Base):
    """An org that uses a shared app, and the people Platform invited to it for the org."""

    __tablename__ = "shared_app_subscriptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    app_id: Mapped[str] = mapped_column(String(36), ForeignKey("runpod_apps.id", ondelete="CASCADE"), nullable=False)
    organization_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    invited: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)  # emails
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)
    created_by: Mapped[str | None] = mapped_column(String(255), nullable=True)

    __table_args__ = (UniqueConstraint("app_id", "organization_id", name="uq_shared_app_subscription"),)
