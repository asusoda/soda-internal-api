import uuid

from flask import Blueprint, jsonify, request
from sqlalchemy.exc import IntegrityError

from core.db import db_connect
from core.http.responses import error_handler
from core.log import get_logger
from modules.auth import access
from modules.auth.decorators import auth_required
from modules.auth.routes import officer_route
from modules.organizations import service as organizations
from modules.points import service as points
from modules.users import service as users
from modules.users.models import User, UserOrganizationMembership
from modules.users.service import (
    active_members,
    active_membership,
    link_or_create_user,
    member_fields,
    member_input,
    merge_profile_fields,
)

logger = get_logger(__name__)

users_blueprint = Blueprint("users", __name__, template_folder=None, static_folder=None)


@users_blueprint.route("/", methods=["GET"])
def users_index():
    return jsonify({"message": "users api"}), 200


@users_blueprint.route("/<string:org_prefix>/viewUser", methods=["GET"])
@auth_required
@error_handler
def view_user_in_org(org_prefix):
    user_identifier = request.args.get("user_identifier")

    if not user_identifier:
        return jsonify({"error": "User identifier (email, UUID, or username) is required."}), 400

    db = next(db_connect.get_db())

    try:
        organization = organizations.find_by_prefix(db, org_prefix, active_only=True)

        if not organization:
            return jsonify({"error": "Organization not found"}), 404

        user = (
            db.query(User)
            .filter(
                (User.email == user_identifier) | (User.uuid == user_identifier) | (User.username == user_identifier)
            )
            .first()
        )

        if not user:
            return jsonify({"error": "User not found."}), 404

        membership = active_membership(db, user.id, organization.id)

        if not membership:
            return jsonify({"error": "User is not a member of this organization"}), 404

        org_points = points.total_points(db, user.id, organization.id) or 0

        points_data = [points.history_json(record) for record in points.history(db, user.id, organization.id)]

        user_data = {
            "id": user.id,
            "name": user.name,
            "username": user.username,
            "email": user.email,
            "uuid": user.uuid,
            **member_fields(user, membership),
            "major": user.major,
            "discord_linked": bool(user.discord_id),
            "created_at": user.created_at.isoformat() if user.created_at else None,
            "points": org_points,
            "points_history": points_data,
            "joined_at": membership.joined_at.isoformat() if membership.joined_at else None,
            "organization": {
                "id": organization.id,
                "name": organization.name,
                "prefix": organization.prefix,
                "description": organization.description,
            },
        }

        return jsonify(user_data), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()


@users_blueprint.route("/<string:org_prefix>/createUser", methods=["POST"])
@auth_required
@error_handler
def create_user_in_org(org_prefix):
    user_email = request.args.get("email")
    user_name = request.args.get("name")
    args = member_input(request.args.to_dict())
    student_id = args.get("student_id")
    class_standing = args.get("class_standing")

    if not user_email or not user_name:
        return jsonify({"error": "Email and name are required"}), 400

    db = next(db_connect.get_db())
    try:
        organization = organizations.find_by_prefix(db, org_prefix, active_only=True)

        if not organization:
            return jsonify({"error": "Organization not found"}), 404

        existing_user = db.query(User).filter_by(email=user_email).first()

        if existing_user:
            membership = active_membership(db, existing_user.id, organization.id)

            if membership:
                return jsonify({"error": "User is already a member of this organization"}), 400

            new_membership = UserOrganizationMembership(user_id=existing_user.id, organization_id=organization.id)
            db.add(new_membership)
            db.commit()
            return jsonify({"message": "Existing user added to organization successfully."}), 200

        new_user = User(
            email=user_email,
            name=user_name,
            username=None,
            student_id=student_id if student_id and student_id != "N/A" else None,
            class_standing=class_standing or "N/A",
            major="N/A",
            uuid=str(uuid.uuid4()),
        )
        try:
            db.add(new_user)
            db.commit()
            db.refresh(new_user)
        except IntegrityError:
            db.rollback()

            if user_email:
                logger.warning(f"Duplicate email found for {user_email}, returning existing user.")
                existing_user = db.query(User).filter_by(email=user_email).first()
                if existing_user:
                    new_membership = UserOrganizationMembership(
                        user_id=existing_user.id, organization_id=organization.id
                    )
                    db.add(new_membership)
                    db.commit()
                    return jsonify({"message": "Existing user added to organization successfully."}), 200
            raise

        membership = UserOrganizationMembership(user_id=new_user.id, organization_id=organization.id)
        db.add(membership)
        db.commit()

        return jsonify({"message": "User created and added to organization successfully."}), 201

    except Exception as e:
        db.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()


@users_blueprint.route("/<string:org_prefix>/user", methods=["GET", "POST"])
@auth_required
@error_handler
def user_in_org(org_prefix):
    user_email = request.args.get("email") if request.method == "GET" else request.json.get("email")

    if not user_email:
        return jsonify({"error": "Email is required."}), 400

    db = next(db_connect.get_db())

    try:
        organization = organizations.find_by_prefix(db, org_prefix, active_only=True)

        if not organization:
            return jsonify({"error": "Organization not found"}), 404

        user = db.query(User).filter_by(email=user_email).first()

        if request.method == "GET":
            if not user:
                return jsonify({"error": "User not found."}), 404

            membership = active_membership(db, user.id, organization.id)

            if not membership:
                return jsonify({"error": "User is not a member of this organization"}), 404

            user_data = {
                "name": user.name,
                "email": user.email,
                "uuid": user.uuid,
                **member_fields(user, membership),
                "major": user.major,
            }
            return jsonify(user_data), 200

        elif request.method == "POST":
            data = member_input(request.json or {})

            if user:
                membership = active_membership(db, user.id, organization.id)

                if not membership:
                    return jsonify({"error": "User is not a member of this organization"}), 404

                if "name" in data:
                    user.name = data["name"]
                if "student_id" in data:
                    user.student_id = data["student_id"]
                if "class_standing" in data:
                    user.class_standing = data["class_standing"]
                if "major" in data:
                    user.major = data["major"]
                if "profile_fields" in data:
                    error = merge_profile_fields(membership, data["profile_fields"])
                    if error:
                        db.rollback()
                        return jsonify({"error": error}), 400

                db.commit()
                return jsonify({"message": "User information updated successfully."}), 200

            else:
                new_user = User(
                    name=data.get("name"),
                    email=user_email,
                    username=None,
                    student_id=data.get("student_id")
                    if data.get("student_id") and data.get("student_id") != "N/A"
                    else None,
                    class_standing=data.get("class_standing", "N/A"),
                    major=data.get("major", "N/A"),
                    uuid=str(uuid.uuid4()),
                )
                try:
                    db.add(new_user)
                    db.commit()
                    db.refresh(new_user)
                except IntegrityError:
                    db.rollback()

                    if user_email:
                        logger.warning(f"Duplicate email found for {user_email}, returning existing user.")
                        existing_user = db.query(User).filter_by(email=user_email).first()
                        if existing_user:
                            membership = (
                                db.query(UserOrganizationMembership)
                                .filter_by(user_id=existing_user.id, organization_id=organization.id)
                                .first()
                            )
                            if not membership:
                                membership = UserOrganizationMembership(
                                    user_id=existing_user.id, organization_id=organization.id
                                )
                                db.add(membership)
                            else:
                                if hasattr(membership, "is_active") and not membership.is_active:
                                    membership.is_active = True
                            db.commit()
                            return jsonify({"message": "User created and added to organization successfully."}), 201
                    raise

                membership = UserOrganizationMembership(user_id=new_user.id, organization_id=organization.id)
                if "profile_fields" in data:
                    error = merge_profile_fields(membership, data["profile_fields"])
                    if error:
                        db.rollback()
                        return jsonify({"error": error}), 400
                db.add(membership)
                db.commit()

                return jsonify({"message": "User created and added to organization successfully."}), 201

    except Exception as e:
        db.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()


@users_blueprint.route("/<string:org_prefix>/submit-form", methods=["POST"])
def handle_form_submission_in_org(org_prefix):
    try:
        data = request.get_json()

        discordID = data.get("discordID")
        role = data.get("role")

    except Exception:
        logger.exception("Error while handling form submission for org_prefix=%s", org_prefix)
        return jsonify({"error": "An internal error occurred while processing the form."}), 500

    return jsonify({"message": "recieved id: " + discordID + " and role: " + role}), 200


@users_blueprint.route("/<string:org_prefix>/users", methods=["GET"])
@auth_required
@error_handler
def get_organization_users(org_prefix):
    """Get all users for a specific organization"""
    db = next(db_connect.get_db())
    try:
        organization = organizations.find_by_prefix(db, org_prefix, active_only=True)

        if not organization:
            return jsonify({"error": "Organization not found"}), 404

        totals = points.totals_by_user(db, organization.id)
        users_data = [
            {
                "id": user.id,
                "name": user.name,
                "username": user.username,
                "email": user.email,
                **member_fields(user, membership),
                "major": user.major,
                "discord_linked": bool(user.discord_id),
                "points": totals.get(user.id) or 0,
                "joined_at": membership.joined_at.isoformat() if membership.joined_at else None,
            }
            for membership, user in active_members(db, organization.id)
        ]

        return jsonify(
            {
                "organization": {
                    "name": organization.name,
                    "prefix": organization.prefix,
                    "description": organization.description,
                },
                "total_members": len(users_data),
                "users": users_data,
            }
        ), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()


@users_blueprint.route("/<string:org_prefix>/users/<string:user_identifier>", methods=["GET"])
@auth_required
@error_handler
def get_user_in_organization(org_prefix, user_identifier):
    """Get a specific user's details within an organization"""
    db = next(db_connect.get_db())
    try:
        organization = organizations.find_by_prefix(db, org_prefix, active_only=True)

        if not organization:
            return jsonify({"error": "Organization not found"}), 404

        user = (
            db.query(User)
            .filter(
                (User.email == user_identifier) | (User.uuid == user_identifier) | (User.username == user_identifier)
            )
            .first()
        )

        if not user:
            return jsonify({"error": "User not found"}), 404

        membership = active_membership(db, user.id, organization.id)

        if not membership:
            return jsonify({"error": "User is not a member of this organization"}), 404

        user_points = points.total_points(db, user.id, organization.id) or 0

        points_history = [points.history_json(record) for record in points.history(db, user.id, organization.id)]

        return jsonify(
            {
                "user": {
                    "id": user.id,
                    "name": user.name,
                    "username": user.username,
                    "email": user.email,
                    **member_fields(user, membership),
                    "major": user.major,
                    "discord_linked": bool(user.discord_id),
                    "created_at": user.created_at.isoformat() if user.created_at else None,
                },
                "organization": {
                    "name": organization.name,
                    "prefix": organization.prefix,
                    "description": organization.description,
                },
                "membership": {
                    "points": user_points,
                    "joined_at": membership.joined_at.isoformat() if membership.joined_at else None,
                    "points_history": points_history,
                },
            }
        ), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()


@users_blueprint.route("/<string:org_prefix>/users", methods=["POST"])
@auth_required
@error_handler
def add_user_to_organization(org_prefix):
    """Add a user to a specific organization"""
    data = request.json
    db = next(db_connect.get_db())
    try:
        organization = organizations.find_by_prefix(db, org_prefix, active_only=True)

        if not organization:
            return jsonify({"error": "Organization not found"}), 404

        if not data.get("name") and not data.get("username"):
            return jsonify({"error": "Either name or username is required"}), 400

        fields = member_input(data)
        student_id = fields.get("student_id")
        user_data = {
            "username": fields.get("username"),
            "email": fields.get("email"),
            "name": fields.get("name"),
            "student_id": student_id if student_id and student_id != "N/A" else None,
            "class_standing": fields.get("class_standing", "N/A"),
            "major": fields.get("major", "N/A"),
            "profile_fields": fields.get("profile_fields"),
        }

        user = link_or_create_user(organization.id, user_data, data.get("discord_id"))

        if not user:
            return jsonify({"error": "Failed to create or link user"}), 500

        return jsonify(
            {
                "message": "User added to organization successfully",
                "user": {
                    "id": user.id,
                    "name": user.name,
                    "username": user.username,
                    "email": user.email,
                    "discord_linked": bool(user.discord_id),
                },
                "organization": {"name": organization.name, "prefix": organization.prefix},
            }
        ), 201

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()


# Members from the org's Discord server


@officer_route(users_blueprint, "/discord/roles", ["GET"])
def discord_roles(db, org):
    """Server roles to filter members by."""
    return {"roles": users.server_roles(access.discord_directory(), org.guild_id)}


@officer_route(users_blueprint, "/discord/sync", ["POST"])
def discord_sync(db, org):
    """Add the server's members to the org's members. Body: roles (ids; any of them, empty for all), dry_run."""
    data = request.get_json(silent=True) or {}
    directory = access.discord_directory()
    return users.sync_from_discord(
        db, int(org.id), org.guild_id, directory, data.get("roles") or [], data.get("dry_run") is True
    )
