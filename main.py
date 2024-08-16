from shared import app, config

# from modules.bot.api import game_blueprint
from modules.public.api import public_blueprint
from modules.auth.api import auth_blueprint

# app.register_blueprint(game_blueprint, url_prefix="/game")
app.register_blueprint(public_blueprint, url_prefix="/")
app.register_blueprint(auth_blueprint, url_prefix="/auth")
if __name__ == "__main__":
    # if config.is_prod:
    #     app.run(debug=False, host="0.0.0.0", port=8080)
    # else:
    app.run(debug=True)
