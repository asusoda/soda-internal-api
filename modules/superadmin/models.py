"""Who owns each service on the server, as the superadmin set it."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from core.db import Base
from core.time import utcnow


class ServiceOwner(Base):
    """The owner of one container or host process that the host agent lists, by its name."""

    __tablename__ = "server_service_owners"

    name: Mapped[str] = mapped_column(String(128), primary_key=True)
    owner: Mapped[str] = mapped_column(String(16), nullable=False)  # platform, infrastructure or org
    organization_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)
    updated_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
