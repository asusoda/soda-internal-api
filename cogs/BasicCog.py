from discord.ext import commands
import discord
import logging

class BasicCog(commands.Cog):

    def __init__(self, bot):
        self.bot = bot