import discord
from discord.ext import commands

import random

class HelperCog(commands.Cog):

    def __init__(self, bot : commands.Bot):
        self.bot = bot
        self.announcement_channel = None
        self.message_listen_for = []
    
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

    def add_message(self, message : discord.Message):
        self.message_listen_for.append(message)

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction : discord.Reaction, user : discord.User):
        for message in self.message_listen_for:
            if reaction.message.id == message.id:
                if reaction.emoji == "✅":
                    self.bot.add_member(user)

    


    
    


    