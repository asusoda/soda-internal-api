from flask import Flask
from shared import app, bot, logger # Ensure logger is imported here or below
from modules.calendar.service import CalendarService # Import CalendarService

from modules.public.api import public_blueprint
from modules.points.api import points_blueprint
from modules.users.api import users_blueprint
from modules.utils.db import DBConnect
from modules.auth.api import auth_blueprint
from modules.calendar.api import calendar_blueprint
# from modules.calendar.service import CalendarService # Removed local import
from migrations import run_all_migrations
from shared import config # logger is imported above, calendar_service removed
import threading
from apscheduler.schedulers.background import BackgroundScheduler # Import APScheduler

# Instantiate and attach CalendarService after app is defined
calendar_service = CalendarService(logger)
app.calendar_service = calendar_service

# Register Blueprints
app.register_blueprint(public_blueprint, url_prefix="/")
app.register_blueprint(points_blueprint, url_prefix="/points")
app.register_blueprint(users_blueprint, url_prefix="/users")
app.register_blueprint(auth_blueprint, url_prefix="/auth")
app.register_blueprint(calendar_blueprint, url_prefix="/calendar")

# --- Scheduler Setup ---
scheduler = BackgroundScheduler(daemon=True)

def sync_job():
    """Job function to sync Notion to Google Calendar."""
    with app.app_context():
        logger.info("Running scheduled Notion to Google Calendar sync...")
        try:
            # Instantiate service within context to ensure access to app resources
            # calendar_service is now imported from shared.py
            calendar_service.sync_notion_to_google()
            logger.info("Scheduled sync completed successfully.")
        except Exception as e:
            logger.error(f"Error during scheduled sync: {e}", exc_info=True)

# --- App Initialization ---
def initialize_app():
    """Initialize the application with necessary setup"""
    # Run all database migrations
    run_all_migrations()

    # Start Discord bot in a separate thread
    bot_thread = threading.Thread(target=bot.run)
    bot_thread.daemon = True
    bot_thread.start()

    # Add and start the scheduler job
    scheduler.add_job(sync_job, 'interval', minutes=15, id='notion_google_sync_job')
    scheduler.start()
    logger.info("APScheduler started for Notion-Google Calendar sync.")
    
    # Start Flask app
    # Ensure use_reloader=False if debug is False, as reloader can cause scheduler issues
    app.run(host='0.0.0.0', port=8000, debug=False, use_reloader=False)

if __name__ == "__main__":
    initialize_app()
