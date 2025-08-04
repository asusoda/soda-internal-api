from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Float
from sqlalchemy.orm import relationship
from datetime import datetime
from modules.utils.base import Base
from modules.organizations.models import Organization

# User model for the database
# Updated User model for the database
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    discord_id = Column(String, unique=True, index=True)
    username = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    points = relationship("Points", back_populates="user")

    def __repr__(self):
        return f"<User(id={self.id}, discord_id={self.discord_id}, username={self.username})>"


class Points(Base):
    __tablename__ = "points"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    points = Column(Float, default=0.0)
    last_updated = Column(DateTime, default=datetime.utcnow)
    user = relationship("User", back_populates="points")
    organization = relationship("Organization", backref="points")

    def __repr__(self):
        return f"<Points(id={self.id}, user_id={self.user_id}, organization_id={self.organization_id}, points={self.points}, last_updated={self.last_updated})>"
