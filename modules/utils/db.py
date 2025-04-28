import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from modules.points.models import Base


class DBConnect:
    def __init__(self, db_url="sqlite:///./user.db") -> None:
        self.SQLALCHEMY_DATABASE_URL = db_url
        
        # Ensure the database directory exists
        self._ensure_db_directory()
        
        self.engine = create_engine(
            self.SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
        )
        self.SessionLocal = sessionmaker(
            autocommit=False, autoflush=False, bind=self.engine
        )
        self.check_and_create_tables()

    def _ensure_db_directory(self):
        """Extract the database file path and ensure its directory exists"""
        if self.SQLALCHEMY_DATABASE_URL.startswith('sqlite:///'):
            # Remove sqlite:/// prefix to get the file path
            db_path = self.SQLALCHEMY_DATABASE_URL[10:]
            
            # Normalize path to handle potential ./ prefix
            db_path = os.path.normpath(db_path)
            
            # Get the directory part of the path
            db_dir = os.path.dirname(db_path)
            
            # If there's a directory component and it doesn't exist, create it
            if db_dir and not os.path.exists(db_dir):
                os.makedirs(db_dir, exist_ok=True)
                print(f"Created database directory: {db_dir}")

    def check_and_create_tables(self):
        if self.SQLALCHEMY_DATABASE_URL.startswith('sqlite:///'):
            # Get the database file path
            db_path = self.SQLALCHEMY_DATABASE_URL[10:]
            db_path = os.path.normpath(db_path)
            
            # Create tables if the database doesn't exist or is empty
            if not os.path.exists(db_path) or os.path.getsize(db_path) == 0:
                print(f"Creating database tables in {db_path}")
                Base.metadata.create_all(bind=self.engine)
        else:
            # For non-SQLite databases, always try to create tables
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
