from shared import app, bot, discord_oauth, AUTHORIZED_USERS, bot_running
from routes.api import *
from routes.views import *

if __name__ == "__main__":
    app.run(debug=True)


