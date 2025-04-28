from flask import Blueprint, render_template, session, redirect, url_for
from modules.auth.decoraters import auth_required
from datetime import datetime
from shared import logger
import os

# Create an absolute path to the templates directory
template_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")

# Change the name from "public" to "public_views" to avoid conflict
# Use the absolute path for template_folder
public_views = Blueprint("public_views", __name__, 
                         template_folder=template_dir)

@public_views.route("/", methods=["GET"])
def index():
    """Render the login page"""
    # If user is already logged in, redirect to home
    if session.get('user'):
        return redirect(url_for('public_views.home'))
    
    return render_template("public/login.html", current_year=datetime.now().year)

@public_views.route("/home", methods=["GET"])
@auth_required
def home():
    """Render the home page"""
    return render_template("public/home.html", 
                          user=session.get('user'),
                          current_year=datetime.now().year)

@public_views.route("/500", methods=["GET"])
def server_error():
    """Render the 500 error page"""
    return render_template("public/server_error.html", current_year=datetime.now().year) 