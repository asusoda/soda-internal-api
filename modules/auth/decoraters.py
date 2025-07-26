from shared import tokenManger
from flask import request, jsonify
from dotenv import load_dotenv
import functools
import os


def auth_required(f):
    """
    A decorator for Flask endpoints to ensure the user is authorized through Discord OAuth2.
    """

    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        token = None

        if "Authorization" in request.headers:
            token = request.headers["Authorization"].split(" ")[
                1
            ]  # Extract the token from the Authorization header

        if not token:
            print("Token is missing")
            return jsonify({"message": "Token is missing!"}), 401

        try:
            if not tokenManger.is_token_valid(token):
                print("Token is invalid")
                return jsonify({"message": "Token is invalid!"}), 401
            elif tokenManger.is_token_expired(token):
                print("Token is expired")
                return jsonify({"message": "Token is expired!"}), 403
            else:
                return f(*args, **kwargs)
        except Exception as e:
            return jsonify({"message": str(e)}), 401

    return wrapper


def low_level_authentication(f):
    """
    A decorator for Flask endpoints to ensure the user is authorized through a low-level authentication mechanism.

    This is a very badly designed and implemented auth mechanism. It is intended to be used only while the authentication mechanism is being developed.
    """
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
       load_dotenv()
       token = request.headers.get("Authorization")
       if token == os.environ["SUPER_SECRET_PASSWORD"]:
            return f(*args, **kwargs)
       else:
            return jsonify({"message": "Unauthorized"}), 401
       
    return wrapper


def error_handler(f):
    """
    A decorator for Flask endpoints to handle any exceptions that occur during their execution.
    """

    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    return wrapper
