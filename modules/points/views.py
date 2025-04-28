from flask import Blueprint, render_template, request, session, redirect, url_for
from modules.auth.decoraters import auth_required, error_handler
from modules.points.models import User, Points
from shared import db_connect, logger
from datetime import datetime
from sqlalchemy import func
import os

# Create an absolute path to the templates directory
template_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")

points_views = Blueprint("points_views", __name__, template_folder=template_dir)

@points_views.route("/leaderboard", methods=["GET"])
@auth_required
def leaderboard():
    """Render the points leaderboard page"""
    try:
        db = next(db_connect.get_db())
        
        # Get the points sum for each user and join with user data
        leaderboard_data = db.query(
            User.name,
            User.email,
            User.academic_standing,
            func.sum(Points.points).label('total_points')
        ).join(
            Points, User.email == Points.user_email
        ).group_by(
            User.email
        ).order_by(
            func.sum(Points.points).desc()
        ).all()
        
        # Format the data for the template
        users_data = [
            {
                'name': user.name,
                'email': user.email,
                'academic_standing': user.academic_standing,
                'total_points': user.total_points
            }
            for user in leaderboard_data
        ]
        
        return render_template("points/leaderboard.html", 
                              users=users_data,
                              current_user=session.get('user'),
                              current_year=datetime.now().year)
    except Exception as e:
        logger.error(f"Error fetching leaderboard: {str(e)}")
        return redirect(url_for('public_views.server_error'))
    finally:
        db.close()

@points_views.route("/add", methods=["GET", "POST"])
@auth_required
def add_points():
    """Handle adding points to a user"""
    if request.method == "GET":
        # Get all users for the dropdown
        try:
            db = next(db_connect.get_db())
            users = db.query(User).all()
            users_data = [{'name': user.name, 'email': user.email} for user in users]
            
            return render_template("points/add_points.html", 
                                  users=users_data,
                                  current_user=session.get('user'),
                                  current_year=datetime.now().year)
        except Exception as e:
            logger.error(f"Error fetching users for add points: {str(e)}")
            return redirect(url_for('public_views.server_error'))
        finally:
            db.close()
    
    elif request.method == "POST":
        user_email = request.form.get('user_email')
        points_amount = request.form.get('points')
        event_name = request.form.get('event')
        
        if not user_email or not points_amount or not event_name:
            return render_template("points/add_points.html", 
                                  error="All fields are required",
                                  current_user=session.get('user'),
                                  current_year=datetime.now().year)
        
        try:
            points_amount = int(points_amount)
            
            db = next(db_connect.get_db())
            
            # Check if user exists
            user = db.query(User).filter_by(email=user_email).first()
            if not user:
                return render_template("points/add_points.html", 
                                      error="User not found",
                                      current_user=session.get('user'),
                                      current_year=datetime.now().year)
            
            # Create points record
            points_record = Points(
                user_email=user_email,
                points=points_amount,
                event=event_name,
                awarded_by_officer=session.get('user', {}).get('name', 'Unknown')
            )
            
            db.add(points_record)
            db.commit()
            
            return redirect(url_for('points_views.leaderboard'))
        except ValueError:
            return render_template("points/add_points.html", 
                                  error="Points must be a number",
                                  current_user=session.get('user'),
                                  current_year=datetime.now().year)
        except Exception as e:
            db.rollback()
            logger.error(f"Error adding points: {str(e)}")
            return redirect(url_for('public_views.server_error'))
        finally:
            db.close() 