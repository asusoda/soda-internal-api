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
@auth_required
@error_handler
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


@users_blueprint.route("/createUser", methods=["POST"])
@auth_required
@error_handler
def create_user():
    user_email = request.args.get('email')
    user_name = request.args.get('name')
    user_asu_id = request.args.get('asu_id')
    user_academic_standing = request.args.get('academic_standing')
    try:
        db = next(db_connect.get_db())
        user = User(
            email=user_email,
            name=user_name,
            asu_id=user_asu_id,
            academic_standing=user_academic_standing
        )
        db.add(user)
        db.commit()
        db.close()
        return jsonify({"message": "User created successfully."}), 201
    except Exception as e:
        db.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()


@users_blueprint.route("/user", methods=["GET", "POST"])
@auth_required
@error_handler
def user():
    # Get the user email from query parameters for GET request or from POST data
    user_email = request.args.get('email') if request.method == "GET" else request.json.get('email')

    if not user_email:
        return jsonify({"error": "Email is required."}), 400

    db = next(db_connect.get_db())

    try:
        # Query the user by email
        user = db.query(User).filter_by(email=user_email).first()

        # Handle GET request - return user info if found
        if request.method == "GET":
            if not user:
                return jsonify({"error": "User not found."}), 404

            user_data = {
                "name": user.name,
                "email": user.email,
                "uuid": user.uuid,
                "asu_id": user.asu_id,
                "academic_standing": user.academic_standing,
                "major": user.major
            }
            return jsonify(user_data), 200

        # Handle POST request - update user info or create a new user if not found
        elif request.method == "POST":
            data = request.json

            if user:
                # Update user fields only if they are provided
                if 'name' in data:
                    user.name = data['name']
                if 'asu_id' in data:
                    user.asu_id = data['asu_id']
                if 'academic_standing' in data:
                    user.academic_standing = data['academic_standing']
                if 'major' in data:
                    user.major = data['major']

                db.commit()
                return jsonify({"message": "User information updated successfully."}), 200

            else:
                # Create a new user if not found
                new_user = User(
                    name=data.get('name'),
                    email=user_email,
                    asu_id=data.get('asu_id'),
                    academic_standing=data.get('academic_standing'),
                    major=data.get('major')
                )

                db.add(new_user)
                db.commit()
                return jsonify({"message": "User created successfully."}), 201

    except Exception as e:
        db.rollback()  # Rollback in case of any error
        return jsonify({"error": str(e)}), 500

    except Exception as e:
        db.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()
