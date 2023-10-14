
from discord.ext import commands
from discord.ext import tasks
from ..utils.JeprodayGame import JeprodayGame
from ..utils.JeprodayQuestion import JeprodayQuestion
import os
import requests
import json
import random
import uuid
import discord
import logging



class GameCog(commands.Cog):

    def __init__(self, bot, logger, questions) -> None:
            self.bot = bot
            self.logger = logger
            self.game = JeprodayGame

    @commands.command()
    async def show(self, ctx):
        """Show the list of Jeproday questions in an embed UI."""
        embed = discord.Embed(title="Jeproday Questions", description="Here are the available questions:", color=0x00ff00)
        
        for question in self.questions:
             if not question.answered:
                embed.add_field(name=question.category, value= question.value , inline=False)
             else:
                embed.add_field(name=question.category, value= "XXXXXXX", inline=False)
        
        await ctx.send(embed=embed)
