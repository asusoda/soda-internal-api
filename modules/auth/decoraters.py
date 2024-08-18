from shared import tokenManger
from flask import request, jsonify
import functools


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
            return jsonify({"message": "Token is missing!"}), 401

        try:
            if not tokenManger.is_token_valid(token):
                return jsonify({"message": "Token is invalid!"}), 401
            elif tokenManger.is_token_expired(token):
                return jsonify({"message": "Token is expired!"}), 403
            else:
                return f(*args, **kwargs)
        except Exception as e:
            return jsonify({"message": str(e)}), 401
        
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
        