# modules/calendar/api.py
from flask import Blueprint, jsonify, request, current_app # Add current_app

# Assuming shared resources are correctly set up
from shared import logger, config # Remove calendar_service import
from sentry_sdk import start_transaction, capture_exception, set_tag

# Import the new service and error handler
from .errors import APIErrorHandler

# Initialize the service and a top-level error handler for routes
# calendar_service is now imported from shared.py
route_error_handler = APIErrorHandler(logger, "CalendarAPI_Route")

# Create Flask Blueprint
calendar_blueprint = Blueprint("calendar", __name__)

@calendar_blueprint.route("/notion-webhook", methods=["POST"])
def notion_webhook():
    """
    Webhook endpoint triggered by Notion (or manually) to initiate a full sync
    from Notion to Google Calendar.
    """
    # Create a transaction but don't use context manager to avoid nested context manager issues
    transaction = start_transaction(op="webhook", name="notion_webhook_sync")
    route_error_handler.transaction = transaction # Assign transaction to handler
    route_error_handler.operation_name = "notion_webhook_sync" # Set operation name
    logger.info("Received POST request on /notion-webhook, triggering full Notion->Google sync.")
    set_tag("request_type", "POST")

    try:
        # Delegate the entire sync process to the CalendarService
        # The service method handles its own detailed spans and logging
        sync_result = current_app.calendar_service.sync_notion_to_google(transaction)

        # Return response based on the service result
        if sync_result.get("status") == "error":
            logger.error(f"Sync via webhook finished with error: {sync_result.get('message')}")
            # Use 500 for server-side errors during sync
            return jsonify(sync_result), 500
        elif sync_result.get("status") == "warning":
            logger.warning(f"Sync via webhook finished with warning: {sync_result.get('message')}")
            # Use 207 Multi-Status or 200 OK with warning details
            return jsonify(sync_result), 207
        else:
            logger.info(f"Sync via webhook completed successfully: {sync_result.get('message')}")
            return jsonify(sync_result), 200

    except Exception as e:
        # Catch any unexpected errors at the route level
        # Use the route-level error handler
        route_error_handler.handle_generic_error(e)
        # Return a generic 500 error response
        return jsonify({"status": "error", "message": "An unexpected error occurred processing the webhook."}), 500
    finally:
        route_error_handler.transaction = None # Clear transaction from handler
        # Make sure to finish transaction if no response has been returned yet
        if transaction:
            transaction.finish()


@calendar_blueprint.route("/events", methods=["GET"])
def get_calendar_events_for_frontend():
    """
    API endpoint to fetch published Notion events, parse them,
    and format them for frontend display. Does not interact with Google Calendar directly.
    """
    # Create a transaction but don't use context manager to avoid nested context manager issues
    transaction = start_transaction(op="api", name="get_frontend_events")
    route_error_handler.transaction = transaction
    route_error_handler.operation_name = "get_frontend_events"
    logger.info("Received GET request on /events for frontend data.")
    set_tag("request_type", "GET")

    # Check for required configuration first
    if not config.NOTION_DATABASE_ID:
        logger.error("Required configuration NOTION_DATABASE_ID is missing in .env for /events endpoint.")
        set_tag("config_error", "missing_database_id")
        transaction.set_status("failed_precondition")
        return jsonify({"status": "error", "message": "Notion database ID not configured on server."}), 500

    try:
        # Delegate fetching and formatting to the service
        frontend_result = current_app.calendar_service.get_events_for_frontend(transaction)

        if frontend_result.get("status") == "error":
            logger.error(f"Failed to get frontend events: {frontend_result.get('message')}")
            # Determine appropriate status code (500 for server/fetch errors)
            return jsonify(frontend_result), 500
        else:
            logger.info(f"Successfully prepared {len(frontend_result.get('events', []))} events for frontend.")
            return jsonify(frontend_result), 200

    except Exception as e:
        # Catch unexpected errors at the route level
        route_error_handler.handle_generic_error(e)
        return jsonify({"status": "error", "message": "An unexpected error occurred fetching events for frontend."}), 500
    finally:
        route_error_handler.transaction = None
        # Make sure to finish transaction if no response has been returned yet
        if transaction:
            transaction.finish()


@calendar_blueprint.route("/delete-all-events", methods=["POST"])
def delete_all_calendar_events():
    """
    Admin endpoint to delete ALL events from the configured Google Calendar.
    Requires 'ALLOW_DELETE_ALL' config flag to be True. USE WITH EXTREME CAUTION.
    """
    # Create a transaction but don't use context manager to avoid nested context manager issues
    transaction = start_transaction(op="admin", name="delete_all_events_route")
    route_error_handler.transaction = transaction
    route_error_handler.operation_name = "delete_all_events_route"
    logger.warning("Received POST request on /delete-all-events. THIS IS A DESTRUCTIVE OPERATION.")
    set_tag("request_type", "POST")

    # Basic checks before calling service
    if not config.GOOGLE_CALENDAR_ID:
        logger.error("GOOGLE_CALENDAR_ID not configured. Aborting delete-all.")
        transaction.set_status("failed_precondition")
        return jsonify({"status": "error", "message": "Google Calendar ID not configured on server."}), 500

    # The service method contains the ALLOW_DELETE_ALL check
    try:
        delete_result = current_app.calendar_service.delete_all_events(transaction)

        status_code = 500 # Default to error
        if delete_result.get("status") == "success":
            status_code = 200
            logger.info(f"Delete all events completed: {delete_result.get('message')}")
        elif delete_result.get("status") == "partial_error":
            status_code = 207 # Multi-Status
            logger.warning(f"Delete all events finished with partial errors: {delete_result.get('message')}")
        elif delete_result.get("message") == "Operation prevented by server configuration.":
            status_code = 403 # Forbidden
            logger.error(f"Delete all events prevented by config.")
        else: # Generic error from service
            logger.error(f"Delete all events failed: {delete_result.get('message')}")

        return jsonify(delete_result), status_code

    except Exception as e:
        # Catch unexpected errors at the route level
        route_error_handler.handle_generic_error(e)
        return jsonify({"status": "error", "message": "An unexpected error occurred during the delete-all operation."}), 500
    finally:
        route_error_handler.transaction = None
        # Make sure to finish transaction if no response has been returned yet
        if transaction:
            transaction.finish()


# --- Removed Old Functions ---
# All functions like get_google_calendar_service, fetch_notion_events, parse_event_data,
# update_google_calendar, create_event, update_event, batch_delete_events, clear_synced_events,
# get_all_gcal_events_for_sync, extract_property, parse_single_date_string, etc.
# have been moved to the service, client, utils, or models modules.
