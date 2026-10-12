import asyncio
import os
import secrets
import subprocess  # nosec B404 - subprocess needed for git commit hash retrieval
import threading
from datetime import UTC, datetime

import discord
from flask import Flask, abort, jsonify, request
from flask_cors import CORS

from core import jobs
from core.config import config
from core.http.audit_hook import register_audit
from core.http.cached import register_cache_invalidation
from core.http.request_log import register_request_logging
from core.integrations.discord import DiscordDirectory
from core.log import get_logger, init_sentry
from modules.auth.tokens import token_manager
from modules.bot.bot import BotFork
from modules.bot.factory import create_bot
from modules.cli import register_cli
from modules.dashboard import errors as error_alerts
from modules.manifest import load_jobs, load_tools
from modules.registry import register_modules

logger = get_logger(__name__)

init_sentry(config.SENTRY, "api")
error_alerts.setup("api")


class App(Flask):
    """The Flask app with the Discord clients that routes read from current_app."""

    discord_directory: DiscordDirectory
    # Set only while the bot runs in this process (RUN_BOT_IN_API)
    auth_bot: BotFork


app = App("SoDA internal API", static_folder=None)
CORS(
    app,
    resources={
        r"/*": {
            "origins": [
                "http://localhost:3000",
                "http://127.0.0.1:3000",
                "http://localhost:5173",
                "http://127.0.0.1:5173",
                "https://thesoda.io",
                "https://admin.thesoda.io",
                # Extra origins for other deployments, comma-separated
                *[o.strip() for o in os.environ.get("CORS_EXTRA_ORIGINS", "").split(",") if o.strip()],
                config.DASHBOARD_URL,
            ],
            "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            "allow_headers": ["Content-Type", "Authorization", "X-Organization-ID", "X-Organization-Prefix"],
            "supports_credentials": True,
        }
    },
)

# Signs session cookies. Without FLASK_SECRET_KEY or SECRET_KEY, a random key is used and sessions end at restart.
app.secret_key = os.environ.get("FLASK_SECRET_KEY") or os.environ.get("SECRET_KEY")
if not app.secret_key:
    logger.warning("FLASK_SECRET_KEY is not set; using a random session key until restart")
    app.secret_key = secrets.token_hex(32)

# A bigger body gets 413 before Flask reads it
app.config["MAX_CONTENT_LENGTH"] = config.MAX_REQUEST_MB * 1_000_000

# Officer, member and guild lookups go to Discord's REST API, so the API does not need the bot
app.discord_directory = DiscordDirectory(config.BOT_TOKEN)


def get_git_commit_hash():
    """The commit hash: GIT_COMMIT_HASH from the Docker build, else git rev-parse HEAD."""
    commit_hash = os.environ.get("GIT_COMMIT_HASH")
    if commit_hash:
        return commit_hash

    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],  # nosec B603, B607 - hardcoded git command with no user input
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        )
        return result.stdout.strip()
    except Exception:
        return "unknown"


COMMIT_HASH = get_git_commit_hash()

STARTUP_TIME = datetime.now(UTC)


@app.route("/health")
def health():
    return jsonify(
        {
            "status": "healthy",
            "service": "soda-internal-api",
            "commit": COMMIT_HASH,
            "started_at": STARTUP_TIME.isoformat(),
        }
    ), 200


register_request_logging(app, token_manager)

register_audit(app, token_manager)

register_cache_invalidation(app)


@app.before_request
def refuse_disabled_routes():
    """A path that starts with a DISABLED_ROUTES prefix gets the 404 of an unknown route."""
    if config.DISABLED_ROUTES and request.path.startswith(config.DISABLED_ROUTES):
        abort(404)


register_modules(app)
load_tools()

# On Postgres the worker process (worker_main.py) runs the jobs; on SQLite a thread here runs the periodic jobs.
load_jobs()
jobs.start_inline_scheduler()

# `flask --app main org|jobs|config ...`
register_cli(app)


def run_auth_bot_in_thread():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    auth_bot_instance = create_bot(loop)
    app.auth_bot = auth_bot_instance
    try:
        logger.info("Starting auth bot thread...")
        auth_bot_token = config.BOT_TOKEN
        if not auth_bot_token:
            logger.error("BOT_TOKEN not found. Auth bot will not start.")
            return
        loop.run_until_complete(auth_bot_instance.start(auth_bot_token))
    except discord.errors.LoginFailure:
        logger.error("Login failed for auth bot. Check BOT_TOKEN.")
    except Exception as e:
        logger.error(f"Error in auth bot thread: {e}", exc_info=True)
    finally:
        if loop.is_running() and not auth_bot_instance.is_closed():
            logger.info("Closing auth bot...")
            loop.run_until_complete(auth_bot_instance.close())
        loop.close()
        logger.info("Auth bot thread finished and loop closed.")


def initialize_app():
    is_prod = os.environ.get("IS_PROD", "").lower() == "true"
    use_reloader = not is_prod

    # With the reloader, Werkzeug runs this file in a parent and a child process. Only the child
    # (WERKZEUG_RUN_MAIN) starts the bot, so each scheduled post goes out once.
    # In production RUN_BOT_IN_API is false and bot_main.py runs the bot.
    run_bot = os.environ.get("RUN_BOT_IN_API", "true").lower() == "true"
    if not run_bot:
        logger.info("RUN_BOT_IN_API is false; the bot runs in its own process")
    elif not use_reloader or os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        auth_thread = threading.Thread(target=run_auth_bot_in_thread, name="AuthBotThread")
        auth_thread.daemon = True
        auth_thread.start()
        logger.info("Auth bot thread initiated")
    else:
        logger.info("Reloader parent process; auth bot will start in the reloaded child process")

    # 0.0.0.0 so the port is reachable from outside the container
    app.run(host="0.0.0.0", port=8000, debug=not is_prod, use_reloader=use_reloader)  # nosec B104


if __name__ == "__main__":
    initialize_app()
