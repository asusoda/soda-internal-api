from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, JSON, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
from modules.utils.db import Base

class Organization(Base):
    """Model representing a Discord organization/guild."""
    __tablename__ = "organizations"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    prefix = Column(String(20), nullable=False, unique=True)  # URL-friendly prefix for the organization
    
    guild_id = Column(String(50), nullable=False, unique=True)
    description = Column(String(500))
    icon_url = Column(String(255))
    is_active = Column(Boolean, default=True)
    config = Column(JSON, default=dict)  # Store organization-specific settings
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<Organization(name='{self.name}', guild_id='{self.guild_id}')>"

    def to_dict(self):
        """Convert organization to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "prefix": self.prefix,
            "guild_id": self.guild_id,
            "description": self.description,
            "icon_url": self.icon_url,
            "is_active": self.is_active,
            "config": self.config,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }

class OrganizationConfig(Base):
    """Model for organization-specific configurations."""
    __tablename__ = "organization_configs"

    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    key = Column(String(100), nullable=False)
    value = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationship
    organization = relationship("Organization", backref="configurations")

    def __repr__(self):
        return f"<OrganizationConfig(org_id={self.organization_id}, key='{self.key}')>"

    def to_dict(self):
        """Convert config to dictionary."""
        return {
            "id": self.id,
            "organization_id": self.organization_id,
            "key": self.key,
            "value": self.value,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }
    
class Officer(Base):
    """Model for organization officers."""
    __tablename__ = "officers"

    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    user_id = Column(String(50), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationship
    organization = relationship("Organization", backref="officers")