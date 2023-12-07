import discord
from discord.ext import commands
import logging
import os
import json
import random
import uuid
import inspect
import asyncio
import threading
from cogs.HelperCog import HelperCog
from cogs.GameCog import GameCog
from utils.Jeopardy import JeopardyGame



import discord
import threading
import asyncio
import nest_asyncio
import inspect
from discord.ext import commands

nest_asyncio.apply()
class BotFork(commands.Bot):
    """
    An extended version of the discord.ext.commands.Bot class. This class 
    supports additional functionality like managing cogs and controlling 
    the bot's online status.

    Attributes:
        setup (bool): Indicates if the bot has been set up.
        active_game (Any): Stores the current active game instance.
        token (str): Discord bot token.
    """

    def __init__(self, *args, **kwargs):
        """
        Initializes the BotFork instance.

        Args:
            *args: Variable length argument list.
            **kwargs: Arbitrary keyword arguments.
        """
        self.setup = False
        self.active_game = None
        super().__init__(*args, **kwargs, guild_ids=[])
        super().add_cog(HelperCog(self))
        super().add_cog(GameCog(self))

    def set_token(self, token):
        """
        Sets the bot token.

        Args:
            token (str): Discord bot token.
        """
        self.token = token

    async def on_ready(self):
        """
        Asynchronous event handler for when the bot is ready.
        """
        for guild in self.guilds:
            print(f'{self.user} is connected to the following guild:\n'
                  f'{guild.name}(id: {guild.id})')

    async def run(self):
        """
        Starts the bot. If the bot is already set up, changes the bot's presence to online.
        """
        if not self.setup:
            self.setup = True
            threading.Thread(target=super().run, args=(self.token,)).start()
        else:
           await self.change_presence(status=discord.Status.online)

    async def stop(self):
        """
        Asynchronous method to stop the bot, changing its presence to offline.
        """
        await self.change_presence(status=discord.Status.offline)


    def execute(self, cog_name, command, *args, **kwargs):
        """Executes a command in the specified cog synchronously."""
        cog = self.get_cog(cog_name)
        if cog is None:
            raise ValueError(f"Cog {cog_name} not found")

        method = getattr(cog, command, None)
        if method is None:
            raise ValueError(f"Command {command} not found in cog {cog_name}")

        if inspect.iscoroutinefunction(method):
            # If the method is a coroutine, run it in the event loop
            return self.loop.create_task(method(*args, **kwargs))
        else:
            # If the method is not a coroutine, just call it directly
            return method(*args, **kwargs)
    

    def get_guilds(self):
        """
        Retrieves a list of guilds the bot is a member of.

        Returns:
            list: A list of guilds.
        """
        return super().guilds
  
    # async def setup_game(self):
    #     """
    #     Sets up a game instance.

    #     Args:
    #         game (dict): The game data.
    #     """
    #     game = self.active_game
    #     guild = self.guilds[0]
    #     category = await guild.create_category("Jeopardy")
    #     game_category = category
    #     voice_channels = [] 
    #     for team in game.teams:
    #         role = await guild.create_role(name=team.get_name())
    #         self.roles.append(role)

    #         overwrites = {
    #             guild.default_role: discord.PermissionOverwrite(view_channel=True, connect=False, speak=False),
    #             role: discord.PermissionOverwrite(view_channel=True, connect=True, speak=True)
    #         }

    #         channel = await guild.create_voice_channel(team.get_name(), category=category, overwrites=overwrites)
    #         voice_channels.append(channel)

    #     announcement_channel = await guild.create_text_channel("announcements", category=category)
    #     scoreboard_channel = await guild.create_text_channel("scoreboard", category=category)

    #     game_cog = self.get_cog("GameCog")
    #     return await game_cog.setup_game(self.announcement_channel, self.game_category, self.scoreboard_channel, self.roles, self.voice_channels)