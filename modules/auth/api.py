from flask import request, jsonify, Blueprint, redirect, current_app
from shared import config, bot, db, tokenManger
from modules.auth.decoraters import auth_required
import requests

auth_blueprint = Blueprint("auth", __name__, template_folder=None, static_folder=None)
CLIENT_ID = config.CLIENT_ID
SECRET_KEY = config.CLIENT_SECRET
REDIRECT_URI = config.REDIRECT_URI
GUILD_ID = 762811961238618122


@auth_blueprint.route("/login", methods=["GET"])
def login():
    return redirect(
        f"https://discord.com/oauth2/authorize?client_id={CLIENT_ID}&redirect_uri={REDIRECT_URI}&response_type=code&scope=identify%20guilds"
    )


@auth_blueprint.route("/callback", methods=["GET"])
def callback():
    code = request.args.get("code")
    if not code:
        return jsonify({"error": "No authorization code provided"}), 400
    print(
        {
            "client_id": CLIENT_ID,
            "client_secret": SECRET_KEY,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT_URI,
        }
    )
    token_response = requests.post(
        "https://discord.com/api/v10/oauth2/token",
        data={
            "client_id": CLIENT_ID,
            "client_secret": SECRET_KEY,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT_URI,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    token_response_data = token_response.json()
    print("Token Response: ", token_response_data)
    if "access_token" in token_response_data:
        access_token = token_response_data["access_token"]

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }
        user_response = requests.get(
            "https://discord.com/api/v10/users/@me", headers=headers
        )
        user_info = user_response.json()
        user_id = user_info["id"]

        print("User Info: ", user_info)
        if bot.check_officer(user_id):
            name = bot.get_name(user_id)
            code = tokenManger.generate_token(username=name)
            full_url = f"{config.CLIENT_URL}/auth/?code={code}"
            print(full_url)
            return redirect(full_url)
        else:
            full_url = f"{config.CLIENT_URL}/auth/?error=Unauthorized Access"

    else:
        return jsonify({"error": "Failed to retrieve access token"}), 400


@auth_blueprint.route("/validToken", methods=["GET"])
def valid_token():
    token = request.headers.get("Authorization").split(" ")[
        1
    ]  # Extract the token from the Authorization header
    if tokenManger.is_token_valid(token):
        if tokenManger.is_token_expired(token):
            return jsonify(
                {
                    "status": "success",
                    "valid": True,
                    "expired": True,
                }
            ), 200
        else:
            return jsonify(
                {
                    "status": "success",
                    "valid": True,
                    "expired": False,
                }
            ), 200
    else:
        return jsonify(
            {
                "status": "error",
                "valid": False,
            }
        ), 401


@auth_blueprint.route("/refresh", methods=["GET"])
def refresh_token():
    token = request.headers.get("Authorization").split(" ")[
        1
    ]  # Extract the token from the Authorization header
    if tokenManger.is_token_valid(token):
        if tokenManger.is_token_expired(token):
            new_token = tokenManger.refresh_token(token)
            return jsonify(
                {
                    "status": "success",
                    "valid": True,
                    "expired": True,
                    "token": new_token,
                }
            ), 200
        else:
            return jsonify(
                {
                    "status": "success",
                    "valid": True,
                    "expired": False,
                    "token": token,
                    "error": "Token is not expired",
                }
            ), 400
    else:
        return jsonify(
            {
                    "status": "error", 
                    "valid": False, 
                    "error": "Invalid token"
            }
        ), 401


@auth_blueprint.route("/name", methods=["GET"])
@auth_required
def get_name():
    autorisation = request.headers.get("Authorization").split(" ")[
        1
    ]  # Extract the token from the Authorization header
    return jsonify({"name": tokenManger.retrieve_username(autorisation)}), 200


@auth_blueprint.route("/success")
def success():
    return "You have successfully logged in with Discord!"
