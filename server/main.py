from shared import app
from server.modules.bot.api import game_blueprint

app.register_blueprint(game_blueprint, url_prefix="/game")
if __name__ == "__main__":

    app.run(debug=True)