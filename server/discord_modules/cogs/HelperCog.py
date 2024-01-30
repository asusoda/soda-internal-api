import discord
from discord.ext import commands
from typing import Optional, List, Dict, Any, Union, Tuple, Callable, Awaitable
import random
import asyncio
class HelperCog(commands.Cog):
        """
        A utility cog for a Discord bot, providing methods for managing server
        elements such as channels, categories, roles, and handling messages and reactions.

        Attributes:
                bot (commands.Bot): The instance of the bot that this cog is part of.
                announcement_channel (discord.TextChannel): A channel for announcements.
                message_listen_for (list): A list of messages to listen for reactions.
        """
                
        def __init__(self, bot : commands.Bot):
                """
                Initializes the HelperCog instance.

                Args:
                bot (commands.Bot): The instance of the bot that this cog is part of.
                """
                self.bot = bot
                self.announcement_channel = None
                self.message_listen_for = []
            
        async def create_category(self, guild: discord.Guild ,name : str, position : Optional[int] = 0):
                """
                Creates a new category in the guild.

                Args:
                guild (discord.Guild): The guild where the category will be created.
                name (str): The name of the category.
                position (int, optional): The position in the guild's channel list.

                Returns:
                discord.CategoryChannel: The created category channel.
                """
                category = asyncio.run(guild.create_category(name = name))
                await category.edit(position=position)
                return category
    
        async def create_text_channel(self, guild: discord.Guild, name : str, category : Optional[discord.CategoryChannel], overwrites : Optional[Dict[discord.Role, discord.PermissionOverwrite]] = None):
                """
                Creates a new text channel in the guild.

                Args:
                guild (discord.Guild): The guild where the channel will be created.
                name (str): The name of the channel.
                category (discord.CategoryChannel): The category to create the channel in.
                overwrites (dict, optional): A dictionary of role overwrites.
                """
                if overwrites is None:
                        channel = await guild.create_text_channel(name, category=category)
                        return channel
                else:
                        channel = await guild.create_text_channel(name, category=category, overwrites=overwrites)
                        return channel
    
        async def create_voice_channel(self, guild: discord.Guild, name : str, category : Optional[discord.CategoryChannel], overwrites : Optional[Dict[discord.Role, discord.PermissionOverwrite]] = None):
                """
                Creates a new voice channel in the guild.

                Args:
                guild (discord.Guild): The guild where the channel will be created.
                name (str): The name of the channel.
                category (discord.CategoryChannel): The category to create the channel in.
                overwrites (dict, optional): A dictionary of role overwrites.
                """
                channel = await guild.create_voice_channel(name, category=category, overwrites=overwrites)
                return channel
    
        async def create_role(self, guild: discord.Guild, name : str, colour : Optional[discord.Colour] = None):
                """
                Creates a new role in the guild.
                
                Args:
                guild (discord.Guild): The guild where the role will be created.
                name (str): The name of the role.
                colour (discord.Colour, optional): The colour of the role.
                """
                role = await guild.create_role(name=name, colour=colour)
                return role
    
        async def delete_category(self, category : discord.CategoryChannel):
                """
                Deletes a category.

                Args:
                category (discord.CategoryChannel): The category to be deleted.
                """
                await category.delete()

        async def delete_text_channel(self, channel : discord.TextChannel):
                """
                Deletes a text channel.
                
                Args:
                channel (discord.TextChannel): The text channel to be deleted.
                """
                await channel.delete()
        
        async def delete_voice_channel(self, channel : discord.VoiceChannel):
                """
                Deletes a voice channel.

                Args:
                channel (discord.VoiceChannel): The voice channel to be deleted.
                """
                await channel.delete()

        async def delete_role(self, role : discord.Role):
                """
                Deletes a role.

                Args:
                role (discord.Role): The role to be deleted.
                """
                await role.delete()

        async def send_message(self, channel : discord.TextChannel, embed : Optional[discord.Embed], content : Optional[str], view : Optional[discord.ui.View] = None):
                """
                Sends a message to a channel.

                Args:
                channel (discord.TextChannel): The channel to send the message to.
                embed (discord.Embed, optional): An embed to send.
                content (str, optional): Content to send.
                view (discord.ui.View, optional): A view to send.
                """
                if view is None:
                        if embed is None:
                                message = self.bot.loop.create_task(channel.send(content))
                        elif content is None:
                                message = self.bot.loop.create_task(channel.send(embed=embed))
                        else:
                                raise Exception("Both embed and content cannot be None.")
                        return message
                else:
                        if embed is None:
                                message = self.bot.loop.create_task(channel.send(content, view=view))
                        elif content is None:
                                message = self.bot.loop.create_task(channel.send(embed=embed, view=view))
                        else:
                                raise Exception("Both embed and content cannot be None.")
                        return message
                
        async def edit_message(self, message : discord.Message, embed : Optional[discord.Embed], content : Optional[str], view : Optional[discord.ui.View] = None):
                """
                Edits a message.

                Args:
                message (discord.Message): The message to edit.
                embed (discord.Embed, optional): An embed to send.
                content (str, optional): Content to send.
                view (discord.ui.View, optional): A view to send.
                """
                
                if view is None:
                        if embed is None:
                                await message.edit(content=content)
                        elif content is None:
                                await message.edit(embed=embed)
                        else:
                                raise Exception("Both embed and content cannot be None.")
                else:
                        if embed is None:
                                await message.edit(content=content, view=view)
                        elif content is None:
                                await message.edit(embed=embed, view=view)
                        else:
                                raise Exception("Both embed and content cannot be None.")
                return message

        async def add_reaction(self, message : discord.Message, emoji : str):
                """
                Adds a reaction to a message.

                Args:
                message (discord.Message): The message to add the reaction to.
                emoji (str): The emoji to add.
                """
                await message.add_reaction(emoji)
                return message
    
        def add_to_listner(self, message : discord.Message, emoji : str):
                """
                Adds a message to the list of messages to listen for reactions.

                Args:
                message (discord.Message): The message to add.
                emoji (str): The emoji to listen for.
                """
                self.message_listen_for.append({
                        "message": message,
                        "emoji": emoji
                        })
        
        def remove_from_listner(self, message : discord.Message, emoji : str):
                """
                Removes a message from the list of messages to listen for reactions.
                
                Args:
                message (discord.Message): The message to remove.
                emoji (str): The emoji to stop listening for.
                """
                for message in self.message_listen_for:
                        if message["message"] == message and message["emoji"] == emoji:
                                self.message_listen_for.remove(message)
                                return True
                return False
     

        @commands.Cog.listener()
        async def on_reaction_add(self, reaction : discord.Reaction, user : discord.User):
                """     
                Asynchronous event handler for when a reaction is added to a message.
                
                Args:
                reaction (discord.Reaction): The reaction that was added.
                user (discord.User): The user that added the reaction.
                """
                print(f"Reaction added by {user.name}")
                for message in self.message_listen_for:
                        if reaction.message.id == message["message"].id:
                                if reaction.emoji == message["emoji"]:
                                        self.bot.execute("GameCog", "add_member", user)

        @commands.Cog.listener()
        async def on_reaction_remove(self, reaction : discord.Reaction, user : discord.User):
                """     
                Asynchronous event handler for when a reaction is removed from a message.
                
                Args:
                reaction (discord.Reaction): The reaction that was removed.
                user (discord.User): The user that removed the reaction.
                """
                print("Reaction removed")
                for message in self.message_listen_for:
                        if reaction.message.id == message["message"].id:
                                if reaction.emoji == message["emoji"]:
                                        self.bot.execute("GameCog", "remove_member", user)
 

        @discord.slash_command(name="clear", description="Clears the game environment from the Discord server.", guild_ids=[1011586463219060807])
        async def clear(self, ctx : commands.Context):
                """
                Clears the game environment from the Discord server.
                """
                await ctx.defer()
                guild = self.bot.guilds[0]
                for category in guild.categories:
                        if category.name == "Jeopardy":
                                for channel in category.channels:
                                        await channel.delete()
                                await category.delete()
                
                for role in guild.roles:
                        if role.name.startswith("Team"):
                                await role.delete()

                await ctx.respond("Cleared the game environment.")
    


    
    


    