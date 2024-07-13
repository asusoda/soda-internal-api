from shared import app, config
from modules.bot.api import game_blueprint

app.register_blueprint(game_blueprint, url_prefix="/game")
if __name__ == "__main__":
    if config.is_prod:
        app.run(debug=False, host="0.0.0.0", port=8080)
    else:
      app.run(debug=True)