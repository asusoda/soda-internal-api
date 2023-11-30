
from discord.ext import commands
from discord.ext import tasks
from typing import Optional, List, Dict, Any, Union, Tuple, Callable, Awaitable
import discord
import random
import asyncio
from utils.Jeopardy import JeopardyGame
from utils.Team import Team


class GameCog(commands.Cog):
    """
    A cog for managing a game (Jeopardy-style) within a Discord server. It handles game setup,
    participant management, and environment cleanup.

    Attributes:
        bot (commands.Bot): The instance of the bot that this cog is part of.
        game (JeopardyGame): The current game instance.
        game_category (discord.CategoryChannel): The category under which game channels are created.
        roles (list): A list of roles created for the game.
        announcement_channel (discord.TextChannel): The channel for game announcements.
        voice_channels (list): List of voice channels created for the game.
        scoreboard_channel (discord.TextChannel): The channel for displaying the game scoreboard.
        scoreboard (Any): The scoreboard object for the game.
    """

    def __init__(self, bot):
        """
        Initializes the GameCog instance.

        Args:
            bot (commands.Bot): The instance of the bot that this cog is part of.
        """
        self.bot = bot
        self.game = None
        self.game_category = None
        self.roles = []
        self.announcement_channel = None
        self.voice_channels = []
        self.scoreboard_channel = None
        self.scoreboard = None

    def set_game(self, game: dict) -> bool:
        """
        Sets the game instance for the cog.

        Args:
            game (dict): The game data.

        Returns:
            bool: True if the game is set successfully.
        """
        self.game = JeopardyGame(game)
        return True

    def get_game(self) -> Optional[dict]:
        """
        Retrieves the current game's data in JSON format.

        Returns:
            dict: The game data, or None if no game is set.
        """
        if self.game is None:
            return None
        return self.game.to_json()

    def setup_game(self):
        """`
        Asynchronously sets up the game environment in the Discord server.
        """
        guild = self.bot.guilds[0]
        category = self.bot.execute("HelperCog", "create_category", guild, "Jeopardy")
        self.game_category = category
             
        for team in self.game.teams:
            role = self.bot.execute("HelperCog", "create_role", guild, team.get_name())
            self.roles.append(role)

            overwrites = {
                guild.default_role: discord.PermissionOverwrite(view_channel=True, connect=False, speak=False),
                role: discord.PermissionOverwrite(view_channel=True, connect=True, speak=True)
            }

            channel = self.bot.execute("HelperCog", "create_voice_channel", guild, team.get_name(), category, overwrites)
            self.voice_channels.append(channel)

        self.announcement_channel = self.bot.execute("HelperCog", "create_text_channel", guild, "announcements", category)
        self.scoreboard_channel = self.bot.execute("HelperCog", "create_text_channel", guild, "scoreboard", category)

        return True
    



    async def clear_game(self):
        """
        Asynchronously clears the game environment from the Discord server.
        """
        for role in self.roles:
            await self.bot.execute("HelperCog", "delete_role", role)
        for channel in self.voice_channels:
            await self.bot.execute("HelperCog", "delete_voice_channel", channel)

        await self.bot.execute("HelperCog", "delete_category", self.game_category)
        await self.bot.execute("HelperCog", "delete_text_channel", self.announcement_channel)
        await self.bot.execute("HelperCog", "delete_text_channel", self.scoreboard_channel)

        # Resetting attributes
        self.roles = []
        self.voice_channels = []
        self.game_category = None
        self.announcement_channel = None
        self.scoreboard_channel = None
        self.scoreboard = None
        self.game = None
        return True

    def add_member(self, member: discord.Member) -> bool:
        """
        Adds a member to the current game.

        Args:
            member (discord.Member): The member to add to the game.

        Returns:
            bool: True if the member is added successfully.
        """
        self.game.add_member(member)
        return True
        


        
        
        


     