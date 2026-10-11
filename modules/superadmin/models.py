"""Who owns each service on the server, as the superadmin set it."""

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String

from core.db import Base
from core.time import utcnow


class ServiceOwner(Base):
    """The owner of one container or host process that the host agent lists, by its name."""

    __tablename__ = "server_service_owners"

    name = Column(String(128), primary_key=True)
    owner = Column(String(16), nullable=False)  # platform, infrastructure or org
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True)
    updated_at = Column(DateTime, nullable=False, default=utcnow)
    updated_by = Column(String(255), nullable=True)
