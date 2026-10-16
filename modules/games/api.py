import asyncio
import json
from collections.abc import Coroutine
from typing import Any

import discord
from flask import Blueprint, current_app, jsonify, request

from core.db import db_connect as db
from core.log import get_logger
from modules.auth.access import any_officer_denial, current_principal, is_superadmin, officer_guild_ids
from modules.bot.bot import BotFork

from . import service
from .cog import GameCog

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


def _ready_bot() -> BotFork | None:
    """The bot of this process when it runs here and is ready, else None."""
    bot = getattr(current_app, "auth_bot", None)
    if isinstance(bot, BotFork) and bot.is_ready():
        return bot
    return None


async def _on_bot(bot: BotFork, coro: Coroutine[Any, Any, Any]) -> Any:
    """Run coro on the bot's event loop and wait for its result. Discord objects work only on that loop."""
    try:
        loop = bot.loop
    except AttributeError:
        loop = None
    if loop is None or loop is asyncio.get_running_loop() or not loop.is_running():
        return await coro
    return await asyncio.wrap_future(asyncio.run_coroutine_threadsafe(coro, loop))


def _game_guild(bot: BotFork) -> tuple[discord.Guild | None, str | None]:
    """The Discord server of the org that runs the game, or None and the reason.

    It is the guild_id argument, or else the one server of the bot where the caller is an officer and games is on.
    """
    principal = current_principal()
    allowed = None
    if principal is not None and principal.discord_id and not is_superadmin(principal.discord_id):
        allowed = officer_guild_ids(principal.discord_id) or frozenset()
    requested = request.args.get("guild_id")
    guilds = [
        guild
        for guild in bot.guilds
        if (allowed is None or str(guild.id) in allowed) and (requested is None or str(guild.id) == requested)
    ]
    session = db.SessionLocal()
    try:
        guilds = [guild for guild in guilds if service.enabled_for_guilds(session, [guild.id])]
    finally:
        session.close()
    if len(guilds) == 1:
        return guilds[0], None
    if not guilds:
        return None, "The bot is not in a server of an org where you are an officer and games is on"
    return None, "You are an officer in more than one server of the bot. Set guild_id to the server of the game"


def _game_cog(bot: BotFork) -> GameCog | None:
    """The GameCog of the bot, or None when the bot does not have it."""
    cog = bot.get_cog("GameCog")
    return cog if isinstance(cog, GameCog) else None


@game_blueprint.route("/", methods=["GET"])
def game_index():
    logger.debug("Game API index endpoint called")
    return jsonify({"message": "game api for auth_bot"}), 200


@game_blueprint.route("/getavailablegames", methods=["GET"])
def get_available_games():
    logger.info("Getting available games")
    session = db.SessionLocal()
    try:
        games = service.list_games(session)
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
    finally:
        session.close()


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
    session = db.SessionLocal()
    try:
        service.get_game(session, game_name)
        return jsonify({"message": f"Game {game_name} started", "status": "success"}), 200
    except Exception as e:
        logger.error(f"Error starting game {game_name}: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 400
    finally:
        session.close()


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
    session = db.SessionLocal()
    try:
        # Read the file content first since FileStorage is not directly compatible with json.load
        file_content = file.read()
        game_data = json.loads(file_content.decode("utf-8"))
        if not service.is_valid_game(game_data):
            logger.warning("Invalid game JSON format")
            return jsonify({"error": "Invalid game JSON format"}), 400

        service.save_game(session, game_data)
        logger.info(f"Game {game_data['game']['name']} uploaded successfully")
        return jsonify({"message": "File uploaded and validated successfully"}), 200

    except json.JSONDecodeError:
        logger.error("Invalid JSON in uploaded file", exc_info=True)
        return jsonify({"error": "Invalid JSON"}), 400
    except Exception as e:
        logger.error(f"Error uploading game: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 400
    finally:
        session.close()


@game_blueprint.route("/getgame", methods=["GET"])
def get_game():
    name = request.args.get("name")
    logger.info(f"Getting game data for: {name}")
    if not name:
        logger.warning("Game not found: no name")
        return jsonify({"error": "Game not found"}), 404
    session = db.SessionLocal()
    try:
        game_doc = service.get_game(session, name)
        return jsonify({"info": game_doc["game"], "questions": game_doc["questions"]}), 200
    except service.GameError as e:
        logger.warning(f"Game not found: {name}")
        return jsonify({"error": e.message}), e.status
    except Exception as e:
        logger.error(f"Error retrieving game {name}: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 400
    finally:
        session.close()


@game_blueprint.route("/setactivegame", methods=["POST"])
async def set_active_game():
    bot = _ready_bot()
    if bot is None:
        logger.warning("Auth bot not ready or not available for /setactivegame")
        return jsonify({"error": "Auth bot is not available or not ready."}), 503

    name = request.args.get("name")
    date = request.args.get("date")
    time = request.args.get("time")
    logger.info(f"Setting active game: {name} for date: {date}, time: {time}")

    session = db.SessionLocal()
    try:
        game_to_set = None
        for g in service.list_games(session):
            if g["game"]["name"] == name:
                game_to_set = {"game": g["game"], "questions": g["questions"]}
                break

        if game_to_set:
            cog = _game_cog(bot)
            if cog:
                if cog.is_setup():
                    return jsonify({"error": "A game is set up in Discord. Clean it with /cleanactivegame first"}), 409
                guild, reason = _game_guild(bot)
                if guild is None:
                    return jsonify({"error": reason}), 400
                cog.set_game(game_to_set, date, time)
                await _on_bot(bot, cog.setup_game(guild))
                logger.info(f"Active game set successfully: {name} guild={guild.id}")
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
    finally:
        session.close()


@game_blueprint.route("/getactivegame", methods=["GET"])
async def get_active_game():
    bot = _ready_bot()
    if bot is None:
        logger.warning("Auth bot not ready or not available for /getactivegame")
        return jsonify({"error": "Auth bot is not available or not ready."}), 503

    logger.info("Getting active game state from auth_bot")
    try:
        cog = _game_cog(bot)
        if cog:
            game_data = cog.get_game()
            if game_data is not None:
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
    bot = _ready_bot()
    if bot is None:
        logger.warning("Auth bot not ready or not available for /cleanactivegame")
        return jsonify({"error": "Auth bot is not available or not ready."}), 503

    logger.info("Cleaning active game via auth_bot")
    try:
        cog = _game_cog(bot)
        if cog:
            await _on_bot(bot, cog.clear_game())
            logger.info("Active game cleaned successfully via GameCog")
            return jsonify({"message": "Active game cleaned successfully"}), 200
        else:
            logger.error("GameCog not found on auth_bot")
            return jsonify({"error": "Functionality not found"}), 500
    except Exception as e:
        logger.error(f"Error cleaning active game: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 400


@game_blueprint.route("/getactivegamestate", methods=["GET"])
def get_active_game_state():
    bot = _ready_bot()
    if bot is None:
        logger.warning("Auth bot not ready or not available for /getactivegamestate")
        return jsonify({"error": "Auth bot is not available or not ready."}), 503

    logger.info("Getting active game state from auth_bot")
    try:
        # The state is the JSON of GameCog.game: teams, scores, questions and the announced and started flags
        cog = _game_cog(bot)
        if cog and cog.game is not None:
            return jsonify(cog.game.to_json()), 200
        else:
            logger.info("No active game or state found in GameCog")
            return jsonify({"error": "No active game set or state unavailable"}), 404
    except Exception as e:
        logger.error(f"Error retrieving active game state: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 400


@game_blueprint.route("/startactivegame", methods=["POST"])
async def start_active_game():
    bot = _ready_bot()
    if bot is None:
        logger.warning("Auth bot not ready or not available for /startactivegame")
        return jsonify({"error": "Auth bot is not available or not ready."}), 503

    logger.info("Starting active game via auth_bot")
    try:
        cog = _game_cog(bot)
        if cog:
            if not await _on_bot(bot, cog.start_game()):
                return jsonify({"error": "No active game is set up"}), 400
            logger.info("Active game started successfully via GameCog")
            return jsonify({"message": "Active game started successfully"}), 200
        else:
            logger.error("GameCog not found on auth_bot")
            return jsonify({"error": "GameCog not found"}), 500
    except Exception as e:
        logger.error(f"Error starting active game: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 400


@game_blueprint.route("/endactivegame", methods=["POST"])
async def end_active_game():
    bot = _ready_bot()
    if bot is None:
        logger.warning("Auth bot not ready or not available for /endactivegame")
        return jsonify({"error": "Auth bot is not available or not ready."}), 503

    logger.info("Ending active game via auth_bot")
    try:
        cog = _game_cog(bot)
        if cog:
            if not await _on_bot(bot, cog.end_game()):
                return jsonify({"error": "No active game is set up"}), 400
            logger.info("Active game ended successfully via GameCog")
            return jsonify({"message": "Active game ended successfully"}), 200
        else:
            logger.error("end_game method or GameCog not found on auth_bot")
            return jsonify({"error": "Functionality not found"}), 500
    except Exception as e:
        logger.error(f"Error ending active game: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 400


@game_blueprint.route("/revealquestion", methods=["POST"])
async def reveal_question():
    bot = _ready_bot()
    if bot is None:
        logger.warning("Auth bot not ready or not available for /revealquestion")
        return jsonify({"error": "Auth bot is not available or not ready."}), 503

    uuid = request.args.get("uuid")
    if not uuid:
        return jsonify({"error": "Missing uuid parameter"}), 400
    logger.info(f"Revealing question with UUID: {uuid} via auth_bot")
    try:
        cog = _game_cog(bot)
        if cog:
            if not await _on_bot(bot, cog.show_question(uuid)):
                return jsonify({"error": "No active game is set up or the question is not found"}), 400
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
    bot = _ready_bot()
    if bot is None:
        logger.warning("Auth bot not ready or not available for /revealanswer")
        return jsonify({"error": "Auth bot is not available or not ready."}), 503

    uuid = request.args.get("uuid")
    if not uuid:
        return jsonify({"error": "Missing uuid parameter"}), 400
    logger.info(f"Revealing answer for question UUID: {uuid} via auth_bot")
    try:
        cog = _game_cog(bot)
        if cog:
            if not await _on_bot(bot, cog.show_answer(uuid)):
                return jsonify({"error": "No active game is set up or the question is not found"}), 400
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
    bot = _ready_bot()
    if bot is None:
        logger.warning("Auth bot not ready or not available for /awardpoints")
        return jsonify({"error": "Auth bot is not available or not ready."}), 503

    team = request.args.get("team")
    points = request.args.get("points")
    if not team or not points:
        return jsonify({"error": "Missing team or points parameter"}), 400
    logger.info(f"Awarding {points} points to team: {team} via auth_bot")
    try:
        cog = _game_cog(bot)
        if cog:
            if not await _on_bot(bot, cog.award_points(team, int(points))):
                return jsonify({"error": "No active game is set or the team is not found"}), 400
            logger.info(f"Awarded {points} to team {team} successfully via GameCog")
            return jsonify({"message": "Points awarded successfully"}), 200
        else:
            logger.error("GameCog not found on auth_bot")
            return jsonify({"error": "GameCog not found"}), 500
    except Exception as e:
        logger.error(f"Error awarding points to team {team}: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 400
