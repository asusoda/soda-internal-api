from flask import Blueprint, jsonify, request, session

from core.db import db_connect
from core.errors import ServiceError
from core.log import get_logger
from modules.auth.access import current_principal, discord_directory
from modules.auth.decorators import superadmin_required
from modules.auth.routes import respond
from modules.auth.tokens import token_manager
from modules.organizations.models import Organization
from modules.runpod import service as apps
from modules.runpod import shared

from . import service

logger = get_logger(__name__)

superadmin_blueprint = Blueprint("superadmin", __name__)


@superadmin_blueprint.route("/check", methods=["GET"])
def check_superadmin():
    """Whether the caller is the superadmin: 200 when yes, 403 when no.

    It answers for the caller's own valid token only, so it does not need superadmin_required.
    """
    try:
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            logger.error("Invalid Authorization header format")
            return jsonify({"error": "Authorization header required"}), 401

        token_data = token_manager.decode_token(auth_header.split(" ")[1])
        if not token_data:
            logger.error("Failed to decode token")
            return jsonify({"error": "Invalid token"}), 401

        user_discord_id = token_data.get("discord_id")
        if not user_discord_id:
            logger.error("Token missing Discord ID")
            return jsonify({"error": "Token missing Discord ID"}), 401

        if service.is_superadmin(user_discord_id):
            return jsonify({"is_superadmin": True}), 200
        return jsonify({"is_superadmin": False}), 403
    except Exception as e:
        logger.exception(f"Error in check_superadmin: {e}")
        return jsonify({"error": f"Error checking superadmin status: {str(e)}"}), 500


@superadmin_blueprint.route("/dashboard", methods=["GET"])
@superadmin_required
def get_dashboard():
    """Guilds without an org, every org, and the orgs whose guild has the caller."""
    try:
        directory = discord_directory()
        if directory is None or not directory.is_ready():
            return jsonify({"error": "Bot not available"}), 503

        guilds = directory.list_guilds()
        db = next(db_connect.get_db())
        existing_orgs = db.query(Organization).all()
        officer_id = session.get("user", {}).get("discord_id")
        officer_orgs = service.officer_orgs(directory, existing_orgs, officer_id)

        return jsonify(
            {
                "available_guilds": service.available_guilds(guilds, existing_orgs),
                "existing_orgs": [org.to_dict() for org in existing_orgs],
                "officer_orgs": [org.to_dict() for org in officer_orgs],
            }
        )
    except Exception as e:
        logger.exception(f"Error in get_dashboard: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        if "db" in locals():
            db.close()


@superadmin_blueprint.route("/guild_roles/<guild_id>", methods=["GET"])
@superadmin_required
def get_guild_roles(guild_id):
    """The guild's roles, highest first, without @everyone and integration roles."""
    try:
        directory = discord_directory()
        if directory is None or not directory.is_ready():
            return jsonify({"error": "Bot not available"}), 503

        try:
            guild_id_int = int(guild_id)
        except ValueError:
            logger.error(f"Invalid guild ID format: {guild_id}")
            return jsonify({"error": "Invalid guild ID format"}), 400

        guild = directory.get_guild(guild_id_int)
        if not guild:
            logger.error(f"Guild not found for ID: {guild_id_int}")
            return jsonify({"error": "Guild not found"}), 404

        return jsonify({"roles": service.guild_roles(directory, guild_id_int)})
    except Exception as e:
        logger.exception(f"Error in get_guild_roles: {e}")
        return jsonify({"error": str(e)}), 500


@superadmin_blueprint.route("/update_officer_role/<int:org_id>", methods=["PUT"])
@superadmin_required
def update_officer_role(org_id):
    """Set the org's officer role. An empty officer_role_id clears it."""
    try:
        data = request.get_json()
        if not data or "officer_role_id" not in data:
            logger.error("Missing officer_role_id in request data")
            return jsonify({"error": "officer_role_id is required"}), 400

        officer_role_id = data["officer_role_id"]

        directory = discord_directory()
        if directory is None or not directory.is_ready():
            return jsonify({"error": "Bot not available"}), 503

        db = next(db_connect.get_db())
        org = db.query(Organization).filter_by(id=org_id).first()

        if not org:
            logger.error(f"Organization not found for ID: {org_id}")
            return jsonify({"error": "Organization not found"}), 404

        try:
            guild = directory.get_guild(int(org.guild_id))
            if not guild:
                logger.error(f"Guild not found for ID: {org.guild_id}")
                return jsonify({"error": "Guild not found"}), 404

            if officer_role_id and not service.role_in_guild(directory, org.guild_id, officer_role_id):
                logger.error(f"Role not found in guild for ID: {officer_role_id}")
                return jsonify({"error": "Role not found in guild"}), 404

        except (ValueError, AttributeError) as e:
            logger.error(f"Error verifying role: {e}")
            return jsonify({"error": f"Invalid role ID format: {str(e)}"}), 400

        org.officer_role_id = officer_role_id
        db.commit()

        return jsonify({"message": f"Officer role updated successfully for {org.name}", "organization": org.to_dict()})
    except Exception as e:
        logger.exception(f"Error in update_officer_role: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        if "db" in locals():
            db.close()


@superadmin_blueprint.route("/add_org/<guild_id>", methods=["POST"])
@superadmin_required
def add_organization(guild_id):
    """Add an org for a guild the bot is in, with default settings."""
    try:
        directory = discord_directory()
        if directory is None or not directory.is_ready():
            return jsonify({"error": "Bot not available"}), 503

        try:
            guild_id_int = int(guild_id)
        except ValueError:
            return jsonify({"error": "Invalid guild ID format"}), 400

        guild = directory.get_guild(guild_id_int)
        if not guild:
            return jsonify({"error": "Guild not found"}), 404

        new_org = service.new_organization(guild)

        db = next(db_connect.get_db())
        try:
            if db.query(Organization).filter_by(prefix=new_org.prefix).first() is not None:
                return jsonify({"error": f"The prefix {new_org.prefix} is already taken"}), 409
            db.add(new_org)
            db.commit()
        finally:
            db.close()

        return jsonify({"message": f"Organization {guild['name']} added successfully!"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@superadmin_blueprint.route("/remove_org/<int:org_id>", methods=["DELETE"])
@superadmin_required
def remove_organization(org_id):
    """Delete an org."""
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


@superadmin_blueprint.route("/audit", methods=["GET"])
@superadmin_required
def get_audit():
    """Audit log across all orgs, newest first. ?org=<prefix>&limit=100&before_id=<id>."""
    from core import audit

    db = next(db_connect.get_db())
    try:
        entries = audit.list_entries(
            db,
            org=request.args.get("org"),
            limit=request.args.get("limit", 100, type=int),
            before_id=request.args.get("before_id", type=int),
        )
        return jsonify({"entries": entries})
    finally:
        db.close()


@superadmin_blueprint.route("/publishers", methods=["GET"])
@superadmin_required
def get_publishers():
    """Orgs that may write knowledge every org can search, and where the right comes from."""
    from modules.knowledge import service as knowledge

    db = next(db_connect.get_db())
    try:
        return respond(db, lambda db: {"publishers": knowledge.publishers(db)})
    finally:
        db.close()


@superadmin_blueprint.route("/publishers/<int:org_id>", methods=["PUT"])
@superadmin_required
def put_publisher(org_id):
    """Mark or unmark an org as a knowledge publisher. Body: {"publisher": true}."""
    from modules.knowledge import service as knowledge

    data = request.get_json(silent=True) or {}
    db = next(db_connect.get_db())
    try:
        return respond(db, lambda db: {"publishers": knowledge.set_publisher(db, org_id, data.get("publisher"))})
    finally:
        db.close()


@superadmin_blueprint.route("/errors", methods=["GET"])
@superadmin_required
def get_errors():
    """Errors of every org and of the whole server, newest first. ?org=<prefix>&status=open|resolved|all."""
    from core import error_log

    db = next(db_connect.get_db())
    try:
        return jsonify(
            {
                "errors": error_log.list_groups(
                    db,
                    org=request.args.get("org") or None,
                    everything=True,
                    status=request.args.get("status", "open"),
                    limit=request.args.get("limit", 100, type=int),
                )
            }
        )
    finally:
        db.close()


@superadmin_blueprint.route("/errors/<string:action>", methods=["POST"])
@superadmin_required
def change_errors(action):
    """Resolve or reopen errors of any org. Body: {"ids": [1, 2]}."""
    from core import error_log

    ids = (request.get_json(silent=True) or {}).get("ids")
    if action not in ("resolve", "reopen"):
        return jsonify({"error": "Unknown action"}), 404
    if not isinstance(ids, list) or not ids or len(ids) > 200 or not all(isinstance(i, int) for i in ids):
        return jsonify({"error": "ids must be a list of 1 to 200 error ids"}), 400
    db = next(db_connect.get_db())
    try:
        changed = error_log.set_resolved(db, ids, resolved=action == "resolve", actor="superadmin")
        return jsonify({"changed": changed})
    finally:
        db.close()


def _org_or_404(db, org_id: int) -> Organization:
    org = db.query(Organization).filter_by(id=org_id).first()
    if org is None:
        raise ServiceError("Organization not found", 404)
    return org


@superadmin_blueprint.route("/server", methods=["GET"])
@superadmin_required
def get_server():
    """The server's health: load, memory, disk, database size, this container, the bot and the job queue."""
    directory = discord_directory()
    bot_ready = None if directory is None else bool(directory.is_ready())
    db = next(db_connect.get_db())
    try:
        return respond(db, lambda db: service.server(db, bot_ready))
    finally:
        db.close()


@superadmin_blueprint.route("/server/services", methods=["GET"])
@superadmin_required
def get_server_services():
    """Each container and host process on the server, from the host agent, with its owner."""
    db = next(db_connect.get_db())
    try:
        return respond(db, service.server_services)
    finally:
        db.close()


@superadmin_blueprint.route("/server/services/<string:name>", methods=["PUT"])
@superadmin_required
def put_server_service(name):
    """Set who owns a service. Body: {"owner": "org", "organization_id": 1}, or {"owner": null} for the labels."""
    body = request.get_json(silent=True)
    principal = current_principal()
    actor = f"superadmin:{principal.discord_id}" if principal and principal.discord_id else "superadmin"
    db = next(db_connect.get_db())
    try:
        return respond(db, lambda db: service.set_service_owner(db, name, body, actor))
    finally:
        db.close()


@superadmin_blueprint.route("/limits", methods=["GET"])
@superadmin_required
def get_limits():
    """Every declared limit, and each org's limits, use and overrides."""
    db = next(db_connect.get_db())
    try:
        return respond(db, service.all_limits)
    finally:
        db.close()


@superadmin_blueprint.route("/limits/<int:org_id>", methods=["GET"])
@superadmin_required
def get_org_limits(org_id):
    """One org's limits, use and overrides."""
    db = next(db_connect.get_db())
    try:
        return respond(db, lambda db: service.org_limits(db, _org_or_404(db, org_id)))
    finally:
        db.close()


@superadmin_blueprint.route("/limits/<int:org_id>", methods=["PUT"])
@superadmin_required
def put_org_limits(org_id):
    """Set an org's limits. Body: {"limits": {"knowledge.sources": 200, "godfather.pods": null}}.

    A number sets the limit, null removes the limit, "default" goes back to the default.
    """
    changes = (request.get_json(silent=True) or {}).get("limits")
    principal = current_principal()
    actor = f"superadmin:{principal.discord_id}" if principal and principal.discord_id else "superadmin"
    db = next(db_connect.get_db())
    try:
        return respond(db, lambda db: service.set_org_limits(db, _org_or_404(db, org_id), changes, actor))
    finally:
        db.close()


@superadmin_blueprint.route("/submodules", methods=["GET"])
@superadmin_required
def get_submodules():
    """Every submodule with its subscribers, shared pages, passages and failing pages."""
    from modules.submodules import service as submodules

    db = next(db_connect.get_db())
    try:
        return respond(db, lambda db: {"submodules": submodules.overview(db)})
    finally:
        db.close()


def _superadmin_actor() -> str:
    principal = current_principal()
    return f"superadmin:{principal.discord_id}" if principal and principal.discord_id else "superadmin"


def _shared(work):
    db = next(db_connect.get_db())
    try:
        return respond(db, work)
    finally:
        db.close()


@superadmin_blueprint.route("/shared-apps", methods=["GET"])
@superadmin_required
def list_shared_apps():
    """The shared apps: apps the deployment owns on This server, which orgs subscribe to."""
    return _shared(lambda db: {"apps": shared.list_shared(db)})


@superadmin_blueprint.route("/shared-apps/<string:name>", methods=["GET"])
@superadmin_required
def get_shared_app(name):
    """One shared app with its deployments, the names of its secrets and its subscribers."""
    return _shared(lambda db: shared.get_shared(db, name))


@superadmin_blueprint.route("/shared-apps/<string:name>", methods=["PUT"])
@superadmin_required
def put_shared_app(name):
    """Register a shared app or replace its manifest. Body: {"manifest": {...}}. It runs on This server."""
    manifest = (request.get_json(silent=True) or {}).get("manifest")
    return _shared(lambda db: shared.put_shared(db, name, manifest))


@superadmin_blueprint.route("/shared-apps/<string:name>", methods=["DELETE"])
@superadmin_required
def delete_shared_app(name):
    """Remove a shared app and its container. Its data folders stay on the server."""
    return _shared(lambda db: apps.delete_app(db, None, name))


@superadmin_blueprint.route("/shared-apps/<string:name>/deploy", methods=["POST"])
@superadmin_required
def deploy_shared_app(name):
    """Deploy a tag of a shared app. Body: {"tag": "1.2.3", "dry_run": false}."""
    body = request.get_json(silent=True) or {}
    actor = _superadmin_actor()
    return _shared(
        lambda db: (apps.deploy(db, None, None, name, body.get("tag"), actor, bool(body.get("dry_run"))), 202)
    )


@superadmin_blueprint.route("/shared-apps/<string:name>/rollback", methods=["POST"])
@superadmin_required
def rollback_shared_app(name):
    """Deploy the last healthy tag before the current one."""
    body = request.get_json(silent=True) or {}
    actor = _superadmin_actor()
    return _shared(lambda db: (apps.rollback(db, None, None, name, actor, bool(body.get("dry_run"))), 202))


@superadmin_blueprint.route("/shared-apps/<string:name>/pod", methods=["GET"])
@superadmin_required
def shared_app_pod(name):
    """The container of a shared app, as the runner describes it."""
    return _shared(lambda db: {"pod": apps.pod(db, None, name)})


@superadmin_blueprint.route("/shared-apps/<string:name>/secrets", methods=["PUT"])
@superadmin_required
def put_shared_app_secrets(name):
    """Save secrets of a shared app. Body: {"secrets": {"ADMIN_TOKEN": "...", "OLD_KEY": null}}."""
    values = (request.get_json(silent=True) or {}).get("secrets")
    actor = _superadmin_actor()
    return _shared(lambda db: shared.set_secrets(db, name, values, actor))


@superadmin_blueprint.route("/shared-apps/<string:name>/action", methods=["POST"])
@superadmin_required
def shared_app_action(name):
    """Start, stop or restart a shared app. Body: {"action": "restart"}."""
    action = (request.get_json(silent=True) or {}).get("action")
    return _shared(lambda db: apps.app_action(db, None, name, action))


@superadmin_blueprint.route("/shared-apps/<string:name>/logs", methods=["GET"])
@superadmin_required
def shared_app_logs(name):
    lines = request.args.get("lines", 200, type=int)
    return _shared(lambda db: apps.app_logs(db, None, name, lines))


@superadmin_blueprint.route("/server/services/<string:name>/action", methods=["POST"])
@superadmin_required
def server_service_action(name):
    """Start, stop or restart a service on the server, if the runner's policy lists it. Body: {"action": "restart"}."""
    action = (request.get_json(silent=True) or {}).get("action")
    return _shared(lambda db: service.service_action(db, name, action, _superadmin_actor()))


@superadmin_blueprint.route("/server/services/<string:name>/logs", methods=["GET"])
@superadmin_required
def server_service_logs(name):
    lines = request.args.get("lines", 200, type=int)
    return _shared(lambda db: service.service_logs(db, name, lines))
