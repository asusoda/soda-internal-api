
from discord.ext import commands
from discord.ext import tasks
from typing import Optional, List, Dict, Any, Union, Tuple, Callable, Awaitable
import discord
import random
import asyncio
from utils.Jeopardy import JeopardyGame
from utils.Team import Team


class GameCog(commands.Cog):
 
        def __init__(self, bot) -> None:
            self.bot = bot
            self.game = None

        
        def set_game(self, game):
            self.game = game

        def get_game(self):
            return self.game
        

        def clear_game(self):
                self.game = None

        


        
        
        


     