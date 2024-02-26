from shared import app,  bot, bot_running, discord_oauth, db
from flask import jsonify, request, redirect, url_for
from os import listdir
import json

@app.route('/api/getavailablegames', methods=['GET'])
def get_available_games():
    try:
        games = db.get_all_games()
        game_data = []
        for game in games:
            game_ = game["game"]
            game_data.append({
                "name": game_["name"],
                "description": game_["description"],
                "uuid": game_["uuid"]
            })

        return jsonify(game_data), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 400
    

@app.route('/api/gamedata', methods=['GET'])
def get_game_data():
    file_name = request.args.get("file_name")
    with open(f'./data/{file_name}.json') as f:
        game_data = json.load(f)
    return jsonify(game_data)


@app.route('/api/startgame', methods=['POST'])
def start_game():
    game_name = request.form['name']
    # files = listdir("./data")
    # for file in files:
    #     if file.startswith(game_name):
    #         with open(f'./data/{file}') as f:
    #             game_data = json.load(f)
    game_data = db.get_game(game_name)
            

@app.route('/api/stopgame', methods=['POST'])
def stop_game():
    pass


@app.route('/api/botstatus', methods=['GET'])
def bot_status():
    return jsonify({"status": bot_running})


@app.route('/api/startbot', methods=['POST'])
async def start_bot():
    global bot_running 
    bot_running = True
    await bot.run()
    return jsonify({"message": "Bot started successfully", "status": "success"}), 200

@app.route('/api/stopbot', methods=['POST'])
async def stop_bot():
    global bot_running 
    bot_running = False
    await bot.stop()
    return jsonify({"message": "Bot stopped successfully", "status": "success"}), 200



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
        db.add_or_update_game(game_data)
        return jsonify({'message': 'File uploaded and validated successfully'}), 200

    except json.JSONDecodeError:
        return jsonify({'error': 'Invalid JSON'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 400
    
@app.route('/api/getgame', methods=['GET'])
def get_game():
    name = request.args.get("name")
    games = db.get_all_games()
    data = {}
    for game in games:
        if game["game"]["name"] == name:
            data["info"] = game["game"]
            data["questions"] = game["questions"]
            return jsonify(data), 200
    return jsonify({'error': 'Game not found'}), 404


@app.route('/api/setactivegame', methods=['POST'])
async def set_active_game():
    name = request.args.get("name")
    date = request.args.get("date")
    time = request.args.get("time")
    if bot_running:
        games = db.get_all_games()
        data = {}
        for game in games:
            if game["game"]["name"] == name:
                data = {"game": game["game"], "questions": game["questions"]}
                # bot.execute("GameCog", "set_game", data, date, time)
                cog = bot.get_cog("GameCog")
                cog.set_game(data, date, time)
                return jsonify({'message': 'Active game set successfully'}), 200
    else:
        return jsonify({'error': 'Bot not running!!'}), 400


@app.route('/api/getactivegame', methods=['GET'])
async def get_active_game():
    if bot.execute("GameCog", "get_game") not in [None, ""]:
        # return jsonify(bot.execute("GameCog", "get_game")), 200
        cog = bot.get_cog("GameCog")
        return jsonify(cog.get_game()), 200
    else:
        return jsonify({'error': 'No active game set'}), 404


@app.route('/api/cleanactivegame', methods=['POST'])
async def clean_active_game():
    await bot.clean_game()
    return jsonify({'message': 'Active game cleaned successfully'}), 200

@app.route('/api/getactivegamestate', methods=['GET'])
def get_active_game_state():
    if bot.active_game not in [None, ""]:
        return jsonify(bot.active_game.get_state()), 200
    else:
        return jsonify({'error': 'No active game set'}), 404
    
@app.route('/api/startactivegame', methods=['POST'])
async def start_active_game():
    # bot.execute("GameCog", "start_game")
    cog = bot.get_cog("GameCog")
    await cog.start_game()

    return jsonify({'message': 'Active game started successfully'}), 200

@app.route('/api/endactivegame', methods=['POST'])
def end_active_game():
    bot.end_game()
    return jsonify({'message': 'Active game ended successfully'}), 200


@app.route('/api/revealquestion', methods=['POST'])
def reveal_question():
    uuid = request.args.get("uuid")
    # bot.execute("GameCog", "show_question", uuid)
    cog = bot.get_cog("GameCog")
    cog.show_question(uuid)
    return jsonify({'message': 'Question revealed successfully'}), 200


@app.route('/api/revealanswer', methods=['POST'])
async def reveal_answer():
    uuid = request.args.get("uuid")
    cog = bot.get_cog("GameCog")
    await cog.show_answer(uuid)
    return jsonify({'message': 'Answer revealed successfully'}), 200


@app.route('/api/awardpoints', methods=['POST'])
async def award_points():
    team = request.args.get("team")
    points = request.args.get("points")
    # await bot.execute("GameCog", "award_points", team, points)
    cog = bot.get_cog("GameCog")
    cog.award_points(team, points)
    return jsonify({'message': 'Points awarded successfully'}), 200


