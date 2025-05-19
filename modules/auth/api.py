from flask import request, jsonify, Blueprint, redirect, current_app
from shared import config, tokenManger, logger
from modules.auth.decoraters import auth_required, error_handler
import requests

auth_blueprint = Blueprint("auth", __name__, template_folder=None, static_folder=None)
CLIENT_ID = config.AUTH_CLIENT_ID
CLIENT_SECRET = config.AUTH_CLIENT_SECRET
REDIRECT_URI = config.AUTH_REDIRECT_URI
GUILD_ID = 762811961238618122

logger.info(f"Auth API using CLIENT_ID: {CLIENT_ID} and REDIRECT_URI: {REDIRECT_URI}")

@auth_blueprint.route("/login", methods=["GET"])
def login():
    logger.info(f"Redirecting to Discord OAuth login for client_id: {CLIENT_ID}")
    return redirect(
        f"https://discord.com/oauth2/authorize?client_id={CLIENT_ID}&redirect_uri={REDIRECT_URI}&response_type=code&scope=identify%20guilds"
    )

@auth_blueprint.route("/validToken", methods=["GET"])
@auth_required
def validToken():
    token = request.headers.get("Authorization").split(" ")[
        1
    ]  # Extract the token from the Authorization header
    if tokenManger.is_token_valid(token):
        return jsonify({"status": "success", "valid": True, "expired": False}), 200
    else:
        return jsonify({"status": "error", "valid": False}), 401

@auth_blueprint.route("/callback", methods=["GET"])
def callback():
    bot = current_app.auth_bot if hasattr(current_app, 'auth_bot') else None
    if not bot or not bot.is_ready():
        logger.error("Auth bot is not available or not ready for /callback")
        return jsonify({"error": "Authentication service temporarily unavailable. Bot not ready."}), 503

    code = request.args.get("code")
    if not code:
        logger.warning("No authorization code provided in /callback")
        return jsonify({"error": "No authorization code provided"}), 400
    
    logger.info("Received authorization code, exchanging for token.")
    token_response = requests.post(
        "https://discord.com/api/v10/oauth2/token",
        data={
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT_URI,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    token_response_data = token_response.json()

    if "access_token" in token_response_data:
        access_token = token_response_data["access_token"]
        logger.info("Access token received, fetching user info.")
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }
        user_response = requests.get(
            "https://discord.com/api/v10/users/@me", headers=headers
        )
        user_info = user_response.json()
        user_id = user_info.get("id")

        if not user_id:
            logger.error("Failed to retrieve user ID from Discord user info.")
            return jsonify({"error": "Failed to retrieve user information"}), 500

        logger.info(f"User ID {user_id} obtained. Checking officer status via auth_bot.")
        if bot.check_officer(user_id):
            name = bot.get_name(user_id)
            logger.info(f"User {name} (ID: {user_id}) is an officer. Generating internal token.")
            internal_token = tokenManger.generate_token(username=name)
            full_url = f"{config.CLIENT_URL}/auth/?code={internal_token}"
            logger.info(f"Redirecting officer {name} to client URL with token.")
            return redirect(full_url)
        else:
            logger.warning(f"User ID {user_id} is not an officer. Unauthorized access.")
            full_url = f"{config.CLIENT_URL}/auth/?error=Unauthorized%20Access"
            return redirect(full_url)
    else:
        logger.error(f"Failed to retrieve access token from Discord: {token_response_data}")
        return jsonify({"error": "Failed to retrieve access token"}), 400


@auth_blueprint.route("/validateToken", methods=["GET"])
def valid_token():
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return jsonify({"status": "error", "message": "Authorization header missing or malformed"}), 401
    
    token = auth_header.split(" ")[1]

    if tokenManger.is_token_valid(token):
        if tokenManger.is_token_expired(token):
            logger.info(f"Token is valid but expired.")
            return jsonify(
                {"status": "success", "valid": True, "expired": True}
            ), 200
        else:
            logger.info(f"Token is valid and not expired.")
            return jsonify(
                {"status": "success", "valid": True, "expired": False}
            ), 200
    else:
        logger.warning(f"Token validation failed (invalid).")
        return jsonify(
            {"status": "error", "valid": False, "message": "Token is invalid"}
        ), 401


@auth_blueprint.route("/refresh", methods=["GET"])
@auth_required
def refresh_token():
    token = request.headers.get("Authorization").split(" ")[1]
    username = tokenManger.retrieve_username(token)

    if not username:
        logger.warning("Refresh attempt for token with no associated username or invalid token.")
        return jsonify({"status": "error", "valid": False, "error": "Invalid token for refresh"}), 401

    if tokenManger.is_token_expired(token):
        logger.info(f"Refreshing expired token for user: {username}")
        new_token = tokenManger.refresh_token(token)
        return jsonify(
            {"status": "success", "valid": True, "expired": False, "token": new_token}
        ), 200
    else:
        logger.info(f"Refresh attempt for a token that is not expired. User: {username}")
        return jsonify(
            {
                "status": "success",
                "valid": True,
                "expired": False,
                "token": token,
                "message": "Token is not expired, refresh not needed.",
            }
        ), 200


@auth_blueprint.route("/appToken", methods=["GET"])
@auth_required
@error_handler
def generate_app_token():
    token = request.headers.get("Authorization").split(" ")[1]
    appname = request.args.get("appname")
    if not appname:
        return jsonify({"error": "appname query parameter is required"}), 400
    
    username = tokenManger.retrieve_username(token)
    if not username:
         return jsonify({"error": "Invalid user token"}), 401

    logger.info(f"Generating app token for user {username}, app: {appname}")
    app_token_value = tokenManger.genreate_app_token(username, appname)
    return jsonify({"app_token": app_token_value}), 200


@auth_blueprint.route("/name", methods=["GET"])
@auth_required
def get_name():
    autorisation = request.headers.get("Authorization").split(" ")[
        1
    ]  # Extract the token from the Authorization header
    username = tokenManger.retrieve_username(autorisation)
    if username:
        logger.info(f"Retrieved name for current token: {username}")
        return jsonify({"name": username}), 200
    else:
        logger.warning("Could not retrieve name from token.")
        return jsonify({"error": "Unable to retrieve username from token"}), 401


@auth_blueprint.route("/logout", methods=["GET"])
@auth_required
def logout():
    token = request.headers.get("Authorization").split(" ")[
        1
    ]  # Extract the token from the Authorization header
    tokenManger.delete_token(token)
    logger.info(f"User token blacklisted (logged out).")
    return jsonify({"message": "Logged out"}), 200


@auth_blueprint.route("/success")
def success():
    return "You have successfully logged in with Discord! (This is a generic success page)"
