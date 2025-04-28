from flask import Blueprint, session, redirect, url_for, request, flash, render_template
from shared import logger, tokenManger
import os
from datetime import datetime

# Create an absolute path to the templates directory
template_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")

auth_views = Blueprint("auth_views", __name__, template_folder=template_dir)

# Mock user database for the simple authentication example
# In a real application, you would store this in a proper database
USERS = {
    "admin@soda.asu.edu": {
        "password": "admin123",
        "name": "Admin User",
        "role": "admin"
    },
    "officer@soda.asu.edu": {
        "password": "officer123",
        "name": "Officer User",
        "role": "officer"
    },
    "member@soda.asu.edu": {
        "password": "member123",
        "name": "Regular Member",
        "role": "member"
    }
}

@auth_views.route("/login", methods=["GET", "POST"])
def login():
    """Handle login form submission"""
    if request.method == "GET":
        return render_template("auth/login_form.html", current_year=datetime.now().year)
    
    # POST request - form submission
    email = request.form.get('email')
    password = request.form.get('password')
    
    # Validate credentials
    if email in USERS and USERS[email]['password'] == password:
        # Generate a token for the authenticated user
        user_data = {
            "username": USERS[email]['name'],
            "email": email,
            "role": USERS[email]['role']
        }
        token = tokenManger.generate_token(username=USERS[email]['name'])
        
        # Store user information in session
        session['user'] = user_data
        session['token'] = token
        
        flash("Login successful!", "success")
        return redirect(url_for('public_views.home'))
    else:
        flash("Invalid email or password", "error")
        return render_template("auth/login_form.html", current_year=datetime.now().year)

@auth_views.route("/callback", methods=["GET"])
def callback():
    """
    This method is preserved for backward compatibility
    but is no longer needed with local authentication
    """
    return redirect(url_for('auth_views.login'))

@auth_views.route("/logout", methods=["GET"])
def logout():
    """Log out the user by clearing the session"""
    session.clear()
    flash("You have been logged out", "success")
    return redirect(url_for('public_views.index')) 