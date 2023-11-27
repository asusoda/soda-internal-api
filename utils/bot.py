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




class BotFork(commands.Bot):
    def __init__(self, *args, **kwargs):
        self.setup = False
        self.active_game = None
        super().__init__( *args, **kwargs, guild_ids = [])
        super().add_cog(HelperCog(self))
        super().add_cog(GameCog(self))

    def set_token(self, token):
        self.token = token

    async def on_ready(self):
        print("Bot is ready.")
    

    def run(self):
        """Starts the bot"""
        if not self.setup:
            self.setup = True
            
            threading.Thread(target=super().run, args=(self.token,)).start()
        else:
            asyncio.run(self.change_presence(status=discord.Status.online))

    
    async def stop(self):
        """Stops the bot"""
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
            loop = asyncio.get_event_loop()
            return loop.run_until_complete(method(*args, **kwargs))
        else:
            # If the method is not a coroutine, just call it directly
            return method(*args, **kwargs)

    def game(self, data):
        self.active_game = data
        self.set_active_game(data)


    def set_active_game(self, data):
        self.active_game = JeopardyGame(data)
        cog = self.get_cog("GameCog")
        cog.set_game(data)    


    async def clean_game(self):
        guild = self.guilds[0]
        for category in guild.categories:
            if category.name == "Jeopardy":
                for channel in category.channels:
                    await channel.delete()
                await category.delete()
        roles = []
        for role in guild.roles:
            if role.name.startswith("Team"):
                roles.append(role)
        for role in roles:
            await role.delete()

    def award_points(self, team, points):
        self.active_game.award_points(team, points)

    
    def get_active_game(self):
        return self.active_game

  