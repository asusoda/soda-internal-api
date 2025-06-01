from sqlalchemy import Column, String, Integer, ForeignKey, DateTime
from sqlalchemy.orm import declarative_base, relationship
import uuid
from datetime import datetime

Base = declarative_base()


# User model for the database
# Updated User model for the database
class User(Base):
    __tablename__ = "users"
    email = Column(String, primary_key=True, nullable=False, unique=True)  # Email as the primary key
    uuid = Column(String, nullable=False, unique=True, default=lambda: str(uuid.uuid4()))  # UUID as a secondary key
    asu_id = Column(String, nullable=True)
    name = Column(String, nullable=False)
    academic_standing = Column(String, nullable=False)
    major = Column(String, nullable=False)
    points = relationship("Points", backref="user", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<User(name={self.name}, email={self.email}, uuid={self.uuid}, academic_standing={self.academic_standing})>"


class Points(Base):
    __tablename__ = "points"
    id = Column(Integer, primary_key=True, autoincrement=True)
    points = Column(Integer, nullable=False)
    event = Column(String, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    awarded_by_officer = Column(String, nullable=False)
    user_email = Column(String, ForeignKey("users.email"), nullable=False)  # Add this column

    def __repr__(self):
        return f"<Points(points={self.points}, event={self.event}, timestamp={self.timestamp}, awarded_by_officer={self.awarded_by_officer})>"
