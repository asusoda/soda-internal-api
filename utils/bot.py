import discord
from discord.ext import commands
import logging
import os
import json
import random
import uuid
import asyncio
from ..cogs.ModerationCog import Moderation
from ..cogs.GameCog import GameCog
from ..cogs.MusicCog import MusicCog




class MyBot(commands.Bot):
    def __init__(self, *args, **kwargs):
        self.setup = False
        super().__init__( *args, **kwargs)

    def set_token(self, token):
        self.token = token

    async def on_ready(self):
        print("Bot is ready.")
        


    def run(self):
        """Starts the bot"""
        if not self.setup:
            self.setup = True
            super().run(self.token, reconnect=True)
            super().add_cog(Moderation(self))
            super().add_cog(GameCog(self))
            super().add_cog(MusicCog(self))

        else:
            asyncio.run(self.change_presence(status=discord.Status.online))

    async def stop(self):
        """Stops the bot"""
        super().remove_cog("Moderation")
        super().remove_cog("GameCog")
        super().remove_cog("MusicCog")
        await self.change_presence(status=discord.Status.offline)

        