import discord
from discord.ext import commands

import random

class BasicCog(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.announcement_channel = None
        self.message_event_listeners = []

    
    
        
    @discord.slash_command(name="clean", description="Clean up the Jeopardy game", guild_ids=[1011586463219060807])
    async def clean_game(self, ctx):
        await ctx.defer()
        guild = ctx.guild
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
        await ctx.respond("Jeopardy game cleaned up!")


    