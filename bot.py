from typing import Any, Coroutine
import discord
from discord.ext import commands
import os
import requests
import json
import random
import asyncio
import datetime
from datetime import datetime
import time
import sys

class Bot(discord.Client):

    def __init__(self, intents, logger):
        super().__init__(intents=intents)
        self.logger = logger

    async def on_ready(self):
        print('Logged on as', self.user)
        await self.change_presence(activity=discord.Game(name="!help"))

    async def on_message(self, message):
        print('Message from {0.author}: {0.content}'.format(message))