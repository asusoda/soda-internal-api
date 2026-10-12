"""Point entries. Members and memberships are in modules/users/models.py."""

from datetime import UTC, datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.db import Base


class Points(Base):
    """Points one member got (or spent, when negative) in one org."""

    __tablename__ = "points"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"))
    organization_id: Mapped[int] = mapped_column(Integer, ForeignKey("organizations.id"), nullable=False)
    points: Mapped[float | None] = mapped_column(Float, default=0.0)
    event: Mapped[str | None] = mapped_column(String, nullable=True)
    awarded_by_officer: Mapped[str | None] = mapped_column(String, nullable=True)
    timestamp: Mapped[datetime | None] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
    last_updated: Mapped[datetime | None] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
    user = relationship("User", back_populates="points")
    organization = relationship("Organization", backref="points")

    __table_args__ = (
        Index("ix_points_organization_id_user_id", "organization_id", "user_id"),
        Index("ix_points_user_id", "user_id"),
    )

    def __repr__(self):
        return f"<Points(id={self.id}, user_id={self.user_id}, organization_id={self.organization_id}, points={self.points}, event={self.event}, timestamp={self.timestamp})>"
