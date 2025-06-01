from flask import Blueprint, jsonify, request, current_app
from sentry_sdk import start_transaction, capture_exception, set_tag

# Import the service and shared resources
from .service import OCPService
from ..errors import APIErrorHandler
from .utils import extract_property
from modules.auth.decoraters import auth_required

# Setup logger from shared resources
from shared import logger, config
# Initialize the error handler for routes
route_error_handler = APIErrorHandler(logger, "OCPApi_Route")

# Create Flask Blueprint - remove the url_prefix to avoid duplicate prefixes
ocp_blueprint = Blueprint("ocp", __name__)

# Initialize OCP service immediately
try:
    logger.info("Initializing OCP service...")
    ocp_service = OCPService()
    logger.info("OCP service initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize OCP service: {str(e)}")
    # Still set to avoid repeated initialization attempts
    ocp_service = OCPService(db_connect=None, notion_client=None)

@ocp_blueprint.route("/sync-from-notion", methods=["POST"])
def sync_from_notion():
    """
    Endpoint to sync officer contribution points from Notion events.
    Fetches events from the configured Notion database and updates the OCP database.
    """
    transaction = start_transaction(op="webhook", name="ocp_notion_sync")
    route_error_handler.transaction = transaction
    route_error_handler.operation_name = "ocp_notion_sync"
    logger.info("Received POST request on /calendar/ocp/sync-from-notion, triggering Notion->OCP sync.")
    set_tag("request_type", "POST")
    
    # Check if Notion database ID is configured
    if not config.NOTION_DATABASE_ID:
        logger.error("Required configuration NOTION_DATABASE_ID is missing in .env for /calendar/ocp/sync-from-notion endpoint.")
        set_tag("config_error", "missing_database_id")
        transaction.set_status("failed_precondition")
        return jsonify({"status": "error", "message": "Notion database ID not configured on server."}), 500
    
    try:
        # Delegate sync to the OCP service
        sync_result = ocp_service.sync_notion_to_ocp(config.NOTION_DATABASE_ID, transaction)
        
        # Return response based on service result
        if sync_result.get("status") == "error":
            logger.error(f"OCP sync via webhook finished with error: {sync_result.get('message')}")
            return jsonify(sync_result), 500
        elif sync_result.get("status") == "warning":
            logger.warning(f"OCP sync via webhook finished with warning: {sync_result.get('message')}")
            return jsonify(sync_result), 207
        else:
            logger.info(f"OCP sync via webhook completed successfully: {sync_result.get('message')}")
            return jsonify(sync_result), 200
            
    except Exception as e:
        # Catch unexpected errors at the route level
        route_error_handler.handle_generic_error(e)
        return jsonify({"status": "error", "message": "An unexpected error occurred processing the webhook."}), 500
    finally:
        route_error_handler.transaction = None
        if transaction:
            transaction.finish()

@ocp_blueprint.route("/debug-sync-from-notion", methods=["POST"])
def debug_sync_from_notion():
    """
    Debug endpoint to sync officer contribution points from Notion events with detailed output.
    Fetches events from the configured Notion database, shows raw data, and updates the OCP database.
    """
    transaction = start_transaction(op="debug", name="ocp_notion_sync_debug")
    route_error_handler.transaction = transaction
    route_error_handler.operation_name = "ocp_notion_sync_debug"
    logger.info("Received POST request on /calendar/ocp/debug-sync-from-notion, triggering Notion->OCP sync with debug output.")
    set_tag("request_type", "POST")
    
    # Check if Notion database ID is configured
    if not config.NOTION_DATABASE_ID:
        logger.error("Required configuration NOTION_DATABASE_ID is missing in .env")
        transaction.set_status("failed_precondition")
        return jsonify({"status": "error", "message": "Notion database ID not configured on server."}), 500
    
    try:
        # Display informational message
        print("\n=========================================================")
        print("BEGINNING NOTION SYNC DEBUG - RAW EVENT DATA WILL FOLLOW")
        print("=========================================================\n")
        
        # Special debug function to look at the raw people data in properties
        try:
            print("FETCHING EVENTS FROM NOTION FOR SPECIAL DEBUG ANALYSIS...")
            notion_events = ocp_service.notion_client.fetch_events(config.NOTION_DATABASE_ID)
            
            # Look for the examples with mismatched counts
            for event in notion_events:
                props = event.get('properties', {})
                for prop_name, prop_value in props.items():
                    if 'people' in prop_value:
                        people = prop_value.get('people', [])
                        if len(people) > 0:
                            print(f"\n=========== EXAMINING '{prop_name}' PROPERTY ===========")
                            print(f"Event: {extract_property(props, 'Name', 'title')}")
                            print(f"Property: {prop_name}")
                            print(f"People count: {len(people)}")
                            print(f"All people names in this property:")
                            for i, person in enumerate(people):
                                print(f"  {i+1}. {person.get('name', 'Unnamed')}")
                                
                                # Detailed examination of person object
                                print(f"     ID: {person.get('id', 'No ID')}")
                                print(f"     Keys in person object: {list(person.keys())}")
                                if 'person' in person:
                                    person_obj = person.get('person', {})
                                    print(f"     Person sub-object keys: {list(person_obj.keys())}")
                            print("=======================================================")
        except Exception as e:
            print(f"Error in special debug analysis: {str(e)}")
        
        # Delegate sync to the OCP service
        sync_result = ocp_service.sync_notion_to_ocp(config.NOTION_DATABASE_ID, transaction)
        
        # Print completion message
        print("\n=========================================================")
        print("NOTION SYNC DEBUG COMPLETE")
        print("=========================================================\n")
        
        # Return response based on service result
        if sync_result.get("status") == "error":
            logger.error(f"OCP sync via debug endpoint finished with error: {sync_result.get('message')}")
            return jsonify(sync_result), 500
        elif sync_result.get("status") == "warning":
            logger.warning(f"OCP sync via debug endpoint finished with warning: {sync_result.get('message')}")
            return jsonify(sync_result), 207
        else:
            logger.info(f"OCP sync via debug endpoint completed successfully: {sync_result.get('message')}")
            return jsonify(sync_result), 200
            
    except Exception as e:
        # Catch unexpected errors at the route level
        route_error_handler.handle_generic_error(e)
        return jsonify({"status": "error", "message": "An unexpected error occurred processing the debug sync."}), 500
    finally:
        route_error_handler.transaction = None
        if transaction:
            transaction.finish()

@ocp_blueprint.route("/diagnose-unknown-officers", methods=["GET", "POST"])
@auth_required
def diagnose_unknown_officers():
    """
    Endpoint to diagnose issues with officers missing names in the database.
    Lists all events with missing UUIDs or officers with "Unknown" names.
    Ignores issues with missing emails or department information.
    Supports both GET and POST methods to ensure compatibility with frontend.
    """
    transaction = start_transaction(op="admin", name="diagnose_unknown_officers")
    route_error_handler.transaction = transaction
    route_error_handler.operation_name = "diagnose_unknown_officers"
    logger.info(f"Received {request.method} request on /calendar/ocp/diagnose-unknown-officers")
    set_tag("request_type", request.method)
    
    try:
        # Call the diagnostic function from the service
        diagnosis_result = ocp_service.diagnose_unknown_officers()
        
        # Return appropriate response based on diagnosis
        if diagnosis_result.get("status") == "error":
            logger.error(f"Officer diagnosis failed: {diagnosis_result.get('message')}")
            return jsonify(diagnosis_result), 500
        else:
            logger.info(f"Officer diagnosis completed. Found {diagnosis_result.get('total_issues')} issues.")
            return jsonify(diagnosis_result), 200
    except Exception as e:
        route_error_handler.handle_generic_error(e)
        return jsonify({"status": "error", "message": "An unexpected error occurred during officer diagnosis."}), 500
    finally:
        route_error_handler.transaction = None
        if transaction:
            transaction.finish()

@ocp_blueprint.route("/officers", methods=["GET"])
@auth_required
def get_officer_leaderboard():
    """Get all officers with their total points in leaderboard format."""
    transaction = start_transaction(op="api", name="get_officer_leaderboard")
    route_error_handler.transaction = transaction
    route_error_handler.operation_name = "get_officer_leaderboard"
    logger.info("Received GET request on /calendar/ocp/officers for leaderboard")
    set_tag("request_type", "GET")
    
    try:
        officers = ocp_service.get_officer_leaderboard()
        return jsonify({
            "status": "success", 
            "officers": officers,
            "leaderboard_description": "Officers ranked by total contribution points"
        }), 200
    except Exception as e:
        route_error_handler.handle_generic_error(e)
        return jsonify({"status": "error", "message": "An unexpected error occurred fetching officer leaderboard."}), 500
    finally:
        route_error_handler.transaction = None
        if transaction:
            transaction.finish()

@ocp_blueprint.route("/officer/<email>/contributions", methods=["GET"])
@auth_required
def get_officer_contributions(email):
    """Get all contributions for a specific officer."""
    transaction = start_transaction(op="api", name="get_officer_contributions")
    route_error_handler.transaction = transaction
    route_error_handler.operation_name = "get_officer_contributions"
    logger.info(f"Received GET request on /calendar/ocp/officer/{email}/contributions")
    set_tag("request_type", "GET")
    set_tag("officer_email", email)
    
    try:
        contributions = ocp_service.get_officer_contributions(email)
        if not contributions:
            return jsonify({"status": "warning", "message": f"No contributions found for officer {email}", "contributions": []}), 200
        return jsonify({"status": "success", "contributions": contributions}), 200
    except Exception as e:
        route_error_handler.handle_generic_error(e)
        return jsonify({"status": "error", "message": "An unexpected error occurred fetching officer contributions."}), 500
    finally:
        route_error_handler.transaction = None
        if transaction:
            transaction.finish()

@ocp_blueprint.route("/add-contribution", methods=["POST"])
@auth_required
def add_contribution():
    """
    Add a contribution record for an officer.
    
    Expected JSON body:
    {
        "email": "officer@example.com",  # Required
        "name": "Officer Name",          # Optional, for new officers
        "event": "Event description",    # Required
        "points": 1,                     # Optional, default 1
        "role": "Event Lead",            # Optional
        "event_type": "GBM",             # Optional
        "timestamp": "2023-10-15T12:00:00Z"  # Optional, defaults to now
    }
    """
    transaction = start_transaction(op="api", name="add_contribution")
    route_error_handler.transaction = transaction
    route_error_handler.operation_name = "add_contribution"
    logger.info("Received POST request on /calendar/ocp/add-contribution")
    set_tag("request_type", "POST")
    
    try:
        # Get request data
        data = request.json
        if not data:
            return jsonify({"status": "error", "message": "Request body must be JSON"}), 400
            
        # Add contribution through service
        result = ocp_service.add_officer_points(data)
        
        if result.get("status") == "error":
            return jsonify(result), 400
        else:
            return jsonify(result), 201
    except Exception as e:
        route_error_handler.handle_generic_error(e)
        return jsonify({"status": "error", "message": "An unexpected error occurred adding contribution."}), 500
    finally:
        route_error_handler.transaction = None
        if transaction:
            transaction.finish()

@ocp_blueprint.route("/contribution/<int:point_id>", methods=["PUT"])
@auth_required
def update_contribution(point_id):
    """
    Update an existing contribution record.
    
    Expected JSON body contains fields to update:
    {
        "points": 2,                    # Optional
        "event": "Updated description", # Optional
        "role": "New role",             # Optional
        "event_type": "Special Event"   # Optional
    }
    """
    transaction = start_transaction(op="api", name="update_contribution")
    route_error_handler.transaction = transaction
    route_error_handler.operation_name = "update_contribution"
    logger.info(f"Received PUT request on /calendar/ocp/contribution/{point_id}")
    set_tag("request_type", "PUT")
    set_tag("point_id", point_id)
    
    try:
        # Get request data
        data = request.json
        if not data:
            return jsonify({"status": "error", "message": "Request body must be JSON"}), 400
            
        # Update contribution through service
        result = ocp_service.update_officer_points(point_id, data)
        
        if result.get("status") == "error":
            return jsonify(result), 404 if "not found" in result.get("message", "") else 400
        else:
            return jsonify(result), 200
    except Exception as e:
        route_error_handler.handle_generic_error(e)
        return jsonify({"status": "error", "message": "An unexpected error occurred updating contribution."}), 500
    finally:
        route_error_handler.transaction = None
        if transaction:
            transaction.finish()

@ocp_blueprint.route("/contribution/<int:point_id>", methods=["DELETE"])
@auth_required
def delete_contribution(point_id):
    """Delete a contribution record."""
    transaction = start_transaction(op="api", name="delete_contribution")
    route_error_handler.transaction = transaction
    route_error_handler.operation_name = "delete_contribution"
    logger.info(f"Received DELETE request on /calendar/ocp/contribution/{point_id}")
    set_tag("request_type", "DELETE")
    set_tag("point_id", point_id)
    
    try:
        # Delete contribution through service
        result = ocp_service.delete_officer_points(point_id)
        
        if result.get("status") == "error":
            return jsonify(result), 404 if "not found" in result.get("message", "") else 400
        else:
            return jsonify(result), 200
    except Exception as e:
        route_error_handler.handle_generic_error(e)
        return jsonify({"status": "error", "message": "An unexpected error occurred deleting contribution."}), 500
    finally:
        route_error_handler.transaction = None
        if transaction:
            transaction.finish()

@ocp_blueprint.route("/officer/<officer_id>", methods=["GET"])
@auth_required
def get_officer_details(officer_id):
    """Get detailed information about a specific officer including their points and events."""
    transaction = start_transaction(op="api", name="get_officer_details")
    route_error_handler.transaction = transaction
    route_error_handler.operation_name = "get_officer_details"
    logger.info(f"Received GET request on /calendar/ocp/officer/{officer_id}")
    set_tag("request_type", "GET")
    set_tag("officer_id", officer_id)
    
    try:
        officer_details = ocp_service.get_officer_details(officer_id)
        if not officer_details:
            return jsonify({"status": "warning", "message": f"No officer found with identifier {officer_id}"}), 404
        return jsonify({"status": "success", "officer": officer_details}), 200
    except Exception as e:
        route_error_handler.handle_generic_error(e)
        return jsonify({"status": "error", "message": "An unexpected error occurred fetching officer details."}), 500
    finally:
        route_error_handler.transaction = None
        if transaction:
            transaction.finish()

@ocp_blueprint.route("/events", methods=["GET"])
def get_all_events():
    """Get all contribution events across all officers."""
    transaction = start_transaction(op="api", name="get_all_events")
    route_error_handler.transaction = transaction
    route_error_handler.operation_name = "get_all_events"
    logger.info("Received GET request on /calendar/ocp/events")
    set_tag("request_type", "GET")
    
    try:
        events = ocp_service.get_all_events()
        return jsonify({
            "status": "success", 
            "events": events,
            "events_count": len(events)
        }), 200
    except Exception as e:
        route_error_handler.handle_generic_error(e)
        return jsonify({"status": "error", "message": "An unexpected error occurred fetching all events."}), 500
    finally:
        route_error_handler.transaction = None
        if transaction:
            transaction.finish()

@ocp_blueprint.route("/repair-officers", methods=["POST"])
@auth_required
def repair_unknown_officers():
    """
    Endpoint to repair events with officers missing names.
    This runs a repair process to match events with correct officers based on names.
    Focuses only on officers with missing names and ignores issues with missing emails or departments.
    """
    transaction = start_transaction(op="admin", name="repair_unknown_officers")
    route_error_handler.transaction = transaction
    route_error_handler.operation_name = "repair_unknown_officers"
    logger.info("Received POST request on /calendar/ocp/repair-officers")
    set_tag("request_type", "POST")
    
    try:
        # Call the repair function from the service
        repair_result = ocp_service.repair_unknown_officers()
        
        # Return appropriate response based on repair result
        if repair_result.get("status") == "error":
            logger.error(f"Officer repair failed: {repair_result.get('message')}")
            return jsonify(repair_result), 500
        else:
            logger.info(f"Officer repair completed: {repair_result.get('message')}")
            return jsonify(repair_result), 200
    except Exception as e:
        route_error_handler.handle_generic_error(e)
        return jsonify({"status": "error", "message": "An unexpected error occurred during officer repair."}), 500
    finally:
        route_error_handler.transaction = None
        if transaction:
            transaction.finish() 