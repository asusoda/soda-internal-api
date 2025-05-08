from flask import Blueprint, render_template, request, session, redirect, url_for, flash
from modules.auth.decoraters import auth_required, error_handler
from modules.points.models import User, Points
from shared import db_connect, logger
from datetime import datetime
from sqlalchemy import func
import os

# Create an absolute path to the templates directory
template_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")

points_views = Blueprint("points_views", __name__, template_folder=template_dir)

@points_views.route("/points/leaderboard", methods=["GET"])
@auth_required
def leaderboard():
    """Render the points leaderboard page"""
    try:
        db = next(db_connect.get_db())
        # Get users with their total points, ordered by points descending
        leaderboard_data = db.query(
            User,
            func.coalesce(func.sum(Points.points), 0).label('total_points')
        ).outerjoin(
            Points, User.id == Points.user_id
        ).group_by(
            User.id
        ).order_by(
            func.coalesce(func.sum(Points.points), 0).desc()
        ).all()

        # Format the data for the template
        users_data = []
        for user, total_points in leaderboard_data:
            users_data.append({
                'name': user.name,
                'email': user.email,
                'academic_standing': user.academic_standing,
                'total_points': total_points
            })

        return render_template("points/leaderboard.html",
                            current_user=session.get('token'),
                            current_year=datetime.now().year,
                            users=users_data)
    except Exception as e:
        logger.error(f"Error fetching leaderboard: {str(e)}")
        return redirect(url_for('public_views.server_error'))
    finally:
        db.close()

@points_views.route("/points/add", methods=["GET", "POST"])
@auth_required
def add_points():
    """Add points to a user"""
    if request.method == "GET":
        try:
            db = next(db_connect.get_db())
            # Get all users for the dropdown
            users = db.query(User).all()
            return render_template("points/add_points.html",
                                current_user=session.get('token'),
                                current_year=datetime.now().year,
                                users=users)
        except Exception as e:
            logger.error(f"Error fetching users: {str(e)}")
            return redirect(url_for('public_views.server_error'))
        finally:
            db.close()
    
    elif request.method == "POST":
        try:
            db = next(db_connect.get_db())
            user_id = request.form.get('user_id')
            points = int(request.form.get('points'))
            event = request.form.get('event')
            
            # Create new points record
            points_record = Points(
                user_id=user_id,
                points=points,
                event=event,
                awarded_by_officer=session.get('token').get('name', 'Unknown')
            )
            
            db.add(points_record)
            db.commit()
            
            flash('Points added successfully!', 'success')
            return redirect(url_for('points_views.leaderboard'))
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error adding points: {str(e)}")
            flash(f'Error adding points: {str(e)}', 'error')
            return redirect(url_for('points_views.add_points'))
        finally:
            db.close() 