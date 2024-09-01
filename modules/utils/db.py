import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from modules.points.models import Base


class DBConnect:
    def __init__(self, db_url="sqlite:///./user.db") -> None:
        self.SQLALCHEMY_DATABASE_URL = db_url
        self.engine = create_engine(
            self.SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
        )
        self.SessionLocal = sessionmaker(
            autocommit=False, autoflush=False, bind=self.engine
        )
        self.check_and_create_tables()

    def check_and_create_tables(self):
        # Check if the database file exists
        if not os.path.exists("./user.db"):
            Base.metadata.create_all(bind=self.engine)

    def get_db(self):
        db = self.SessionLocal()
        try:
            yield db
        finally:
            db.close()

    def create_user(self, db, user):
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    def create_point(self, db, point):
        db.add(point)
        db.commit()
        db.refresh(point)
        return point
