from shared import tokenManger
from flask import request, jsonify, session, redirect, url_for, session
from dotenv import load_dotenv
import functools
import os
from functools import wraps


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
                    return redirect(url_for('auth.login'))
                elif tokenManger.is_token_expired(session['token']):
                    session.pop('token', None)
                    return redirect(url_for('auth.login'))
                return f(*args, **kwargs)
            except Exception as e:
                session.pop('token', None)
                return redirect(url_for('auth.login'))

        # If no session, check Authorization header (for API calls)
        token = None
        if "Authorization" in request.headers:
            token = request.headers["Authorization"].split(" ")[1]

        if not token:
            return redirect(url_for('auth.login'))

        try:
            if not tokenManger.is_token_valid(token):
                return jsonify({"message": "Token is invalid!"}), 401
            elif tokenManger.is_token_expired(token):
                return jsonify({"message": "Token is expired!"}), 403
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
