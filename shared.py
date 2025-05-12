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
import sentry_sdk # Added for Sentry
from sentry_sdk.integrations.flask import FlaskIntegration # Added for Sentry

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask("SoDA internal API", 
    static_folder=os.path.join(os.path.dirname(os.path.dirname(__file__)), "web/build"),  # Path to built frontend files
    template_folder=os.path.join(os.path.dirname(os.path.dirname(__file__)), "web/build"),  # Path to built frontend files
)
CORS(app, 
     resources={r"/*": {"origins": "*"}},
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

# Initialize database connection
db_connect = DBConnect("sqlite:///./data/user.db")
tokenManger = TokenManager()

def init_discord_bot():
    # Use default intents and enable only what's needed
    intents = discord.Intents.default()
    intents.message_content = True  # For reading message content
    intents.guild_messages = True   # For message events in guilds

    # Create a standard py-cord bot
    bot = discord.Bot(intents=intents)
    notion = Client(auth=config.NOTION_API_KEY)

    # Register summarizer commands - only using the cog approach
    try:
        from modules.summarizer.discord_modules.setup import setup_summarizer_cog
        setup_summarizer_cog(bot)
        logger.info("Summarizer cog registered successfully")
    except Exception as e:
        logger.error(f"Error registering summarizer cog: {e}")

    return bot, notion

# Initialize Discord bot and Notion client
bot, notion = init_discord_bot()
