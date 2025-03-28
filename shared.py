from flask import Flask, Blueprint
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

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask("SoDA internal API", static_folder=None, template_folder=None)
CORS(app, 
     resources={r"/*": {"origins": "*"}},
)

# Initialize configuration
config = Config()

# Initialize database connection
db_connect = DBConnect("sqlite:///./data/user.db")
tokenManger = TokenManager()

def init_discord_bot():
    intents = discord.Intents.all()
    bot = BotFork(command_prefix="!", intents=intents)
    notion = Client(auth=config.NOTION_API_KEY)
    bot.set_token(config.BOT_TOKEN)
    return bot, notion

# Initialize Discord bot and Notion client
bot, notion = init_discord_bot()
