from shared import bot, app, db
from routes.views import *
from routes.api import *
from routes.game_api import *
import os 
import random
import discord





if __name__ == "__main__":
    app.run(debug=True)

