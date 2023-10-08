import discord
from discord.ext import commands, ipc

class MyBot(commands.Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def set_token(self, token):
        self.token = token

    async def on_ready(self):
        """Called upon the READY event"""
        print("Bot is ready.")
        for guild in self.guilds:
            print(guild.name)


    def run(self):
        """Starts the bot"""
        super().run(self.token, reconnect=True)