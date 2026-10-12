import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from core.db import Base
from core.time import utcnow


class Session(Base):
    """Table kept for schema compatibility; no code reads it."""

    __tablename__ = "sessions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    data: Mapped[Any] = mapped_column(JSON, nullable=False)
    expiry: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    created_at: Mapped[datetime.datetime | None] = mapped_column(DateTime, default=func.utcnow())
    updated_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime, default=func.utcnow(), onupdate=func.utcnow()
    )

    def __repr__(self):
        return f"<Session {self.session_id}>"


class RefreshToken(Base):
    """Model for storing refresh tokens in the database so they persist across server restarts"""

    __tablename__ = "refresh_tokens"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    token: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    username: Mapped[str] = mapped_column(String(255), nullable=False)
    discord_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    expires_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    created_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime, default=lambda: datetime.datetime.now(datetime.UTC).replace(tzinfo=None)
    )

    def __repr__(self):
        return f"<RefreshToken {self.token[:8]}...>"


class RevokedToken(Base):
    """A revoked access or app token, kept until it would have expired anyway."""

    __tablename__ = "revoked_tokens"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    expires_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    created_at: Mapped[datetime.datetime | None] = mapped_column(DateTime, default=utcnow)


class AppToken(Base):
    """An app token an officer issued. A token whose row is missing or revoked is refused."""

    __tablename__ = "app_tokens"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    jti: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    app_name: Mapped[str] = mapped_column(String(255), nullable=False)
    discord_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    expires_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    revoked_at: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime.datetime | None] = mapped_column(DateTime, default=utcnow)


class MachineToken(Base):
    """A token for an app, agent or CLI, bound to one org and a set of scopes. Only its hash is stored."""

    __tablename__ = "machine_tokens"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)  # app, agent, cli, oauth
    scopes: Mapped[Any] = mapped_column(JSON, nullable=False)
    # Per-integration limits, such as {"github": {"repos": ["org/*"], "tools": ["github.*issue*"]}}
    limits: Mapped[Any | None] = mapped_column(JSON, nullable=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    display: Mapped[str] = mapped_column(String(20), nullable=False)  # first characters, to tell tokens apart in a list
    created_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    expires_at: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True)
    last_used_at: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True)
    revoked_at: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True)
