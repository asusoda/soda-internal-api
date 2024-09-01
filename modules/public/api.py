from flask import jsonify, request, Blueprint
import json
from modules.points.models import User, Points
from shared import db_connect
from sqlalchemy import func
from modules.auth.decoraters import error_handler

public_blueprint = Blueprint(
    "public", __name__, template_folder=None, static_folder=None
)


@public_blueprint.route("/", methods=["GET"])
def index():
    return jsonify({"message": "Welcome to SoDA's trusty internal API"}), 200


@public_blueprint.route("/getnextevent", methods=["GET"])
def get_next_event():
    pass


@public_blueprint.route("/leaderboard", methods=["GET"])
def get_leaderboard():
    db = next(db_connect.get_db())
    try:
        # Aggregate points for each user, use left join to include users without points
        leaderboard = (
            db.query(
                User.name,
                func.coalesce(func.sum(Points.points), 0).label("total_points"),
            )
            .outerjoin(Points)  # Ensure users with no points are included
            .group_by(User.uuid)
            .order_by(
                func.sum(Points.points).desc(), User.name.asc()
            )  # Sort by points then by name
            .all()
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    finally:
        db.close()

    # Return the sorted leaderboard without the user.uuid
    return jsonify(
        [{"name": name, "points": total_points} for name, total_points in leaderboard]
    ), 200
