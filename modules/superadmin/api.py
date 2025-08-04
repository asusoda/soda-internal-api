from flask import Blueprint, jsonify, request, session, current_app
from shared import db_connect
from modules.organizations.models import Organization
from modules.organizations.config import OrganizationSettings
from modules.auth.decoraters import superadmin_required

superadmin_blueprint = Blueprint("superadmin", __name__)

@superadmin_blueprint.route("/check", methods=["GET"])
@superadmin_required
def check_superadmin():
    """Check if user has superadmin privileges"""
    return jsonify({"is_superadmin": True}), 200

@superadmin_blueprint.route("/dashboard", methods=["GET"])
@superadmin_required
def get_dashboard():
    """Get SuperAdmin dashboard data"""
    try:
        # Get the auth bot from Flask app context
        auth_bot = current_app.auth_bot if hasattr(current_app, 'auth_bot') else None
        if not auth_bot or not auth_bot.is_ready():
            return jsonify({"error": "Bot not available"}), 503
        
        # Get all guilds where the bot is a member
        guilds = auth_bot.guilds
        
        # Get existing organizations from the database
        db = next(db_connect.get_db())
        existing_orgs = db.query(Organization).all()
        existing_guild_ids = {org.guild_id for org in existing_orgs}
        
        # Filter guilds to show only those not already added
        available_guilds = []
        for guild in guilds:
            if str(guild.id) not in existing_guild_ids:
                available_guilds.append({
                    "id": str(guild.id),
                    "name": guild.name,
                    "icon": {
                        "url": str(guild.icon.url) if guild.icon else None
                    }
                })
        
        # Get officer's organizations - check which orgs the current user is an officer of
        officer_orgs = []
        officer_id = session.get('user', {}).get('discord_id')
        if officer_id:
            for org in existing_orgs:
                try:
                    guild = auth_bot.get_guild(int(org.guild_id))
                    if guild and guild.get_member(int(officer_id)):
                        officer_orgs.append(org)
                except (ValueError, AttributeError):
                    # Skip if guild_id is invalid or guild not found
                    continue
        
        return jsonify({
            "available_guilds": available_guilds,
            "existing_orgs": [org.to_dict() for org in existing_orgs],
            "officer_orgs": [org.to_dict() for org in officer_orgs]
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()

@superadmin_blueprint.route("/add_org/<guild_id>", methods=["POST"])
@superadmin_required
def add_organization(guild_id):
    """Add a new organization to the system"""
    try:
        # Get the auth bot from Flask app context
        auth_bot = current_app.auth_bot if hasattr(current_app, 'auth_bot') else None
        if not auth_bot or not auth_bot.is_ready():
            return jsonify({"error": "Bot not available"}), 503
        
        # Convert guild_id to int for comparison with guild.id
        try:
            guild_id_int = int(guild_id)
        except ValueError:
            return jsonify({"error": "Invalid guild ID format"}), 400
        
        # Find the guild
        guild = next((g for g in auth_bot.guilds if g.id == guild_id_int), None)
        if not guild:
            return jsonify({"error": "Guild not found"}), 404
        
        # Create prefix from guild name
        prefix = guild.name.lower().replace(' ', '_').replace('-', '_')
        
        # Create new organization with default settings
        settings = OrganizationSettings()
        new_org = Organization(
            name=guild.name,
            guild_id=str(guild.id),
            prefix=prefix,
            description=f"Discord server: {guild.name}",
            icon_url=str(guild.icon.url) if guild.icon else None,
            config=settings.to_dict()
        )
        
        # Save to database
        db = next(db_connect.get_db())
        db.add(new_org)
        db.commit()
        
        return jsonify({"message": f"Organization {guild.name} added successfully!"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()

@superadmin_blueprint.route("/remove_org/<int:org_id>", methods=["DELETE"])
@superadmin_required
def remove_organization(org_id):
    """Remove an organization from the system"""
    try:
        db = next(db_connect.get_db())
        org = db.query(Organization).filter_by(id=org_id).first()
        
        if not org:
            return jsonify({"error": "Organization not found"}), 404
            
        org_name = org.name
        db.delete(org)
        db.commit()
        
        return jsonify({"message": f"Organization {org_name} removed successfully!"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        db.close() 