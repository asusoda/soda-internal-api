from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from modules.points.models import Base

class DBConnect:
    def __init__(self, database_url="sqlite:///./test.db"):
        self.SQLALCHEMY_DATABASE_URL = database_url
        self.engine = create_engine(
            self.SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
        )
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        self.create_tables()

    def create_tables(self):
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
