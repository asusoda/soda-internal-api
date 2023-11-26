import discord
from discord.ext import commands
import logging
import os
import json
import random
import uuid
import asyncio
from cogs.HelperCog import HelperCog
from cogs.GameCog import GameCog
from utils.Jeopardy import JeopardyGame




class BotFork(commands.Bot):
    def __init__(self, *args, **kwargs):
        self.setup = False
        self.active_game = None
        super().__init__( *args, **kwargs, guild_ids = [])

    def set_token(self, token):
        self.token = token

    async def on_ready(self):
        print("Bot is ready.")
    

    def run(self):
        """Starts the bot"""
        if not self.setup:
            self.setup = True
            super().add_cog(HelperCog(self))
            super().add_cog(GameCog(self))
            super().run(self.token, reconnect=True)
        else:
            asyncio.run(self.change_presence(status=discord.Status.online))

    
    async def stop(self):
        """Stops the bot"""
        await self.change_presence(status=discord.Status.offline)

        
    def game(self, data):
        self.active_game = data
        self.set_active_game(data)


    def set_active_game(self, data):
        self.active_game = JeopardyGame(data)
        cog = self.get_cog("GameCog")
        cog.set_game(data)
    


      
    async def create_game_channels_and_roles(self, game):
                
                if self.game is None:
                        self.game = game
                else:
                        raise Exception("Game already set. Clear the existing game first.")

                guild = self.bot.guilds[0]
                print(guild)
                print("Creating category")

                # Create category and await the result
                category = await guild.create_category("Jeopardy")
                await category.edit(position=0)

                roles = []
                for i in range(5):
                        # Create role and await the result
                        role = await guild.create_role(name=f"Team {i+1}")
                        await role.edit(colour=discord.Colour(random.randint(0, 0xFFFFFF)))
                        roles.append(role)

                overwrites = {
                        guild.default_role: discord.PermissionOverwrite(view_channel=True, send_messages=False)
                }

                print("Creating announcement channel")
                self.announcement_channel = await guild.create_text_channel(
                        "announcement", category=category, overwrites=overwrites
                )
                self.scoreboard_channel = await guild.create_text_channel(
                        "scoreboard", category=category, overwrites=overwrites
                )

                # Create voice channels for each role
                for role in roles:
                        overwrites = {
                        guild.default_role: discord.PermissionOverwrite(view_channel=True, connect=False, speak=False),
                        role: discord.PermissionOverwrite(view_channel=True, connect=True, speak=True)
                        }
                        print(f"Creating voice channel for {role.name}")
                        await guild.create_voice_channel(role.name, category=category, overwrites=overwrites)

                # Create and send an announcement embed
                categories = [str(category_name) for category_name in self.game.questions.keys()]
                embed = discord.Embed(
                        title=self.game.name,
                        description=f'Announcing {self.game.name}, a Jeopardy game.',
                        colour=discord.Colour(random.randint(0, 0xFFFFFF))
                )
                embed.add_field(name="Description", value=self.game.description, inline=False)
                embed.add_field(name="Categories", value="\n".join(categories), inline=False)

                print("Sending announcement embed")
                message = await self.announcement_channel.send(embed=embed)
                await message.add_reaction("✅")


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

    def award_points(self, team, points):
        self.active_game.award_points(team, points)

    
    def get_active_game(self):
        return self.active_game

  