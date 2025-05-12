from shared import tokenManger
from flask import request, jsonify, session, redirect, url_for, session
from shared import bot, db_connect
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


def auth_officer(f):
    """
    A decorator for Flask endpoints to ensure the user is an officer of the organization.
    """
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        request_path = request.path.split("/")
        if len(request_path) > 2:
            org_prefix = request_path[1]
