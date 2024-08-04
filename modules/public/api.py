from flask import jsonify, request, Blueprint
import json

public_blueprint = Blueprint('public', __name__, template_folder=None, static_folder=None)

@public_blueprint.route('/', methods=['GET'])
def index():
    return jsonify({"message": "Welcome to SoDA's trusty internal API"}), 200


@public_blueprint.route('/getnextevent', methods=['GET'])
def get_next_event():
    pass