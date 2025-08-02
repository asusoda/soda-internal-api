from flask import Flask, send_from_directory, current_app # Import current_app
from shared import app, logger, config, create_summarizer_bot, create_auth_bot
from modules.calendar.service import CalendarService
from modules.ocp.notion_sync_service import NotionOCPSyncService # Import NotionOCPSyncService

from modules.public.api import public_blueprint
from modules.points.api import points_blueprint
from modules.users.api import users_blueprint
from modules.utils.db import DBConnect
from modules.auth.api import auth_blueprint
from modules.calendar.api import calendar_blueprint
from modules.summarizer.api import summarizer_blueprint
from modules.bot.api import game_blueprint
from modules.storefront.api import storefront_blueprint
from migrations import run_all_migrations
import threading
import asyncio
from apscheduler.schedulers.background import BackgroundScheduler
import os

# Instantiate and attach CalendarService after app is defined
calendar_service = CalendarService(logger)
app.calendar_service = calendar_service

# Instantiate and attach NotionOCPSyncService for OCP syncing
ocp_sync_service = NotionOCPSyncService(logger)
app.ocp_sync_service = ocp_sync_service

# Register Blueprints
app.register_blueprint(public_blueprint, url_prefix="/")
app.register_blueprint(points_blueprint, url_prefix="/points")
app.register_blueprint(users_blueprint, url_prefix="/users")
app.register_blueprint(auth_blueprint, url_prefix="/auth")
app.register_blueprint(calendar_blueprint, url_prefix="/calendar")
app.register_blueprint(summarizer_blueprint, url_prefix="/summarizer")
app.register_blueprint(game_blueprint, url_prefix="/bot")
app.register_blueprint(storefront_blueprint, url_prefix="/storefront")


# --- Scheduler Setup ---
scheduler = BackgroundScheduler(daemon=True)

def sync_job():
    with app.app_context():
        logger.info("Running scheduled Notion to Google Calendar sync...")
        try:
            calendar_service.sync_notion_to_google()
            logger.info("Scheduled sync completed successfully.")
        except Exception as e:
            logger.error(f"Error during scheduled sync: {e}", exc_info=True)

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

def ocp_sync_job():
    """Job function to sync Notion to OCP database."""
    with app.app_context():
        logger.info("Running scheduled Notion to OCP database sync...")
        try:
            # Use the OCP sync service to run the sync
            sync_result = ocp_sync_service.sync_notion_to_ocp()
            
            if sync_result.get("status") == "success":
                logger.info(f"Scheduled OCP sync completed successfully: {sync_result.get('message')}")
            else:
                logger.warning(f"Scheduled OCP sync completed with issues. Status: {sync_result.get('status')}, Message: {sync_result.get('message')}")
                
        except Exception as e:
            logger.error(f"Error during scheduled OCP sync: {e}", exc_info=True)

# --- App Initialization ---
def initialize_app():
    run_all_migrations()

    summarizer_thread = threading.Thread(target=run_summarizer_bot_in_thread, name="SummarizerBotThread")
    summarizer_thread.daemon = True
    summarizer_thread.start()
    logger.info("Summarizer bot thread initiated")

    auth_thread = threading.Thread(target=run_auth_bot_in_thread, name="AuthBotThread")
    auth_thread.daemon = True
    auth_thread.start()
    logger.info("Auth bot thread initiated")

    scheduler.add_job(sync_job, 'interval', minutes=15, id='notion_google_sync_job')
    scheduler.add_job(ocp_sync_job, 'interval', minutes=15, id='notion_ocp_sync_job')
    scheduler.start()
    logger.info("APScheduler started with Notion-Google Calendar sync (15 min) and Notion-OCP sync (15 min).")

    logger.info(f"Starting Flask application on port {config.SERVER_PORT} with debug={config.SERVER_DEBUG}")
    app.run(host='0.0.0.0', port=8000, debug=config.SERVER_DEBUG, use_reloader=False)

if __name__ == "__main__":
    initialize_app()
