from shared import tokenManger
from flask import request, jsonify, session, current_app
from shared import db_connect
from dotenv import load_dotenv
import functools
import os
from functools import wraps
import logging

logger = logging.getLogger(__name__)


def auth_required(f):
    """
    A decorator for Flask endpoints to ensure the user is authenticated.
    Checks both session cookies and Authorization headers.
    """
    @wraps(f)
    def wrapper(*args, **kwargs):
        # Check session cookie first
        if session.get('token'):
            try:
                if not tokenManger.is_token_valid(session['token']):
                    session.pop('token', None)
                    return jsonify({"message": "Session token is invalid!"}), 401
                elif tokenManger.is_token_expired(session['token']):
                    session.pop('token', None)
                    return jsonify({"message": "Session token has expired!"}), 401
                return f(*args, **kwargs)
            except Exception as e:
                session.pop('token', None)
                return jsonify({"message": "Session authentication failed!"}), 401

        # If no session, check Authorization header (for API calls)
        token = None
        if "Authorization" in request.headers:
            token = request.headers["Authorization"].split(" ")[1]

        if not token:
            return jsonify({"message": "Authentication required!"}), 401

        try:
            if not tokenManger.is_token_valid(token):
                return jsonify({"message": "Token is invalid!"}), 401
            elif tokenManger.is_token_expired(token):
                return jsonify({"message": "Token is expired!"}), 403
            return f(*args, **kwargs)
        except Exception as e:
            return jsonify({"message": str(e)}), 401

    return wrapper


def superadmin_required(f):
    """
    A decorator for API endpoints to ensure the user is a superadmin.
    Checks authentication and superadmin role.
    """
    @wraps(f)
    def wrapper(*args, **kwargs):
        # First check authentication
        token = None
        
        # Check session cookie first
        if session.get('token'):
            token = session.get('token')
            try:
                if not tokenManger.is_token_valid(token):
                    return jsonify({"message": "Token is invalid!"}), 401
                elif tokenManger.is_token_expired(token):
                    return jsonify({"message": "Token is expired!"}), 403
                
                # Check superadmin role from session
                if session.get('user', {}).get('role') != 'admin':
                    return jsonify({"message": "Superadmin access required!"}), 403
                    
                return f(*args, **kwargs)
            except Exception as e:
                return jsonify({"message": str(e)}), 401
        
        # Check Authorization header (for API calls)
        if "Authorization" in request.headers:
            token = request.headers["Authorization"].split(" ")[1]
        
        if not token:
            return jsonify({"message": "Authentication required!"}), 401

        try:
            if not tokenManger.is_token_valid(token):
                return jsonify({"message": "Token is invalid!"}), 401
            elif tokenManger.is_token_expired(token):
                return jsonify({"message": "Token is expired!"}), 403
            
            # For API calls, we need to verify superadmin status from the token
            token_data = tokenManger.decode_token(token)
            if not token_data:
                return jsonify({"message": "Invalid token data!"}), 401
            
            # Try to get discord_id directly from token (more secure)
            discord_id = token_data.get('discord_id')
            if discord_id:
                # Direct lookup using discord_id (secure and efficient)
                try:
                    # Get the auth bot from Flask app context
                    auth_bot = current_app.auth_bot if hasattr(current_app, 'auth_bot') else None
                    if not auth_bot or not auth_bot.is_ready():
                        return jsonify({"message": "Bot not available for verification!"}), 503
                    
                    if not auth_bot.check_officer(str(discord_id)):
                        return jsonify({"message": "Superadmin access required!"}), 403
                except Exception as e:
                    return jsonify({"message": f"Error verifying superadmin status: {str(e)}"}), 401
            else:
                # Fallback to username lookup for older tokens (less secure)
                username = token_data.get('username')
                if not username:
                    return jsonify({"message": "Token missing user identification!"}), 401
                
                # Find the user's discord_id by looking through the bot's guild members
                # This is a reverse lookup: username -> discord_id (less secure)
                user_discord_id = None
                try:
                    # Get the auth bot from Flask app context
                    auth_bot = current_app.auth_bot if hasattr(current_app, 'auth_bot') else None
                    if not auth_bot or not auth_bot.is_ready():
                        return jsonify({"message": "Bot not available for verification!"}), 503
                    
                    for guild in auth_bot.guilds:
                        for member in guild.members:
                            display_name = member.nick if member.nick else member.name
                            if display_name == username:
                                user_discord_id = member.id
                                break
                        if user_discord_id:
                            break
                    
                    if not user_discord_id:
                        return jsonify({"message": "User not found in Discord!"}), 401
                    
                    # Check if user is still an officer using the bot's check_officer method
                    if not auth_bot.check_officer(str(user_discord_id)):
                        return jsonify({"message": "Superadmin access required!"}), 403
                        
                except Exception as e:
                    return jsonify({"message": f"Error verifying superadmin status: {str(e)}"}), 401
                
            return f(*args, **kwargs)
        except Exception as e:
            return jsonify({"message": str(e)}), 401

    return wrapper


def error_handler(f):
    """
    Decorator to handle errors and return JSON error responses.
    """
    
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except Exception as e:
            logger.error(f"Error in {f.__name__}: {str(e)}")
            return jsonify({"error": str(e)}), 500
    
    return wrapper
