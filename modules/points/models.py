from sqlalchemy import Column, String, Integer, ForeignKey, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime

Base = declarative_base()


# User model for the database
class User(Base):
    __tablename__ = "users"
    uuid = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    asu_id = Column(String, nullable=False, unique=True)
    name = Column(String, nullable=False)
    email = Column(String, nullable=False, unique=True)
    academic_standing = Column(String, nullable=False)
    points = relationship("Points", backref="user", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<User(name={self.name}, email={self.email}, academic_standing={self.academic_standing})>"


class Points(Base):
    __tablename__ = "points"
    id = Column(Integer, primary_key=True, autoincrement=True)
    points = Column(Integer, nullable=False)
    event = Column(String, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    awarded_by_officer = Column(String, nullable=False)
    user_id = Column(String, ForeignKey("users.uuid"), nullable=False)

    def __repr__(self):
        return f"<Points(points={self.points}, event={self.event}, timestamp={self.timestamp}, awarded_by_officer={self.awarded_by_officer})>"
