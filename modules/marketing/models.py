from sqlalchemy import Column, String, Integer, Text, DateTime, JSON, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from modules.points.models import Base


class MarketingEvent(Base):
    """
    Model for storing marketing events and their generated content
    """
    __tablename__ = "marketing_events"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    event_id = Column(String(255), unique=True, nullable=False, index=True)  # External event ID
    name = Column(String(255), nullable=False)
    date = Column(DateTime, nullable=True)
    location = Column(String(255), nullable=True)
    info = Column(Text, nullable=True)
    
    # Generated content
    content = Column(JSON, nullable=True)  # Stores the generated content for different platforms
    html = Column(Text, nullable=True)     # GrapesJS HTML content
    css = Column(Text, nullable=True)      # GrapesJS CSS content
    
    # Status tracking
    status = Column(String(50), default='pending')  # pending, completed, posted
    is_completed = Column(Boolean, default=False)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    def __repr__(self):
        return f"<MarketingEvent(id={self.id}, event_id={self.event_id}, name={self.name}, status={self.status})>"

    def to_dict(self):
        """Convert the model to a dictionary for API responses"""
        return {
            'id': self.id,
            'event_id': self.event_id,
            'name': self.name,
            'date': self.date.isoformat() if self.date else None,
            'location': self.location,
            'info': self.info,
            'content': self.content,
            'grapes_code': {
                'html': self.html or '',
                'css': self.css or ''
            },
            'status': self.status,
            'is_completed': self.is_completed,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None
        }


class MarketingConfig(Base):
    """
    Model for storing marketing configuration settings
    """
    __tablename__ = "marketing_config"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String(255), unique=True, nullable=False)
    value = Column(Text, nullable=True)
    description = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<MarketingConfig(key={self.key}, value={self.value})>"


class MarketingLog(Base):
    """
    Model for logging marketing activities and metrics
    """
    __tablename__ = "marketing_logs"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    event_id = Column(String(255), nullable=False)
    action = Column(String(100), nullable=False)  # generate_content, post_social, send_notification, etc.
    platform = Column(String(50), nullable=True)  # instagram, linkedin, discord, email
    status = Column(String(50), nullable=False)   # success, failed, pending
    message = Column(Text, nullable=True)
    metadata = Column(JSON, nullable=True)        # Store additional data like error details, response data
    
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<MarketingLog(event_id={self.event_id}, action={self.action}, status={self.status})>"
