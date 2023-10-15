from quart import Quart, render_template, redirect, url_for
from quart_discord import DiscordOAuth2Session
from quart import render_template, redirect, url_for, jsonify
from .main import app, discord, bot, AUTHORIZED_USERS, bot_running, intents, db
import asyncio
import discord as dpy
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
    
@app.route("/gamepanel")
async def gamepanel():
    if await discord.authorized:
        user = await discord.fetch_user()
        if str(user.id) in AUTHORIZED_USERS:
            return await render_template("gamepanel.html", authorized=await discord.authorized, user=user)