
from discord.ext import commands
from discord.ext import tasks
from typing import Optional, List, Dict, Any, Union, Tuple, Callable, Awaitable
import discord
import random
import asyncio
from  discord.Jeopardy import JeopardyGame
from discord.Team import Team


class QuestionPost(discord.ui.View):

    def __init__ (self, channel: discord.StageChannel):
        super().__init__()
        self.channel = channel

    @discord.ui.button(label="Buzz In", style=discord.ButtonStyle.blurple)
    async def button_callback(self, button: discord.ui.Button, interaction: discord.Interaction):
        user = interaction.user         
        await interaction.response.send_message(f"<@{user.id}> You buzzed in!")
        button.disabled = True
        return user
    

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
        self.date = None
        self.time = None

    def set_game(self, game: dict, date: str, time: str) -> bool:
        """
        Sets the game instance for the cog.

        Args:
            game (dict): The game data.

        Returns:
            bool: True if the game is set successfully.
        """
        self.game = JeopardyGame(game)
        self.date = date
        self.time = time
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


    def is_setup(self) -> bool:
        """
        Checks if the game environment is set up.

        Returns:
            bool: True if the game environment is set up.
        """
        return self.game.is_announced


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

    def add_member(self, member: discord.User) -> bool:
        """
        Adds a member to the current game.

        Args:
            member (discord.Member): The member to add to the game.

        Returns:
            bool: True if the member is added successfully.
        """
        self.game.add_member(member)
        return True
        
    def remove_member(self, member: discord.User) -> bool:
        """
        Removes a member from the current game.

        Args:
            member (discord.Member): The member to remove from the game.

        Returns:
            bool: True if the member is removed successfully.
        """
        self.game.remove_member(member)
        return True

    async def setup_game(self):
        """
        Asynchronously sets up the game environment in the Discord server.
        """
        guild = self.bot.guilds[0]
        print("Creating channels and roles")
        category = await guild.create_category("Jeopardy")
        await category.edit(position=0)
        self.game_category = category
        self.stage = await guild.create_stage_channel("Stage", category=category)
        for team in self.game.teams:
            role = await guild.create_role(name=team.get_name())
            self.roles.append(role)

            overwrites = {
                guild.default_role: discord.PermissionOverwrite(view_channel=True, connect=False, speak=False),
                role: discord.PermissionOverwrite(view_channel=True, connect=True, speak=True)
            }
            channel = await guild.create_voice_channel(team.get_name(), overwrites=overwrites, category=category)
            self.voice_channels.append(channel)

        self.announcement_channel = await guild.create_text_channel("announcements", category=category)
        self.scoreboard_channel = await guild.create_text_channel("scoreboard", category=category)
        self.game.is_announced = True
        embed = discord.Embed(
        title="🌟 JEOPARDY GAME NIGHT ANNOUNCEMENT 🌟",
        description="Get ready for an exciting evening of trivia and fun!",
        color=discord.Color.random()  
    )
        embed.add_field(name="Date", value=self.date, inline=False)
        embed.add_field(name="Time", value=self.time, inline=False)
        embed.add_field(name="Location", value="SODA Discord Server", inline=False)
        embed.add_field(name="How to Enroll?", value="React with ✅.", inline=False)
        embed.set_footer(text="React with ✅ to enroll!")
        message = await self.announcement_channel.send(embed=embed)
        await message.add_reaction("✅")
        self.bot.execute("HelperCog", "add_to_listner", message, "✅" )
        return True
        
            
    async def show_question(self, uuid):
        """
        Asynchronously shows a question to the players.

        Args:
            uuid (str): The UUID of the question to show.
        """
        question = self.g
