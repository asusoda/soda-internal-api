from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Text, JSON
from sqlalchemy.orm import relationship
from shared.database import Base

class CalendarEvent(Base):
    """Base model for calendar events that links Notion and Google Calendar events"""
    __tablename__ = 'calendar_events'

    id = Column(Integer, primary_key=True)
    title = Column(String(255), nullable=False)
    description = Column(Text)
    location = Column(String(255))
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False)
    timezone = Column(String(50), default='UTC')
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_published = Column(Boolean, default=True)
    guests = Column(JSON)  # Store as list of email addresses
    metadata = Column(JSON)  # Store additional metadata

    # Foreign keys to link with Notion and Google Calendar
    notion_event_id = Column(String(255), unique=True)
    google_calendar_event_id = Column(String(255), unique=True)

    # Relationships
    notion_event = relationship("NotionEvent", back_populates="calendar_event", uselist=False)
    google_event = relationship("GoogleEvent", back_populates="calendar_event", uselist=False)

class NotionEvent(Base):
    """Model for Notion-specific event data"""
    __tablename__ = 'notion_events'

    id = Column(Integer, primary_key=True)
    notion_page_id = Column(String(255), unique=True, nullable=False)
    notion_database_id = Column(String(255), nullable=False)
    last_edited_time = Column(DateTime)
    properties = Column(JSON)  # Store raw Notion properties
    calendar_event_id = Column(Integer, ForeignKey('calendar_events.id'))
    
    # Relationship
    calendar_event = relationship("CalendarEvent", back_populates="notion_event")

class GoogleEvent(Base):
    """Model for Google Calendar-specific event data"""
    __tablename__ = 'google_events'

    id = Column(Integer, primary_key=True)
    google_event_id = Column(String(255), unique=True, nullable=False)
    calendar_id = Column(String(255), nullable=False)
    etag = Column(String(255))  # For tracking changes
    html_link = Column(String(255))  # Link to view event in Google Calendar
    calendar_event_id = Column(Integer, ForeignKey('calendar_events.id'))
    
    # Relationship
    calendar_event = relationship("CalendarEvent", back_populates="google_event") 