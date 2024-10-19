import logging
import sys
import time
import re
import os
from flask import Blueprint, jsonify, request
from modules.auth.decoraters import auth_required, error_handler
from modules.points.models import User, Points
from shared import config, db_connect

# Flask Blueprint for users
users_blueprint = Blueprint("users", __name__, template_folder=None, static_folder=None)

@users_blueprint.route("/", methods=["GET"])
def users_index():
    return jsonify({"message": "users api"}), 200

@users_blueprint.route("/viewUser", methods=["GET"])
def view_user():
    # Get the user identifier from the query parameters (can be email or UUID)
    user_identifier = request.args.get('user_identifier')

    if not user_identifier:
        return jsonify({"error": "User identifier (email or UUID) is required."}), 400

    db = next(db_connect.get_db())
    
    try:
        # Query the user by either email or UUID
        user = db.query(User).filter((User.email == user_identifier) | (User.uuid == user_identifier)).first()

        if not user:
            return jsonify({"error": "User not found."}), 404

        # Query the points earned by the user
        points_records = db.query(Points).filter_by(user_email=user.email).all()

        # Prepare the points data
        points_data = [
            {
                "points": record.points,
                "event": record.event,
                "timestamp": record.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                "awarded_by_officer": record.awarded_by_officer
            }
            for record in points_records
        ]

        # Prepare the user data along with the points
        user_data = {
            "name": user.name,
            "uuid": user.uuid,
            "academic_standing": user.academic_standing,
            "major": user.major,
            "points_earned": points_data
        }

        return jsonify(user_data), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()


@users_blueprint.route("/user", methods=["GET", "POST"])
def user():
    # Get the user email from query parameters for GET request or from POST data
    user_email = request.args.get('email') if request.method == "GET" else request.json.get('email')

    if not user_email:
        return jsonify({"error": "Email is required."}), 400

    db = next(db_connect.get_db())

    try:
        # Query the user by email
        user = db.query(User).filter_by(email=user_email).first()

        if not user:
            return jsonify({"error": "User not found."}), 404

        # Handle GET request - return user info
        if request.method == "GET":
            user_data = {
                "name": user.name,
                "email": user.email,
                "uuid": user.uuid,
                "asu_id": user.asu_id,
                "academic_standing": user.academic_standing,
                "major": user.major
            }
            return jsonify(user_data), 200

        # Handle POST request - update user info
        elif request.method == "POST":
            data = request.json

            # Update user fields only if they are provided
            if 'name' in data:
                user.name = data['name']
            if 'asu_id' in data:
                user.asu_id = data['asu_id']
            if 'academic_standing' in data:
                user.academic_standing = data['academic_standing']
            if 'major' in data:
                user.major = data['major']

            # Commit the updates to the database
            db.commit()

            return jsonify({"message": "User information updated successfully."}), 200

    except Exception as e:
        db.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()

@users_blueprint.route("/submit-form", methods=["POST"])
def handle_form_submission():
    try:
        # Get the JSON data from the POST request
        data = request.get_json()

        # Extract full name and role from the form submission
        discordID = data.get('discordID')
        role = data.get('role')

    except Exception as e:
        return jsonify({'error': str(e)}), 500
    
    return jsonify({"message": "recieved id: " + discordID + " and role: " + role}), 200