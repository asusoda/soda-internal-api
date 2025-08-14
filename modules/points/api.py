import csv
from flask import Flask, jsonify, request, Blueprint
from sqlalchemy.orm import Session
from modules.auth.decoraters import auth_required
from modules.utils.db import DBConnect
from modules.points.models import User, Points
from shared import db_connect, tokenManger
from io import StringIO
from sqlalchemy import func
import threading

points_blueprint = Blueprint(
    "points", __name__, template_folder=None, static_folder=None
)


@points_blueprint.route("/", methods=["GET"])
def index():
    return jsonify({"message": "Points"}), 200


@points_blueprint.route("/add_user", methods=["POST"])
@auth_required
def add_user():
    data = request.json
    db = next(db_connect.get_db())
    try:
        # Check if user already exists
        existing_user = db.query(User).filter_by(email=data["email"]).first()
        if existing_user:
            return jsonify({"error": "User already exists"}), 301
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
@auth_required
def add_points():
    data = request.json
    db = next(db_connect.get_db())
    try:
        # Validate required fields
        if not data.get("organization_id"):
            return jsonify({"error": "organization_id is required"}), 400
        
        # Check if the user exists by discord_id
        user = db.query(User).filter_by(discord_id=data["user_discord_id"]).first()
        if not user:
            return jsonify({"error": "User does not exist"}), 404

        # Add points to the user
        point = Points(
            points=data["points"],
            user_id=user.id,
            organization_id=data["organization_id"],
        )
        db.add(point)
        db.commit()
        db.refresh(point)
    except Exception as e:
        db.rollback()
        return jsonify({"error": str(e)}), 400
    finally:
        db.close()
    return jsonify(
        {
            "id": point.id,
            "points": point.points,
            "user_id": point.user_id,
            "organization_id": point.organization_id,
            "last_updated": point.last_updated.isoformat() if point.last_updated else None,
        }
    ), 201


@points_blueprint.route("/get_users", methods=["GET"])
@auth_required
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
@auth_required
def get_points():
    db = next(db_connect.get_db())
    try:
        # Get organization_id from query parameters
        organization_id = request.args.get('organization_id')
        
        if not organization_id:
            return jsonify({"error": "organization_id parameter is required"}), 400
        
        # Filter points by organization
        points = db.query(Points).filter_by(organization_id=organization_id).all()
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    finally:
        db.close()
    return jsonify(
        [
            {
                "id": point.id,
                "points": point.points,
                "last_updated": point.last_updated.isoformat() if point.last_updated else None,
                "user_id": point.user_id,
                "organization_id": point.organization_id,
            }
            for point in points
        ]
    ), 200



@points_blueprint.route("/leaderboard", methods=["GET"])
def get_leaderboard():
    token = None
    show_email = False  # Default to showing UUID unless authentication succeeds

    # Extract token from Authorization header
    if "Authorization" in request.headers:
        token = request.headers["Authorization"].split(" ")[1]  # Get the token part

    # If the token is present, validate it
    if token:
        try:
            # Check if the token is valid and not expired
            if tokenManger.is_token_valid(token) and not tokenManger.is_token_expired(token):
                show_email = True  # If valid, set to show email
            elif tokenManger.is_token_expired(token):
                return jsonify({"message": "Token is expired!"}), 403  # Expired token
        except Exception as e:
            return jsonify({"message": str(e)}), 401  # Token is invalid or some error occurred

    # Get organization_id from query parameters
    organization_id = request.args.get('organization_id')
    if not organization_id:
        return jsonify({"error": "organization_id parameter is required"}), 400

    db = next(db_connect.get_db())
    try:
        leaderboard = (
            db.query(
                User.name,
                User.email,  # Include both email and UUID in the query
                User.uuid,
                func.coalesce(func.sum(Points.points), 0).label("total_points"),
            )
            .outerjoin(Points)
            .filter(Points.organization_id == organization_id)  # Filter by organization
            .group_by(User.email, User.uuid, User.name)  # Group by email and UUID for uniqueness
            .order_by(
                func.sum(Points.points).desc(), User.name.asc()
            )
            .all()
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    finally:
        db.close()

    # Return the result based on whether the token is valid or not
    return jsonify(
        [
            {
                "name": name,
                "identifier": email if show_email else uuid,  # Show email if token is valid, else UUID
                "points": total_points
            }
            for name, email, uuid, total_points in leaderboard
        ]
    ), 200


@points_blueprint.route("/uploadEventCSV", methods=["POST"])
@auth_required
def upload_event_csv():
    if 'file' not in request.files or 'event_name' not in request.form or 'event_points' not in request.form:
        return jsonify({"error": "Missing required fields"}), 400

    file = request.files['file']
    event_name = request.form['event_name']
    event_points = int(request.form['event_points'])

    # Check file extension
    if not file.filename.endswith('.csv'):
        return jsonify({"error": "File must be a CSV"}), 400

    # Read the file content
    file_content = file.stream.read().decode('utf-8')

    # Start a new thread to process the CSV in the background
    background_thread = threading.Thread(target=process_csv_in_background, args=(file_content, event_name, event_points))
    background_thread.start()

    # Return an immediate response while the CSV is being processed
    return jsonify({"message": "File is being processed in the background."}), 202


@points_blueprint.route("/getUserPoints", methods=["GET"])
@auth_required
def get_user_points():
    discord_id = request.args.get('discord_id')
    organization_id = request.args.get('organization_id')
    
    if not discord_id:
        return jsonify({"error": "discord_id parameter is missing"}), 400
    
    if not organization_id:
        return jsonify({"error": "organization_id parameter is missing"}), 400

    db = next(db_connect.get_db())
    try:
        # Check if the user exists
        user = db.query(User).filter_by(discord_id=discord_id).first()
        if not user:
            return jsonify({"error": "User does not exist"}), 404  # Not Found status code

        # Query all points earned by the user in the specific organization
        points_records = db.query(Points).filter_by(
            user_id=user.id, 
            organization_id=organization_id
        ).all()
        
        if not points_records:
            return jsonify({"message": "No points earned by this user in this organization"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 400
    finally:
        db.close()

    return jsonify(
        [
            {
                "id": record.id,
                "points": record.points,
                "organization_id": record.organization_id,
                "last_updated": record.last_updated.isoformat() if record.last_updated else None
            }
            for record in points_records
        ]
    ), 200


@points_blueprint.route("/getUserTotalPoints", methods=["GET"])
@auth_required
def get_user_total_points():
    discord_id = request.args.get('discord_id')
    organization_id = request.args.get('organization_id')
    
    if not discord_id:
        return jsonify({"error": "discord_id parameter is missing"}), 400
    
    if not organization_id:
        return jsonify({"error": "organization_id parameter is missing"}), 400

    db = next(db_connect.get_db())
    try:
        # Check if the user exists
        user = db.query(User).filter_by(discord_id=discord_id).first()
        if not user:
            return jsonify({"error": "User does not exist"}), 404

        # Calculate total points for the user in the specific organization
        total_points = db.query(func.sum(Points.points)).filter_by(
            user_id=user.id, 
            organization_id=organization_id
        ).scalar() or 0.0

    except Exception as e:
        return jsonify({"error": str(e)}), 400
    finally:
        db.close()

    return jsonify({
        "user_id": user.id,
        "discord_id": user.discord_id,
        "username": user.username,
        "organization_id": organization_id,
        "total_points": total_points
    }), 200

    
@points_blueprint.route("/assignPoints", methods=["POST"])
@auth_required
def assign_points():
    data = request.json
    db = next(db_connect.get_db())
    try:
        # Validate required fields
        if not data.get("user_identifier"):
            return jsonify({"error": "user_identifier is required"}), 400

        user_identifier = data["user_identifier"]
        
        # Try to find user by email first (since it's more common)
        user = db.query(User).filter_by(email=user_identifier).first()
        
        # If not found by email, try UUID
        if not user:
            user = db.query(User).filter_by(uuid=user_identifier).first()

        if not user:
            return jsonify({"error": "User not found"}), 404

        # Add points to the user
        point = Points(
            points=data["points"],
            event=data["event"],
            awarded_by_officer=data["awarded_by_officer"],
            user_email=user.email  # Use the found user's email
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
            "user_email": db_point.user_email,
        }
    ), 201




@points_blueprint.route("/delete_points", methods=["DELETE"])
@auth_required
def delete_points_by_event():
    data = request.json
    if not data or "user_email" not in data or "event" not in data:
        return jsonify({"error": "user_email and event are required"}), 400

    db = next(db_connect.get_db())
    try:
        # Find the points entry by user email and event name
        points_entry = db.query(Points).filter_by(
            user_email=data["user_email"],
            event=data["event"]
        ).first()
        
        if not points_entry:
            return jsonify({"error": "Points entry not found"}), 404
            
        # Delete the points entry
        db.delete(points_entry)
        db.commit()
        
        return jsonify({
            "message": "Points deleted successfully",
            "deleted_points": {
                "points": points_entry.points,
                "event": points_entry.event,
                "timestamp": points_entry.timestamp,
                "awarded_by_officer": points_entry.awarded_by_officer,
                "user_email": points_entry.user_email
            }
        }), 200
        
    except Exception as e:
        db.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()


def process_csv_in_background(file_content, event_name, event_points):
    csv_file = StringIO(file_content)

    # Skip the first 5 lines and read the content from the 6th line
    for _ in range(5):
        next(csv_file)

    # Now read the CSV starting from the 6th row which contains the headers
    csv_reader = csv.DictReader(csv_file)

    db = next(db_connect.get_db())
    success_count = 0
    errors = []

    try:
        for row in csv_reader:
            email = row.get('Campus Email')
            name = row.get('First Name') + ' ' + row.get('Last Name')
            asu_id = 'N/A'
            marked_by = row.get('Marked By')

            if not email or not name or not marked_by:
                errors.append(f"Missing required fields in row: {row}")
                continue  # Skip this row if any field is missing

            # Check if user exists
            user = db.query(User).filter_by(email=email).first()

            if not user:
                # Create user if doesn't exist
                user = User(
                    email=email,
                    name=name,
                    asu_id=asu_id,
                    academic_standing="N/A",
                    major="N/A"
                )
                db_user = db_connect.create_user(db, user)
                user_email = db_user.email
            else:
                user_email = user.email

            # Add points for the event
            point = Points(
                points=event_points,
                event=event_name,
                awarded_by_officer=marked_by,
                user_email=user_email
            )
            db_connect.create_point(db, point)
            success_count += 1

    except Exception as e:
        errors.append(str(e))
    finally:
        db.close()

    # Log the result of the processing (optional: you can store this to a DB or file)
    print(f"Processed {success_count} users. Errors: {errors}")