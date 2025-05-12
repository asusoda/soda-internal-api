from flask import Flask, send_from_directory
from shared import app, bot, logger # Ensure logger is imported here or below
from modules.calendar.service import CalendarService # Import CalendarService

from modules.public.api import public_blueprint
from modules.points.api import points_blueprint
from modules.users.api import users_blueprint
from modules.utils.db import DBConnect
from modules.auth.api import auth_blueprint
from modules.calendar.api import calendar_blueprint
from modules.superadmin.views import superadmin_views  # Add SuperAdmin views import

# Import our new views blueprints
from modules.public.views import public_views
from modules.users.views import users_views
from modules.auth.views import auth_views
from modules.points.views import points_views

from shared import config # logger is imported above, calendar_service removed
import threading
from apscheduler.schedulers.background import BackgroundScheduler # Import APScheduler
import os
from datetime import datetime

# Enable Flask's debug mode and template auto-reload for development
app.config['DEBUG'] = True
app.config['TEMPLATES_AUTO_RELOAD'] = True

# Set a secret key for session management
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'dev-secret-key')

# Configure Jinja2 to output template path during rendering (helps debug template issues)
app.config['EXPLAIN_TEMPLATE_LOADING'] = True

# Instantiate and attach CalendarService after app is defined
calendar_service = CalendarService(logger)
app.calendar_service = calendar_service

# Register API Blueprints (used for API calls)
app.register_blueprint(public_blueprint, url_prefix="/api")
app.register_blueprint(points_blueprint, url_prefix="/api/points")
app.register_blueprint(users_blueprint, url_prefix="/api/users")
app.register_blueprint(auth_blueprint, url_prefix="/api/auth")
app.register_blueprint(calendar_blueprint, url_prefix="/api/calendar")

# Register Views Blueprints (used for template rendering)
app.register_blueprint(public_views, url_prefix="/")
app.register_blueprint(users_views, url_prefix="/users")
app.register_blueprint(auth_views, url_prefix="/auth")
app.register_blueprint(points_views, url_prefix="/points")
app.register_blueprint(superadmin_views, url_prefix="/superadmin")  # Register SuperAdmin views

# Template context processor to inject current year into all templates
@app.context_processor
def inject_current_year():
    return {'current_year': datetime.now().year}

# Configure static file serving
@app.route('/<path:path>')
def serve_static(path):
    if path.startswith('api/'):
        # Skip API routes
        return "", 404
    return send_from_directory(app.static_folder, path)

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

    # Start Discord bot in a separate thread
    bot_thread = threading.Thread(target=bot.run)
    bot_thread.daemon = True
    bot_thread.start()

    # Add and start the scheduler job
    scheduler.add_job(sync_job, 'interval', minutes=15, id='notion_google_sync_job')
    scheduler.start()
    logger.info("APScheduler started for Notion-Google Calendar sync.")
    
    # Start Flask app
    # Use debug=True in development to help with template errors
    app.run(host='0.0.0.0', port=8000, debug=True, use_reloader=False)

if __name__ == "__main__":
    initialize_app()
