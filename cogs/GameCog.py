
from discord.ext import commands
from discord.ext import tasks
from typing import Optional, List, Dict, Any, Union, Tuple, Callable, Awaitable

from utils.JeprodyGame import JeopardyGame
from utils.Team import Team
from utils.JeprodyQuestion import JeopardyQuestion

import os
import requests
import json
import random
import uuid
import discord
import logging


class GameCog(commands.Cog):
 
        def __init__(self, bot, logger) -> None:
            self.bot    = bot
            self.logger = logger
            self.game = JeopardyGame(game_data=json.load(open('game.json', 'r')))
            self.teams : Optional[Team] = []
            self.questions : Optional[JeopardyQuestion] = []
            for team in self.game.teams:
                self.logger.info(f"Team: {team}")
                self.teams.append(Team(team))
            for question in self.game.get_questions():
                self.logger.info(f"Question: {question}")
                self.questions.append(question)

             

        def set_game(self, game):
                if self.game is None:
                        self.game = game
                else:
                        raise Exception("Game already set. Clear the exisiting game first.")
                
        def clear_game(self):
                self.game = None


        
        
        


     