from flask import jsonify, request, Blueprint, send_from_directory
import json
import os
from modules.points.models import User, Points
from shared import db_connect
from sqlalchemy import func, case, and_
from modules.auth.decoraters import error_handler
from datetime import datetime


public_blueprint = Blueprint(
    "public", __name__, template_folder=None, static_folder=None
)




@public_blueprint.route("/getnextevent", methods=["GET"])
def get_next_event():
    pass

@public_blueprint.route("/leaderboard", methods=["GET"])
def get_leaderboard():
    start_date = datetime(2025, 1, 1) # Jan 1, 2025
    end_date = datetime(2025, 5, 12) # May 12, 2025
    db = next(db_connect.get_db())
    try:
        # First, get the total points and names of all users
        leaderboard = (
            db.query(
                User.name,
                func.coalesce(func.sum(Points.points), 0).label("total_points"),
                User.uuid,
                func.coalesce(
                    func.sum(
                        case(
                            (and_(Points.timestamp >= start_date, Points.timestamp <= end_date), Points.points),
                            else_=0
                        )
                    ),
                    0
                ).label("curr_sem_points"),
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
                    "awarded_by": detail.awarded_by_officer,
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
            "points_details": user_details.get(uuid, []),  # Get details or empty list if none
            "curr_sem_points": curr_sem_points,
        }
        for name, total_points, uuid, curr_sem_points in leaderboard
    ]), 200

# Catch-all route for static files - must be last to not interfere with API routes
@public_blueprint.route('/', defaults={'path': ''})
@public_blueprint.route('/<path:path>')
def serve_static(path):
    if path == "":
        return send_from_directory('web/build', 'index.html')
    elif os.path.exists(os.path.join('web/build', path)):
        return send_from_directory('web/build', path)
    else:
        return send_from_directory('web/build', 'index.html')
