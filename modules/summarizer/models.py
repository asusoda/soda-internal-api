from sqlalchemy import Column, Integer, String, Boolean, Text, Float, DateTime
from sqlalchemy.sql import func
from modules.points.models import Base

class SummarizerConfig(Base):
    """
    Model for storing summarizer configuration settings
    """
    __tablename__ = 'summarizer_config'
    
    id = Column(Integer, primary_key=True)
    api_key = Column(String(255), nullable=True)  # Gemini API key (encrypted)
    model_name = Column(String(100), default="gemini-2.5-pro")  # Gemini model to use
    default_duration = Column(String(10), default="24h")  # Default duration for summaries
    max_tokens = Column(Integer, default=1024)  # Maximum tokens for summary generation
    temperature = Column(Float, default=0.7)  # Temperature setting for generation
    enabled = Column(Boolean, default=True)  # Whether the summarizer is enabled
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    def to_dict(self):
        """Convert model to dictionary for API responses"""
        return {
            "id": self.id,
            "model_name": self.model_name,
            "default_duration": self.default_duration,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "enabled": self.enabled,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }

class SummaryLog(Base):
    """
    Model for logging summary requests and metrics
    """
    __tablename__ = 'summary_logs'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(String(100), nullable=False)  # Discord user ID
    channel_id = Column(String(100), nullable=False)  # Discord channel ID
    guild_id = Column(String(100), nullable=False)  # Discord guild/server ID
    duration = Column(String(10), nullable=False)  # Duration requested
    message_count = Column(Integer, default=0)  # Number of messages summarized
    completion_time = Column(Float, nullable=True)  # Time taken to generate summary in seconds
    error = Column(Boolean, default=False)  # Whether an error occurred
    error_message = Column(Text, nullable=True)  # Error message if applicable
    created_at = Column(DateTime, default=func.now())
    
    def to_dict(self):
        """Convert model to dictionary for API responses"""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "channel_id": self.channel_id,
            "guild_id": self.guild_id,
            "duration": self.duration,
            "message_count": self.message_count,
            "completion_time": self.completion_time,
            "error": self.error,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }