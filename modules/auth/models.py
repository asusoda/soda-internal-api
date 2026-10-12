import datetime

from sqlalchemy import JSON, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.sql import func

from core.db import Base
from core.time import utcnow


class Session(Base):
    """Table kept for schema compatibility; no code reads it."""

    __tablename__ = "sessions"
    id = Column(Integer, primary_key=True)
    session_id = Column(String(255), unique=True, nullable=False)
    data = Column(JSON, nullable=False)
    expiry = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=func.utcnow())
    updated_at = Column(DateTime, default=func.utcnow(), onupdate=func.utcnow())

    def __repr__(self):
        return f"<Session {self.session_id}>"


class RefreshToken(Base):
    """Model for storing refresh tokens in the database so they persist across server restarts"""

    __tablename__ = "refresh_tokens"
    id = Column(Integer, primary_key=True)
    token = Column(String(255), unique=True, nullable=False, index=True)
    username = Column(String(255), nullable=False)
    discord_id = Column(String(255), nullable=True)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.UTC).replace(tzinfo=None))

    def __repr__(self):
        return f"<RefreshToken {self.token[:8]}...>"


class RevokedToken(Base):
    """A revoked access or app token, kept until it would have expired anyway."""

    __tablename__ = "revoked_tokens"
    id = Column(Integer, primary_key=True)
    token_hash = Column(String(64), unique=True, nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=utcnow)


class AppToken(Base):
    """An app token an officer issued. A token whose row is missing or revoked is refused."""

    __tablename__ = "app_tokens"
    id = Column(Integer, primary_key=True)
    jti = Column(String(64), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    app_name = Column(String(255), nullable=False)
    discord_id = Column(String(255), nullable=True)
    expires_at = Column(DateTime, nullable=False)
    revoked_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utcnow)


class MachineToken(Base):
    """A token for an app, agent or CLI, bound to one org and a set of scopes. Only its hash is stored."""

    __tablename__ = "machine_tokens"
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    kind = Column(String(20), nullable=False)  # app, agent, cli, oauth
    scopes = Column(JSON, nullable=False)
    # Per-integration limits, such as {"github": {"repos": ["org/*"], "tools": ["github.*issue*"]}}
    limits = Column(JSON, nullable=True)
    token_hash = Column(String(64), unique=True, nullable=False, index=True)
    display = Column(String(20), nullable=False)  # first characters, to tell tokens apart in a list
    created_by = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=True)
    last_used_at = Column(DateTime, nullable=True)
    revoked_at = Column(DateTime, nullable=True)
