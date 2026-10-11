import json

from flask import Blueprint, current_app, jsonify, request

from core.db import db_connect as db
from core.log import get_logger
from modules.auth.access import any_officer_denial, current_principal, is_superadmin, officer_guild_ids

from . import service

logger = get_logger("games.api")

game_blueprint = Blueprint("game", __name__, template_folder=None, static_folder=None)

logger.info("Bot API module initialized (game_blueprint)")


@game_blueprint.before_request
def require_officer():
    """The game controls post to Discord and award points, so only officers may call them."""
    denial = any_officer_denial()
    if denial:
        return jsonify({"message": denial[0]}), denial[1]
    if not _games_on():
        return jsonify({"message": "The games feature is off for your organization"}), 404
    return None


def _games_on() -> bool:
    """Whether the caller is an officer of an org with the games module on. The superadmin always is."""
    principal = current_principal()
    if principal is None or not principal.discord_id or is_superadmin(principal.discord_id):
        return True
    guilds = officer_guild_ids(principal.discord_id)
    if not guilds:
        return True
    session = db.SessionLocal()
    try:
        return service.enabled_for_guilds(session, guilds)
    finally:
        session.close()


@game_blueprint.route("/", methods=["GET"])
def game_index():
    logger.debug("Game API index endpoint called")
    return jsonify({"message": "game api for auth_bot"}), 200


@game_blueprint.route("/getavailablegames", methods=["GET"])
def get_available_games():
    logger.info("Getting available games")
    try:
        games = db.get_all_games()  # type: ignore[attr-defined]
        game_data = []
        for game in games:
            game_ = game["game"]
            game_data.append(
                {
                    "name": game_["name"],
                    "description": game_["description"],
                    "uuid": game_["uuid"],
                }
            )
        logger.debug(f"Retrieved {len(game_data)} games")
        return jsonify(game_data), 200
    except Exception as e:
        logger.error(f"Error retrieving available games: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 400


@game_blueprint.route("/gamedata", methods=["GET"])
def get_game_data():
    file_name = request.args.get("file_name")
    logger.info(f"Getting game data for file: {file_name}")
    try:
        return jsonify(service.read_game_file(file_name))
    except Exception as e:
        logger.error(f"Error retrieving game data: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 400


@game_blueprint.route("/startgame", methods=["POST"])
def start_game():
    game_name = request.form["name"]
    logger.info(f"Starting game: {game_name}")
    try:
        db.get_game(game_name)  # type: ignore[attr-defined]
        return jsonify({"message": f"Game {game_name} started", "status": "success"}), 200
    except Exception as e:
        logger.error(f"Error starting game {game_name}: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 400


@game_blueprint.route("/stopgame", methods=["POST"])
def stop_game():
    logger.info("Stopping current game")
    try:
        return jsonify({"message": "Game stopped", "status": "success"}), 200
    except Exception as e:
        logger.error(f"Error stopping game: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 400


@game_blueprint.route("/uploadgame", methods=["POST"])
def upload_game():
    if "file" not in request.files:
        logger.warning("No file part in request")
        return jsonify({"error": "No file part"}), 400

    file = request.files["file"]
    if file.filename == "":
        logger.warning("No selected file")
        return jsonify({"error": "No selected file"}), 400

    logger.info(f"Uploading game file: {file.filename}")
    try:
        # Read the file content first since FileStorage is not directly compatible with json.load
        file_content = file.read()
        game_data = json.loads(file_content.decode("utf-8"))
        if not service.is_valid_game(game_data):
            logger.warning("Invalid game JSON format")
            return jsonify({"error": "Invalid game JSON format"}), 400

        db.add_or_update_game(game_data)  # type: ignore[attr-defined]
        logger.info(f"Game {game_data['game']['name']} uploaded successfully")
        return jsonify({"message": "File uploaded and validated successfully"}), 200

    except json.JSONDecodeError:
        logger.error("Invalid JSON in uploaded file", exc_info=True)
        return jsonify({"error": "Invalid JSON"}), 400
    except Exception as e:
        logger.error(f"Error uploading game: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 400


@game_blueprint.route("/getgame", methods=["GET"])
def get_game():
    name = request.args.get("name")
    logger.info(f"Getting game data for: {name}")
    try:
        games = db.get_all_games()  # type: ignore[attr-defined]
        data = {}
        for game_doc in games:  # renamed to avoid conflict with blueprint name
            if game_doc["game"]["name"] == name:
                data["info"] = game_doc["game"]
                data["questions"] = game_doc["questions"]
                return jsonify(data), 200
        logger.warning(f"Game not found: {name}")
        return jsonify({"error": "Game not found"}), 404
    except Exception as e:
        logger.error(f"Error retrieving game {name}: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 400


@game_blueprint.route("/setactivegame", methods=["POST"])
async def set_active_game():
    bot = current_app.auth_bot if hasattr(current_app, "auth_bot") else None
    if not bot or not bot.is_ready():  # type: ignore[attr-defined]
        logger.warning("Auth bot not ready or not available for /setactivegame")
        return jsonify({"error": "Auth bot is not available or not ready."}), 503

    name = request.args.get("name")
    date = request.args.get("date")
    time = request.args.get("time")
    logger.info(f"Setting active game: {name} for date: {date}, time: {time}")

    try:
        games = db.get_all_games()  # type: ignore[attr-defined]
        game_to_set = None
        for g in games:
            if g["game"]["name"] == name:
                game_to_set = {"game": g["game"], "questions": g["questions"]}
                break

        if game_to_set:
            cog = bot.get_cog("GameCog")  # type: ignore[attr-defined]
            if cog:
                cog.set_game(game_to_set, date, time)
                logger.info(f"Active game set successfully: {name}")
                return jsonify({"message": "Active game set successfully"}), 200
            else:
                logger.error("GameCog not found on auth_bot")
                return jsonify({"error": "GameCog not found"}), 500
        else:
            logger.warning(f"Game not found for setactivegame: {name}")
            return jsonify({"error": "Game not found"}), 404
    except Exception as e:
        logger.error(f"Error setting active game {name}: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 400


@game_blueprint.route("/getactivegame", methods=["GET"])
async def get_active_game():
    bot = current_app.auth_bot if hasattr(current_app, "auth_bot") else None
    if not bot or not bot.is_ready():  # type: ignore[attr-defined]
        logger.warning("Auth bot not ready or not available for /getactivegame")
        return jsonify({"error": "Auth bot is not available or not ready."}), 503

    logger.info("Getting active game state from auth_bot")
    try:
        cog = bot.get_cog("GameCog")  # type: ignore[attr-defined]
        if cog:
            game_data = cog.get_game()
            if game_data not in [None, ""]:
                return jsonify(game_data), 200
            else:
                logger.info("No active game set in GameCog")
                return jsonify({"error": "No active game set"}), 404
        else:
            logger.error("GameCog not found on auth_bot")
            return jsonify({"error": "GameCog not found"}), 500
    except Exception as e:
        logger.error(f"Error retrieving active game: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 400


@game_blueprint.route("/cleanactivegame", methods=["POST"])
async def clean_active_game():
    bot = current_app.auth_bot if hasattr(current_app, "auth_bot") else None
    if not bot or not bot.is_ready():  # type: ignore[attr-defined]
        logger.warning("Auth bot not ready or not available for /cleanactivegame")
        return jsonify({"error": "Auth bot is not available or not ready."}), 503

    logger.info("Cleaning active game via auth_bot")
    try:
        # GameCog.clear_game, else a clean_game method on the bot
        cog = bot.get_cog("GameCog")  # type: ignore[attr-defined]
        if cog and hasattr(cog, "clear_game"):
            await cog.clear_game()
            logger.info("Active game cleaned successfully via GameCog")
            return jsonify({"message": "Active game cleaned successfully"}), 200
        elif hasattr(bot, "clean_game"):
            await bot.clean_game()  # type: ignore[attr-defined]
            logger.info("Active game cleaned successfully via bot.clean_game()")
            return jsonify({"message": "Active game cleaned successfully"}), 200
        else:
            logger.error("clean_game method or GameCog not found on auth_bot")
            return jsonify({"error": "Functionality not found"}), 500
    except Exception as e:
        logger.error(f"Error cleaning active game: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 400


@game_blueprint.route("/getactivegamestate", methods=["GET"])
def get_active_game_state():
    bot = current_app.auth_bot if hasattr(current_app, "auth_bot") else None
    if not bot or not bot.is_ready():  # type: ignore[attr-defined]
        logger.warning("Auth bot not ready or not available for /getactivegamestate")
        return jsonify({"error": "Auth bot is not available or not ready."}), 503

    logger.info("Getting active game state from auth_bot")
    try:
        # The state of GameCog.game, else of bot.active_game
        cog = bot.get_cog("GameCog")  # type: ignore[attr-defined]
        if cog and hasattr(cog, "game") and cog.game is not None and hasattr(cog.game, "get_state"):
            state = cog.game.get_state()
            return jsonify(state), 200
        elif hasattr(bot, "active_game") and bot.active_game not in [None, ""]:
            return jsonify(bot.active_game.get_state()), 200  # type: ignore[attr-defined]
        else:
            logger.info("No active game or state found in GameCog or bot")
            return jsonify({"error": "No active game set or state unavailable"}), 404
    except Exception as e:
        logger.error(f"Error retrieving active game state: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 400


@game_blueprint.route("/startactivegame", methods=["POST"])
async def start_active_game():
    bot = current_app.auth_bot if hasattr(current_app, "auth_bot") else None
    if not bot or not bot.is_ready():  # type: ignore[attr-defined]
        logger.warning("Auth bot not ready or not available for /startactivegame")
        return jsonify({"error": "Auth bot is not available or not ready."}), 503

    logger.info("Starting active game via auth_bot")
    try:
        cog = bot.get_cog("GameCog")  # type: ignore[attr-defined]
        if cog:
            await cog.start_game()
            logger.info("Active game started successfully via GameCog")
            return jsonify({"message": "Active game started successfully"}), 200
        else:
            logger.error("GameCog not found on auth_bot")
            return jsonify({"error": "GameCog not found"}), 500
    except Exception as e:
        logger.error(f"Error starting active game: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 400


@game_blueprint.route("/endactivegame", methods=["POST"])
async def end_active_game():  # Changed to async to align with potential async cog methods
    bot = current_app.auth_bot if hasattr(current_app, "auth_bot") else None
    if not bot or not bot.is_ready():  # type: ignore[attr-defined]
        logger.warning("Auth bot not ready or not available for /endactivegame")
        return jsonify({"error": "Auth bot is not available or not ready."}), 503

    logger.info("Ending active game via auth_bot")
    try:
        cog = bot.get_cog("GameCog")  # type: ignore[attr-defined]
        if cog and hasattr(cog, "end_game"):  # end_game is in GameCog.py
            await cog.end_game()
            logger.info("Active game ended successfully via GameCog")
            return jsonify({"message": "Active game ended successfully"}), 200
        else:
            logger.error("end_game method or GameCog not found on auth_bot")
            return jsonify({"error": "Functionality not found"}), 500
    except Exception as e:
        logger.error(f"Error ending active game: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 400


@game_blueprint.route("/revealquestion", methods=["POST"])
async def reveal_question():  # Changed to async
    bot = current_app.auth_bot if hasattr(current_app, "auth_bot") else None
    if not bot or not bot.is_ready():  # type: ignore[attr-defined]
        logger.warning("Auth bot not ready or not available for /revealquestion")
        return jsonify({"error": "Auth bot is not available or not ready."}), 503

    uuid = request.args.get("uuid")
    logger.info(f"Revealing question with UUID: {uuid} via auth_bot")
    try:
        cog = bot.get_cog("GameCog")  # type: ignore[attr-defined]
        if cog:
            await cog.show_question(uuid)  # show_question is async in GameCog
            logger.info(f"Question {uuid} revealed successfully via GameCog")
            return jsonify({"message": "Question revealed successfully"}), 200
        else:
            logger.error("GameCog not found on auth_bot")
            return jsonify({"error": "GameCog not found"}), 500
    except Exception as e:
        logger.error(f"Error revealing question {uuid}: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 400


@game_blueprint.route("/revealanswer", methods=["POST"])
async def reveal_answer():
    bot = current_app.auth_bot if hasattr(current_app, "auth_bot") else None
    if not bot or not bot.is_ready():  # type: ignore[attr-defined]
        logger.warning("Auth bot not ready or not available for /revealanswer")
        return jsonify({"error": "Auth bot is not available or not ready."}), 503

    uuid = request.args.get("uuid")
    logger.info(f"Revealing answer for question UUID: {uuid} via auth_bot")
    try:
        cog = bot.get_cog("GameCog")  # type: ignore[attr-defined]
        if cog:
            await cog.show_answer(uuid)
            logger.info(f"Answer for question {uuid} revealed successfully via GameCog")
            return jsonify({"message": "Answer revealed successfully"}), 200
        else:
            logger.error("GameCog not found on auth_bot")
            return jsonify({"error": "GameCog not found"}), 500
    except Exception as e:
        logger.error(f"Error revealing answer for question {uuid}: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 400


@game_blueprint.route("/awardpoints", methods=["POST"])
async def award_points():
    bot = current_app.auth_bot if hasattr(current_app, "auth_bot") else None
    if not bot or not bot.is_ready():  # type: ignore[attr-defined]
        logger.warning("Auth bot not ready or not available for /awardpoints")
        return jsonify({"error": "Auth bot is not available or not ready."}), 503

    team = request.args.get("team")
    points = request.args.get("points")
    logger.info(f"Awarding {points} points to team: {team} via auth_bot")
    try:
        cog = bot.get_cog("GameCog")  # type: ignore[attr-defined]
        if cog:
            await cog.award_points(team, points)  # award_points is async in GameCog
            logger.info(f"Awarded {points} to team {team} successfully via GameCog")
            return jsonify({"message": "Points awarded successfully"}), 200
        else:
            logger.error("GameCog not found on auth_bot")
            return jsonify({"error": "GameCog not found"}), 500
    except Exception as e:
        logger.error(f"Error awarding points to team {team}: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 400
