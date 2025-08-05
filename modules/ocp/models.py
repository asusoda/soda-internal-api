from sqlalchemy import Column, String, Integer, ForeignKey, DateTime, JSON
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime
from modules.utils.db import Base


class Officer(Base):
    __tablename__ = "ocp_officers"  # Changed to avoid conflict with organization officers
    
    # Make email optional, use UUID as primary key instead
    uuid = Column(String, primary_key=True, nullable=False, unique=True, default=lambda: str(uuid.uuid4()))
    email = Column(String, nullable=True, unique=True)  # Email is now optional
    name = Column(String, nullable=False)
    title = Column(String, nullable=False, default="Unknown")  # Officer title/role
    department = Column(String, nullable=False, default="Unknown")  # Engineering, Finance, Marketing, etc.
    points = relationship("OfficerPoints", backref="officer", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Officer(name={self.name}, email={self.email}, title={self.title}, department={self.department})>"


class OfficerPoints(Base):
    __tablename__ = "ocp_officer_points"  # Changed to avoid conflict
    id = Column(Integer, primary_key=True, autoincrement=True)
    points = Column(Integer, nullable=False)
    event = Column(String, nullable=False)
    role = Column(String, nullable=False)  # Event Lead, Event Staff, Logistics Staff
    event_type = Column(String, nullable=True)  # GBM, Special Event, etc.
    timestamp = Column(DateTime, default=datetime.utcnow)
    officer_uuid = Column(String, ForeignKey("ocp_officers.uuid"), nullable=False)  # Updated foreign key
    notion_page_id = Column(String, nullable=True)  # To link with the Notion event
    event_metadata = Column(JSON, nullable=True)  # Store additional event metadata if needed

    def __repr__(self):
        return f"<OfficerPoints(points={self.points}, event={self.event}, role={self.role}, event_type={self.event_type}, timestamp={self.timestamp})>" 