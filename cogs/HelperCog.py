import discord
from discord.ext import commands
from typing import Optional, List, Dict, Any, Union, Tuple, Callable, Awaitable
import random

class HelperCog(commands.Cog):

        def __init__(self, bot : commands.Bot):
                self.bot = bot
                self.announcement_channel = None
                self.message_listen_for = []
            
        async def create_category(self, guild: discord.Guild ,name : str, position : Optional[int] = 0):
                category = await guild.create_category(name)
                await category.edit(position=position)
                return category
    
        async def create_text_channel(self, guild: discord.Guild, name : str, category : Optional[discord.CategoryChannel], overwrites : Optional[Dict[discord.Role, discord.PermissionOverwrite]] = None):
                channel = await guild.create_text_channel(name, category=category, overwrites=overwrites)
                return channel
    
        async def create_voice_channel(self, guild: discord.Guild, name : str, category : Optional[discord.CategoryChannel], overwrites : Optional[Dict[discord.Role, discord.PermissionOverwrite]] = None):
                channel = await guild.create_voice_channel(name, category=category, overwrites=overwrites)
                return channel
    
        async def create_role(self, guild: discord.Guild, name : str, colour : Optional[discord.Colour] = None):
                role = await guild.create_role(name=name, colour=colour)
                return role
    
        async def delete_category(self, category : discord.CategoryChannel):
                await category.delete()

        async def delete_text_channel(self, channel : discord.TextChannel):
                await channel.delete()
        
        async def delete_voice_channel(self, channel : discord.VoiceChannel):
                await channel.delete()

        async def delete_role(self, role : discord.Role):
                await role.delete()


        async def send_message(self, channel : discord.TextChannel, embed : Optional[discord.Embed], content : Optional[str], view : Optional[discord.ui.View] = None):
                if view is None:
                        if embed is None:
                                message = await channel.send(content)
                        elif content is None:
                                message = await channel.send(embed=embed)
                        else:
                                raise Exception("Both embed and content cannot be None.")
                        return message
                else:
                        if embed is None:
                                message = await channel.send(content, view=view)
                        elif content is None:
                                message = await channel.send(embed=embed, view=view)
                        else:
                                raise Exception("Both embed and content cannot be None.")
                        return message
                
        async def edit_message(self, message : discord.Message, embed : Optional[discord.Embed], content : Optional[str], view : Optional[discord.ui.View] = None):
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
                await message.add_reaction(emoji)
                return message
    
        def add_to_listner(self, message : discord.Message, emoji : str):
                self.message_listen_for.append({
                        "message": message,
                        "emoji": emoji
                        })
        
        def remove_from_listner(self, message : discord.Message, emoji : str):
                for message in self.message_listen_for:
                        if message["message"] == message and message["emoji"] == emoji:
                                self.message_listen_for.remove(message)
                                return True
                return False
     

        @commands.Cog.listener()
        async def on_reaction_add(self, reaction : discord.Reaction, user : discord.User):
                for message in self.message_listen_for:
                        if reaction.message.id == message["message"].id:
                                if reaction.emoji == message["emoji"]:
                                        self.bot.execute("GameCog", "add_member", user)
 

    


    
    


    