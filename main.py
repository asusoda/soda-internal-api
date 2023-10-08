from quart import Quart, render_template, redirect, url_for
from quart_discord import DiscordOAuth2Session
import os
import json
from bot import MyBot
import asyncio
from quart import jsonify

app = Quart("SODA Discord Bot", static_folder="static", template_folder="templates")
app.secret_key = os.urandom(24) 
os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "true"      
app.config["DISCORD_CLIENT_ID"] = 1153940272867180594   
app.config["DISCORD_CLIENT_SECRET"] = "_2DJ787FBtThsR9oaPI3Qx3MsB4rNwdN"                
app.config["DISCORD_REDIRECT_URI"] = "http://localhost:5000/callback"                 
app.config["DISCORD_BOT_TOKEN"] = "MTE1Mzk0MDI3Mjg2NzE4MDU5NA.GW4vDt.TTACYu1rK2KwI3qRTmcfAsPcF8IARJQQAK_Kco"

AUTHORIZED_USERS = json.load(open("authorised.json", "r"))
bot_running = False
bot = MyBot()
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
    if await discord.authorized:
        user = await discord.fetch_user()
        if user.id in AUTHORIZED_USERS:
            asyncio.create_task(bot.start())
            bot_running = True
            return await render_template("dashboard.html", authorized=await discord.authorized, user=user)
        else:
            return await render_template("dashboard.html", authorized=await discord.authorized, user=user, error="You are not authorized to start the bot.")
    else:
        return await render_template("dashboard.html", authorized=await discord.authorized, user=user, error="You are not logged in.")

@app.route("/stop_bot", methods=["POST"])
async def stop_bot():
    if await discord.authorized:
        user = await discord.fetch_user()
        if user.id in AUTHORIZED_USERS:
            await bot.logout()
            bot_running = False
            return await render_template("dashboard.html", authorized=await discord.authorized, user=user)
        else:
            return await render_template("dashboard.html", authorized=await discord.authorized, user=user, error="You are not authorized to stop the bot.")
    else:
        return await render_template("dashboard.html", authorized=await discord.authorized, user=user, error="You are not logged in.")

@app.route("/status", methods=["GET"])
async def status():
    return jsonify({"status": bot_running})


if __name__ == "__main__":
    app.run(debug=True)