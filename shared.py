from flask import Flask, Blueprint, send_from_directory
from flask_cors import CORS
import discord
import os
from modules.utils.db import DBConnect
from notion_client import Client
import asyncio
from modules.utils.config import Config
# from modules.utils.db import DBManager
import logging
from modules.utils.db import DBConnect, Base
from modules.utils.TokenManager import TokenManager
from modules.bot.discord_modules.bot import BotFork
import sentry_sdk # Added for Sentry
from sentry_sdk.integrations.flask import FlaskIntegration # Added for Sentry
from modules.organizations.models import Organization, OrganizationConfig

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask("SoDA internal API", 
    static_folder=os.path.join(os.path.dirname(os.path.dirname(__file__)), "web/build"),  # Path to built frontend files
    template_folder=os.path.join(os.path.dirname(os.path.dirname(__file__)), "web/build"),  # Path to built frontend files
)
CORS(app, 
     resources={r"/*": {
         "origins": ["http://localhost:3000", "http://127.0.0.1:3000"],
         "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
         "allow_headers": ["Content-Type", "Authorization", "X-Organization-ID", "X-Organization-Prefix"],
         "supports_credentials": True
     }},
)

# Initialize configuration
config = Config()

# Initialize Sentry (ensure SENTRY_DSN is set in your environment)
if config.SENTRY_DSN:
    sentry_sdk.init(
        dsn=config.SENTRY_DSN,
        integrations=[FlaskIntegration()],
        # Set traces_sample_rate to 1.0 to capture 100%
        # of transactions for performance monitoring.
        # Adjust lower for production.
        traces_sample_rate=1.0,
        # Set profiles_sample_rate to 1.0 to profile 100%
        # of sampled transactions. Adjust lower for production.
        profiles_sample_rate=1.0,
        # Consider adding environment='development' or 'production'
        # environment=config.FLASK_ENV or 'production' # Example
    )
    logger.info("Sentry initialized.")
else:
    logger.warning("SENTRY_DSN not found in environment. Sentry not initialized.")

# Initialize token manager
tokenManger = TokenManager()

# Initialize database connection
db_connect = DBConnect()

# Initialize Discord bot
bot = BotFork(command_prefix="!", intents=discord.Intents.all())

# Initialize Notion client
notion = Client(auth=config.NOTION_API_KEY)

# Initialize logger
logger = logging.getLogger(__name__)

# Periodic cleanup of expired refresh tokens
def cleanup_expired_tokens():
    """Clean up expired refresh tokens periodically"""
    try:
        tokenManger.cleanup_expired_refresh_tokens()
        logger.info("Cleaned up expired refresh tokens")
    except Exception as e:
        logger.error(f"Error cleaning up expired tokens: {e}")

# Schedule cleanup every hour
import threading
import time

def run_cleanup_scheduler():
    """Run the cleanup scheduler in a separate thread"""
    while True:
        cleanup_expired_tokens()
        time.sleep(3600)  # Run every hour

# Start cleanup scheduler in background thread
cleanup_thread = threading.Thread(target=run_cleanup_scheduler, daemon=True)
cleanup_thread.start()

# Ensure all tables are created after all models are imported
Base.metadata.create_all(bind=db_connect.engine)

def init_discord_bot():
    intents = discord.Intents.all()
    bot = BotFork(command_prefix="!", intents=intents)
    notion = Client(auth=config.NOTION_API_KEY)
    bot.set_token(config.BOT_TOKEN)
    return bot, notion

# Initialize Discord bot and Notion client
bot, notion = init_discord_bot()
