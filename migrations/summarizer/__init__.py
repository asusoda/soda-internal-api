import os
from modules.utils.db import DBConnect
from modules.summarizer.models import SummarizerConfig, SummaryLog
import logging

logger = logging.getLogger(__name__)

def run_migration():
    """Create the summarizer tables if they don't exist"""
    # Make sure data directory exists
    os.makedirs('./data', exist_ok=True)
    
    # Create a database connection
    db_connect = DBConnect("sqlite:///./data/user.db")
    db = next(db_connect.get_db())
    
    try:
        # Create the tables
        SummarizerConfig.__table__.create(db_connect.engine, checkfirst=True)
        SummaryLog.__table__.create(db_connect.engine, checkfirst=True)
        
        # Check if we need to create a default config
        config = db.query(SummarizerConfig).first()
        if not config:
            # Create default config with the specified model
            config = SummarizerConfig(
                model_name="models/gemini-2.0-flash",
                default_duration="24h",
                max_tokens=8192,
                temperature=0.7,
                enabled=True
            )
            db.add(config)
            db.commit()
            logger.info("Created default summarizer configuration")
            
        logger.info("Summarizer migration completed successfully")
    except Exception as e:
        logger.error(f"Error in summarizer migration: {e}")
        db.rollback()
        raise
    finally:
        db.close()