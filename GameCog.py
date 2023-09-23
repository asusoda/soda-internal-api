import discord
import logging
from discord.ext import commands
from discord.ext import tasks
import os
import requests
import json
import random
import uuid

class JeprodayQuestion:
    def __init__(self, category, question, answer, value, uuid):
        self.category = category
        self.question = question
        self.answer = answer
        self.value = value
        self.answered = False


class GameCog(commands.Cog):

    def __init__(self, bot, logger, questions) -> None:
            self.bot = bot
            self.logger = logger
            self.questions = questions

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
