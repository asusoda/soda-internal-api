from utils.config import Config
from discord.bot import BotFork
from utils.db import DBManager
from utils.TokenManager import TokenManager
from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from flask_discord import DiscordOAuth2Session, requires_authorization, Unauthorized

import os
import json
import discord
import random

config = Config()
db = DBManager(config)
# token_manager = TokenManager()
app = Flask("SODA Discord Bot", static_folder="static", template_folder="templates")

app.secret_key = config.get_secret_key()
os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "true"
app.config["DISCORD_CLIENT_ID"] = config.get_client_id()
app.config["DISCORD_CLIENT_SECRET"] = config.get_client_secret()
app.config["DISCORD_REDIRECT_URI"] = config.get_redirect_uri()
app.config["DISCORD_BOT_TOKEN"] = config.get_bot_token()


AUTHORIZED_USERS = json.load(open("authorised.json", "r"))['users']
bot_running = False


discord_oauth = DiscordOAuth2Session(app)

intents = discord.Intents.all()

bot = BotFork(command_prefix="!", intents=intents)
bot.set_token(config.get_bot_token())


