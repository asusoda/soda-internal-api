import os
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from shared import config

def run_calendar_migrations():
    """Execute the SQL migration script to create calendar event tables"""
    try:
        # Read the SQL file
        current_dir = os.path.dirname(os.path.abspath(__file__))
        sql_file = os.path.join(current_dir, 'create_tables.sql')
        
        with open(sql_file, 'r') as f:
            sql_commands = f.read()

        # Connect to the database
        conn = psycopg2.connect(
            dbname=config.DB_NAME,
            user=config.DB_USER,
            password=config.DB_PASSWORD,
            host=config.DB_HOST,
            port=config.DB_PORT
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        
        # Execute the SQL commands
        with conn.cursor() as cur:
            cur.execute(sql_commands)
        
        print("Calendar migrations completed successfully!")
        
    except Exception as e:
        print(f"Error during calendar migration: {str(e)}")
        raise
    finally:
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    run_calendar_migrations() 