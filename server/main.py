from shared import app
from modules.bot.bot import game_blueprint

app.register_blueprint(game_blueprint, url_prefix="/game")
if __name__ == "__main__":

    app.run(debug=True)