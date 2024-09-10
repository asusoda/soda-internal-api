from flask import Flask, jsonify, request, Blueprint
from sqlalchemy.orm import Session
from modules.utils.db import DBConnect
from modules.points.models import User, Points
from shared import db_connect
from sqlalchemy import func

points_blueprint = Blueprint(
    "points", __name__, template_folder=None, static_folder=None
)


@points_blueprint.route("/", methods=["GET"])
def index():
    return jsonify({"message": "Points"}), 200


@points_blueprint.route("/add_user", methods=["POST"])
def add_user():
    data = request.json
    db = next(db_connect.get_db())
    try:
        # Check if user already exists
        existing_user = db.query(User).filter_by(email=data["email"]).first()
        if existing_user:
            return jsonify({"error": "User already exists"}), 400

        # Create a new user
        user = User(
            asu_id=data["asu_id"],
            name=data["name"],
            email=data["email"],
            academic_standing=data["academic_standing"],
            major=data["major"]
        )
        db_user = db_connect.create_user(db, user)
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    finally:
        db.close()
    return jsonify(
        {
            "uuid": db_user.uuid,
            "name": db_user.name,
            "email": db_user.email,
            "academic_standing": db_user.academic_standing,
            "asu_id": db_user.asu_id,
            "major": db_user.major,
        }
    ), 201


@points_blueprint.route("/add_points", methods=["POST"])
def add_points():
    data = request.json
    db = next(db_connect.get_db())
    try:
        # Check if the user exists by email
        user = db.query(User).filter_by(email=data["user_email"]).first()
        if not user:
            # If user doesn't exist, create the user first
            # user = User(
            #     name=data["user_name"],
            #     email=data["user_email"],
            #     academic_standing=data["user_academic_standing"],
            #     asu_id=data["asu_id"],  # Ensure asu_id is provided when creating new user
            #     major=data["major"]
            # )
            # db_user = db_connect.create_user(db, user)
            # user_id = db_user.uuid
            return jsonify({"error": "User does not exist"}), 301
        else:
            user_id = user.uuid

        # Add points to the user
        point = Points(
            points=data["points"],
            event=data["event"],
            awarded_by_officer=data["awarded_by_officer"],
            user_id=user_id,
        )
        db_point = db_connect.create_point(db, point)
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    finally:
        db.close()
    return jsonify(
        {
            "id": db_point.id,
            "points": db_point.points,
            "event": db_point.event,
            "timestamp": db_point.timestamp,
            "awarded_by_officer": db_point.awarded_by_officer,
            "user_id": db_point.user_id,
        }
    ), 201


@points_blueprint.route("/get_users", methods=["GET"])
def get_users():
    db = next(db_connect.get_db())
    try:
        users = db.query(User).all()
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    finally:
        db.close()
    return jsonify(
        [
            {
                "uuid": user.uuid,
                "name": user.name,
                "email": user.email,
                "academic_standing": user.academic_standing,
                "asu_id": user.asu_id,
                "major": user.major,
            }
            for user in users
        ]
    ), 200


@points_blueprint.route("/get_points", methods=["GET"])
def get_points():
    db = next(db_connect.get_db())
    try:
        points = db.query(Points).all()
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    finally:
        db.close()
    return jsonify(
        [
            {
                "id": point.id,
                "points": point.points,
                "event": point.event,
                "timestamp": point.timestamp,
                "awarded_by_officer": point.awarded_by_officer,
                "user_id": point.user_id,
            }
            for point in points
        ]
    ), 200


@points_blueprint.route("/leaderboard", methods=["GET"])
def get_leaderboard():
    db = next(db_connect.get_db())
    try:
        leaderboard = (
            db.query(
                User.name,
                func.coalesce(func.sum(Points.points), 0).label("total_points"),
            )
            .outerjoin(Points)
            .group_by(User.uuid)
            .order_by(
                func.sum(Points.points).desc(), User.name.asc()
            )
            .all()
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    finally:
        db.close()

    return jsonify(
        [{"name": name, "points": total_points} for name, total_points in leaderboard]
    ), 200
