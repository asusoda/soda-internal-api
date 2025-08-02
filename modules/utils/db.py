import os
import logging
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Set up logger
logger = logging.getLogger(__name__)

# Create a centralized Base for all models
Base = declarative_base()

class DBConnect:
    def __init__(self, db_url="sqlite:///./data/user.db") -> None:
        self.SQLALCHEMY_DATABASE_URL = db_url
        self.engine = create_engine(
            self.SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
        )
        self.SessionLocal = sessionmaker(
            autocommit=False, autoflush=False, bind=self.engine
        )
        self.check_and_create_tables()

    def check_and_create_tables(self):
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
    def create_officer(self, db, officer):
        """Create a new officer record"""
        try:
            db.add(officer)
            db.commit()
            db.refresh(officer)
            if officer.email:
                logger.info(f"Created officer: {officer.name} ({officer.email})")
            else:
                logger.info(f"Created officer: {officer.name}")
            return officer
        except Exception as e:
            logger.error(f"Error creating officer: {str(e)}")
            db.rollback()
            raise

    def create_officer_points(self, db, points):
        """Create a new officer points record"""
        try:
            db.add(points)
            db.commit()
            db.refresh(points)
            logger.info(f"Created points record: {points.id} for officer UUID {points.officer_uuid}")
            return points
        except Exception as e:
            logger.error(f"Error creating officer points: {str(e)}")
            db.rollback()
            raise
        
    def get_officer_by_email(self, db, email):
        """Get an officer by email"""
        try:
            from modules.ocp.models import Officer
            if not email:
                return None
            return db.query(Officer).filter(Officer.email == email).first()
        except Exception as e:
            logger.error(f"Error getting officer by email: {str(e)}")
            return None
    
    def get_officer_by_name(self, db, name):
        """Get an officer by name"""
        try:
            from modules.ocp.models import Officer
            if not name:
                return None
            return db.query(Officer).filter(Officer.name == name).first()
        except Exception as e:
            logger.error(f"Error getting officer by name: {str(e)}")
            return None
        
    def get_officer_points(self, db, officer_uuid):
        """Get all points for an officer by UUID"""
        try:
            from modules.ocp.models import OfficerPoints
            return db.query(OfficerPoints).filter(OfficerPoints.officer_uuid == officer_uuid).all()
        except Exception as e:
            logger.error(f"Error getting officer points: {str(e)}")
            return []
    
    def get_all_officers(self, db):
        """Get all officers"""
        try:
            from modules.ocp.models import Officer
            return db.query(Officer).all()
        except Exception as e:
            logger.error(f"Error getting all officers: {str(e)}")
            return []
        
    def get_points_by_event(self, db, notion_page_id):
        """Get points by event"""
        try:
            from modules.ocp.models import OfficerPoints
            return db.query(OfficerPoints).filter(OfficerPoints.notion_page_id == notion_page_id).all()
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
