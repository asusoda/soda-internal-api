"""Members' connected accounts (OAuth grants) and logins in progress. Tokens are stored encrypted."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from core.db import Base, new_uuid
from core.time import utcnow


class AccountGrant(Base):
    __tablename__ = "account_grants"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    organization_id: Mapped[int] = mapped_column(Integer, ForeignKey("organizations.id"), nullable=False)
    discord_id: Mapped[str] = mapped_column(String(32), nullable=False)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    access_token: Mapped[str] = mapped_column(Text, nullable=False)  # Fernet ciphertext
    refresh_token: Mapped[str | None] = mapped_column(Text, nullable=True)  # Fernet ciphertext
    scopes: Mapped[str] = mapped_column(Text, nullable=False, default="")  # space separated, as the provider granted
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)

    __table_args__ = (UniqueConstraint("organization_id", "discord_id", "provider", name="uq_account_grant_owner"),)


class AccountLogin(Base):
    """A login an agent started for a member. One use; the browser must sign in to Discord as that member."""

    __tablename__ = "account_logins"

    state: Mapped[str] = mapped_column(String(64), primary_key=True)
    organization_id: Mapped[int] = mapped_column(Integer, ForeignKey("organizations.id"), nullable=False)
    discord_id: Mapped[str] = mapped_column(String(32), nullable=False)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    # set once Discord confirmed the member
    verified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    __table_args__ = (Index("ix_account_logins_expires_at", "expires_at"),)
