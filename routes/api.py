from quart import render_template, redirect, url_for, jsonify, request
from shared import app, discord_oauth, bot, AUTHORIZED_USERS, bot_running, discord
import json
import asyncio
import discord as dpy


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



@app.route('/getGameData', methods=['GET'])
async def get_game_data():
    # Assuming your game data is stored in a file called 'game_data.json'
    with open('game_data.json') as f:
        game_data = json.load(f)
    return jsonify(game_data)


@app.route('/awardPoints', methods=['POST'])
async def award_points():
    team = request.form['team']
    points = request.form['points']

