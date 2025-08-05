#!/usr/bin/env python3
"""
Migration script to move data from the old OCP database to the new consolidated database.
This script should be run once to migrate existing OCP data to the new database structure.
"""

import os
import sqlite3
import logging
from datetime import datetime
from modules.utils.db import DBConnect, Base
from modules.ocp.models import Officer, OfficerPoints

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def migrate_ocp_data():
    """
    Migrate data from the old OCP database to the new consolidated database.
    """
    old_db_path = "./data/ocp.db"
    new_db_path = "./data/user.db"
    
    # Check if old database exists
    if not os.path.exists(old_db_path):
        logger.info("Old OCP database does not exist. No migration needed.")
        return
    
    logger.info(f"Found old OCP database at {old_db_path}")
    logger.info(f"Will migrate data to {new_db_path}")
    
    try:
        # Connect to old database
        old_conn = sqlite3.connect(old_db_path)
        old_cursor = old_conn.cursor()
        
        # Initialize new database connection
        db_connect = DBConnect(f"sqlite:///{new_db_path}")
        
        # Get a database session for the new database
        db_session = next(db_connect.get_db())
        
        # Check if tables exist in old database
        old_cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        old_tables = [row[0] for row in old_cursor.fetchall()]
        
        logger.info(f"Tables found in old database: {old_tables}")
        
        migrated_officers = 0
        migrated_points = 0
        
        # Migrate officers table
        if 'officers' in old_tables:
            logger.info("Migrating officers table...")
            old_cursor.execute("SELECT uuid, email, name, title, department FROM officers")
            officers_data = old_cursor.fetchall()
            
            for officer_data in officers_data:
                uuid, email, name, title, department = officer_data
                
                # Check if officer already exists in new database
                existing_officer = db_session.query(Officer).filter(Officer.uuid == uuid).first()
                if not existing_officer:
                    new_officer = Officer(
                        uuid=uuid,
                        email=email,
                        name=name,
                        title=title,
                        department=department
                    )
                    db_session.add(new_officer)
                    migrated_officers += 1
                    logger.debug(f"Migrated officer: {name} ({email})")
                else:
                    logger.debug(f"Officer already exists: {name} ({email})")
            
            db_session.commit()
            logger.info(f"Migrated {migrated_officers} officers")
        
        # Migrate officer_points table
        if 'officer_points' in old_tables:
            logger.info("Migrating officer_points table...")
            old_cursor.execute("""
                SELECT id, points, event, role, event_type, timestamp, officer_uuid, notion_page_id, event_metadata 
                FROM officer_points
            """)
            points_data = old_cursor.fetchall()
            
            for point_data in points_data:
                point_id, points, event, role, event_type, timestamp, officer_uuid, notion_page_id, event_metadata = point_data
                
                # Check if points record already exists in new database
                existing_points = db_session.query(OfficerPoints).filter(OfficerPoints.id == point_id).first()
                if not existing_points:
                    new_points = OfficerPoints(
                        id=point_id,
                        points=points,
                        event=event,
                        role=role,
                        event_type=event_type,
                        timestamp=datetime.fromisoformat(timestamp) if timestamp else datetime.utcnow(),
                        officer_uuid=officer_uuid,
                        notion_page_id=notion_page_id,
                        event_metadata=event_metadata
                    )
                    db_session.add(new_points)
                    migrated_points += 1
                    logger.debug(f"Migrated points record: {point_id}")
                else:
                    logger.debug(f"Points record already exists: {point_id}")
            
            db_session.commit()
            logger.info(f"Migrated {migrated_points} points records")
        
        # Close connections
        old_conn.close()
        db_session.close()
        
        logger.info("Migration completed successfully!")
        logger.info(f"Migrated {migrated_officers} officers and {migrated_points} points records")
        
        # Ask user if they want to backup the old database
        backup_old_db = input("\nDo you want to backup the old OCP database? (y/n): ").lower().strip()
        if backup_old_db == 'y':
            backup_path = f"{old_db_path}.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            import shutil
            shutil.copy2(old_db_path, backup_path)
            logger.info(f"Old database backed up to: {backup_path}")
            
            # Ask if user wants to delete the old database
            delete_old_db = input("Do you want to delete the old OCP database? (y/n): ").lower().strip()
            if delete_old_db == 'y':
                os.remove(old_db_path)
                logger.info("Old OCP database deleted.")
            else:
                logger.info("Old OCP database preserved.")
        
    except Exception as e:
        logger.error(f"Error during migration: {str(e)}")
        raise

if __name__ == "__main__":
    print("OCP Database Migration Script")
    print("=" * 40)
    print("This script will migrate data from the old OCP database to the new consolidated database.")
    print("Make sure you have a backup of your data before proceeding.")
    print()
    
    proceed = input("Do you want to proceed with the migration? (y/n): ").lower().strip()
    if proceed == 'y':
        migrate_ocp_data()
    else:
        print("Migration cancelled.") 