from shared import app,  bot, AUTHORIZED_USERS, bot_running, discord_oauth, db, token_manager
from flask import request, jsonify, redirect, url_for, session
import functools
# def requires_admin_authorization(view):
#     """
#     A decorator for Flask views to ensure the user is authorized through Discord OAuth2 and
#     is also an admin user (as per the AUTHORIZED_USERS list).
#     """

#     @functools.wraps(view)
#     def wrapper(*args, **kwargs):
#         # First, check if the user is authorized
#         if not current_app.discord.authorized:
#             raise exceptions.Unauthorized

#         # Then check if the authorized user is an admin
#         user = current_app.discord.fetch_user()
#         if str(user.id) not in AUTHORIZED_USERS:
#            return view(Unauthorized), 401

#         return view(*args, **kwargs)

#     return wrapper


def token_required(f):
    """
    A decorator for Flask endpoints to ensure the user is authorized through Discord OAuth2.
    """
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        token = None

        if 'Authorization' in request.headers:
            token = request.headers['Authorization']

        if not token:
            return jsonify({'message': 'Token is missing!'}), 401
        
        try:
            if not token_manager.is_token_valid(token):
                return jsonify({'message': 'Token is invalid!'}), 401
            elif token_manager.is_token_expired(token):
                return f(*args, **kwargs, expired=True)
            else:
                return f(*args, **kwargs)
        except Exception as e:
            return jsonify({'message': str(e)}), 401
        

    return wrapper


def admin_only(f):
    """
    A decorator for Flask endpoints to ensure the user is authorized through Discord OAuth2 and
    is also an admin user (as per the AUTHORIZED_USERS list).
    """
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        token = None

        if 'Authorization' in request.headers:
            token = request.headers['Authorization']

        if not token:
            return jsonify({'message': 'Token is missing!'}), 401
        
        try:
            if not token_manager.is_token_valid(token):
                return jsonify({'message': 'Token is invalid!'}), 401
            elif token_manager.is_token_expired(token):
                return f(*args, **kwargs, expired=True)
            else:
                return f(*args, **kwargs)
        except Exception as e:
            return jsonify({'message': str(e)}), 401
        

    return wrapper
