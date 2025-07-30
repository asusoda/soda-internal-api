from flask import jsonify, request, Blueprint, send_from_directory
import json
import os
from modules.points.models import User, Points
from shared import db_connect
from sqlalchemy import func
from modules.auth.decoraters import error_handler

# Update the blueprint to include the static folder
public_blueprint = Blueprint(
    "public", __name__,
    template_folder=None,
    static_folder=os.path.join(os.path.dirname(os.path.abspath(__file__)), "static"),
    static_url_path='/static/public'
)

@public_blueprint.route('/favicon.ico')
def favicon():
    return send_from_directory(
        os.path.join(public_blueprint.root_path, 'static'),
        'favicon.ico', mimetype='image/vnd.microsoft.icon'
    )



@public_blueprint.route("/getnextevent", methods=["GET"])
def get_next_event():
    pass

@public_blueprint.route("/leaderboard", methods=["GET"])
def get_leaderboard():
    db = next(db_connect.get_db())
    try:
        # First, get the total points and names of all users
        leaderboard = (
            db.query(
                User.name,
                func.coalesce(func.sum(Points.points), 0).label("total_points"),
                User.uuid
            )
            .outerjoin(Points)  # Ensure users with no points are included
            .group_by(User.uuid)
            .order_by(
                func.sum(Points.points).desc(), User.name.asc()
            )  # Sort by points then by name
            .all()
        )

        # Then, get the detailed points information for each user
        user_details = {}
        for user in db.query(User).all():
            points_details = (
                db.query(
                    Points.event,
                    Points.points,
                    Points.timestamp,
                    Points.awarded_by_officer
                )
                .filter(Points.user_email == user.email)
                .all()
            )
            # Format points details as a list of dictionaries
            user_details[user.uuid] = [
                {
                    "event": detail.event,
                    "points": detail.points,
                    "timestamp": detail.timestamp,
                    "awarded_by": detail.awarded_by_officer
                }
                for detail in points_details
            ]
            
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    finally:
        db.close()

    # Combine the leaderboard and detailed points information
    return jsonify([
        {
            "name": name,
            "total_points": total_points,
            "points_details": user_details.get(uuid, [])  # Get details or empty list if none
        }
        for name, total_points, uuid in leaderboard
    ]), 200

