from flask import jsonify, request, redirect, url_for
from flask_discord import DiscordOAuth2Session, requires_authorization, Unauthorized
from shared import app,  bot, AUTHORIZED_USERS, bot_running, discord_oauth
from os import listdir
import json
import asyncio
import os


@app.errorhandler(Unauthorized)
def redirect_unauthorized(e):
    return redirect(url_for("login"))

@app.route("/logout/")
def logout():
    discord_oauth.revoke()
    return redirect(url_for("index"))

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


@app.route('/api/getactivegame', methods=['GET'])
def get_active_game():
    if bot.active_game not in [None, ""]:
        print(bot.active_game.to_json())
        return jsonify(bot.active_game.to_json()), 200
    else:
        return jsonify({'error': 'No active game set'}), 404
    

@app.route('/api/getactivegamedata', methods=['GET'])
def get_active_game_data():
    if bot.active_game not in [None, ""]:
        return jsonify(bot.active_game.to_json()), 200
    else:
        return jsonify({'error': 'No active game set'}), 404

@app.route('/api/awardpoints', methods=['POST'])
def award_points():
    team = request.args.get("team")
    points = request.args.get("points")
    bot.award_points(team, points)
    return jsonify({'message': 'Points awarded successfully'}), 200

@app.route('/api/cleanactivegame', methods=['POST'])
def clean_active_game():
    bot.clean_game()
    return jsonify({'message': 'Active game cleaned successfully'}), 200

@app.route('/api/getactivegamestate', methods=['GET'])
def get_active_game_state():
    if bot.active_game not in [None, ""]:
        return jsonify(bot.active_game.get_state()), 200
    else:
        return jsonify({'error': 'No active game set'}), 404
    
@app.route('/api/startactivegame', methods=['POST'])
def start_active_game():
    bot.start_game()
    return jsonify({'message': 'Active game started successfully'}), 200

@app.route('/api/endactivegame', methods=['POST'])
def end_active_game():
    bot.end_game()
    return jsonify({'message': 'Active game ended successfully'}), 200
