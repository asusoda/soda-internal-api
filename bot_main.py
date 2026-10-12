"""Run the Discord bot as its own process.

The API used to start the bot in a thread inside the web process. Under gunicorn that would start
one bot per worker, and every scheduled post would go out once per worker. In production the bot
runs here instead, as the `bot` compose service, from the same image as the API.
"""

import asyncio
import contextlib
import signal
import sys

import discord

from core.config import config
from core.log import get_logger, init_sentry
from modules.bot.factory import create_bot
from modules.dashboard import errors as error_alerts

logger = get_logger(__name__)


def main() -> int:
    init_sentry(config.SENTRY, "bot")
    error_alerts.setup("bot")
    if not config.BOT_TOKEN:
        logger.error("BOT_TOKEN is not set; the bot cannot start")
        return 1
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    bot = create_bot(loop)
    # As PID 1 in its container, the process ignores SIGTERM with no handler, and `podman stop` waits 10s to kill it.
    # Windows has no add_signal_handler.
    # The loop keeps only a weak reference to a task, so close_tasks holds it. A second SIGTERM does nothing.
    close_tasks: set[asyncio.Task] = set()

    def on_sigterm() -> None:
        if not close_tasks:
            close_tasks.add(loop.create_task(bot.close()))

    with contextlib.suppress(NotImplementedError):
        loop.add_signal_handler(signal.SIGTERM, on_sigterm)
    try:
        logger.info("Starting Discord bot process")
        loop.run_until_complete(bot.start(config.BOT_TOKEN))
    except discord.errors.LoginFailure:
        logger.error("Discord rejected BOT_TOKEN")
        return 1
    except KeyboardInterrupt:
        logger.info("Bot process interrupted")
    finally:
        if not bot.is_closed():
            loop.run_until_complete(bot.close())
        loop.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
