
from discord.ext import commands
from discord.ext import tasks
from typing import Optional, List, Dict, Any, Union, Tuple, Callable, Awaitable
import discord
import random
import asyncio
from  discord_modules.cogs.jeopardy.Jeopardy import JeopardyGame
from  discord_modules.cogs.jeopardy.JeopardyQuestion import JeopardyQuestion
from  discord_modules.cogs.jeopardy.Team import Team
from  discord_modules.cogs.UI import QuestionPost
    
    
        
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
    
    def __init__(self, bot : commands.Bot):
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
        self.gameboard = None
        self.date = None
        self.time = None
        self.question_post = {}
        self.stage = None
        self.guild = None

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
        self.question_post = {}
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

    async def start_game(self):
        """
        Asynchronously starts the game.
        """
        self.game.start()
        self.scoreboard_channel = await self.guild.create_text_channel("scoreboard", category=self.game_category)
        self.game.attach_roles(self.roles)
        self.balance_teams()
        await self.assign_roles()
        await self.update_scoreboard()
        await self.update_gameboard()
        return True
    
    
    def balance_teams(self):
        """
        Balances the teams in the game.
        """
        members = self.game.get_members()
        random.shuffle(members)  # Shuffle the members list to randomize team assignments

        player_count = len(members)
        team_count = len(self.game.teams)

        if team_count == 0:
            raise ValueError("No teams are set up in the game.")

        team_size = player_count // team_count

        # Clear current members from each team
        for team in self.game.teams:
            team.members.clear()

        # Distribute members evenly across teams
        for i, member in enumerate(members):
            self.game.teams[i % team_count].members.append(member)

        # Handle any remaining members if the division isn't exact
        remaining_members = player_count % team_count
        if remaining_members > 0:
            extra_members = members[-remaining_members:]
            for i, member in enumerate(extra_members):
                self.game.teams[i].members.append(member)

        
    async def assign_roles(self):
        """
        Assigns roles to each team.
        """
        for team in self.game.teams:
            for member in team.members:
                await member.add_roles(team.role)

    async def setup_game(self):
        """
        Asynchronously sets up the game environment in the Discord server.
        """
        self.guild = self.bot.guilds[0]
        category = await self.guild.create_category("Jeopardy")
        await category.edit(position=0)
        self.game_category = category
        self.stage = await self.guild.create_stage_channel(name = "Game Stage",topic = self.game.name ,category=category)
        for team in self.game.teams:
            role = await self.guild.create_role(name=team.get_name())
            self.roles.append(role)

            overwrites = {
                self.guild.default_role: discord.PermissionOverwrite(view_channel=True, connect=False, speak=False),
                role: discord.PermissionOverwrite(view_channel=True, connect=True, speak=True)
            }
            channel = await self.guild.create_voice_channel(team.get_name(), overwrites=overwrites, category=category)
            self.voice_channels.append(channel)

        self.announcement_channel = await self.guild.create_text_channel("announcements", category=category)
        self.game.is_announced = True
        embed = discord.Embed(
        title="🌟 JEOPARDY GAME NIGHT ANNOUNCEMENT 🌟",
        description="Get ready for an exciting evening of trivia and fun!",
        color=discord.Color.random()  
    )
        embed.add_field(name="Date", value=self.date, inline=False)
        embed.add_field(name="Time", value=self.time, inline=False)
        embed.add_field(name="Location", value="The SoDA Discord Server", inline=False)
        embed.add_field(name="How to Enroll?", value="React with ✅.", inline=False)
        embed.set_footer(text="React with ✅ to enroll!")
        message = await self.announcement_channel.send(embed=embed)
        await message.add_reaction("✅")
        self.bot.execute("HelperCog", "add_to_listner", message, "✅" )
        return True
        
    
    
    async def show_question(self, uuid : str):
        """
        Asynchronously shows a question to the players.

        Args:
            uuid (str): The UUID of the question to show.
        """
        if uuid in self.question_post.keys():
            question_data = self.game.get_question_by_uuid(uuid)
            embed = discord.Embed(
                title="🌟QUESTION🌟",
                description= "Here is the question again! \n" ,
                color=discord.Color.random()  
            )
            embed.add_field(name="Category", value=question_data.category, inline=True)
            embed.add_field(name="Value", value=question_data.value, inline=True)
            embed.add_field(name="Question", value=question_data.question, inline=False)
            question = QuestionPost(question=question_data, voice=self.stage, cog=self, avoid=self.question_post[uuid]['rolesAnswered'], question_uuid=uuid)
            await self.question_post[uuid]['message_id'].edit(embed=embed, view=question)
        else:
            question_data = self.game.get_question_by_uuid(uuid)
            embed = discord.Embed(
                title="🌟QUESTION🌟",
                description= "Here is the question! \n" ,
                color=discord.Color.random()  
            )
            embed.add_field(name="Category", value=question_data.category, inline=True)
            embed.add_field(name="Value", value=question_data.value, inline=True)
            embed.add_field(name="Question", value=question_data.question, inline=False)
            question = QuestionPost(question=question_data, voice=self.stage, cog=self, question_uuid=uuid, avoid=[])
            self.question_post[uuid] = {
                                        "message_id":await self.announcement_channel.send(embed=embed, view=question),
                                        "rolesAnswered": []
                                        }
            await self.update_gameboard()
            return True
    

    async def show_answer(self, uuid : str):
        """
        Asynchronously shows the answer to a question.

        Args:
            uuid (str): The UUID of the question to show the answer to.
        """
        
        boolean, question_data = self.game.answer_question(uuid)
        if boolean:
            embed = discord.Embed(
                title="🌟ANSWER🌟",
                description= "Here is the answer! \n" ,
                color=discord.Color.random()  
            )
            embed.add_field(name="Category", value=question_data.category, inline=True)
            embed.add_field(name="Value", value=question_data.value, inline=True)
            embed.add_field(name="Question", value=question_data.question, inline=False)
            embed.add_field(name="Answer", value=question_data.answer, inline=False)
            await self.announcement_channel.send(embed=embed)

            return True
        else:
            return False


    async def award_points(self, team_name: str, points: int):
            """
            Asynchronously awards points to a team.

            Args:
                team_name (str): The name of the team to award points to.
                points (int): The number of points to award.
            """
            self.game.award_points(team_name, points)
            await self.update_scoreboard()
            return True


    async def update_scoreboard(self):
        if self.game.is_started:
            if self.scoreboard is None:
                embed = discord.Embed(
                title="🌟SCOREBOARD🌟",
                description= "Here is the scoreboard! \n" ,
                color=discord.Color.blurple() 
                )
                for team in self.game.teams:
                    embed.add_field(name=team.name, value=team.score, inline=True)
                
                self.scoreboard = await self.scoreboard_channel.send(embed=embed)
            else:
                embed = discord.Embed(
                title="🌟SCOREBOARD🌟",
                description= "Here is the scoreboard! \n" ,
                color=discord.Color.blurple() 
                )
                for team in self.game.teams:
                    embed.add_field(name=team.name, value=team.score, inline=True)
                await self.scoreboard.edit(embed=embed)
        else:
            pass

    async def update_gameboard(self):
        if self.game.is_started:
            if self.gameboard is None:
                data = self.game.get_board()
                embed = discord.Embed(title=f"Jeopardy Game: {self.game.name}", description=self.game.description, color=0x1E90FF)
                for category in data.keys():
                    question_data = data[category]
                    embed.add_field(name=category, value= str(question_data), inline=False)
                self.gameboard = await self.announcement_channel.send(embed=embed)

            else:
                data = self.game.get_board()
                embed = discord.Embed(title=f"Jeopardy Game: {self.game.name}", description=self.game.description, color=0x1E90FF)
                for category in data.keys():
                    question_data = data[category]

                    embed.add_field(name=category, value= str(question_data), inline=False)
                await self.gameboard.edit(embed=embed)

                    
    async def end_game(self):
        """
        Asynchronously ends the game.
        """
        embed = discord.Embed(
            title="🌟GAME OVER🌟",
            description= "Thanks for playing! \n" ,
            color=discord.Color.green()
        )
        winners = self.game.get_winners()
        if len(winners) == 1:
            embed.add_field(name="Winner", value=winners[0], inline=False)
        else:
            embed.add_field(name="Winners", value=', '.join(winners), inline=False)

        await self.announcement_channel.send(embed=embed)
        return True
    
    def get_member_role(self, member) -> discord.Role: 
        """
        Retrieves the role assigned to a member.

        Args:
            member (discord.Member): The member to retrieve the role for.

        Returns:
            discord.Role: The role assigned to the member.
        """
        for role in self.roles:
            if role in member.roles:
                return role
        return None

    