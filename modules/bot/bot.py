import asyncio
import inspect

import nest_asyncio
from discord.ext import commands

from core.log import get_logger

logger = get_logger("modules.bot.discord_modules.bot")


class BotFork(commands.Bot):
    """The Discord bot. Holds the active game and runs cog commands for the API."""

    def __init__(self, *args, **kwargs):
        self.active_game = None
        super().__init__(*args, **kwargs, guild_ids=[])

    async def on_ready(self):
        logger.info(f"Logged in as {self.user} (ID: {self.user.id if self.user else None})")

    def execute(self, cog_name, command, *args, priority="NORMAL", **kwargs):
        """Run a command of a cog. A coroutine runs now with priority NOW, else it goes on the bot loop."""
        cog = self.get_cog(cog_name)
        if cog is None:
            raise ValueError(f"Cog {cog_name} not found")

        method = getattr(cog, command, None)
        if method is None:
            raise ValueError(f"Command {command} not found in cog {cog_name}")

        if inspect.iscoroutinefunction(method):
            if priority == "NOW":
                nest_asyncio.apply()
                return asyncio.run(method(*args, **kwargs))
            return self.loop.create_task(method(*args, **kwargs))
        return method(*args, **kwargs)
