from flask import request, jsonify, Blueprint, redirect, current_app

import functools
from shared import token_manager, discord

auth_blueprint = Blueprint('auth', __name__, template_folder=None, static_folder=None)

@auth_blueprint.route('/login', methods=['GET'])
def login():
    return discord.create_session()

@auth_blueprint.route('/callback', methods=['GET'])
def callback():
    code = request.args.get('code')
    if code:
        username = discord.get_username_from_code(code)
        token_manager.get_or_create_token(username)
        return redirect(f'{current_app.config['CLIENT_URL']}/?token={token_manager.get_token(username)}')
    
        
@auth_blueprint.route('/login', methods=['POST'])
def login():
    token = request.json.get('token')
    if token:
        if token_manager.is_token_valid(token):
            return jsonify({'message': 'Successfully logged in!'}), 200
        else:
            return jsonify({'message': 'Token is invalid!'}), 401
    else:
        return jsonify({'message': 'Token is missing!'}), 401
    

    
@auth_blueprint.route('/logout', methods=['POST'])
def logout():
    token = request.json.get('token')
    if token:
        if token_manager.is_token_valid(token):
            return jsonify({'message': 'Successfully logged out!'}), 200
        else:
            return jsonify({'message': 'Token is invalid!'}), 401
    else:
        return jsonify({'message': 'Token is missing!'}), 401
    
