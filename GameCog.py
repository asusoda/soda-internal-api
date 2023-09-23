import discord
import logging
from discord.ext import commands
from discord.ext import tasks



class GameCog(commands.Cog):

    def __init__(self, bot, logger) -> None:
            self.bot = bot
            self.logger = logger

    @