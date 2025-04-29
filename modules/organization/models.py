from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
from modules.utils.base import Base

class Organization(Base):
    __tablename__ = "organizations"

    id = Column(Integer, primary_key=True, index=True)
    discord_guild_id = Column(String, unique=True, index=True)
    name = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    config = relationship("OrganizationConfig", back_populates="organization", uselist=False)

class OrganizationConfig(Base):
    __tablename__ = "organization_configs"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"))
    config = Column(JSON)
    organization = relationship("Organization", back_populates="config") 