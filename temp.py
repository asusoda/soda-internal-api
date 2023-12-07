import discord
from discord.ext import commands
import logging
import os
import json
import random
import uuid
import asyncio
from cogs.BasicCog import BasicCog
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
            super().add_cog(BasicCog(self))
            super().run(self.token, reconnect=True)
            

        else:
            asyncio.run(self.change_presence(status=discord.Status.online))

    
    async def stop(self):
        """Stops the bot"""
        super().remove_cog("GameCog")
        super().remove_cog("MusicCog")
        print("Bot is stopping.")
        await self.change_presence(status=discord.Status.offline)

        
    def game(self, data):
        self.active_game = data
        self.set_active_game(data)

    async def async_set_active_game(self, data):
        print(self.guilds)
        guild = self.guilds[0]  # Assumes the bot is at least in one guild
        print(guild)

        # Create a "Jeopardy" category and channels within it
        print("Creating category")
        category = await guild.create_category("Jeopardy")
        await category.edit(position=0)

        # Create roles and set permissions
        roles = []
        for i in range(5):
            role = await guild.create_role(name=f"Team {i+1}")
            await role.edit(colour=discord.Colour(random.randint(0, 0xFFFFFF)))
            roles.append(role)

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=True, send_messages=False)
        }

        print("Creating announcement channel")
        self.announcement_channel = await guild.create_text_channel(
            "announcement",
            category=category,
            overwrites=overwrites
        )
        self.scoreboard_channel = await guild.create_text_channel(
            "scoreboard",
            category=category,
            overwrites=overwrites
        )

        for role in roles:
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(view_channel=True, connect=False, speak=False),
                role: discord.PermissionOverwrite(view_channel=True, connect=True, speak=True)
            }
            print(f"Creating voice channel for {role.name}")
            await guild.create_voice_channel(role.name, category=category, overwrites=overwrites)

        # Create an announcement embed
        categories = [str(category_name) for category_name in data["questions"].keys()]
        embed = discord.Embed(
            title=data["game"]["name"],
            description=f'Announcing {data["game"]["name"]}, a Jeopardy game.',
            colour=discord.Colour(random.randint(0, 0xFFFFFF))
        )
        embed.add_field(name="Description", value=data["game"]["description"], inline=False)
        embed.add_field(name="Categories", value="\n".join(categories), inline=False)
        
        print("Sending announcement embed")
        await self.announcement_channel.send(embed=embed)

    def set_active_game(self, data):
        self.active_game = JeopardyGame(data)
        print(self.active_game)
        self.loop.create_task(self.async_set_active_game(data))

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

  