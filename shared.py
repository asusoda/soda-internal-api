from flask import Flask, Blueprint
from flask_cors import CORS
import discord
import os
import asyncio
from modules.utils.config import Config

from modules.utils.db import DBConnect, Base
from modules.utils.TokenManager import TokenManager
from modules.bot.discord_modules.bot import BotFork


config = Config()
db = DBConnect()
app = Flask("SoDA internal API", static_folder=None, template_folder=None)
CORS(app)
tokenManger = TokenManager()


bot_running = False
intents = discord.Intents.all()
bot = BotFork(command_prefix="!", intents=intents)
bot.set_token(config.BOT_TOKEN)
asyncio.run(bot.run())
