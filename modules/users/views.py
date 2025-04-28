from flask import Blueprint, render_template, request, session, redirect, url_for, flash
from modules.auth.decoraters import auth_required, error_handler
from modules.points.models import User, Points
from shared import db_connect, logger
from datetime import datetime
import os

# Create an absolute path to the templates directory
template_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")

users_views = Blueprint("users_views", __name__, template_folder=template_dir)

@users_views.route("/", methods=["GET"])
@auth_required
def user_page():
    """Render the users management page"""
    try:
        db = next(db_connect.get_db())
        users = db.query(User).all()
        
        # Format user data for the template
        users_data = []
        for user in users:
            # Get the total points for each user
            total_points = db.query(Points).filter_by(user_email=user.email).with_entities(
                Points.points).all()
            total = sum(points[0] for points in total_points) if total_points else 0
            
            users_data.append({
                'name': user.name,
                'email': user.email,
                'uuid': user.uuid,
                'academic_standing': user.academic_standing,
                'major': user.major,
                'total_points': total
            })
            
        return render_template("users/users.html", 
                              users=users_data,
                              current_user=session.get('user'),
                              current_year=datetime.now().year)
    except Exception as e:
        logger.error(f"Error fetching users: {str(e)}")
        return redirect(url_for('public_views.server_error'))
    finally:
        db.close()

@users_views.route("/view", methods=["GET"])
@auth_required
def view_user():
    """Render the individual user view page"""
    user_identifier = request.args.get('user_identifier')
    
    if not user_identifier:
        flash("User identifier is required", "error")
        return redirect(url_for('users_views.user_page'))
    
    try:
        db = next(db_connect.get_db())
        user = db.query(User).filter((User.email == user_identifier) | 
                                     (User.uuid == user_identifier)).first()
        
        if not user:
            flash("User not found", "error")
            return redirect(url_for('users_views.user_page'))
        
        # Get points records for the user
        points_records = db.query(Points).filter_by(user_email=user.email).all()
        
        # Format points records
        points_data = []
        total_points = 0
        
        for record in points_records:
            points_data.append({
                "points": record.points,
                "event": record.event,
                "timestamp": record.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                "awarded_by_officer": record.awarded_by_officer
            })
            total_points += record.points
        
        user_data = {
            "name": user.name,
            "email": user.email,
            "uuid": user.uuid,
            "academic_standing": user.academic_standing,
            "major": user.major,
            "total_points": total_points,
            "points_records": points_data
        }
        
        return render_template("users/user_detail.html", 
                              user=user_data,
                              current_user=session.get('user'),
                              current_year=datetime.now().year)
    except Exception as e:
        logger.error(f"Error viewing user: {str(e)}")
        return redirect(url_for('public_views.server_error'))
    finally:
        db.close()

@users_views.route("/create", methods=["GET", "POST"])
@auth_required
def create_user():
    """Handle user creation"""
    if request.method == "GET":
        return render_template("users/create_user.html", 
                              current_user=session.get('user'),
                              current_year=datetime.now().year)
    
    elif request.method == "POST":
        user_email = request.form.get('email')
        user_name = request.form.get('name')
        user_asu_id = request.form.get('asu_id')
        user_academic_standing = request.form.get('academic_standing')
        user_major = request.form.get('major')
        
        if not user_email or not user_name:
            flash("Email and name are required", "error")
            return redirect(url_for('users_views.create_user'))
        
        try:
            db = next(db_connect.get_db())
            
            # Check if user already exists
            existing_user = db.query(User).filter_by(email=user_email).first()
            if existing_user:
                flash("User with this email already exists", "error")
                return redirect(url_for('users_views.create_user'))
            
            user = User(
                email=user_email,
                name=user_name,
                asu_id=user_asu_id,
                academic_standing=user_academic_standing,
                major=user_major
            )
            
            db.add(user)
            db.commit()
            
            flash("User created successfully", "success")
            return redirect(url_for('users_views.user_page'))
        except Exception as e:
            db.rollback()
            logger.error(f"Error creating user: {str(e)}")
            flash("An error occurred while creating the user", "error")
            return redirect(url_for('users_views.create_user'))
        finally:
            db.close() 