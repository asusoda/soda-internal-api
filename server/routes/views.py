# from quart import Quart, render_template, redirect, url_for, render_template, redirect, url_for, jsonify, request, session
from flask import Flask, render_template, redirect, url_for, request
from shared import app, bot, AUTHORIZED_USERS, bot_running, discord_oauth
import asyncio
import requests
import json

@app.route("/")
def index():

        return render_template("login.html")   



@app.route("/login/")
def login():
    return discord_oauth.create_session()

@app.route("/callback/")
def callback():
    code = request.args.get("code")
    discord_oauth.callback()
    return redirect(url_for("panel")) 

@app.route("/logout/")
def logout():
    discord_oauth.revoke()
    return redirect(url_for("index"))

@app.route("/panel")
def panel():
    if discord_oauth.authorized:
        user = discord_oauth.fetch_user()
        if str(user.id) in AUTHORIZED_USERS:
            return render_template("index.html", user=user)
        else:
            return redirect(url_for("unauthorized"))
    return redirect(url_for("index"))
    
@app.route("/unauthorized")
def unauthorized():
    return render_template("unauthorized.html")


