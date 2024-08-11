from flask import Flask, jsonify, request, Blueprint
from sqlalchemy.orm import Session
from modules.utils.db import DBConnect
from modules.points.models import User, Points
from shared import db_connect


points_blueprint = Blueprint('points', __name__, template_folder=None, static_folder=None)

@points_blueprint.route('/', methods=['GET'])
def index():
    return jsonify({"message": "Points"}), 200

@points_blueprint.route('/users', methods=['POST'])
def add_user():
    data = request.json
    db = next(db_connect.get_db())
    try:
        user = User(
            name=data['name'],
            email=data['email'],
            academic_standing=data['academic_standing']
        )
        db_user = db_connect.create_user(db, user)
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    finally:
        db.close()
    return jsonify({
        "uuid": db_user.uuid,
        "name": db_user.name,
        "email": db_user.email,
        "academic_standing": db_user.academic_standing
    }), 201

@points_blueprint.route('/points', methods=['POST'])
def add_point():
    data = request.json
    db = next(db_connect.get_db())
    try:
        user_id = data.get('user_id')
        if not user_id:
            user = User(
                name=data['user_name'],
                email=data['user_email'],
                academic_standing=data['user_academic_standing']
            )
            db_user = db_connect.create_user(db, user)
            user_id = db_user.uuid

        point = Points(
            points=data['points'],
            event=data['event'],
            awarded_by_officer=data['awarded_by_officer'],
            user_id=user_id
        )
        db_point = db_connect.create_point(db, point)
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    finally:
        db.close()
    return jsonify({
        "id": db_point.id,
        "points": db_point.points,
        "event": db_point.event,
        "timestamp": db_point.timestamp,
        "awarded_by_officer": db_point.awarded_by_officer,
        "user_id": db_point.user_id
    }), 201

@points_blueprint.route('/users', methods=['GET'])
def get_users():
    db = next(db_connect.get_db())
    try:
        users = db.query(User).all()
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    finally:
        db.close()
    return jsonify([{
        "uuid": user.uuid,
        "name": user.name,
        "email": user.email,
        "academic_standing": user.academic_standing
    } for user in users]), 200

@points_blueprint.route('/points', methods=['GET'])
def get_points():
    db = next(db_connect.get_db())
    try:
        points = db.query(Points).all()
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    finally:
        db.close()
    return jsonify([{
        "id": point.id,
        "points": point.points,
        "event": point.event,
        "timestamp": point.timestamp,
        "awarded_by_officer": point.awarded_by_officer,
        "user_id": point.user_id
    } for point in points]), 200



