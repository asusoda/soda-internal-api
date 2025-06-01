import os
import logging
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from modules.points.models import Base

# Set up logger
logger = logging.getLogger(__name__)

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


class OCPDBManager:
    """Centralized database manager for Officer Contribution Points (OCP)"""
    
    def __init__(self, db_url="sqlite:///./data/ocp.db"):
        """Initialize the OCP database connection"""
        self.SQLALCHEMY_DATABASE_URL = db_url
        logger.info(f"Initializing OCPDBManager with database URL: {db_url}")
        
        try:
            # Ensure data directory exists
            os.makedirs(os.path.dirname(db_url.replace('sqlite:///', '')), exist_ok=True)
            
            # Create engine and session
            self.engine = create_engine(
                self.SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
            )
            self.SessionLocal = sessionmaker(
                autocommit=False, autoflush=False, bind=self.engine
            )
            logger.info("OCP database engine and session factory created")
            
            # Check if tables exist and create them if needed
            self.check_and_create_tables()
            
        except Exception as e:
            logger.error(f"Error initializing OCP database: {str(e)}")
            self.engine = None
            self.SessionLocal = None
            raise
    
    def check_and_create_tables(self):
        """Check if database tables exist and create them if they don't"""
        try:
            # Extract the database file path from the URL
            db_path = self.SQLALCHEMY_DATABASE_URL.replace('sqlite:///', '')
            
            # Check if the database file exists
            if not os.path.exists(db_path):
                logger.info(f"OCP database file does not exist at {db_path}. Will create tables.")
                # Import the Base class from the models module
                from modules.calendar.ocp.models import Base
                Base.metadata.create_all(bind=self.engine)
                logger.info("OCP database tables created successfully")
            else:
                logger.info(f"OCP database file already exists at {db_path}. Using existing database.")
        except Exception as e:
            logger.error(f"Error checking/creating OCP database tables: {str(e)}")
            raise
    
    def create_tables(self, Base):
        """Create database tables from SQLAlchemy models if they don't exist"""
        try:
            # Check if tables exist by inspecting the database
            from sqlalchemy import inspect
            inspector = inspect(self.engine)
            
            # Get the table names from the Base metadata
            table_names = Base.metadata.tables.keys()
            existing_tables = inspector.get_table_names()
            
            # Check if all tables exist
            tables_exist = all(table in existing_tables for table in table_names)
            
            if not tables_exist:
                logger.info("Some OCP database tables are missing. Creating tables...")
                Base.metadata.create_all(bind=self.engine)
                logger.info("OCP database tables created successfully")
            else:
                logger.info("All OCP database tables already exist. No tables created.")
        except Exception as e:
            logger.error(f"Error creating OCP database tables: {str(e)}")
            raise
    
    def get_db(self):
        """Get a database session"""
        if self.SessionLocal is None:
            logger.error("Cannot get database session: Database not initialized")
            raise ValueError("Database connection not initialized")
            
        db = self.SessionLocal()
        try:
            yield db
        finally:
            db.close()
            
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
            from modules.calendar.ocp.models import Officer
            if not email:
                return None
            return db.query(Officer).filter(Officer.email == email).first()
        except Exception as e:
            logger.error(f"Error getting officer by email: {str(e)}")
            return None
    
    def get_officer_by_name(self, db, name):
        """Get an officer by name"""
        try:
            from modules.calendar.ocp.models import Officer
            if not name:
                return None
            return db.query(Officer).filter(Officer.name == name).first()
        except Exception as e:
            logger.error(f"Error getting officer by name: {str(e)}")
            return None
        
    def get_officer_points(self, db, officer_uuid):
        """Get all points for an officer by UUID"""
        try:
            from modules.calendar.ocp.models import OfficerPoints
            return db.query(OfficerPoints).filter(OfficerPoints.officer_uuid == officer_uuid).all()
        except Exception as e:
            logger.error(f"Error getting officer points: {str(e)}")
            return []
    
    def get_all_officers(self, db):
        """Get all officers"""
        try:
            from modules.calendar.ocp.models import Officer
            return db.query(Officer).all()
        except Exception as e:
            logger.error(f"Error getting all officers: {str(e)}")
            return []
        
    def get_points_by_event(self, db, notion_page_id):
        """Get points by event"""
        try:
            from modules.calendar.ocp.models import OfficerPoints
            return db.query(OfficerPoints).filter(OfficerPoints.notion_page_id == notion_page_id).all()
        except Exception as e:
            logger.error(f"Error getting points by event: {str(e)}")
            return []
    
    def delete_officer_points(self, db, point_id):
        """Delete an officer points record"""
        try:
            from modules.calendar.ocp.models import OfficerPoints
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
