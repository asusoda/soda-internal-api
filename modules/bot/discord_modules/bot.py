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

    def check_officer(self, user_id, superadmin_user_id) -> list[int]:
        """
        Checks if a user has the 'Officer' role in any organization.
        Returns a list of guild IDs where the user has the officer role.
        """
        from shared import db_connect
        from modules.organizations.models import Organization
        
        print(f"🔍 [DEBUG] check_officer called for user_id: {user_id}, superadmin_user_id: {superadmin_user_id}")
        guild_ids_with_officer_role = []
        
        try:
            # Check if the user is a superadmin first (with proper type conversion)
            if str(user_id) == str(superadmin_user_id):
                print(f"👑 [DEBUG] User is superadmin, returning all guild IDs")
                all_guild_ids = [guild.id for guild in self.get_guilds()]
                print(f"�� [DEBUG] Superadmin guild IDs: {all_guild_ids}")
                return all_guild_ids
            
            # Get database connection
            print(f"📊 [DEBUG] Getting database connection...")
            db = next(db_connect.get_db())
            print(f"✅ [DEBUG] Database connection established")
            
            # Get all organizations from the database
            print(f"🏢 [DEBUG] Querying active organizations...")
            organizations = db.query(Organization).filter_by(is_active=True).all()
            print(f"�� [DEBUG] Found {len(organizations)} active organizations")
            
            for i, org in enumerate(organizations):
                print(f"\n�� [DEBUG] Processing organization {i+1}/{len(organizations)}: {org.name}")
                print(f"   📊 [DEBUG] Organization details:")
                print(f"      - Guild ID: {org.guild_id}")
                print(f"      - Officer Role ID: {org.officer_role_id}")
                print(f"      - Is Active: {org.is_active}")
                
                # Skip organizations without officer role configured
                if not org.officer_role_id:
                    print(f"   ⚠️  [DEBUG] Skipping {org.name} - no officer role configured")
                    continue
                
                try:
                    # Get the guild
                    print(f"   🏛️  [DEBUG] Getting guild with ID: {org.guild_id}")
                    guild = super().get_guild(int(org.guild_id))
                    if not guild:
                        print(f"   ❌ [DEBUG] Guild not found for ID: {org.guild_id}")
                        continue
                    print(f"   ✅ [DEBUG] Found guild: {guild.name}")
                    
                    # Get the officer role
                    print(f"   👑 [DEBUG] Getting officer role with ID: {org.officer_role_id}")
                    officer_role = guild.get_role(int(org.officer_role_id))
                    if not officer_role:
                        print(f"   ❌ [DEBUG] Officer role not found for ID: {org.officer_role_id}")
                        continue
                    print(f"   ✅ [DEBUG] Found officer role: {officer_role.name}")
                    
                    # Check if the user has the officer role
                    print(f"   👤 [DEBUG] Getting member with user_id: {user_id}")
                    member = guild.get_member(int(user_id))
                    if not member:
                        print(f"   ❌ [DEBUG] Member not found in guild for user_id: {user_id}")
                        continue
                    print(f"   ✅ [DEBUG] Found member: {member.display_name}")
                    
                    # Check if user has the officer role
                    has_officer_role = officer_role in member.roles
                    print(f"   🔍 [DEBUG] Checking if member has officer role: {has_officer_role}")
                    
                    if has_officer_role:
                        print(f"   🎉 [DEBUG] User has officer role! Adding guild_id: {org.guild_id}")
                        guild_ids_with_officer_role.append(org.guild_id)
                    else:
                        print(f"   ❌ [DEBUG] User does not have officer role")
                        # Debug: show all roles the user has
                        user_roles = [role.name for role in member.roles]
                        print(f"   📋 [DEBUG] User's roles: {user_roles}")
                        
                except (ValueError, AttributeError) as e:
                    # Skip if guild_id or role_id is invalid
                    print(f"   ❌ [DEBUG] Error checking organization {org.name}: {e}")
                    print(f"   �� [DEBUG] Error type: {type(e).__name__}")
                    continue
                    
        except Exception as e:
            print(f"❌ [DEBUG] Error in check_officer: {e}")
            print(f"�� [DEBUG] Error type: {type(e).__name__}")
            import traceback
            print(f"�� [DEBUG] Full traceback:")
            traceback.print_exc()
        finally:
            if 'db' in locals():
                print(f"🔒 [DEBUG] Closing database connection...")
                db.close()
                print(f"✅ [DEBUG] Database connection closed")
        
        print(f"🎯 [DEBUG] Final result - Guild IDs with officer role: {guild_ids_with_officer_role}")
        return guild_ids_with_officer_role
    
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
