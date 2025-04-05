from flask import Blueprint, jsonify, request
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import BatchHttpRequest # Added for batch operations
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional, Any
from notion_client.helpers import collect_paginated_api
from notion_client import APIErrorCode, APIResponseError
from shared import config, notion, logger, sentry_sdk
from sentry_sdk import capture_exception, set_tag, set_context, start_transaction
calendar_blueprint = Blueprint("calendar", __name__)

def get_google_calendar_service():
    """Initialize and return authenticated Google Calendar service"""
    with start_transaction(op="google", name="get_calendar_service") as transaction:
        SCOPES = ['https://www.googleapis.com/auth/calendar', 'https://www.googleapis.com/auth/calendar.events']
        try:
            set_context("google_api", {
                "scopes": SCOPES,
                "service_account": bool(config.GOOGLE_SERVICE_ACCOUNT)
            })
            
            with transaction.start_child(op="auth", description="create_credentials") as span:
                credentials = service_account.Credentials.from_service_account_info(
                    config.GOOGLE_SERVICE_ACCOUNT,
                    scopes=SCOPES
                )
                span.set_data("credentials_created", bool(credentials))
            
            with transaction.start_child(op="build", description="build_service") as span:
                service = build('calendar', 'v3', credentials=credentials)
                span.set_data("service_created", bool(service))
                return service
                
        except Exception as e:
            capture_exception(e)
            logger.error(f"Google API initialization failed: {str(e)}")
            set_tag("google_service_init", "failed")
            return None

@calendar_blueprint.route("/notion-webhook", methods=["POST", "GET"])
def notion_webhook():
    with start_transaction(op="webhook", name="notion_webhook") as transaction:
        # Any request (GET or POST) triggers a full sync
        set_tag("request_type", request.method)
        logger.info(f"Received {request.method} request, triggering full Notion sync.")
        
        try:
            database_id = config.NOTION_DATABASE_ID
            set_context("notion", {"database_id": database_id})
            
            with transaction.start_child(op="fetch", description="fetch_notion_events") as span:
                notion_events = fetch_notion_events(database_id)
                span.set_data("event_count", len(notion_events) if notion_events else 0)
            
            # Check the result of fetching Notion events
            if notion_events is None:
                # Fetch failed (error logged in fetch_notion_events)
                logger.error("Notion fetch failed. Skipping Google Calendar update and clearing.")
                set_tag("sync_status", "notion_fetch_failed")
                return jsonify({"status": "error", "message": "Failed to fetch events from Notion. Calendar not updated."}), 500

            elif not notion_events:
                # Fetch succeeded, but returned zero events
                logger.warning("Successfully fetched 0 published future events from Notion. Clearing future Google Calendar events.")
                set_tag("sync_status", "no_events")
                with transaction.start_child(op="clear", description="clear_future_events"):
                    clear_future_events()
                return jsonify({
                    "status": "success",
                    "message": "Successfully fetched 0 events from Notion. Future Google Calendar events cleared."
                }), 200
                
            else:
                # Fetch succeeded and returned events
                set_tag("sync_status", "success")
                with transaction.start_child(op="parse", description="parse_event_data") as span:
                    parsed_events = parse_event_data(notion_events)
                    span.set_data("parsed_count", len(parsed_events))
                
                logger.info(f"Parsed {len(parsed_events)} events from Notion.")
                
                with transaction.start_child(op="update", description="update_google_calendar") as span:
                    results = update_google_calendar(parsed_events)
                    span.set_data("processed_count", len(results))
                
                logger.info(f"Google Calendar update process completed. Results: {len(results)} events processed.")
                return jsonify({
                    "status": "success",
                    "message": f"Calendar sync complete. Processed {len(results)} events.",
                    "events_processed": results
                }), 200

        except Exception as e:
            capture_exception(e)
            logger.error(f"Error processing webhook: {str(e)}")
            set_tag("sync_status", "error")
            return jsonify({"status": "error", "message": str(e)}), 500

def share_calendar_with_user(service, calendar_id: str):
    """Share the calendar with the specified user"""
    with start_transaction(op="google", name="share_calendar") as transaction:
        try:
            set_context("share_calendar", {
                "calendar_id": calendar_id,
                "user_email": config.GOOGLE_USER_EMAIL
            })
            
            rule = {
                'scope': {
                    'type': 'user',
                    'value': config.GOOGLE_USER_EMAIL
                },
                'role': 'writer'
            }
            
            with transaction.start_child(op="share", description="insert_acl") as span:
                service.acl().insert(calendarId=calendar_id, body=rule).execute()
                span.set_data("share_success", True)
                logger.info(f"Calendar shared with {config.GOOGLE_USER_EMAIL}")
                
        except HttpError as e:
            capture_exception(e)
            logger.error(f"HTTP error sharing calendar: {e.resp.status} - {e.error_details}")
            set_context("http_error", {"status": e.resp.status, "details": e.error_details})
        except Exception as e:
            capture_exception(e)
            logger.error(f"Unexpected error sharing calendar: {str(e)}")
            set_tag("error_type", "unexpected")

def ensure_calendar_access() -> Optional[str]:
    """
    Ensure the calendar specified in config exists and is accessible.
    Returns the calendar ID if found and accessible, otherwise None.
    Does NOT create the calendar if it's missing.
    """
    with start_transaction(op="google", name="ensure_calendar_access") as transaction:
        service = get_google_calendar_service()
        if not service:
            set_tag("google_service", "failed")
            return None

        calendar_id_to_check = config.GOOGLE_CALENDAR_ID
        if not calendar_id_to_check:
            logger.error("Required configuration GOOGLE_CALENDAR_ID is missing in .env")
            set_tag("config_error", "missing_calendar_id")
            return None

        try:
            set_context("calendar_access", {
                "calendar_id": calendar_id_to_check
            })
            
            # Attempt to get the calendar by ID
            with transaction.start_child(op="verify", description="verify_access") as span:
                logger.info(f"Verifying access to Google Calendar with ID: {calendar_id_to_check}")
                calendar = service.calendars().get(calendarId=calendar_id_to_check).execute()
                
                span.set_data("calendar_details", {
                    "summary": calendar['summary'],
                    "access_verified": True
                })
                
                logger.info(f"Successfully verified access to calendar: {calendar['summary']} ({calendar_id_to_check})")
                set_tag("calendar_access", "success")
                return calendar_id_to_check

        except HttpError as e:
            capture_exception(e)
            error_context = {
                "status": e.resp.status,
                "details": e.error_details,
                "calendar_id": calendar_id_to_check
            }
            
            if e.resp.status == 404:
                set_tag("error_type", "calendar_not_found")
                logger.error(f"Google Calendar with ID '{calendar_id_to_check}' configured in .env was not found.")
                logger.error("Please ensure the ID is correct and the service account has access.")
                
            elif e.resp.status == 403:
                set_tag("error_type", "permission_denied")
                logger.error(f"Access denied (403 Forbidden) for Google Calendar ID '{calendar_id_to_check}'.")
                logger.error("Please ensure the service account has been granted 'Make changes to events' permission for this calendar.")
                
            else:
                set_tag("error_type", "http_error")
                logger.error(f"HTTP error checking for calendar '{calendar_id_to_check}': {e.resp.status} - {e.error_details}")
            
            set_context("http_error", error_context)
            return None
            
        except Exception as e_generic:
            capture_exception(e_generic)
            logger.error(f"Unexpected error checking for calendar '{calendar_id_to_check}': {str(e_generic)}")
            set_tag("error_type", "unexpected")
            return None

def fetch_notion_events(database_id: str) -> Optional[List[Dict]]:
    """Fetch all relevant (published, future) events from Notion database using pagination."""
    with start_transaction(op="notion", name="fetch_notion_events") as transaction:
        try:
            now = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            logger.info(f"Fetching all published Notion events on or after {now} using pagination.")
            set_context("notion_query", {
                "database_id": database_id,
                "date_from": now
            })
            
            # Define the filter - Fetch ALL published events, regardless of date
            query_filter = {
                "filter": {
                    "property": "Published",
                    "checkbox": {
                        "equals": True
                    }
                }
            }

            # Use collect_paginated_api to handle pagination automatically
            with transaction.start_child(op="api_call", description="notion.databases.query") as span:
                all_events = collect_paginated_api(
                    notion.databases.query,
                    database_id=database_id,
                    filter=query_filter
                )
                span.set_data("event_count", len(all_events))
            
            logger.info(f"Fetched a total of {len(all_events)} Notion events via pagination.")
            return all_events
            
        except APIResponseError as error:
            capture_exception(error)
            logger.error(f"Notion API Error during fetch: {error.code} - {error.message}")
            set_context("notion_error", {
                "code": error.code,
                "message": error.message
            })
            # Handle specific errors if needed, e.g., ObjectNotFound
            if error.code == APIErrorCode.ObjectNotFound:
                logger.error(f"Database with ID {database_id} not found.")
                set_tag("error_type", "database_not_found")
            return None # Indicate failure
        except Exception as e:
            capture_exception(e)
            logger.error(f"Unexpected error fetching Notion events: {str(e)}")
            set_tag("error_type", "unexpected")
            return None # Indicate failure

def update_google_calendar(parsed_notion_events: List[Dict]) -> List[Dict]:
    """Update Google Calendar with Notion events using GCAL ID for matching."""
    with start_transaction(op="google", name="update_google_calendar") as transaction:
        service = get_google_calendar_service()
        if not service:
            set_tag("google_service", "failed")
            return []

        set_tag("google_service", "success")
        results = []
        
        try:
            # Fetch all future events from Google Calendar
            with transaction.start_child(op="fetch", description="get_all_calendar_events") as span:
                existing_gcal_events_raw = get_all_calendar_events(service, config.GOOGLE_CALENDAR_ID)
                span.set_data("existing_events", len(existing_gcal_events_raw))
            
            # Create a dictionary for quick lookup by Google Calendar Event ID
            existing_gcal_events = {event['id']: event for event in existing_gcal_events_raw}
            
            processed_gcal_ids = set()
            set_context("sync_stats", {
                "total_notion_events": len(parsed_notion_events),
                "existing_gcal_events": len(existing_gcal_events)
            })

            with transaction.start_child(op="process", description="process_events") as process_span:
                for notion_event_data in parsed_notion_events:
                    notion_page_id = notion_event_data.pop('notion_page_id', None)
                    gcal_id = notion_event_data.pop('gcal_id', None)
                    summary = notion_event_data.get('summary', 'Unknown Event')

                    if not notion_page_id:
                        logger.warning(f"Skipping event '{summary}' because Notion Page ID is missing.")
                        continue

                    try:
                        jump_url = None
                        event_context = {
                            "notion_page_id": notion_page_id,
                            "gcal_id": gcal_id,
                            "summary": summary
                        }
                        
                        with process_span.start_child(op="event", description=f"process_{summary}") as event_span:
                            event_span.set_data("event_context", event_context)
                            
                            if gcal_id and gcal_id in existing_gcal_events:
                                set_tag("event_action", "update")
                                logger.info(f"Found matching event for '{summary}' using GCAL ID: {gcal_id}. Updating.")
                                jump_url = update_event(service, config.GOOGLE_CALENDAR_ID, gcal_id, notion_event_data)
                                processed_gcal_ids.add(gcal_id)
                            
                            elif gcal_id and gcal_id not in existing_gcal_events:
                                set_tag("event_action", "recreate")
                                logger.warning(f"Event '{summary}' has GCAL ID '{gcal_id}' in Notion but not found in Google Calendar. Recreating.")
                                jump_url = create_event(service, config.GOOGLE_CALENDAR_ID, notion_event_data, notion_page_id)

                            else:
                                set_tag("event_action", "create")
                                logger.info(f"No GCAL ID found for '{summary}'. Creating new event.")
                                jump_url = create_event(service, config.GOOGLE_CALENDAR_ID, notion_event_data, notion_page_id)

                            if jump_url:
                                results.append({
                                    "summary": summary,
                                    "jump_url": jump_url
                                })

                    except Exception as e:
                        capture_exception(e)
                        logger.error(f"Error processing event '{summary}' (Notion ID: {notion_page_id}): {str(e)}")
                        set_context("failed_event", event_context)

            # Handle deletions
            gcal_ids_in_notion = {data.get('gcal_id') for data in parsed_notion_events if data.get('gcal_id')}
            ids_to_delete = set(existing_gcal_events.keys()) - processed_gcal_ids
            final_ids_to_delete = {id_ for id_ in ids_to_delete if id_ not in gcal_ids_in_notion}

            if final_ids_to_delete:
                with transaction.start_child(op="delete", description="batch_delete") as delete_span:
                    delete_span.set_data("delete_count", len(final_ids_to_delete))
                    logger.info(f"Preparing to batch delete {len(final_ids_to_delete)} events from Google Calendar.")
                    batch = service.new_batch_http_request(callback=handle_batch_delete_response)
                    
                    for event_id_to_delete in final_ids_to_delete:
                        event_summary = existing_gcal_events.get(event_id_to_delete, {}).get('summary', 'Unknown Event')
                        logger.debug(f"Adding delete request for event '{event_summary}' (GCAL ID: {event_id_to_delete}) to batch.")
                        batch.add(service.events().delete(calendarId=config.GOOGLE_CALENDAR_ID, eventId=event_id_to_delete))
                    
                    try:
                        batch.execute()
                        logger.info(f"Batch delete request executed for {len(final_ids_to_delete)} events.")
                    except HttpError as e:
                        capture_exception(e)
                        logger.error(f"HTTP error executing batch delete request: {e.resp.status} - {e.error_details}")
                        set_context("batch_delete_error", {"status": e.resp.status, "details": e.error_details})
                    except Exception as e:
                        capture_exception(e)
                        logger.error(f"Unexpected error executing batch delete request: {str(e)}")

            return results
        except Exception as e:
            capture_exception(e)
            logger.error(f"Error updating Google Calendar: {str(e)}")
            return []

def get_all_calendar_events(service: Any, calendar_id: str) -> List[Dict]:
    """Get all future events from Google Calendar.
    
    Args:
        service: Authenticated Google Calendar service instance
        calendar_id: ID of the target calendar
    
    Returns:
        List of calendar events in Google API format
    """
    with start_transaction(op="google", name="get_all_calendar_events") as transaction:
        try:
            set_context("calendar_fetch", {
                "calendar_id": calendar_id,
                "time_min": datetime.now(timezone.utc).isoformat()
            })
            
            with transaction.start_child(op="list", description="list_events") as span:
                events_result = service.events().list(
                    calendarId=calendar_id,
                    timeMin=datetime.now(timezone.utc).isoformat(),
                    singleEvents=True,
                    orderBy='startTime'
                ).execute()
                
                items = events_result.get('items', [])
                span.set_data("event_count", len(items))
                return items
                
        except HttpError as e:
            capture_exception(e)
            logger.error(f"HTTP error fetching calendar events: {e.resp.status} - {e.error_details}")
            set_context("http_error", {"status": e.resp.status, "details": e.error_details})
            return []
        except Exception as e:
            capture_exception(e)
            logger.error(f"Unexpected error fetching calendar events: {str(e)}")
            set_tag("error_type", "unexpected")
            return []

# Removed find_matching_event as matching is now based on gcal_id stored in Notion

def update_event(service: Any, calendar_id: str, event_id: str,
                event_data: Dict) -> Optional[str]:
    """Update existing Google Calendar event.
    
    Args:
        service: Authenticated Google Calendar service
        calendar_id: Target calendar ID
        event_id: ID of event to update
        event_data: New event data
    
    Returns:
        Event HTML link if successful, None otherwise
    """
    with start_transaction(op="google", name="update_event") as transaction:
        try:
            set_context("event_update", {
                "calendar_id": calendar_id,
                "event_id": event_id,
                "summary": event_data.get("summary", "Unknown Event")
            })
            
            with transaction.start_child(op="update", description="update_event") as span:
                updated_event = service.events().update(
                    calendarId=calendar_id,
                    eventId=event_id,
                    body=event_data
                ).execute()
                
                span.set_data("event_details", {
                    "id": updated_event['id'],
                    "summary": updated_event.get('summary'),
                    "status": "success"
                })
                
                jump_url = updated_event.get('htmlLink')
                logger.info(f"Updated event: {updated_event['id']}")
                return jump_url
                
        except HttpError as e:
            capture_exception(e)
            logger.error(f"HTTP error updating event {event_id}: {e.resp.status} - {e.error_details}")
            set_context("http_error", {"status": e.resp.status, "details": e.error_details})
            return None
            
        except Exception as e:
            capture_exception(e)
            logger.error(f"Unexpected error updating event {event_id}: {str(e)}")
            set_tag("error_type", "unexpected")
            return None

def create_event(service: Any, calendar_id: str,
                 event_data: Dict, notion_page_id: str) -> Optional[str]:
    """Create new Google Calendar event and update Notion with the GCal ID.
    
    Args:
        service: Authenticated Google Calendar service
        calendar_id: Target calendar ID
        event_data: Event data to create
        notion_page_id: The ID of the Notion page to update with the GCal ID
    
    Returns:
        Event HTML link if successful, None otherwise
    """
    with start_transaction(op="google", name="create_event") as transaction:
        try:
            set_context("event_create", {
                "calendar_id": calendar_id,
                "notion_page_id": notion_page_id,
                "summary": event_data.get("summary", "Unknown Event")
            })
            
            with transaction.start_child(op="create", description="create_gcal_event") as span:
                created_event = service.events().insert(
                    calendarId=calendar_id,
                    body=event_data
                ).execute()
                
                gcal_event_id = created_event['id']
                jump_url = created_event.get('htmlLink')
                span.set_data("event_details", {
                    "gcal_id": gcal_event_id,
                    "summary": created_event.get('summary')
                })
                
                logger.info(f"Created Google Calendar event: {gcal_event_id} for Notion page: {notion_page_id}")

            # Update the Notion page with the new Google Calendar Event ID
            with transaction.start_child(op="update", description="update_notion") as span:
                try:
                    notion.pages.update(
                        page_id=notion_page_id,
                        properties={
                            "gcal_id": {
                                "rich_text": [
                                    {
                                        "type": "text",
                                        "text": {
                                            "content": gcal_event_id
                                        }
                                    }
                                ]
                            }
                        }
                    )
                    span.set_data("notion_update", "success")
                    logger.info(f"Successfully updated Notion page {notion_page_id} with GCAL ID {gcal_event_id}")
                    
                except APIResponseError as notion_e:
                    capture_exception(notion_e)
                    logger.error(f"Notion API error updating page {notion_page_id} with GCAL ID {gcal_event_id}: {notion_e.code} - {notion_e.message}")
                    set_context("notion_error", {
                        "code": notion_e.code,
                        "message": notion_e.message,
                        "gcal_id": gcal_event_id
                    })
                    span.set_data("notion_update", "failed")
                    
                except Exception as notion_e:
                    capture_exception(notion_e)
                    logger.error(f"Unexpected error updating Notion page {notion_page_id} with GCAL ID {gcal_event_id}: {str(notion_e)}")
                    set_tag("error_type", "notion_update_failed")
                    span.set_data("notion_update", "failed")
            
            return jump_url
            
        except HttpError as e:
            capture_exception(e)
            logger.error(f"HTTP error creating Google Calendar event for Notion page {notion_page_id}: {e.resp.status} - {e.error_details}")
            set_context("http_error", {"status": e.resp.status, "details": e.error_details})
            return None
            
        except Exception as e:
            capture_exception(e)
            logger.error(f"Unexpected error creating Google Calendar event for Notion page {notion_page_id}: {str(e)}")
            set_tag("error_type", "unexpected")
            return None

def handle_batch_delete_response(request_id, response, exception):
    """Callback function for batch delete requests."""
    if exception:
        # Handle error
        capture_exception(exception)
        logger.error(f"Batch delete request {request_id} failed: {exception}")
        set_context("batch_delete_error", {
            "request_id": request_id,
            "error": str(exception)
        })
        set_tag("batch_delete_status", "failed")
    else:
        # Process successful response if needed, often delete returns 204 No Content
        logger.debug(f"Batch delete request {request_id} successful.")
        set_tag("batch_delete_status", "success")

def clear_future_events() -> None:
    """Clear all future events from Google Calendar using batch delete."""
    with start_transaction(op="google", name="clear_future_events") as transaction:
        service = get_google_calendar_service()
        if not service:
            logger.error("Failed to get Google Calendar service for clearing events.")
            set_tag("google_service", "failed")
            return

        try:
            now = datetime.now(timezone.utc).isoformat()
            logger.info(f"Fetching future events from calendar {config.GOOGLE_CALENDAR_ID} for clearing.")
            set_context("clear_events", {
                "calendar_id": config.GOOGLE_CALENDAR_ID,
                "time_min": now
            })
            
            events_to_delete = []
            page_token = None
            
            with transaction.start_child(op="fetch", description="fetch_events") as fetch_span:
                while True:
                    events_result = service.events().list(
                        calendarId=config.GOOGLE_CALENDAR_ID,
                        timeMin=now,
                        singleEvents=True,
                        pageToken=page_token
                    ).execute()
                    
                    items = events_result.get('items', [])
                    if not items:
                        break
                        
                    events_to_delete.extend(items)
                    page_token = events_result.get('nextPageToken')
                    if not page_token:
                        break
                
                fetch_span.set_data("events_found", len(events_to_delete))

            if not events_to_delete:
                logger.info("No future events found to clear.")
                return

            logger.info(f"Found {len(events_to_delete)} future events to clear. Preparing batch delete.")
            
            with transaction.start_child(op="delete", description="batch_delete") as delete_span:
                batch = service.new_batch_http_request(callback=handle_batch_delete_response)
                for event in events_to_delete:
                    event_id = event['id']
                    event_summary = event.get('summary', 'Unknown Event')
                    logger.debug(f"Adding delete request for event '{event_summary}' (ID: {event_id}) to batch.")
                    batch.add(service.events().delete(calendarId=config.GOOGLE_CALENDAR_ID, eventId=event_id))

                try:
                    batch.execute()
                    delete_span.set_data("deleted_count", len(events_to_delete))
                    logger.info(f"Batch delete request executed for clearing {len(events_to_delete)} future events.")
                except Exception as batch_e:
                    capture_exception(batch_e)
                    delete_span.set_data("batch_failed", True)
                    raise batch_e

        except HttpError as e:
            capture_exception(e)
            logger.error(f"HTTP error clearing events: {e.resp.status} - {e.error_details}")
            set_context("http_error", {"status": e.resp.status, "details": e.error_details})
        except Exception as e:
            capture_exception(e)
            logger.error(f"Unexpected error clearing events: {str(e)}")
            set_tag("error_type", "unexpected")

def parse_event_data(notion_events: List[Dict]) -> List[Dict]:
    """Parse Notion events into Google Calendar format, including Notion Page ID and GCAL ID.
    
    Args:
        notion_events: Raw Notion database entries
    
    Returns:
        List of parsed events including 'notion_page_id' and 'gcal_id' keys,
        formatted for Google Calendar API.
    """
    with start_transaction(op="notion", name="parse_event_data") as transaction:
        parsed_events = []
        failed_events = 0
        
        set_context("parse_stats", {
            "total_events": len(notion_events)
        })
        
        for event in notion_events:
            try:
                with transaction.start_child(op="parse", description="parse_single_event") as span:
                    properties = event.get('properties', {})
                    notion_page_id = event.get('id')
                    
                    event_context = {
                        "notion_page_id": notion_page_id,
                        "event_type": properties.get('Type', {}).get('select', {}).get('name', 'Unknown')
                    }
                    span.set_data("event_context", event_context)
                    
                    # Extract the gcal_id using the helper function
                    gcal_id_text = extract_property(properties, 'gcal_id', 'rich_text')

                    event_data = {
                        'notion_page_id': notion_page_id,
                        'gcal_id': gcal_id_text,
                        'summary': extract_property(properties, 'Name', 'title'),
                        'location': extract_property(properties, 'Location', 'select'),
                        'description': extract_property(properties, 'Description', 'rich_text'),
                        'start': parse_date(properties.get('Date', {}).get('date', {}), 'start'),
                        'end': None, # Initialize end as None, will be populated below
                    } # End of event_data dictionary definition

                    # --- End date handling (now primarily within parse_date) ---
                    date_prop = properties.get('Date', {}).get('date', {})
                    # parse_date will attempt to parse 'end', and calculate default if needed
                    event_data['end'] = parse_date(date_prop, 'end')
                    # --- End of end date handling logic ---

                    # Remove keys with None values before sending to Google API, but keep internal ones
                    # Ensure 'end' is handled correctly if it ended up being None
                    google_api_payload = {k: v for k, v in event_data.items() if v is not None and k not in ['notion_page_id', 'gcal_id']}

                    if google_api_payload.get('summary') and google_api_payload.get('start'):
                        # Only add reminders if we have the essential info
                        google_api_payload['reminders'] = {"useDefault": True}

                        # Add back the internal IDs to the dict we store in the list
                        parsed_event_entry = google_api_payload.copy()
                        parsed_event_entry['notion_page_id'] = notion_page_id
                        parsed_event_entry['gcal_id'] = gcal_id_text # gcal_id was extracted earlier

                        parsed_events.append(parsed_event_entry)
                        span.set_data("parse_status", "success")
                    else:
                        failed_events += 1
                        span.set_data("parse_status", "missing_required_fields")
                        logger.warning(f"Skipping event {notion_page_id}: Missing required fields (summary or start date) after parsing.")
                    
            except Exception as e:
                capture_exception(e)
                notion_id = event.get('id', 'Unknown ID')
                logger.error(f"Error parsing Notion event (ID: {notion_id}): {str(e)}")
                set_context("failed_event", {
                    "notion_id": notion_id,
                    "error": str(e)
                })
                failed_events += 1
        
        set_context("parse_results", {
            "successful_parses": len(parsed_events),
            "failed_parses": failed_events,
            "total_events": len(notion_events)
        })
        
        logger.info(f"Successfully parsed {len(parsed_events)}/{len(notion_events)} events")
        return parsed_events

# Helper functions
def extract_property(properties: Dict, name: str, prop_type: str) -> Optional[str]:
    """Extract text content from Notion property."""
    try:
        prop_data = properties.get(name, {})
        if not prop_data:
            return None

        if prop_type == 'select':
            return prop_data.get('select', {}).get('name')
        elif prop_type in ['rich_text', 'title']:
            # Handle rich_text and title which are arrays
            prop_array = prop_data.get(prop_type, [])
            # Concatenate content from all text objects in the array
            content_list = [item.get('text', {}).get('content', '') for item in prop_array if item.get('type') == 'text' and item.get('text')]
            full_content = "".join(content_list)
            return full_content if full_content else None
        else:
            # Fallback for potentially simple types or unhandled ones
            return prop_data.get(prop_type)
            
    except Exception as e:
        capture_exception(e)
        logger.error(f"Error extracting property '{name}' of type '{prop_type}': {str(e)}")
        set_context("property_error", {
            "property_name": name,
            "property_type": prop_type,
            "error": str(e)
        })
        return None


def parse_date(date_obj: Dict, key: str) -> Optional[Dict]:
    """Parse datetime value from Notion date property.
    For 'end' key, calculates a 1-hour default if missing/invalid.
    """
    try:
        date_str = date_obj.get(key)
        parsed_date = None

        if date_str:
            try:
                # Attempt to parse the provided date string - primarily for validation
                datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                parsed_date = {
                    "dateTime": date_str,
                    "timeZone": config.TIMEZONE
                }
            except ValueError as e_parse:
                logger.warning(f"Could not parse provided date string for key '{key}': {date_str}. Error: {e_parse}")
                # Proceed to default calculation only if it's the 'end' key

        # If it's the 'end' key AND (parsing failed OR date_str was initially None), calculate default
        if key == 'end' and not parsed_date:
            start_date_str = date_obj.get('start')
            if start_date_str:
                try:
                    start_date_time_obj = datetime.fromisoformat(start_date_str.replace('Z', '+00:00'))
                    end_date_time_obj = start_date_time_obj + timedelta(hours=1)
                    end_date_str = end_date_time_obj.isoformat()
                    parsed_date = {
                        "dateTime": end_date_str,
                        "timeZone": config.TIMEZONE
                    }
                    logger.debug(f"Calculated default end time (1hr after start): {end_date_str}")
                except Exception as e_calc:
                    logger.error(f"Error calculating default end time based on start '{start_date_str}': {e_calc}")
                    capture_exception(e_calc)
                    # parsed_date remains None
            else:
                 logger.warning(f"Cannot calculate default end time for key '{key}' because start time is missing.")

        # For 'start' key, if parsing failed or date_str was None, return None explicitly
        if key == 'start' and not parsed_date:
             logger.warning(f"Start date string is missing or invalid: {date_str}")
             return None # Crucial: Don't return a potentially calculated end time if key was 'start'

        return parsed_date # Return the parsed date (either from input or calculated default for end) or None

    except Exception as e:
        capture_exception(e)
        logger.error(f"General error parsing date for key '{key}': {str(e)}")
        set_context("date_parse_error", {
            "key": key,
            "date_str": date_obj.get(key),
            "error": str(e)
        })
        return None


@calendar_blueprint.route("/events", methods=["GET"])
def get_calendar_events_for_frontend():
    """API endpoint to fetch upcoming Google Calendar events for frontend display."""
    with start_transaction(op="api", name="get_frontend_events") as transaction:
        service = get_google_calendar_service()
        if not service:
            logger.error("Failed to get Google Calendar service for /events endpoint")
            set_tag("api_status", "service_init_failed")
            return jsonify({"status": "error", "message": "Could not connect to Google Calendar"}), 500

        try:
            now = datetime.now(timezone.utc).isoformat()
            logger.info(f"Fetching upcoming events from Google Calendar ID: {config.GOOGLE_CALENDAR_ID}")
            set_context("calendar_fetch", {
                "calendar_id": config.GOOGLE_CALENDAR_ID,
                "time_min": now,
                "max_results": 50
            })
            
            with transaction.start_child(op="fetch", description="list_events") as span:
                events_result = service.events().list(
                    calendarId=config.GOOGLE_CALENDAR_ID,
                    timeMin=now,
                    maxResults=50,  # Limit the number of results, adjust as needed
                    singleEvents=True,
                    orderBy='startTime'
                ).execute()
                
                items = events_result.get('items', [])
                span.set_data("raw_event_count", len(items))
            
            # Format events for frontend consumption
            with transaction.start_child(op="format", description="format_events") as span:
                frontend_events = []
                for item in items:
                    start = item.get('start', {}).get('dateTime', item.get('start', {}).get('date'))
                    end = item.get('end', {}).get('dateTime', item.get('end', {}).get('date'))
                    
                    frontend_events.append({
                        'id': item.get('id'),
                        'title': item.get('summary'),
                        'start': start,
                        'end': end,
                        'location': item.get('location'),
                        'description': item.get('description'),
                        'url': item.get('htmlLink') # Link to the event in Google Calendar
                    })
                
                span.set_data("formatted_event_count", len(frontend_events))
            
            logger.info(f"Successfully fetched {len(frontend_events)} events for frontend")
            set_tag("api_status", "success")
            return jsonify({"status": "success", "events": frontend_events}), 200

        except HttpError as e:
            capture_exception(e)
            logger.error(f"HTTP error fetching calendar events: {e.resp.status} - {e.error_details}")
            set_context("http_error", {"status": e.resp.status, "details": e.error_details})
            return jsonify({"status": "error", "message": f"Error fetching calendar events: {str(e)}"}), 500
            
        except Exception as e:
            capture_exception(e)
            logger.error(f"Error fetching calendar events for frontend: {str(e)}")
            set_tag("error_type", "unexpected")
            return jsonify({"status": "error", "message": f"Error fetching calendar events: {str(e)}"}), 500
