from flask import Blueprint, jsonify, request, session, current_app
from shared import db_connect, config, tokenManger
from modules.organizations.models import Organization
from modules.organizations.config import OrganizationSettings
from modules.auth.decoraters import superadmin_required

superadmin_blueprint = Blueprint("superadmin", __name__)

@superadmin_blueprint.route("/check", methods=["GET"])
@superadmin_required
def check_superadmin():
    """Check if user has superadmin privileges"""
    try:
        print(f"🔍 [DEBUG] check_superadmin endpoint called")
        
        # Get the token from Authorization header
        auth_header = request.headers.get("Authorization")
        print(f"🔍 [DEBUG] Authorization header: {auth_header}")
        
        if not auth_header or not auth_header.startswith("Bearer "):
            print(f"❌ [DEBUG] Invalid Authorization header format")
            return jsonify({"error": "Authorization header required"}), 401
        
        token = auth_header.split(" ")[1]
        print(f"🔍 [DEBUG] Extracted token: {token[:20]}...")
        
        # Decode the token to get user information
        print(f"🔍 [DEBUG] Decoding token...")
        token_data = tokenManger.decode_token(token)
        if not token_data:
            print(f"❌ [DEBUG] Failed to decode token")
            return jsonify({"error": "Invalid token"}), 401
        
        print(f"🔍 [DEBUG] Token data: {token_data}")
        
        # Get Discord ID from token
        user_discord_id = token_data.get('discord_id')
        if not user_discord_id:
            print(f"❌ [DEBUG] Token missing Discord ID")
            return jsonify({"error": "Token missing Discord ID"}), 401
        
        superadmin_id = config.SUPERADMIN_USER_ID
        print(f"🔍 [DEBUG] Superadmin ID from config: {superadmin_id}")
        
        print(f"🔍 [DEBUG] Comparing user_discord_id: {user_discord_id} with superadmin_id: {superadmin_id}")
        print(f"🔍 [DEBUG] String comparison: '{str(user_discord_id)}' == '{str(superadmin_id)}'")
        
        # Check if user's ID matches the superadmin ID
        if str(user_discord_id) == str(superadmin_id):
            print(f"✅ [DEBUG] User is superadmin - returning True")
            return jsonify({"is_superadmin": True}), 200
        else:
            print(f"❌ [DEBUG] User is not superadmin - returning False")
            return jsonify({"is_superadmin": False}), 403
            
    except Exception as e:
        print(f"❌ [DEBUG] Error in check_superadmin: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"Error checking superadmin status: {str(e)}"}), 500

@superadmin_blueprint.route("/dashboard", methods=["GET"])
@superadmin_required
def get_dashboard():
    """Get SuperAdmin dashboard data"""
    try:
        print(f"🔍 [DEBUG] get_dashboard endpoint called")
        
        # Get the auth bot from Flask app context
        print(f"🔍 [DEBUG] Getting auth bot from Flask app context...")
        auth_bot = current_app.auth_bot if hasattr(current_app, 'auth_bot') else None
        if not auth_bot:
            print(f"❌ [DEBUG] Auth bot not found in Flask app context!")
            return jsonify({"error": "Bot not available"}), 503
        
        if not auth_bot.is_ready():
            print(f"❌ [DEBUG] Auth bot is not ready!")
            return jsonify({"error": "Bot not available"}), 503
        
        print(f"✅ [DEBUG] Auth bot is ready")
        
        # Get all guilds where the bot is a member
        guilds = auth_bot.guilds
        print(f"🔍 [DEBUG] Bot is in {len(guilds)} guilds")
        
        # Get existing organizations from the database
        print(f"🔍 [DEBUG] Getting organizations from database...")
        db = next(db_connect.get_db())
        existing_orgs = db.query(Organization).all()
        print(f"🔍 [DEBUG] Found {len(existing_orgs)} existing organizations")
        
        existing_guild_ids = {org.guild_id for org in existing_orgs}
        print(f"🔍 [DEBUG] Existing guild IDs: {existing_guild_ids}")
        
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
        
        print(f"🔍 [DEBUG] Found {len(available_guilds)} available guilds")
        
        # Get officer's organizations - check which orgs the current user is an officer of
        print(f"🔍 [DEBUG] Getting officer organizations...")
        officer_orgs = []
        officer_id = session.get('user', {}).get('discord_id')
        print(f"🔍 [DEBUG] Officer ID from session: {officer_id}")
        
        if officer_id:
            for org in existing_orgs:
                try:
                    guild = auth_bot.get_guild(int(org.guild_id))
                    if guild and guild.get_member(int(officer_id)):
                        officer_orgs.append(org)
                        print(f"🔍 [DEBUG] User is officer in organization: {org.name}")
                except (ValueError, AttributeError) as e:
                    print(f"🔍 [DEBUG] Error checking organization {org.name}: {e}")
                    # Skip if guild_id is invalid or guild not found
                    continue
        
        print(f"🔍 [DEBUG] User is officer in {len(officer_orgs)} organizations")
        
        response_data = {
            "available_guilds": available_guilds,
            "existing_orgs": [org.to_dict() for org in existing_orgs],
            "officer_orgs": [org.to_dict() for org in officer_orgs]
        }
        
        print(f"✅ [DEBUG] Dashboard data prepared successfully")
        return jsonify(response_data)
    except Exception as e:
        print(f"❌ [DEBUG] Error in get_dashboard: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500
    finally:
        if 'db' in locals():
            db.close()

@superadmin_blueprint.route("/guild_roles/<guild_id>", methods=["GET"])
@superadmin_required
def get_guild_roles(guild_id):
    """Get all roles from a specific guild"""
    try:
        print(f"🔍 [DEBUG] get_guild_roles endpoint called for guild_id: {guild_id}")
        
        # Get the auth bot from Flask app context
        print(f"🔍 [DEBUG] Getting auth bot from Flask app context...")
        auth_bot = current_app.auth_bot if hasattr(current_app, 'auth_bot') else None
        if not auth_bot:
            print(f"❌ [DEBUG] Auth bot not found in Flask app context!")
            return jsonify({"error": "Bot not available"}), 503
        
        if not auth_bot.is_ready():
            print(f"❌ [DEBUG] Auth bot is not ready!")
            return jsonify({"error": "Bot not available"}), 503
        
        print(f"✅ [DEBUG] Auth bot is ready")
        
        # Convert guild_id to int for comparison
        try:
            guild_id_int = int(guild_id)
            print(f"🔍 [DEBUG] Converted guild_id to int: {guild_id_int}")
        except ValueError:
            print(f"❌ [DEBUG] Invalid guild ID format: {guild_id}")
            return jsonify({"error": "Invalid guild ID format"}), 400
        
        # Get the guild
        print(f"🔍 [DEBUG] Getting guild with ID: {guild_id_int}")
        guild = auth_bot.get_guild(guild_id_int)
        if not guild:
            print(f"❌ [DEBUG] Guild not found for ID: {guild_id_int}")
            return jsonify({"error": "Guild not found"}), 404
        
        print(f"✅ [DEBUG] Found guild: {guild.name}")
        
        # Get all roles from the guild
        print(f"🔍 [DEBUG] Getting roles from guild...")
        roles = []
        for role in guild.roles:
            # Skip @everyone role and bot roles
            if role.name != "@everyone" and not role.managed:
                roles.append({
                    "id": str(role.id),
                    "name": role.name,
                    "color": str(role.color),
                    "position": role.position,
                    "permissions": role.permissions.value
                })
                print(f"🔍 [DEBUG] Added role: {role.name} (ID: {role.id})")
        
        # Sort roles by position (highest first)
        roles.sort(key=lambda x: x["position"], reverse=True)
        
        print(f"✅ [DEBUG] Found {len(roles)} roles for guild {guild.name}")
        return jsonify({"roles": roles})
    except Exception as e:
        print(f"❌ [DEBUG] Error in get_guild_roles: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@superadmin_blueprint.route("/update_officer_role/<int:org_id>", methods=["PUT"])
@superadmin_required
def update_officer_role(org_id):
    """Update the officer role ID for an organization"""
    try:
        print(f"🔍 [DEBUG] update_officer_role endpoint called for org_id: {org_id}")
        
        # Get the request data
        data = request.get_json()
        print(f"🔍 [DEBUG] Request data: {data}")
        
        if not data or 'officer_role_id' not in data:
            print(f"❌ [DEBUG] Missing officer_role_id in request data")
            return jsonify({"error": "officer_role_id is required"}), 400
        
        officer_role_id = data['officer_role_id']
        print(f"🔍 [DEBUG] Officer role ID: {officer_role_id}")
        
        # Get the auth bot from Flask app context
        print(f"🔍 [DEBUG] Getting auth bot from Flask app context...")
        auth_bot = current_app.auth_bot if hasattr(current_app, 'auth_bot') else None
        if not auth_bot:
            print(f"❌ [DEBUG] Auth bot not found in Flask app context!")
            return jsonify({"error": "Bot not available"}), 503
        
        if not auth_bot.is_ready():
            print(f"❌ [DEBUG] Auth bot is not ready!")
            return jsonify({"error": "Bot not available"}), 503
        
        print(f"✅ [DEBUG] Auth bot is ready")
        
        # Get the organization from database
        print(f"🔍 [DEBUG] Getting organization from database...")
        db = next(db_connect.get_db())
        org = db.query(Organization).filter_by(id=org_id).first()
        
        if not org:
            print(f"❌ [DEBUG] Organization not found for ID: {org_id}")
            return jsonify({"error": "Organization not found"}), 404
        
        print(f"✅ [DEBUG] Found organization: {org.name} (Guild ID: {org.guild_id})")
        
        # Verify the role exists in the guild
        try:
            print(f"🔍 [DEBUG] Getting guild for verification...")
            guild = auth_bot.get_guild(int(org.guild_id))
            if not guild:
                print(f"❌ [DEBUG] Guild not found for ID: {org.guild_id}")
                return jsonify({"error": "Guild not found"}), 404
            
            print(f"✅ [DEBUG] Found guild: {guild.name}")
            
            # If officer_role_id is provided, verify it exists
            if officer_role_id:
                print(f"🔍 [DEBUG] Verifying role exists in guild...")
                role = guild.get_role(int(officer_role_id))
                if not role:
                    print(f"❌ [DEBUG] Role not found in guild for ID: {officer_role_id}")
                    return jsonify({"error": "Role not found in guild"}), 404
                
                print(f"✅ [DEBUG] Found role: {role.name}")
            else:
                print(f"🔍 [DEBUG] No officer role ID provided (clearing role)")
                
        except (ValueError, AttributeError) as e:
            print(f"❌ [DEBUG] Error verifying role: {e}")
            return jsonify({"error": f"Invalid role ID format: {str(e)}"}), 400
        
        # Update the officer role ID
        print(f"🔍 [DEBUG] Updating officer role ID in database...")
        org.officer_role_id = officer_role_id
        db.commit()
        
        print(f"✅ [DEBUG] Officer role updated successfully")
        
        return jsonify({
            "message": f"Officer role updated successfully for {org.name}",
            "organization": org.to_dict()
        })
    except Exception as e:
        print(f"❌ [DEBUG] Error in update_officer_role: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500
    finally:
        if 'db' in locals():
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