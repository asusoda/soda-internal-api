from flask import Blueprint, render_template, session, redirect, url_for, flash, request
from functools import wraps
import os
from datetime import datetime
from shared import bot, db_connect
from modules.organizations.models import Organization
from modules.organizations.config import OrganizationSettings

# Create an absolute path to the templates directory
template_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")

superadmin_views = Blueprint("superadmin_views", __name__, template_folder=template_dir)

def superadmin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session or session['user'].get('role') != 'admin':
            flash("You must be a superadmin to access this page", "error")
            return redirect(url_for('public_views.index'))
        return f(*args, **kwargs)
    return decorated_function

@superadmin_views.route("/superadmin")
@superadmin_required
def dashboard():
    """SuperAdmin dashboard showing all available servers"""
    # Get all guilds where the bot is a member
    guilds = bot.guilds
    
    # Get existing organizations from the database
    db = next(db_connect.get_db())
    try:
        existing_orgs = db.query(Organization).all()
        existing_guild_ids = {org.guild_id for org in existing_orgs}
        
        # Filter guilds to show only those not already added
        available_guilds = [guild for guild in guilds if str(guild.id) not in existing_guild_ids]
        
        # Get officer's organizations
        officer_id = session.get('user', {}).get('discord_id')
        officer_orgs = []
        if officer_id:
            for org in existing_orgs:
                guild = bot.get_guild(int(org.guild_id))
                if guild and guild.get_member(int(officer_id)):
                    officer_orgs.append(org)
        
        return render_template(
            "superadmin/dashboard.html",
            available_guilds=available_guilds,
            existing_orgs=existing_orgs,
            officer_orgs=officer_orgs,
            current_year=datetime.now().year
        )
    finally:
        db.close()

@superadmin_views.route("/superadmin/add_org/<int:guild_id>", methods=["POST"])
@superadmin_required
def add_organization(guild_id):
    """Add a new organization to the system"""
    try:
        # Find the guild
        guild = next((g for g in bot.guilds if g.id == guild_id), None)
        if not guild:
            flash("Guild not found", "error")
            return redirect(url_for('superadmin_views.dashboard'))
        
        # Create new organization with default settings
        settings = OrganizationSettings()
        new_org = Organization(
            name=guild.name,
            guild_id=str(guild.id),
            description=f"Discord server: {guild.name}",
            icon_url=str(guild.icon.url) if guild.icon else None,
            config=settings.to_dict()
        )
        
        # Save to database
        db = next(db_connect.get_db())
        try:
            db.add(new_org)
            db.commit()
            flash(f"Organization {guild.name} added successfully!", "success")
        finally:
            db.close()
    except Exception as e:
        flash(f"Error adding organization: {str(e)}", "error")
    
    return redirect(url_for('superadmin_views.dashboard'))

@superadmin_views.route("/superadmin/remove_org/<int:org_id>", methods=["POST"])
@superadmin_required
def remove_organization(org_id):
    """Remove an organization from the system"""
    try:
        db = next(db_connect.get_db())
        try:
            org = db.query(Organization).filter_by(id=org_id).first()
            if org:
                db.delete(org)
                db.commit()
                flash(f"Organization {org.name} removed successfully!", "success")
            else:
                flash("Organization not found", "error")
        finally:
            db.close()
    except Exception as e:
        flash(f"Error removing organization: {str(e)}", "error")
    
    return redirect(url_for('superadmin_views.dashboard')) 