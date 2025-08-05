from shared import tokenManger
from flask import request, jsonify, session, current_app
from shared import db_connect
from dotenv import load_dotenv
import functools
import os
from functools import wraps
import logging
from shared import config

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
        print(f"🔍 [DEBUG] superadmin_required called for function: {f.__name__}")
        print(f"🔍 [DEBUG] Request method: {request.method}")
        print(f"🔍 [DEBUG] Request headers: {dict(request.headers)}")
        
        # First check authentication
        token = None
        
        # Check session cookie first
        print(f"🔍 [DEBUG] Checking session token...")
        if session.get('token'):
            token = session.get('token')
            print(f"🔍 [DEBUG] Found session token: {token[:20]}...")
            try:
                print(f"🔍 [DEBUG] Validating session token...")
                if not tokenManger.is_token_valid(token):
                    print(f"❌ [DEBUG] Session token is invalid!")
                    return jsonify({"message": "Token is invalid!"}), 401
                elif tokenManger.is_token_expired(token):
                    print(f"❌ [DEBUG] Session token is expired!")
                    return jsonify({"message": "Token is expired!"}), 403
                
                print(f"🔍 [DEBUG] Session token is valid, checking role...")
                user_role = session.get('user', {}).get('role')
                print(f"🔍 [DEBUG] User role from session: {user_role}")
                
                # Check superadmin role from session
                if user_role != 'admin':
                    print(f"❌ [DEBUG] User role '{user_role}' is not admin!")
                    return jsonify({"message": "Superadmin access required!"}), 403
                
                print(f"✅ [DEBUG] Session authentication successful!")
                return f(*args, **kwargs)
            except Exception as e:
                print(f"❌ [DEBUG] Error validating session token: {e}")
                return jsonify({"message": str(e)}), 401
        
        # Check Authorization header (for API calls)
        print(f"🔍 [DEBUG] No session token, checking Authorization header...")
        if "Authorization" in request.headers:
            auth_header = request.headers["Authorization"]
            print(f"🔍 [DEBUG] Authorization header: {auth_header[:50]}...")
            if auth_header.startswith("Bearer "):
                token = auth_header.split(" ")[1]
                print(f"🔍 [DEBUG] Extracted Bearer token: {token[:20]}...")
            else:
                print(f"❌ [DEBUG] Authorization header doesn't start with 'Bearer '")
                return jsonify({"message": "Invalid Authorization header format!"}), 401
        
        if not token:
            print(f"❌ [DEBUG] No token found in session or Authorization header!")
            return jsonify({"message": "Authentication required!"}), 401

        try:
            print(f"🔍 [DEBUG] Validating API token...")
            if not tokenManger.is_token_valid(token):
                print(f"❌ [DEBUG] API token is invalid!")
                return jsonify({"message": "Token is invalid!"}), 401
            elif tokenManger.is_token_expired(token):
                print(f"❌ [DEBUG] API token is expired!")
                return jsonify({"message": "Token is expired!"}), 403
            
            print(f"🔍 [DEBUG] API token is valid, decoding...")
            # For API calls, we need to verify superadmin status from the token
            token_data = tokenManger.decode_token(token)
            if not token_data:
                print(f"❌ [DEBUG] Failed to decode token data!")
                return jsonify({"message": "Invalid token data!"}), 401
            
            print(f"🔍 [DEBUG] Token data: {token_data}")
            
            # Try to get discord_id directly from token (more secure)
            discord_id = token_data.get('discord_id')
            if discord_id:
                print(f"🔍 [DEBUG] Found discord_id in token: {discord_id}")
                # Direct lookup using discord_id (secure and efficient)
                try:
                    # Get the auth bot from Flask app context
                    print(f"🔍 [DEBUG] Getting auth bot from Flask app context...")
                    auth_bot = current_app.auth_bot if hasattr(current_app, 'auth_bot') else None
                    if not auth_bot:
                        print(f"❌ [DEBUG] Auth bot not found in Flask app context!")
                        return jsonify({"message": "Bot not available for verification!"}), 503
                    
                    if not auth_bot.is_ready():
                        print(f"❌ [DEBUG] Auth bot is not ready!")
                        return jsonify({"message": "Bot not available for verification!"}), 503
                    
                    print(f"🔍 [DEBUG] Auth bot is ready, checking officer status...")
                    print(f"🔍 [DEBUG] Checking if user {discord_id} is officer in any guild...")
                    officer_guilds = auth_bot.check_officer(str(discord_id), config.SUPERADMIN_USER_ID)
                    print(f"🔍 [DEBUG] Officer guilds result: {officer_guilds}")
                    
                    if not officer_guilds:  # If user is not officer in any organization
                        print(f"❌ [DEBUG] User is not an officer in any organization!")
                        return jsonify({"message": "Superadmin access required!"}), 403
                    
                    print(f"✅ [DEBUG] User is an officer in {len(officer_guilds)} guild(s)!")
                except Exception as e:
                    print(f"❌ [DEBUG] Error verifying superadmin status: {e}")
                    import traceback
                    traceback.print_exc()
                    return jsonify({"message": f"Error verifying superadmin status: {str(e)}"}), 401
            else:
                print(f"🔍 [DEBUG] No discord_id in token, trying username lookup...")
                # Fallback to username lookup for older tokens (less secure)
                username = token_data.get('username')
                if not username:
                    print(f"❌ [DEBUG] Token missing both discord_id and username!")
                    return jsonify({"message": "Token missing user identification!"}), 401
                
                print(f"🔍 [DEBUG] Using username for lookup: {username}")
                # Find the user's discord_id by looking through the bot's guild members
                # This is a reverse lookup: username -> discord_id (less secure)
                user_discord_id = None
                try:
                    # Get the auth bot from Flask app context
                    print(f"🔍 [DEBUG] Getting auth bot for username lookup...")
                    auth_bot = current_app.auth_bot if hasattr(current_app, 'auth_bot') else None
                    if not auth_bot or not auth_bot.is_ready():
                        print(f"❌ [DEBUG] Auth bot not available for username lookup!")
                        return jsonify({"message": "Bot not available for verification!"}), 503
                    
                    print(f"🔍 [DEBUG] Searching through guild members for username: {username}")
                    for guild in auth_bot.guilds:
                        print(f"🔍 [DEBUG] Checking guild: {guild.name} ({guild.id})")
                        for member in guild.members:
                            display_name = member.nick if member.nick else member.name
                            if display_name == username:
                                user_discord_id = member.id
                                print(f"✅ [DEBUG] Found user in guild {guild.name}: {user_discord_id}")
                                break
                        if user_discord_id:
                            break
                    
                    if not user_discord_id:
                        print(f"❌ [DEBUG] User not found in any Discord guild!")
                        return jsonify({"message": "User not found in Discord!"}), 401
                    
                    print(f"🔍 [DEBUG] Checking officer status for discord_id: {user_discord_id}")
                    # Check if user is still an officer using the bot's check_officer method
                    officer_guilds = auth_bot.check_officer(str(user_discord_id))
                    print(f"🔍 [DEBUG] Officer guilds result: {officer_guilds}")
                    if not officer_guilds:  # If user is not officer in any organization
                        print(f"❌ [DEBUG] User is not an officer in any organization!")
                        return jsonify({"message": "Superadmin access required!"}), 403
                    
                    print(f"✅ [DEBUG] User is an officer in {len(officer_guilds)} guild(s)!")
                        
                except Exception as e:
                    print(f"❌ [DEBUG] Error in username lookup: {e}")
                    import traceback
                    traceback.print_exc()
                    return jsonify({"message": f"Error verifying superadmin status: {str(e)}"}), 401
                
            print(f"✅ [DEBUG] Superadmin authentication successful!")
            return f(*args, **kwargs)
        except Exception as e:
            print(f"❌ [DEBUG] General error in superadmin_required: {e}")
            import traceback
            traceback.print_exc()
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
