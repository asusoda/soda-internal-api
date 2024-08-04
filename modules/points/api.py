from flask import jsonify, request, Blueprint
import json

points_blueprint = Blueprint('points', __name__, template_folder=None, static_folder=None)

# User model 
# Name , Email , Academic Year , Points Earned , Discord Username, UID

# Points model : Parameters (int points, string event, timestamp time, string awarder Officer name)


