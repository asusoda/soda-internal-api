from shared import app,  bot, AUTHORIZED_USERS, bot_running, discord_oauth, db
from flask_discord import DiscordOAuth2Session, requires_authorization, Unauthorized, current_app, exceptions
import functools

def requires_admin_authorization(view):
    """
    A decorator for Flask views to ensure the user is authorized through Discord OAuth2 and
    is also an admin user (as per the AUTHORIZED_USERS list).
    """

    @functools.wraps(view)
    def wrapper(*args, **kwargs):
        # First, check if the user is authorized
        if not current_app.discord.authorized:
            raise exceptions.Unauthorized

        # Then check if the authorized user is an admin
        user = current_app.discord.fetch_user()
        if str(user.id) not in AUTHORIZED_USERS:
           return view(Unauthorized), 401

        return view(*args, **kwargs)

    return wrapper
