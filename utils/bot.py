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
        self.command_queue = asyncio.Queue()
        self.processing_task = asyncio.create_task(self.process_command_queue())
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
        print("Bot is ready.")

    def run(self):
        """
        Starts the bot. If the bot is already set up, changes the bot's presence to online.
        """
        if not self.setup:
            self.setup = True
            threading.Thread(target=super().run, args=(self.token,)).start()
        else:
            asyncio.run(self.change_presence(status=discord.Status.online))

    async def stop(self):
        """
        Asynchronous method to stop the bot, changing its presence to offline.
        """
        await self.change_presence(status=discord.Status.offline)


    async def process_command_queue(self):
        while True:
            cog_name, command, args, kwargs = await self.command_queue.get()
            cog = self.get_cog(cog_name)
            if cog is None:
                print(f"Cog {cog_name} not found")
                continue

            method = getattr(cog, command, None)
            if method is None:
                print(f"Command {command} not found in cog {cog_name}")
                continue

            if asyncio.iscoroutinefunction(method):
                await method(*args, **kwargs)
            else:
                method(*args, **kwargs)
            self.command_queue.task_done()

    def execute(self, cog_name, command, *args, **kwargs):
        """
        Executes a command in the specified cog.

        Args:
            cog_name (str): The name of the cog where the command resides.
            command (str): The command to be executed.
            *args: Variable length argument list.
            **kwargs: Arbitrary keyword arguments.

        Returns:
            The result of the executed command.
        
        Raises:
            ValueError: If the cog or command is not found.
        """
        async def execute(self, cog_name, command, *args, **kwargs):
            threading.Thread(target= await self.command_queue.put, args=(cog_name, command, args, kwargs)).start()
    

    
  