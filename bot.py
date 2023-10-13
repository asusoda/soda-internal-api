import discord
from discord.ext import commands
# from cogs.ModerationCog import Moderation
# from cogs.GameCog import GameCog
# from cogs.MusicCog import MusicCog
import logging
import os
import json
import random
import uuid
import asyncio



class MyBot(commands.Bot):
    def __init__(self, *args, **kwargs):
        super().__init__( *args, **kwargs)

    def set_token(self, token):
        self.token = token

    async def on_ready(self):
        """Called upon the READY event"""
        print("Bot is ready.")
        


    def run(self):
        """Starts the bot"""
        super().run(self.token, reconnect=True)

    def stop(self):
        """Stops the bot"""
        
        