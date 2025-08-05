import discord
from discord.ext import commands
import inspect
import asyncio
import nest_asyncio
from modules.bot.discord_modules.cogs.HelperCog import HelperCog
from modules.bot.discord_modules.cogs.GameCog import GameCog
from modules.bot.discord_modules.cogs.jeopardy.Jeopardy import JeopardyGame


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
        self.active_game = None
        super().__init__(*args, **kwargs, guild_ids=[])
        # super().add_cog(HelperCog(self))
        # super().add_cog(GameCog(self))

    async def on_ready(self):
        """Event that fires when the bot is ready."""
        print(f'Logged in as {self.user} (ID: {self.user.id})')
        print('------')

        # For py-cord, commands should sync automatically
        print("Discord connection established. Commands should be registered automatically.")

    def set_token(self, token):
        """
        Sets the bot token.

        Args:
            token (str): Discord bot token.
        """
        self.token = token

    

    
    def run(self, token=None):
        """
        Starts the bot with the provided token.
        """
        print("Running bot")
        if token:
            self.token = token
        if not self.token:
            raise ValueError("Bot token is required")
        
        # Use the parent class run method directly
        super().run(self.token)

    # py-cord handles command synchronization automatically

    async def stop(self):
        """
        Asynchronous method to stop the bot, changing its presence to offline.
        """
        await self.change_presence(status=discord.Status.offline)

    def execute(self, cog_name, command, *args, priority="NORMAL", **kwargs):
        """Executes a command in the specified cog with optional priority."""
        cog = self.get_cog(cog_name)
        if cog is None:
            raise ValueError(f"Cog {cog_name} not found")

        method = getattr(cog, command, None)
        if method is None:
            raise ValueError(f"Command {command} not found in cog {cog_name}")

        if inspect.iscoroutinefunction(method):
            if priority == "NOW":
                # For highest priority, run the coroutine immediately
                nest_asyncio.apply()
                return asyncio.run(method(*args, **kwargs))
            else:
                # For normal priority, schedule it in the event loop
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

    def check_officer(self, user_id):
        """
        Checks if a user has the 'Officer' role in any organization.
        Returns a list of guild IDs where the user has the officer role.
        """
        from shared import db_connect
        from modules.organizations.models import Organization
        
        guild_ids_with_officer_role = []
        
        try:
            # Get database connection
            db = next(db_connect.get_db())
            
            # Get all organizations from the database
            organizations = db.query(Organization).filter_by(is_active=True).all()
            
            for org in organizations:
                # Skip organizations without officer role configured
                if not org.officer_role_id:
                    continue
                
                try:
                    # Get the guild
                    guild = super().get_guild(int(org.guild_id))
                    if not guild:
                        continue
                    
                    # Get the officer role
                    officer_role = guild.get_role(int(org.officer_role_id))
                    if not officer_role:
                        continue
                    
                    # Check if the user has the officer role
                    member = guild.get_member(int(user_id))
                    if member and officer_role in member.roles:
                        guild_ids_with_officer_role.append(org.guild_id)
                        
                except (ValueError, AttributeError) as e:
                    # Skip if guild_id or role_id is invalid
                    print(f"Error checking organization {org.name}: {e}")
                    continue
                    
        except Exception as e:
            print(f"Error in check_officer: {e}")
        finally:
            db.close()
        
        return guild_ids_with_officer_role

    def is_officer_in_organization(self, user_id, guild_id):
        """
        Checks if a user has the 'Officer' role in a specific organization.
        Returns True if the user is an officer in the specified guild, False otherwise.
        """
        officer_guilds = self.check_officer(user_id)
        return str(guild_id) in officer_guilds

    def get_name(self, user_id):
        guild = super().get_guild(762811961238618122)
        member = guild.get_member(int(user_id))
        if member is not None:
            if member.nick is not None:
                return member.nick
            else:
                return member.name
        else:
            return None
    
    def get_guild_roles(self, guild_id : int):
        guild = super().get_guild(guild_id)
        return guild.roles

    def check_role(self, guild_id : int, role_id : int, user_id : int):
        guild = super().get_guild(guild_id)
        member = guild.get_member(user_id)
        return role_id in [role.id for role in member.roles]
    
    def check_user_officer_status(self, user_id : int, guild_id : int, role_id : int):
        guild = super().get_guild(guild_id)
        member = guild.get_member(user_id)
        return role_id in [role.id for role in member.roles]

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
