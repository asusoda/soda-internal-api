from flask import jsonify, request, Blueprint
import json

points_blueprint = Blueprint('points', __name__, template_folder=None, static_folder=None)

