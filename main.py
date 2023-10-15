from quart import Quart, render_template, redirect, url_for
from quart_discord import DiscordOAuth2Session
from quart import jsonify, request, session

from utils.config import Config
from utils.bot import BotFork
from utils.db import DBManager

import os
import json
import discord

config = Config()
db = DBManager(config)
app = Quart("SODA Discord Bot", static_folder="static", template_folder="templates")
discord = DiscordOAuth2Session(app) 

app.secret_key = config.get_secret_key()
os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "true"      
app.config["DISCORD_CLIENT_ID"] = config.get_client_id()   
app.config["DISCORD_CLIENT_SECRET"] = config.get_client_secret()             
app.config["DISCORD_REDIRECT_URI"] = config.get_redirect_uri()                 
app.config["DISCORD_BOT_TOKEN"] = config.get_bot_token()

AUTHORIZED_USERS = json.load(open("authorised.json", "r"))['users']
bot_running = False
intents = discord.Intents.all()

bot = BotFork(command_prefix="!", intents=intents)
bot.set_token(app.config["DISCORD_BOT_TOKEN"])






if __name__ == "__main__":
    app.run(debug=True)


