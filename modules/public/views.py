from flask import Blueprint, render_template, session, redirect, url_for, request, flash
from datetime import datetime
from shared import logger
import os
from sqlalchemy import func
from shared import db_connect
from modules.organizations.models import Organization, Officer
from modules.points.models import Points, User
from modules.auth.decoraters import auth_required
from shared import bot
# Create an absolute path to the templates directory
template_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")

# Change the name from "public" to "public_views" to avoid conflict
# Use the absolute path for template_folder
public_views = Blueprint("public_views", __name__, 
                         template_folder=template_dir)

@public_views.route("/", methods=["GET"])
def index():
    """Render the login page"""
    return render_template("public/login.html")

@public_views.route("/home", methods=["GET"])
@auth_required
def home():
    """Render the home page with organizations"""
    try:
        db = next(db_connect.get_db())
        # Get all organizations
        organizations = db.query(Organization).all()
        
        return render_template("public/home.html", 
                            current_year=datetime.now().year,
                            organizations=organizations)
    except Exception as e:
        logger.error(f"Error fetching organizations: {str(e)}")
        return redirect(url_for('public_views.server_error'))
    finally:
        db.close()

@public_views.route("/500", methods=["GET"])
def server_error():
    """Render the 500 error page"""
    return render_template("public/server_error.html", current_year=datetime.now().year)

@public_views.route("/organizations", methods=["GET"])
@auth_required
def organizations():
    """View all organizations"""
    try:
        db = next(db_connect.get_db())
        organizations = db.query(Organization).all()
        return render_template("public/organizations.html",
                            current_year=datetime.now().year,
                            organizations=organizations)
    except Exception as e:
        logger.error(f"Error fetching organizations: {str(e)}")
        return redirect(url_for('public_views.server_error'))
    finally:
        db.close()

@public_views.route("/<prefix>", methods=["GET"])
@auth_required
def org_dashboard(prefix):
    """Access organization dashboard using its prefix"""
    try:
        db = next(db_connect.get_db())
        organization = db.query(Organization).filter_by(prefix=prefix).first()
        
        if not organization:
            logger.error(f"Organization with prefix {prefix} not found")
            return redirect(url_for('public_views.server_error'))
        
        # Get all users who are officers in this organization
        officers = db.query(Officer).filter_by(organization_id=organization.id).all()
        officer_user_ids = [officer.user_id for officer in officers]
        
        # Initialize total points and recent points
        total_points = 0
        formatted_points = []
        
        # Only query points if there are officers
        if officer_user_ids:
            # Calculate total points for the organization's officers
            total_points = db.query(func.sum(Points.points)).join(
                User, Points.user_id == User.id
            ).filter(
                User.discord_id.in_(officer_user_ids)
            ).scalar() or 0
            
            # Get recent points activity for the organization's officers
            recent_points = db.query(Points, User).join(
                User, Points.user_id == User.id
            ).filter(
                User.discord_id.in_(officer_user_ids)
            ).order_by(
                Points.last_updated.desc()
            ).limit(5).all()
            
            # Format recent points for template
            formatted_points = [{
                'user': user,
                'points': points.points,
                'timestamp': points.last_updated
            } for points, user in recent_points]
        
        return render_template("public/org_home.html",
                            current_year=datetime.now().year,
                            organization=organization,
                            total_points=total_points,
                            recent_points=formatted_points)
    except Exception as e:
        logger.error(f"Error accessing organization dashboard: {str(e)}")
        return redirect(url_for('public_views.server_error'))
    finally:
        db.close()

@public_views.route("/organization/<int:org_id>", methods=["GET"])
@auth_required
def view_organization(org_id):
    """View a specific organization"""
    try:
        db = next(db_connect.get_db())
        organization = db.query(Organization).get(org_id)
        if not organization:
            logger.error(f"Organization with ID {org_id} not found")
            return redirect(url_for('public_views.server_error'))
        return redirect(url_for('public_views.org_dashboard', prefix=organization.prefix))
    except Exception as e:
        logger.error(f"Error fetching organization: {str(e)}")
        return redirect(url_for('public_views.server_error'))
    finally:
        db.close()

@public_views.route("/organization/<int:org_id>/home", methods=["GET"])
@auth_required
def org_home(org_id):
    """Render the organization home page"""
    try:
        db = next(db_connect.get_db())
        organization = db.query(Organization).get(org_id)
        if not organization:
            logger.error(f"Organization with ID {org_id} not found")
            return redirect(url_for('public_views.server_error'))
        return redirect(url_for('public_views.org_dashboard', prefix=organization.prefix))
    except Exception as e:
        logger.error(f"Error fetching organization home: {str(e)}")
        return redirect(url_for('public_views.server_error'))
    finally:
        db.close()

@public_views.route("/<prefix>/config", methods=["GET", "POST"])
@auth_required
def org_config(prefix):
    """View and edit organization configuration"""
    try:
        db = next(db_connect.get_db())
        organization = db.query(Organization).filter_by(prefix=prefix).first()
        if not organization:
            logger.error(f"Organization with prefix {prefix} not found")
            return redirect(url_for('public_views.server_error'))
        
        # Get roles from Discord server
        try:
            guild_id = int(organization.guild_id)
            roles = bot.get_guild_roles(guild_id)
        except (ValueError, TypeError) as e:
            logger.error(f"Error getting guild roles: {str(e)}")
            roles = []
        
        if request.method == "POST":
            # Update organization details
            # Note: name and guild_id are not included as they are read-only
            organization.prefix = request.form.get('prefix', organization.prefix)
            organization.description = request.form.get('description', organization.description)
            organization.officer_role_id = request.form.get('officer_role', organization.officer_role_id)
            
            # Update points configuration
            try:
                points_per_message = int(request.form.get('points_per_message', organization.points_per_message))
                points_cooldown = int(request.form.get('points_cooldown', organization.points_cooldown))
                organization.points_per_message = points_per_message
                organization.points_cooldown = points_cooldown
            except ValueError:
                flash('Points values must be valid numbers', 'error')
                return redirect(url_for('public_views.org_config', prefix=prefix))
            
            try:
                db.commit()
                flash('Configuration updated successfully', 'success')
            except Exception as e:
                db.rollback()
                logger.error(f"Error updating organization configuration: {str(e)}")
                flash('Error updating configuration', 'error')
            
            return redirect(url_for('public_views.org_config', prefix=prefix))
        
        return render_template("public/org_config.html",
                            current_year=datetime.now().year,
                            organization=organization,
                            roles=roles)
    except Exception as e:
        logger.error(f"Error accessing organization configuration: {str(e)}")
        return redirect(url_for('public_views.server_error'))
    finally:
        db.close() 