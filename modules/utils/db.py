import os
import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Set up logger
logger = logging.getLogger(__name__)

# Create a centralized Base for all models
from .base import Base

class DBConnect:
    def __init__(self, db_url="sqlite:///./data/user.db") -> None:
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
        """Create all tables if they don't exist"""
        print("Creating database tables...")
        Base.metadata.create_all(bind=self.engine)
        print("Database tables created successfully")
        """Check if database file exists and create tables if needed"""
        try:
            # Ensure data directory exists
            os.makedirs(os.path.dirname(self.SQLALCHEMY_DATABASE_URL.replace('sqlite:///', '')), exist_ok=True)
            
            # Check if the database file exists
            db_path = self.SQLALCHEMY_DATABASE_URL.replace('sqlite:///', '')
            if not os.path.exists(db_path):
                logger.info(f"Database file does not exist at {db_path}. Creating tables...")
                # Import all models to register them with Base
                from modules.points.models import User, Points
                from modules.ocp.models import Officer, OfficerPoints
                from modules.calendar.models import CalendarEventLink
                from modules.bot.models import JeopardyGame, ActiveGame
                
                Base.metadata.create_all(bind=self.engine)
                logger.info("Database tables created successfully")
            else:
                logger.info(f"Database file already exists at {db_path}. Using existing database.")
        except Exception as e:
            logger.error(f"Error checking/creating database tables: {str(e)}")
            raise

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

    # OCP-related methods moved from OCPDBManager
    def create_officer(self, db, officer, organization_id):
        """Create a new officer record for a specific organization"""
        try:
            officer.organization_id = organization_id
            db.add(officer)
            db.commit()
            db.refresh(officer)
            return officer
        except Exception as e:
            logger.error(f"Error creating officer: {str(e)}")
            db.rollback()
            raise

    def create_officer_points(self, db, points, organization_id):
        """Create a new officer points record for a specific organization"""
        try:
            points.organization_id = organization_id
            db.add(points)
            db.commit()
            db.refresh(points)
            return points
        except Exception as e:
            logger.error(f"Error creating officer points: {str(e)}")
            db.rollback()
            raise
        
    def get_officer_by_email(self, db, email, organization_id):
        try:
            from modules.ocp.models import Officer
            if not email:
                return None
            return db.query(Officer).filter(Officer.email == email, Officer.organization_id == organization_id).first()
        except Exception as e:
            logger.error(f"Error getting officer by email: {str(e)}")
            return None
    
    def get_officer_by_name(self, db, name, organization_id):
        try:
            from modules.ocp.models import Officer
            if not name:
                return None
            return db.query(Officer).filter(Officer.name == name, Officer.organization_id == organization_id).first()
        except Exception as e:
            logger.error(f"Error getting officer by name: {str(e)}")
            return None
        
    def get_officer_points(self, db, officer_uuid, organization_id):
        try:
            from modules.ocp.models import OfficerPoints
            return db.query(OfficerPoints).filter(OfficerPoints.officer_uuid == officer_uuid, OfficerPoints.organization_id == organization_id).all()
        except Exception as e:
            logger.error(f"Error getting officer points: {str(e)}")
            return []
    
    def get_all_officers(self, db, organization_id):
        try:
            from modules.ocp.models import Officer
            return db.query(Officer).filter(Officer.organization_id == organization_id).all()
        except Exception as e:
            logger.error(f"Error getting all officers: {str(e)}")
            return []
        
    def get_points_by_event(self, db, notion_page_id, organization_id):
        try:
            from modules.ocp.models import OfficerPoints
            return db.query(OfficerPoints).filter(OfficerPoints.notion_page_id == notion_page_id, OfficerPoints.organization_id == organization_id).all()
        except Exception as e:
            logger.error(f"Error getting points by event: {str(e)}")
            return []
    
    def delete_officer_points(self, db, point_id):
        """Delete an officer points record"""
        try:
            from modules.ocp.models import OfficerPoints
            point = db.query(OfficerPoints).filter(OfficerPoints.id == point_id).first()
            if point:
                db.delete(point)
                db.commit()
                logger.info(f"Deleted points record: {point_id}")
                return True
            logger.warning(f"Points record not found: {point_id}")
            return False
        except Exception as e:
            logger.error(f"Error deleting officer points: {str(e)}")
            db.rollback()
            return False
