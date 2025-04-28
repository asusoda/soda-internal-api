from sqlalchemy import (
    Column, Integer, String, Boolean, Table, ForeignKey, UniqueConstraint
)
from sqlalchemy.orm import relationship
from datetime import datetime
from modules.utils.db import Base

# --- association table ----------------------------------------------------
officer_org = Table(
    "officer_org",
    Base.metadata,
    Column("officer_id", ForeignKey("officers.id"), primary_key=True),
    Column("organization_id", ForeignKey("organizations.id"), primary_key=True),
    # Optional: be sure we don’t insert the same pair twice
    UniqueConstraint("officer_id", "organization_id", name="uix_officer_org")
)

# --- domain tables --------------------------------------------------------
class Officer(Base):
    __tablename__ = "officers"

    id           = Column(Integer, primary_key=True)
    name         = Column(String, nullable=False)
    email        = Column(String, nullable=False, unique=True)
    organization = Column(String, nullable=False)  # keep if you still need a “home” org
    token        = Column(String, nullable=False)

    # many-to-many
    organizations = relationship(
        "Organization",
        secondary=officer_org,
        back_populates="officers",
        lazy="selectin"           # eager-loads in one extra query; adjust to taste
    )

class Organization(Base):
    __tablename__ = "organizations"

    id          = Column(Integer, primary_key=True)
    name        = Column(String, nullable=False)
    description = Column(String, nullable=False)

    officers = relationship(
        "Officer",
        secondary=officer_org,
        back_populates="organizations",
        lazy="selectin"
    )

    
    