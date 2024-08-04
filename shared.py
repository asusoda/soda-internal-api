
from flask import Flask, Blueprint
from flask_discord import DiscordOAuth2Session

import discord
import os

from modules.utils.config import Config
from modules.utils.db import DBManager
from modules.utils.TokenManager import TokenManager
from modules.bot.discord_modules.bot import BotFork

config = Config()
db = DBManager(config=config)
app = Flask ("SoDA internal API", static_folder=None, template_folder=None)
app.config['SECRET_KEY'] = config.get_secret_key()
app.config['CLIENT_ID'] = config.get_client_id()
app.config['CLIENT_SECRET'] = config.get_client_secret()
app.config['REDIRECT_URI'] = config.get_redirect_uri()
app.config['BOT_TOKEN'] = config.get_bot_token()


discord = DiscordOAuth2Session(client_id=app.config['CLIENT_ID'], redirect_uri=app.config['REDIRECT_URI'])
tokenManger = TokenManager()



bot_running = False
intents = discord.Intents.all()
bot = BotFork(command_prefix="!", intents=intents)
bot.set_token(config.get_bot_token())