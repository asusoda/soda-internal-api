
from discord.ext import commands
from discord.ext import tasks


from utils.JeprodyGame import JeopardyGame
from utils.JeprodyQuestion import JeopardyQuestion

import os
import requests
import json
import random
import uuid
import discord
import logging

class TempConfig():

        def __init__(self, roles, category, channels) -> None:
                self.roles = roles
                self.category = category
                self.channels = channels

        def purge(self):
                for channel in self.channels:
                        channel.delete()
                for role in self.roles:
                        role.delete()
                self.category.delete()


class GameCog(commands.Cog):
 
        def __init__(self, bot, logger, questions) -> None:
            self.bot = bot
            self.logger = logger
            self.game = None
            self.scheduler = AsyncIOScheduler()

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

        def set_game(self, game):
                if self.game is None:
                        self.game = game
                else:
                        raise Exception("Game already set. Clear the exisiting game first.")
                
        def clear_game(self):
                self.game = None


        async def send_announcment(self):
                channel_id = 1234567890  # Replace with your channel ID
                channel = self.bot.get_channel(channel_id)
                
                embed = discord.Embed(title="Jeopardy Game Announcement", description="Join our Jeopardy game!", color=0x00ff00)
                embed.add_field(name="Number of Teams", value="5", inline=True)
                embed.add_field(name="Players per Team", value="4", inline=True)
                
                message = await channel.send(embed=embed)
    
        async def start_game(self):
                guild = self.bot.guilds[0]
                category = await guild.create_category("Jeopardy")
                await category.edit(position=0)
                roles = []
                for i in range(5):
                          role = await guild.create_role(name=f"Team {i+1}")
                          role.edit(colour=discord.Colour(random.randint(0, 0xFFFFFF)))
                          roles.append(role)
                


     