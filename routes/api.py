from flask import jsonify, request, redirect, url_for
from flask_discord import DiscordOAuth2Session, requires_authorization, Unauthorized
from shared import app,  bot, AUTHORIZED_USERS, bot_running, discord_oauth
from os import listdir
import json
import asyncio
import os


# @app.route("/start_bot", methods=["POST"])
# async def start_bot():
#     global bot_running  # Declare bot_running as global
#     if await discord_oauth.authorized:
#         user = await discord_oauth.fetch_user()
#         print(user)
#         print(user.id)
#         print(AUTHORIZED_USERS)
#         if str(user.id) in AUTHORIZED_USERS:
#             asyncio.create_task(bot.start(token=app.config["DISCORD_BOT_TOKEN"]))
#             bot_running = True
#             return jsonify({"message": "Bot started successfully", "status": "success"}), 200
#         else:
#             print(user.id)
#             return jsonify({"message": "You are not authorized to start the bot.", "status": "unauthorized"}), 403
#     else:
#         return jsonify({"message": "You are not logged in.", "status": "unauthorized"}), 401


# @app.route("/stop_bot", methods=["POST"])
# async def stop_bot():
#     global bot_running  # Declare bot_running as global
#     if await discord_oauth.authorized:
#         user = await discord_oauth.fetch_user()
#         if str(user.id) in AUTHORIZED_USERS:
#             await bot.close()
#             bot_running = False
#             return jsonify({"message": "Bot stopped successfully", "status": "success"}), 200
#         else:
#             return jsonify({"message": "You are not authorized to stop the bot.", "status": "unauthorized"}), 403
#     else:
#         return jsonify({"message": "You are not logged in.", "status": "unauthorized"}), 401

# @app.route("/status", methods=["GET"])
# async def status():
#     return jsonify({"status": bot_running})



# @app.route('/getGameData', methods=['GET'])
# async def get_game_data():
#     # Assuming your game data is stored in a file called 'game_data.json'
#     with open('game_data.json') as f:
#         game_data = json.load(f)
#     return jsonify(game_data)


# @app.route('/awardPoints', methods=['POST'])
# async def award_points():
#     team = request.form['team']
#     points = request.form['points']

@app.route("/login/")
def login():
    return discord_oauth.create_session()


@app.route("/callback/")
def callback():
    code = request.args.get("code")
    discord_oauth.callback()
    return redirect(url_for("gamepanel"))


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


@app.route('/api/gamedata', methods=['GET'])
@requires_authorization
def get_game_data():
    file_name = request.args.get("file_name")
    with open(f'./data/{file_name}.json') as f:
        game_data = json.load(f)
    return jsonify(game_data)


    

@app.route('/api/startgame', methods=['POST'])
def start_game():
    game_name = request.form['name']
    files = listdir("./data")
    for file in files:
        if file.startswith(game_name):
            with open(f'./data/{file}') as f:
                game_data = json.load(f)
            

@app.route('/api/stopgame', methods=['POST'])
def stop_game():
    pass



@app.route('/api/botstatus', methods=['GET'])
def bot_status():
    return jsonify({"status": bot_running})


@app.route('/api/startbot', methods=['POST'])
def start_bot():
    global bot_running
    bot_running = True
    bot.run()
    return jsonify({"message": "Bot started successfully", "status": "success"}), 200

@app.route('/api/stopbot', methods=['POST'])
async def stop_bot():
    global bot_running 
    bot_running = False
    await bot.stop()
    return jsonify({"message": "Bot stopped successfully", "status": "success"}), 200


@app.route('/api/getavailablegames', methods=['GET'])
def get_available_games():
    try:
        files = listdir(os.path.join(app.config['UPLOAD_FOLDER']))
        print(files)
        games = []
        for file in files:
            if file.endswith(".json"):
                with open(f'./data/{file}') as f:
                    game_data = json.load(f)
                    game = {
                        "name": game_data["game"]["name"],
                        "description": game_data["game"]["description"],
                        "file_name": file,
                        "uuid": game_data["game"]["uuid"]
                    }
                    games.append(game)
        return jsonify(games), 200
    except Exception as e:
        print(e)
        return jsonify({'error': str(e)}), 400
    


def is_valid_game_json(data):
    # Check for required top-level keys
    if "game" not in data or "questions" not in data:
        return False
    
    # Validate 'game' structure
    game_info = data["game"]
    required_game_keys = {"name", "description", "players", "categories", "per_category", "teams", "uuid"}
    if not all(key in game_info for key in required_game_keys):
        return False

    # Validate 'questions' structure
    for category, questions in data["questions"].items():
        for question in questions:
            required_question_keys = {"question", "answer", "value", "uuid"}
            if not all(key in question for key in required_question_keys):
                return False

    return True

@app.route('/api/uploadgame', methods=['POST'])
def upload_game():
    # Assuming the file is received as part of a form
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    
    try:
        game_data = json.load(file)
        if not is_valid_game_json(game_data):
            return jsonify({'error': 'Invalid game JSON format'}), 400
        
        with open(app.config['UPLOAD_FOLDER'] + file.filename, 'w') as f:
            json.dump(game_data, f)

        return jsonify({'message': 'File uploaded and validated successfully'}), 200

    except json.JSONDecodeError:
        return jsonify({'error': 'Invalid JSON'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 400
    

@app.route('/api/getgameinfo', methods=['GET'])
def get_game_info():
    uuid = request.args.get("uuid")
    files = listdir(app.config['UPLOAD_FOLDER'])
    for file in files:
        if file.endswith(".json"):
            with open(f'./data/{file}') as f:
                game_data = json.load(f)
                if game_data["game"]["uuid"] == uuid:
                    return jsonify(game_data["game"])
    return jsonify({'error': 'Game not found'}), 404

@app.route('/api/getgamequestions', methods=['GET'])
def get_game_questions():
    uuid = request.args.get("uuid")
    files = listdir(app.config['UPLOAD_FOLDER'])
    for file in files:
        if file.endswith(".json"):
            with open(f'./data/{file}') as f:
                game_data = json.load(f)
                if game_data["game"]["uuid"] == uuid:
                    return jsonify(game_data["questions"])
    return jsonify({'error': 'Game not found'}), 404


@app.route('/api/setactivegame', methods=['POST'])
async def set_active_game():
    uuid = request.args.get("uuid")
    files = listdir(app.config['UPLOAD_FOLDER'])
    for file in files:
        if file.endswith(".json"):
            with open(f'./data/{file}') as f:
                game_data = json.load(f)
                if game_data["game"]["uuid"] == uuid:
                    print("Bot" + str(bot))
                    bot.set_active_game(game_data)
                    
                    return jsonify({'message': 'Active game set successfully'}), 200
    return jsonify({'error': 'Game not found'}), 404

