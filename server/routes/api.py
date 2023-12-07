from flask import jsonify, request, redirect, url_for
from flask_discord import DiscordOAuth2Session, requires_authorization, Unauthorized, current_app, exceptions
from shared import app,  bot, bot_running, discord_oauth, db
from os import listdir
import json



@app.errorhandler(Unauthorized)
def redirect_unauthorized(e):
    return redirect(url_for("login"))


@app.route("/me/")
@requires_authorization
def me():
    user = discord_oauth.fetch_user()
    return f"""
    <html>
        <head>
            <title>{user.name}</title>
        </head>
        <body>
            <img src='{user.avatar_url}' />
        </body>
    </html>"""
 
@app.route('/api/status', methods=['GET'])
def status():
    return jsonify({"status": "success"}), 200



@app.route('/api/getfeatures', methods=['GET'])
def get_features():
    features = {
                 "Authentication" :{ "link":"auth",
                                      "img": "users.svg"
                 },
                 "Jeprody" : {
                                "link":"jeopardy",
                                "img": "jeopardy.svg"
                 },
                 "Bot Management" : {
                                "link":"bot",
                                "img": "settings.svg"
                 }
                 }
                
    return jsonify(features), 200

@app.route('/api/createchannels', methods=['POST'])
async def create_channels():
    if bot.get_cog("GameCog").is_setup():
        return jsonify({'error': 'Channels already created'}), 400
    else:
        bot.execute("GameCog", "setup_game")
        return jsonify({'message': 'Channels created successfully'}), 200


@app.route('/api/clean', methods=['POST'])
async def clean():
    bot.clean_game()
    return jsonify({'message': 'Active game cleaned successfully'}), 200

