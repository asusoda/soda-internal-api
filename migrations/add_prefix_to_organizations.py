from sqlalchemy import create_engine, Column, String, text, Integer, DateTime, Boolean, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
from datetime import datetime

# Get the database URL from environment or use default
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./user.db")

# Create engine and session
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Define the Organization model for table creation
class Organization(Base):
    __tablename__ = "organizations"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    guild_id = Column(String(50), nullable=False, unique=True)
    description = Column(String(500))
    icon_url = Column(String(255))
    is_active = Column(Boolean, default=True)
    config = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

def upgrade():
    """Add prefix column to organizations table"""
    # Create the organizations table if it doesn't exist
    Base.metadata.create_all(bind=engine)
    
    # Create a connection
    with engine.connect() as conn:
        # Check if prefix column exists
        result = conn.execute(text("""
            SELECT name FROM pragma_table_info('organizations') WHERE name='prefix';
        """))
        
        if not result.fetchone():
            # Add prefix column
            conn.execute(text("""
                ALTER TABLE organizations 
                ADD COLUMN prefix VARCHAR(20) UNIQUE
            """))
            
            # Update existing organizations with a default prefix based on their name
            conn.execute(text("""
                UPDATE organizations 
                SET prefix = LOWER(REPLACE(REPLACE(name, ' ', '_'), '-', '_'))
                WHERE prefix IS NULL
            """))
            
            # Make prefix column NOT NULL after setting default values
            if engine.dialect.name != 'sqlite':  # SQLite doesn't support modifying columns
                conn.execute(text("""
                    ALTER TABLE organizations 
                    MODIFY COLUMN prefix VARCHAR(20) NOT NULL
                """))
            
            # Commit the transaction
            conn.commit()
            print("Added prefix column to organizations table")
        else:
            print("Prefix column already exists")

def downgrade():
    """Remove prefix column from organizations table"""
    with engine.connect() as conn:
        # Check if prefix column exists
        result = conn.execute(text("""
            SELECT name FROM pragma_table_info('organizations') WHERE name='prefix';
        """))
        
        if result.fetchone():
            conn.execute(text("""
                ALTER TABLE organizations 
                DROP COLUMN prefix
            """))
            conn.commit()
            print("Removed prefix column from organizations table")
        else:
            print("Prefix column does not exist")

if __name__ == "__main__":
    print("Running migration: Add prefix column to organizations table")
    upgrade()
    print("Migration completed successfully") 