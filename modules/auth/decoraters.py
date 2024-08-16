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
            token = request.headers["Authorization"]

        if not token:
            return jsonify({"message": "Token is missing!"}), 401

        try:
            if not tokenManger.is_token_valid(token):
                return jsonify({"message": "Token is invalid!"}), 401
            elif tokenManger.is_token_expired(token):
                return f(*args, **kwargs, expired=True)
            else:
                return f(*args, **kwargs)
        except Exception as e:
            return jsonify({"message": str(e)}), 401

    return wrapper
