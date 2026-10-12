"""Members and their org memberships."""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.db import Base


class User(Base):
    """A person. One row can be a member of many orgs."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    discord_id: Mapped[str | None] = mapped_column(String, unique=True, index=True, nullable=True)
    username: Mapped[str | None] = mapped_column(String, unique=True, index=True, nullable=True)
    email: Mapped[str | None] = mapped_column(String, unique=True, index=True, nullable=True)
    name: Mapped[str | None] = mapped_column(String)
    # the school's student number
    student_id: Mapped[str | None] = mapped_column(String, unique=True, index=True, nullable=True)
    # freshman, senior, graduate and so on, as the org writes it
    class_standing: Mapped[str | None] = mapped_column(String)
    major: Mapped[str | None] = mapped_column(String)
    uuid: Mapped[str | None] = mapped_column(String, unique=True, index=True)
    created_at: Mapped[datetime | None] = mapped_column(DateTime, default=lambda: datetime.now(UTC))

    points = relationship("Points", back_populates="user")
    orders = relationship("Order", back_populates="user")
    memberships = relationship("UserOrganizationMembership", back_populates="user")

    def __repr__(self):
        return f"<User(id={self.id}, discord_id={self.discord_id}, username={self.username})>"


class UserOrganizationMembership(Base):
    """A user's membership in one org. A user has at most one row per org."""

    __tablename__ = "user_organization_memberships"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    organization_id: Mapped[int] = mapped_column(Integer, ForeignKey("organizations.id"), nullable=False)
    joined_at: Mapped[datetime | None] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
    is_active: Mapped[bool | None] = mapped_column(Boolean, default=True)
    # Fields the org defines for its members, such as major or shirt size
    profile_fields: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"), nullable=False, default=dict, server_default=text("'{}'")
    )

    user = relationship("User", back_populates="memberships")
    organization = relationship("Organization", backref="memberships")

    __table_args__ = (
        UniqueConstraint("user_id", "organization_id", name="unique_user_org"),
        Index("ix_user_organization_memberships_organization_id", "organization_id"),
    )

    def __repr__(self):
        return f"<UserOrganizationMembership(user_id={self.user_id}, org_id={self.organization_id})>"
