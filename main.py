from flask import Flask, current_app # Import current_app
from shared import app, logger, config, create_summarizer_bot, create_auth_bot
from modules.utils.sync_utility import UnifiedSyncService

from modules.public.api import public_blueprint
from modules.points.api import points_blueprint
from modules.users.api import users_blueprint
from modules.utils.db import DBConnect
from modules.auth.api import auth_blueprint
from modules.ocp.api import ocp_blueprint
from modules.summarizer.api import summarizer_blueprint
from modules.bot.api import game_blueprint
from modules.storefront.api import storefront_blueprint
from modules.calendar.api import calendar_blueprint
from modules.organizations.api import organizations_blueprint
from modules.superadmin.api import superadmin_blueprint
# Removed all view blueprint imports - keeping only API blueprints

from shared import config # logger is imported above, calendar_service removed
import threading
import asyncio
from apscheduler.schedulers.background import BackgroundScheduler
import os

from datetime import datetime

# Enable Flask's debug mode and template auto-reload for development
app.config['DEBUG'] = True
app.config['TEMPLATES_AUTO_RELOAD'] = True

# Set a secret key for session management
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'dev-secret-key')

# Configure Jinja2 to output template path during rendering (helps debug template issues)
app.config['EXPLAIN_TEMPLATE_LOADING'] = True

# Instantiate and attach UnifiedSyncService after app is defined
unified_sync_service = UnifiedSyncService(logger)
app.unified_sync_service = unified_sync_service

# Register Blueprints
app.register_blueprint(public_blueprint, url_prefix="/api/public")
app.register_blueprint(points_blueprint, url_prefix="/api/points")
app.register_blueprint(users_blueprint, url_prefix="/api/users")
app.register_blueprint(auth_blueprint, url_prefix="/api/auth")
app.register_blueprint(calendar_blueprint, url_prefix="/api/calendar")
app.register_blueprint(summarizer_blueprint, url_prefix="/api/summarizer")
app.register_blueprint(game_blueprint, url_prefix="/api/bot")
app.register_blueprint(storefront_blueprint, url_prefix="/api/storefront")
app.register_blueprint(ocp_blueprint, url_prefix="/api/ocp")
app.register_blueprint(organizations_blueprint, url_prefix="/api/organizations")
app.register_blueprint(superadmin_blueprint, url_prefix="/api/superadmin")

# # Configure static file serving
# @app.route('/', defaults={'path': ''})
# @app.route('/<path:path>')
# def serve(path):
#     if path == "":
#         return send_from_directory('web/dist', 'index.html')
#     else:
#         return send_from_directory('web/dist', path)

# --- Scheduler Setup ---
scheduler = BackgroundScheduler(daemon=True)

def unified_sync_job():
    """Job function to sync Notion to both Google Calendar and OCP database."""
    with app.app_context():
        logger.info("Running scheduled unified Notion sync (Calendar + OCP)...")
        try:
            # Use the unified sync service to run both syncs
            sync_result = unified_sync_service.sync_notion_to_all()
            
            if sync_result.get("status") == "success":
                logger.info(f"Scheduled unified sync completed successfully: {sync_result.get('message')}")
            elif sync_result.get("status") == "warning":
                logger.warning(f"Scheduled unified sync completed with warnings: {sync_result.get('message')}")
            else:
                logger.error(f"Scheduled unified sync failed: {sync_result.get('message')}")
                
        except Exception as e:
            logger.error(f"Error during scheduled unified sync: {e}", exc_info=True)

# --- Bot Thread Functions ---
def run_summarizer_bot_in_thread():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    # Create bot instance inside the thread, using the thread's loop
    summarizer_bot_instance = create_summarizer_bot(loop)
    try:
        logger.info("Starting summarizer bot thread...")
        summarizer_bot_token = config.AVERY_BOT_TOKEN
        if not summarizer_bot_token:
            logger.error("AVERY_BOT_TOKEN not found. Summarizer bot will not start.")
            return
        # Use bot_instance.start() and manage the loop
        loop.run_until_complete(summarizer_bot_instance.start(summarizer_bot_token))
    except discord.errors.LoginFailure:
        logger.error(f"Login failed for summarizer bot. Check AVERY_BOT_TOKEN.")
    except Exception as e:
        logger.error(f"Error in summarizer bot thread: {e}", exc_info=True)
    finally:
        if loop.is_running() and not summarizer_bot_instance.is_closed():
            logger.info("Closing summarizer bot...")
            loop.run_until_complete(summarizer_bot_instance.close())
        loop.close()
        logger.info("Summarizer bot thread finished and loop closed.")

def run_auth_bot_in_thread():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    # Create bot instance inside the thread, using the thread's loop
    auth_bot_instance = create_auth_bot(loop)
    # Store the auth_bot instance on the Flask app context for API use
    app.auth_bot = auth_bot_instance
    try:
        logger.info("Starting auth bot thread...")
        auth_bot_token = config.BOT_TOKEN
        if not auth_bot_token:
            logger.error("BOT_TOKEN not found. Auth bot will not start.")
            return
        # Use bot_instance.start() and manage the loop
        loop.run_until_complete(auth_bot_instance.start(auth_bot_token))
    except discord.errors.LoginFailure:
        logger.error(f"Login failed for auth bot. Check AUTH_BOT_TOKEN.")
    except Exception as e:
        logger.error(f"Error in auth bot thread: {e}", exc_info=True)
    finally:
        if loop.is_running() and not auth_bot_instance.is_closed():
            logger.info("Closing auth bot...")
            loop.run_until_complete(auth_bot_instance.close())
        loop.close()
        logger.info("Auth bot thread finished and loop closed.")



# --- App Initialization ---
def initialize_app():

    summarizer_thread = threading.Thread(target=run_summarizer_bot_in_thread, name="SummarizerBotThread")
    summarizer_thread.daemon = True
    summarizer_thread.start()
    logger.info("Summarizer bot thread initiated")

    auth_thread = threading.Thread(target=run_auth_bot_in_thread, name="AuthBotThread")
    auth_thread.daemon = True
    auth_thread.start()
    logger.info("Auth bot thread initiated")

    scheduler.add_job(unified_sync_job, 'interval', minutes=15, id='unified_notion_sync_job')
    scheduler.start()
    logger.info("APScheduler started for Notion-Google Calendar sync.")
    
    # Start Flask app
    # Use debug=True in development to help with template errors
    app.run(host='0.0.0.0', port=8000, debug=True, use_reloader=False)

if __name__ == "__main__":
    initialize_app()
