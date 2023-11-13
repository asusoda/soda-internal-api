from shared import bot, app
from routes.api import *
from routes.views import *
import random
import discord
from cogs.BasicCog import BasicCog
                


if __name__ == "__main__":
    app.run(debug=True)

