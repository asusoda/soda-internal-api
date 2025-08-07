# modules/calendar/api.py
from flask import Blueprint, jsonify, request, current_app # Add current_app

# Assuming shared resources are correctly set up
from shared import logger, config, db_connect # Remove calendar_service import
from sentry_sdk import start_transaction, capture_exception, set_tag

# Import the new service and error handler
from .errors import APIErrorHandler
from modules.organizations.models import Organization
from modules.auth.decoraters import auth_required

# Initialize the service and a top-level error handler for routes
route_error_handler = APIErrorHandler(logger, "CalendarAPI_Route")

# Create Flask Blueprint
calendar_blueprint = Blueprint("calendar", __name__)

@calendar_blueprint.route("/debug/organizations", methods=["GET"])
def debug_organizations():
    """Debug endpoint to list all organizations."""
    try:
        with next(db_connect.get_db()) as session:
            orgs = session.query(Organization).filter(Organization.is_active == True).all()
            org_list = [{"id": org.id, "name": org.name, "prefix": org.prefix} for org in orgs]
            return jsonify({
                "status": "success",
                "organizations": org_list,
                "count": len(org_list)
            })
    except Exception as e:
        logger.error(f"Error in debug_organizations: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@calendar_blueprint.route("/<org_prefix>/events", methods=["GET"])
def get_organization_events(org_prefix):
    """
    Public endpoint to get events for a specific organization.
    Accessible via: /api/calendar/{org_prefix}/events
    """
    transaction = start_transaction(op="api", name="get_org_events")
    route_error_handler.transaction = transaction
    route_error_handler.operation_name = "get_org_events"
    logger.info(f"Received GET request for organization events: {org_prefix}")
    set_tag("request_type", "GET")
    set_tag("organization_prefix", org_prefix)

    try:
        with next(db_connect.get_db()) as session:
            # Get organization by prefix
            org = session.query(Organization).filter(
                Organization.prefix == org_prefix,
                Organization.is_active == True
            ).first()
            
            if not org:
                # Check if organization exists but is inactive
                inactive_org = session.query(Organization).filter(
                    Organization.prefix == org_prefix
                ).first()
                
                if inactive_org:
                    logger.warning(f"Organization with prefix '{org_prefix}' exists but is inactive")
                    return jsonify({
                        "status": "error", 
                        "message": f"Organization '{org_prefix}' exists but is inactive"
                    }), 403
                else:
                    logger.warning(f"Organization with prefix '{org_prefix}' not found")
                    return jsonify({
                        "status": "error", 
                        "message": f"Organization '{org_prefix}' not found"
                    }), 404

            # Check if organization has calendar configuration
            if not org.notion_database_id:
                return jsonify({
                    "status": "error",
                    "message": f"Organization '{org_prefix}' has no Notion database configured"
                }), 400

            # Get events using multi-org service
            events_result = current_app.multi_org_calendar_service.get_organization_events_for_frontend(
                org.id, transaction
            )

            if events_result.get("status") == "error":
                logger.error(f"Failed to get events for org {org_prefix}: {events_result.get('message')}")
                return jsonify(events_result), 500
            else:
                logger.info(f"Successfully prepared {len(events_result.get('events', []))} events for org {org_prefix}")
                return jsonify(events_result), 200

    except Exception as e:
        route_error_handler.handle_generic_error(e)
        return jsonify({"status": "error", "message": "An unexpected error occurred"}), 500
    finally:
        route_error_handler.transaction = None
        if transaction:
            transaction.finish()

@calendar_blueprint.route("/<org_prefix>/sync", methods=["POST"])
@auth_required
def sync_organization_calendar(org_prefix):
    """
    Admin endpoint to sync Notion to Google Calendar for a specific organization.
    Accessible via: /api/calendar/{org_prefix}/sync
    Requires authentication.
    """
    transaction = start_transaction(op="admin", name="sync_org_calendar")
    route_error_handler.transaction = transaction
    route_error_handler.operation_name = "sync_org_calendar"
    logger.info(f"Received POST request to sync organization calendar: {org_prefix}")
    set_tag("request_type", "POST")
    set_tag("organization_prefix", org_prefix)

    try:
        with next(db_connect.get_db()) as session:
            # Get organization by prefix
            org = session.query(Organization).filter(
                Organization.prefix == org_prefix,
                Organization.is_active == True
            ).first()
            
            if not org:
                logger.warning(f"Organization with prefix '{org_prefix}' not found or inactive")
                return jsonify({"status": "error", "message": "Organization not found"}), 404

            # Sync using multi-org service
            sync_result = current_app.multi_org_calendar_service.sync_organization_notion_to_google(
                org.id, transaction
            )

            if sync_result.get("status") == "error":
                logger.error(f"Failed to sync org {org_prefix}: {sync_result.get('message')}")
                return jsonify(sync_result), 500
            else:
                logger.info(f"Successfully synced calendar for org {org_prefix}")
                return jsonify(sync_result), 200

    except Exception as e:
        route_error_handler.handle_generic_error(e)
        return jsonify({"status": "error", "message": "An unexpected error occurred"}), 500
    finally:
        route_error_handler.transaction = None
        if transaction:
            transaction.finish()

@calendar_blueprint.route("/<org_prefix>/setup", methods=["POST"])
@auth_required
def setup_organization_calendar(org_prefix):
    """
    Admin endpoint to set up calendar for a new organization.
    Accessible via: /api/calendar/{org_prefix}/setup
    Requires authentication.
    """
    transaction = start_transaction(op="admin", name="setup_org_calendar")
    route_error_handler.transaction = transaction
    route_error_handler.operation_name = "setup_org_calendar"
    logger.info(f"Received POST request to setup organization calendar: {org_prefix}")
    set_tag("request_type", "POST")
    set_tag("organization_prefix", org_prefix)

    try:
        with next(db_connect.get_db()) as session:
            # Get organization by prefix
            org = session.query(Organization).filter(
                Organization.prefix == org_prefix,
                Organization.is_active == True
            ).first()
            
            if not org:
                logger.warning(f"Organization with prefix '{org_prefix}' not found or inactive")
                return jsonify({"status": "error", "message": "Organization not found"}), 404

            # Ensure calendar exists
            calendar_id = current_app.multi_org_calendar_service.ensure_organization_calendar(
                org.id, org.name, transaction
            )

            if calendar_id:
                logger.info(f"Successfully set up calendar {calendar_id} for org {org_prefix}")
                return jsonify({
                    "status": "success",
                    "message": f"Calendar set up for organization {org_prefix}",
                    "calendar_id": calendar_id,
                    "organization_id": org.id
                }), 200
            else:
                logger.error(f"Failed to set up calendar for org {org_prefix}")
                return jsonify({"status": "error", "message": "Failed to set up calendar"}), 500

    except Exception as e:
        route_error_handler.handle_generic_error(e)
        return jsonify({"status": "error", "message": "An unexpected error occurred"}), 500
    finally:
        route_error_handler.transaction = None
        if transaction:
            transaction.finish()

@calendar_blueprint.route("/sync-all", methods=["POST"])
@auth_required
def sync_all_organizations():
    """
    Admin endpoint to sync all organizations with calendar sync enabled.
    Accessible via: /api/calendar/sync-all
    Requires authentication.
    """
    transaction = start_transaction(op="admin", name="sync_all_organizations")
    route_error_handler.transaction = transaction
    route_error_handler.operation_name = "sync_all_organizations"
    logger.info("Received POST request to sync all organizations")
    set_tag("request_type", "POST")

    try:
        # Sync all organizations using multi-org service
        sync_result = current_app.multi_org_calendar_service.sync_all_organizations(transaction)

        if sync_result.get("status") == "error":
            logger.error(f"Failed to sync all organizations: {sync_result.get('message')}")
            return jsonify(sync_result), 500
        else:
            logger.info(f"Successfully synced {sync_result.get('organizations_processed', 0)} organizations")
            return jsonify(sync_result), 200

    except Exception as e:
        route_error_handler.handle_generic_error(e)
        return jsonify({"status": "error", "message": "An unexpected error occurred"}), 500
    finally:
        route_error_handler.transaction = None
        if transaction:
            transaction.finish()

# Legacy endpoints for backward compatibility (deprecated)
@calendar_blueprint.route("/notion-webhook", methods=["POST"])
def notion_webhook():
    """
    Legacy webhook endpoint - now delegates to sync-all.
    """
    logger.warning("Legacy /notion-webhook endpoint called. This will sync all organizations.")
    return sync_all_organizations()

@calendar_blueprint.route("/events", methods=["GET"])
def get_calendar_events_for_frontend():
    """
    Legacy endpoint - returns error as this requires organization context.
    """
    return jsonify({
        "status": "error", 
        "message": "This endpoint requires organization context. Use /api/calendar/{org_prefix}/events instead."
    }), 400

@calendar_blueprint.route("/delete-all-events", methods=["POST"])
def delete_all_calendar_events():
    """
    Legacy endpoint - returns error as this requires organization context.
    """
    return jsonify({
        "status": "error", 
        "message": "This endpoint requires organization context. Use organization-specific endpoints instead."
    }), 400


