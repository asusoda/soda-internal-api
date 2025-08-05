#!/usr/bin/env python3
"""
Script to add missing OCP tables to the existing database.
This script will create the officers and officer_points tables if they don't exist.
"""

import os
import sys
import logging

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, inspect
from modules.utils.base import Base
from modules.ocp.models import Officer, OfficerPoints
from modules.points.models import User, Points
from modules.calendar.models import CalendarEventLink
from modules.bot.models import JeopardyGame, ActiveGame

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def add_missing_tables():
    """Add missing tables to the existing database."""
    db_path = "./data/user.db"
    
    if not os.path.exists(db_path):
        print(f"❌ Database file not found at: {db_path}")
        print("Please run the application first to create the database.")
        return
    
    print("🔧 Adding missing tables to existing database...")
    print(f"📁 Database: {db_path}")
    
    try:
        # Create engine
        engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
        
        # Check existing tables
        inspector = inspect(engine)
        existing_tables = inspector.get_table_names()
        
        print(f"📊 Existing tables: {existing_tables}")
        
        # Check which tables are missing
        expected_tables = {
            'users', 'points', 'officers', 'ocp_officers', 'ocp_officer_points', 
            'calendar_event_links', 'jeopardy_game', 'active_game', 'organizations'
        }
        
        missing_tables = expected_tables - set(existing_tables)
        
        if not missing_tables:
            print("✅ All expected tables already exist!")
            return
        
        print(f"❌ Missing tables: {missing_tables}")
        
        # Create missing tables
        print("🔨 Creating missing tables...")
        
        # Import all models to register them with Base
        # This ensures all table definitions are available
        from modules.points.models import User, Points
        from modules.ocp.models import Officer, OfficerPoints
        from modules.calendar.models import CalendarEventLink
        from modules.bot.models import JeopardyGame, ActiveGame
        from modules.organizations.models import Organization
        
        # Create only the missing tables
        for table_name in missing_tables:
            if table_name in Base.metadata.tables:
                table = Base.metadata.tables[table_name]
                table.create(engine, checkfirst=True)
                print(f"✅ Created table: {table_name}")
            else:
                print(f"⚠️  Table {table_name} not found in Base metadata")
        
        # Verify tables were created
        inspector = inspect(engine)
        updated_tables = inspector.get_table_names()
        print(f"📊 Updated tables: {updated_tables}")
        
        # Check if all expected tables now exist
        still_missing = expected_tables - set(updated_tables)
        if still_missing:
            print(f"❌ Still missing tables: {still_missing}")
        else:
            print("✅ All expected tables now exist!")
        
        engine.dispose()
        
    except Exception as e:
        print(f"❌ Error adding tables: {str(e)}")
        logger.error(f"Error adding tables: {str(e)}", exc_info=True)

def verify_database_structure():
    """Verify the database structure after adding tables."""
    db_path = "./data/user.db"
    
    if not os.path.exists(db_path):
        print("❌ Database file not found")
        return
    
    try:
        engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        
        print("🔍 Database Structure Verification")
        print("=" * 40)
        print(f"📁 Database: {db_path}")
        print(f"📊 Total tables: {len(tables)}")
        print()
        
        expected_tables = {
            'users', 'points', 'officers', 'ocp_officers', 'ocp_officer_points', 
            'calendar_event_links', 'jeopardy_game', 'active_game', 'organizations'
        }
        
        print("Expected tables:")
        for table in sorted(expected_tables):
            status = "✅" if table in tables else "❌"
            print(f"  {status} {table}")
        
        print()
        print("Actual tables:")
        for table in sorted(tables):
            print(f"  📋 {table}")
        
        missing = expected_tables - set(tables)
        extra = set(tables) - expected_tables
        
        if missing:
            print(f"\n❌ Missing tables: {missing}")
        if extra:
            print(f"\n⚠️  Extra tables: {extra}")
        if not missing and not extra:
            print("\n✅ Database structure is correct!")
        
        # Check organizations table structure
        if 'organizations' in tables:
            print("\n🔍 Organizations table structure:")
            columns = inspector.get_columns('organizations')
            for column in columns:
                print(f"  📋 {column['name']}: {column['type']}")
            
            # Check if officer_role_id column exists
            column_names = [col['name'] for col in columns]
            if 'officer_role_id' in column_names:
                print("  ✅ officer_role_id column exists")
            else:
                print("  ❌ officer_role_id column missing")
        
        engine.dispose()
        
    except Exception as e:
        print(f"❌ Error verifying database: {str(e)}")

def main():
    """Main function."""
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        
        if command == "verify":
            verify_database_structure()
        else:
            print("Usage:")
            print("  python add_missing_tables.py        - Add missing tables")
            print("  python add_missing_tables.py verify - Verify database structure")
    else:
        add_missing_tables()
        print("\n" + "=" * 50)
        verify_database_structure()

if __name__ == "__main__":
    main() 