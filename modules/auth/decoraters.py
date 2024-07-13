from shared import token_manager
from flask import request, jsonify
import functools



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
