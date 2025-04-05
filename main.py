from flask import Flask
from shared import app, bot
from modules.public.api import public_blueprint
from modules.points.api import points_blueprint
from modules.users.api import users_blueprint
from modules.utils.db import DBConnect
from modules.auth.api import auth_blueprint
from modules.calendar.api import calendar_blueprint, get_google_calendar_service, delete_duplicate_synced_gcal_events # Added imports
from migrations import run_all_migrations
from shared import config, logger # Added imports
import threading

# Register Blueprints
app.register_blueprint(public_blueprint, url_prefix="/")
app.register_blueprint(points_blueprint, url_prefix="/points")
app.register_blueprint(users_blueprint, url_prefix="/users")
app.register_blueprint(auth_blueprint, url_prefix="/auth")
app.register_blueprint(calendar_blueprint, url_prefix="/calendar")

def initialize_app():
    """Initialize the application with necessary setup"""
    # Run all database migrations
    run_all_migrations()

    # --- Add Duplicate Calendar Event Cleanup ---
    logger.info("Attempting Google Calendar duplicate event cleanup on startup...")
    try:
        gcal_service = get_google_calendar_service()
        if gcal_service and config.GOOGLE_CALENDAR_ID:
            delete_duplicate_synced_gcal_events(gcal_service, config.GOOGLE_CALENDAR_ID)
            logger.info("Duplicate event cleanup process completed.")
        elif not gcal_service:
            logger.warning("Could not get Google Calendar service, skipping duplicate cleanup.")
        else: # No calendar ID configured
             logger.warning("GOOGLE_CALENDAR_ID not configured, skipping duplicate cleanup.")
    except Exception as e_cleanup:
        logger.error(f"Error during startup duplicate event cleanup: {e_cleanup}")
        # Optionally capture to Sentry if desired
        # capture_exception(e_cleanup)
    # --- End Cleanup ---

    # Start Discord bot in a separate thread
    bot_thread = threading.Thread(target=bot.run)
    bot_thread.daemon = True
    bot_thread.start()
    
    # Start Flask app
    app.run(host='0.0.0.0', port=8000, debug=True)

if __name__ == "__main__":
    initialize_app()
