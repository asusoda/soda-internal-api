import requests
from quart import Quart, render_template, redirect, url_for
from quart_discord import DiscordOAuth2Session
import os
import json
from bot import MyBot
import asyncio
from quart import jsonify
import discord

app = Quart("SODA Discord Bot", static_folder="static", template_folder="templates")
app.secret_key = os.urandom(24) 
os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "true"      
app.config["DISCORD_CLIENT_ID"] = 1153940272867180594   
app.config["DISCORD_CLIENT_SECRET"] = "_2DJ787FBtThsR9oaPI3Qx3MsB4rNwdN"                
app.config["DISCORD_REDIRECT_URI"] = "http://localhost:5000/callback"                 
app.config["DISCORD_BOT_TOKEN"] = "MTE1Mzk0MDI3Mjg2NzE4MDU5NA.GW4vDt.TTACYu1rK2KwI3qRTmcfAsPcF8IARJQQAK_Kco"

AUTHORIZED_USERS = json.load(open("authorised.json", "r"))['users']
bot_running = False
intents = discord.Intents.all()

bot = MyBot(command_prefix="!", intents=intents)
bot.set_token(app.config["DISCORD_BOT_TOKEN"])
discord = DiscordOAuth2Session(app) #handle session for authentication

@app.route("/")
async def home():
    return await render_template("home.html", authorized=await discord.authorized)

@app.route("/login")
async def login():
    return await discord.create_session() # handles session creation for authentication

@app.route("/callback")
async def callback():
    try:
        await discord.callback()
    except Exception:
        pass

    return redirect(url_for("dashboard")) 


@app.route("/dashboard")
async def dashboard():
    if await discord.authorized:
        user = await discord.fetch_user()
        return await render_template("dashboard.html", authorized=await discord.authorized, user=user)
        

@app.route("/start_bot", methods=["POST"])
async def start_bot():
    global bot_running  # Declare bot_running as global
    if await discord.authorized:
        user = await discord.fetch_user()
        print(user)
        print(user.id)
        print(AUTHORIZED_USERS)
        if str(user.id) in AUTHORIZED_USERS:
            asyncio.create_task(bot.start(token=app.config["DISCORD_BOT_TOKEN"]))
            bot_running = True
            return jsonify({"message": "Bot started successfully", "status": "success"}), 200
        else:
            print(user.id)
            return jsonify({"message": "You are not authorized to start the bot.", "status": "unauthorized"}), 403
    else:
        return jsonify({"message": "You are not logged in.", "status": "unauthorized"}), 401


@app.route("/stop_bot", methods=["POST"])
async def stop_bot():
    global bot_running  # Declare bot_running as global
    if await discord.authorized:
        user = await discord.fetch_user()
        if str(user.id) in AUTHORIZED_USERS:
            await bot.close()
            bot_running = False
            return jsonify({"message": "Bot stopped successfully", "status": "success"}), 200
        else:
            return jsonify({"message": "You are not authorized to stop the bot.", "status": "unauthorized"}), 403
    else:
        return jsonify({"message": "You are not logged in.", "status": "unauthorized"}), 401

@app.route("/status", methods=["GET"])
async def status():
    return jsonify({"status": bot_running})




if __name__ == "__main__":
    app.run(debug=True)