from flask import Blueprint, jsonify, request
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from datetime import datetime, timedelta, timezone
import json
from typing import List, Dict, Optional, Any
from notion_client.helpers import collect_paginated_api
from notion_client import APIErrorCode, APIResponseError
from shared import config, notion, logger, sentry_sdk
from sentry_sdk import capture_exception, set_tag, set_context, start_transaction
import pytz
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

@calendar_blueprint.route("/notion-webhook", methods=["POST"]) # Only allow POST
def notion_webhook():
    with start_transaction(op="webhook", name="notion_webhook") as transaction:
        # POST request triggers a full sync
        set_tag("request_type", "POST")
        logger.info("Received POST request, triggering full Notion sync.")
        
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
                with transaction.start_child(op="clear", description="clear_synced_events"):
                    clear_synced_events() # Clear all synced events since there are no valid Notion events
                return jsonify({
                    "status": "success",
                    "message": "Successfully fetched 0 events from Notion. Future Google Calendar events cleared."
                }), 200
                
            else:
                # Fetch succeeded and returned events
                # First clear any orphaned or duplicate events
                with transaction.start_child(op="clear", description="clear_invalid_events"):
                    service = get_google_calendar_service()
                    if service:
                        # Get all current GCal events
                        now_utc = datetime.now(timezone.utc).isoformat()
                        all_gcal_events = get_all_gcal_events_for_sync(service, config.GOOGLE_CALENDAR_ID, time_min=now_utc)
                        
                        # Build set of valid Notion IDs
                        valid_notion_ids = {event.get('id') for event in notion_events}
                        
                        # Find events to delete (duplicates or without valid Notion IDs)
                        ids_to_delete = set()
                        notion_id_to_gcal_event = {}  # Track the most recent event for each Notion ID
                        
                        for event in all_gcal_events:
                            gcal_id = event.get('id')
                            notion_id = event.get('extendedProperties', {}).get('private', {}).get('notionPageId')
                            
                            if not notion_id or notion_id not in valid_notion_ids:
                                # Delete events without Notion ID or with invalid Notion ID
                                ids_to_delete.add(gcal_id)
                            else:
                                # Check for duplicates
                                if notion_id in notion_id_to_gcal_event:
                                    # Compare update times to keep the most recent
                                    existing_event = notion_id_to_gcal_event[notion_id]
                                    if event.get('updated', '') > existing_event.get('updated', ''):
                                        # Current event is newer, delete the old one
                                        ids_to_delete.add(existing_event['id'])
                                        notion_id_to_gcal_event[notion_id] = event
                                    else:
                                        # Existing event is newer, delete the current one
                                        ids_to_delete.add(gcal_id)
                                else:
                                    notion_id_to_gcal_event[notion_id] = event
                        
                        # Delete invalid events
                        if ids_to_delete:
                            logger.info(f"Found {len(ids_to_delete)} events to delete (duplicates or invalid)")
                            batch = service.new_batch_http_request(callback=handle_batch_delete_response)
                            for event_id in ids_to_delete:
                                batch.add(service.events().delete(
                                    calendarId=config.GOOGLE_CALENDAR_ID,
                                    eventId=event_id
                                ))
                            batch.execute()
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
            # now = datetime.now(timezone.utc).strftime("%Y-%m-%d") # Date filter removed, fetching all published
            logger.info("Fetching all published Notion events using pagination.")
            set_context("notion_query", {
                "database_id": database_id
                # "date_from": now # Removed date filter context
            })
            
            # Define the filter - Fetch ALL published events, regardless of date
            # Define the filter - Fetch ALL published events
            query_filter = {
                "property": "Published",
                "checkbox": {
                    "equals": True
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
            logger.error(f"Notion API Error during fetch: {error.code} - {str(error)}")
            set_context("notion_error", {
                "code": error.code,
                "message": str(error) # Use str(error) for details
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
            # 1. Fetch all potentially relevant events from Google Calendar
            with transaction.start_child(op="fetch", description="get_all_gcal_events_for_sync") as span:
                # Fetch events starting from today to limit scope
                now_utc = datetime.now(timezone.utc).isoformat()
                all_gcal_events_raw = get_all_gcal_events_for_sync(service, config.GOOGLE_CALENDAR_ID, time_min=now_utc)
                span.set_data("synced_event_count", len(all_gcal_events_raw))

            # 2. Build lookup dictionaries for GCal events
            gcal_events_by_id = {} # GCal ID -> GCal Event
            gcal_events_by_notion_id = {} # Notion Page ID -> List of GCal Events
            duplicates_to_delete = set() # Set of GCal IDs to delete due to being duplicates
            
            # First pass: Group events by Notion ID and build gcal_events_by_id
            for event in all_gcal_events_raw:
                gcal_id = event.get('id')
                notion_page_id_from_gcal = event.get('extendedProperties', {}).get('private', {}).get('notionPageId')
                
                if gcal_id:
                    gcal_events_by_id[gcal_id] = event
                    
                if notion_page_id_from_gcal:
                    if notion_page_id_from_gcal not in gcal_events_by_notion_id:
                        gcal_events_by_notion_id[notion_page_id_from_gcal] = []
                    gcal_events_by_notion_id[notion_page_id_from_gcal].append(event)
            
            # Second pass: Handle duplicates by keeping only the most recently updated event
            for notion_id, events in gcal_events_by_notion_id.items():
                if len(events) > 1:
                    # Sort events by updated timestamp, most recent first
                    sorted_events = sorted(events,
                        key=lambda e: e.get('updated', ''),
                        reverse=True
                    )
                    
                    # Keep the most recently updated event
                    kept_event = sorted_events[0]
                    kept_event_id = kept_event['id']
                    
                    # Mark all other events for deletion
                    for duplicate in sorted_events[1:]:
                        duplicate_id = duplicate['id']
                        duplicates_to_delete.add(duplicate_id)
                        logger.warning(
                            f"Marking duplicate event '{duplicate.get('summary', 'Unknown Event')}' "
                            f"(ID: {duplicate_id}) for deletion. Keeping more recent event "
                            f"'{kept_event.get('summary', 'Unknown Event')}' (ID: {kept_event_id}) "
                            f"for Notion ID: {notion_id}"
                        )
                    
                    # Update gcal_events_by_notion_id to only contain the kept event
                    # Store as a single event instead of a list for consistency
                    gcal_events_by_notion_id[notion_id] = kept_event

            # 3. Build lookup for parsed Notion events (passed into the function)
            notion_events_by_id = {
                event['notion_page_id']: event
                for event in parsed_notion_events if event.get('notion_page_id')
            }

            processed_gcal_ids = set() # Keep track of GCal events we've processed (updated or confirmed exist)
            set_context("sync_stats", {
                "total_notion_events": len(parsed_notion_events),
                "fetched_gcal_events": len(gcal_events_by_id),
                "gcal_events_by_notion_id_count": len(gcal_events_by_notion_id),
                "notion_events_by_id_count": len(notion_events_by_id)
            })

            # 4. Process Notion events for Creates/Updates (One-Way Sync: Notion -> GCal)
            with transaction.start_child(op="process", description="process_notion_events") as process_span:
                for notion_page_id, notion_event_data in notion_events_by_id.items():
                    # Pop internal fields before passing to GCal API functions
                    _ = notion_event_data.pop('gcal_id', None) # gcal_id from Notion is not used for matching anymore
                    _ = notion_event_data.pop('notion_page_id', None) # Already have it as key
                    summary = notion_event_data.get('summary', 'Unknown Event')

                    event_context = {
                        "notion_page_id": notion_page_id,
                        "summary": summary
                    }

                    try:
                        with process_span.start_child(op="event", description=f"process_{summary}") as event_span:
                            event_span.set_data("event_context", event_context)
                            jump_url = None

                            # --- Simplified Matching Logic (Based on Notion ID in GCal) ---
                            existing_gcal_event = gcal_events_by_notion_id.get(notion_page_id)

                            if existing_gcal_event:
                                # Match found based on Notion Page ID stored in GCal. Update it.
                                # Handle case where existing_gcal_event could be a list or a single event
                                if isinstance(existing_gcal_event, list):
                                    # If it's a list, use the first event (should only be one after duplicate handling)
                                    if existing_gcal_event:  # Check if list is not empty
                                        existing_gcal_id = existing_gcal_event[0]['id']
                                    else:
                                        # Skip if list is empty (shouldn't happen, but just in case)
                                        logger.warning(f"Empty event list found for Notion ID {notion_page_id}. Skipping update.")
                                        continue
                                else:
                                    # If it's a single event (dictionary), use it directly
                                    existing_gcal_id = existing_gcal_event['id']
                                set_tag("event_match", "notion_id_match_update")
                                logger.info(f"Matched '{summary}' by Notion ID {notion_page_id} stored in GCal event {existing_gcal_id}. Updating.")
                                jump_url = update_event(service, config.GOOGLE_CALENDAR_ID, existing_gcal_id, notion_event_data, notion_page_id)
                                processed_gcal_ids.add(existing_gcal_id) # Mark GCal event as processed
                            else:
                                # No match found based on Notion Page ID in GCal. Create a new event.
                                set_tag("event_match", "no_match_create")
                                logger.info(f"No existing GCal event found for Notion ID {notion_page_id} ('{summary}'). Creating new event.")
                                jump_url = create_event(service, config.GOOGLE_CALENDAR_ID, notion_event_data, notion_page_id)
                                # Note: The created event's ID isn't added to processed_gcal_ids because it wasn't in the initial fetch.

                            if jump_url:
                                results.append({"summary": summary, "jump_url": jump_url})

                    except Exception as e:
                        capture_exception(e)
                        logger.error(f"Error processing event '{summary}' (Notion ID: {notion_page_id}): {str(e)}")
                        set_context("failed_event", event_context)


            # 5. Handle Deletions: Delete GCal events that are duplicates, lack Notion IDs, or reference non-existent Notion events
            current_notion_ids = set(notion_events_by_id.keys()) # Set of Notion IDs from the current fetch
            ids_to_delete = set()

            with transaction.start_child(op="deletion_check", description="check_for_deleted_events"):
                logger.info(f"Checking {len(gcal_events_by_id)} fetched GCal events against {len(current_notion_ids)} current Notion events for potential deletion.")
                
                # First add all duplicate events to deletion set
                ids_to_delete.update(duplicates_to_delete)
                logger.info(f"Marked {len(duplicates_to_delete)} duplicate events for deletion")
                
                # Then check for events without Notion IDs or with invalid Notion IDs
                for gcal_id, gcal_event in gcal_events_by_id.items():
                    # Skip if already marked for deletion as a duplicate
                    if gcal_id in duplicates_to_delete:
                        continue
                        
                    private_props = gcal_event.get('extendedProperties', {}).get('private', {})
                    notion_page_id_from_gcal = private_props.get('notionPageId')
                    summary = gcal_event.get('summary', 'Unknown Event')

                    # Delete if the GCal event doesn't have a Notion ID stored,
                    # or if the stored Notion ID is not in the current set of Notion events.
                    if not notion_page_id_from_gcal:
                        logger.warning(f"Marking GCal event '{summary}' (ID: {gcal_id}) for deletion because it lacks a notionPageId property.")
                        ids_to_delete.add(gcal_id)
                    elif notion_page_id_from_gcal not in current_notion_ids:
                        logger.info(f"Marking GCal event '{summary}' (ID: {gcal_id}, linked Notion ID: {notion_page_id_from_gcal}) for deletion because the corresponding Notion event was not found in the current fetch.")
                        ids_to_delete.add(gcal_id)
                    # No 'else' needed - if it has a valid notionPageId that exists in Notion, we keep it.

            # Use the calculated ids_to_delete set directly
            final_ids_to_delete = ids_to_delete
            
            # Log summary of what will be deleted
            duplicate_count = len(duplicates_to_delete)
            no_notion_id_count = sum(1 for id in final_ids_to_delete if id not in duplicates_to_delete)
            logger.info(f"Total events marked for deletion: {len(final_ids_to_delete)} "
                       f"({duplicate_count} duplicates, "
                       f"{no_notion_id_count} without valid Notion IDs)")

            if final_ids_to_delete:
                with transaction.start_child(op="delete", description="batch_delete") as delete_span:
                    # Log event summaries for debugging before deletion
                    for event_id_to_delete in final_ids_to_delete:
                        event_summary = gcal_events_by_id.get(event_id_to_delete, {}).get('summary', 'Unknown Event')
                        logger.debug(f"Marking event '{event_summary}' (GCAL ID: {event_id_to_delete}) for deletion.")
                    
                    # Use our helper function to perform the batch delete
                    successful, failed = batch_delete_events(
                        service,
                        config.GOOGLE_CALENDAR_ID,
                        list(final_ids_to_delete),
                        description="sync_cleanup"
                    )
                    
                    delete_span.set_data("successful_deletions", successful)
                    delete_span.set_data("failed_deletions", failed)
                    
                    if failed > 0:
                        logger.warning(f"Failed to delete {failed} events during sync cleanup")

            return results
        except Exception as e:
            capture_exception(e)
            logger.error(f"Error updating Google Calendar: {str(e)}")
            return []

def get_all_gcal_events_for_sync(service: Any, calendar_id: str, time_min: Optional[str] = None) -> List[Dict]:
    """Get all Google Calendar events for sync comparison.

    Fetches events from the specified calendar, optionally filtering by a minimum start time.
    Handles pagination to retrieve all matching events.

    Args:
        service: Authenticated Google Calendar service instance
        calendar_id: ID of the target calendar
        time_min: Optional ISO 8601 timestamp to fetch events starting from this time.

    Returns:
        List of calendar events in Google API format, or empty list on error.
    """
    with start_transaction(op="google", name="get_all_gcal_events_for_sync") as transaction:
        all_synced_events = []
        page_token = None
        try:
            fetch_params = {
                "calendar_id": calendar_id,
                "time_min": time_min
            }
            set_context("gcal_event_fetch", fetch_params)
            logger.info(f"Fetching events from calendar {calendar_id}" + (f" starting from {time_min}" if time_min else "") + ".")

            while True:
                with transaction.start_child(op="list_page", description="list_events_page") as span:
                    events_result = service.events().list(
                        calendarId=calendar_id,
                        singleEvents=True, # Expand recurring events
                        showDeleted=False, # Don't include deleted events
                        pageToken=page_token,
                        timeMin=time_min, # Add timeMin filter
                        maxResults=250 # Fetch in batches
                    ).execute()

                    items = events_result.get('items', [])
                    all_synced_events.extend(items)
                    page_token = events_result.get('nextPageToken')

                    span.set_data("page_event_count", len(items))
                    span.set_data("has_next_page", bool(page_token))

                    if not page_token:
                        break # Exit loop if no more pages

            logger.info(f"Fetched a total of {len(all_synced_events)} events from Google Calendar.")
            transaction.set_data("total_fetched_events", len(all_synced_events))
            return all_synced_events
                
        except HttpError as e:
            capture_exception(e)
            logger.error(f"HTTP error fetching calendar events: {e.resp.status} - {e.error_details}")
            set_context("http_error", {"status": e.resp.status, "details": e.error_details})
            return [] # Return empty list on error
        except Exception as e:
            capture_exception(e)
            logger.error(f"Unexpected error fetching calendar events: {str(e)}")
            set_tag("error_type", "unexpected")
            return [] # Return empty list on error

# Removed find_matching_event as matching is now based on gcal_id stored in Notion

def update_event(service: Any, calendar_id: str, event_id: str,
                 event_data: Dict, notion_page_id: str) -> Optional[str]:
    """Update existing Google Calendar event and ensure sync properties are set.

    Args:
        service: Authenticated Google Calendar service
        calendar_id: Target calendar ID
        event_id: ID of event to update
        event_data: New event data from Notion (parsed)
        notion_page_id: The Notion Page ID corresponding to this event.

    Returns:
        Event HTML link if successful, None otherwise
    """
    with start_transaction(op="google", name="update_event") as transaction:
        # Ensure extended properties structure exists and set Notion ID
        if 'extendedProperties' not in event_data:
            event_data['extendedProperties'] = {}
        if 'private' not in event_data['extendedProperties']:
             event_data['extendedProperties']['private'] = {}

        # Store the Notion Page ID
        event_data['extendedProperties']['private']['notionPageId'] = notion_page_id

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
        # Add extended properties to store Notion ID
        event_data['extendedProperties'] = {
            'private': {
                'notionPageId': notion_page_id
            }
        }

        try:
            set_context("event_create", {
                "calendar_id": calendar_id,
                "notion_page_id": notion_page_id,
                "summary": event_data.get("summary", "Unknown Event")
            })
            
            with transaction.start_child(op="create", description="create_gcal_event") as span:
                # Log the event data being sent to Google API for debugging 400 errors
                logger.debug(f"Attempting to create Google Calendar event with data: {json.dumps(event_data, indent=2, default=str)}")
                
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
                    logger.error(f"Notion API error updating page {notion_page_id} with GCAL ID {gcal_event_id}: {notion_e.code} - {str(notion_e)}")
                    set_context("notion_error", {
                        "code": notion_e.code,
                        "message": str(notion_e), # Use str(error) for details
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
            # Add the problematic payload to Sentry context for easier debugging
            try:
                # Use json.dumps for better readability in Sentry if event_data is complex
                set_context("google_api_request_body", json.loads(json.dumps(event_data, default=str)))
            except Exception as context_err:
                logger.error(f"Failed to add event_data to Sentry context: {context_err}")
                set_context("google_api_request_body", {"error": "Could not serialize event_data"})
            return None
            
        except Exception as e:
            capture_exception(e)
            logger.error(f"Unexpected error creating Google Calendar event for Notion page {notion_page_id}: {str(e)}")
            set_tag("error_type", "unexpected")
            return None

def batch_delete_events(service: Any, calendar_id: str, event_ids: List[str],
                       description: str = "batch_delete") -> Tuple[int, int]:
    """Helper function to batch delete events from Google Calendar.
    
    Args:
        service: Authenticated Google Calendar service
        calendar_id: ID of the calendar to delete events from
        event_ids: List of event IDs to delete
        description: Description for the transaction span
        
    Returns:
        Tuple of (successful_deletions, failed_deletions)
    """
    if not event_ids:
        logger.info("No events to delete.")
        return 0, 0
        
    with start_transaction(op="google", name=f"batch_delete_{description}") as transaction:
        successful_deletions = 0
        failed_deletions = 0
        
        def callback(request_id, response, exception):
            nonlocal successful_deletions, failed_deletions
            if exception:
                failed_deletions += 1
                capture_exception(exception)
                logger.error(f"Batch delete request {request_id} failed: {exception}")
                set_context("batch_delete_error", {
                    "request_id": request_id,
                    "error": str(exception)
                })
            else:
                successful_deletions += 1
                logger.debug(f"Batch delete request {request_id} successful.")
                
        # Process in chunks to stay under API limits
        BATCH_SIZE = 900  # Stay under the 1000 limit
        
        for i in range(0, len(event_ids), BATCH_SIZE):
            chunk = event_ids[i:i + BATCH_SIZE]
            if not chunk:
                continue
                
            batch = service.new_batch_http_request(callback=callback)
            logger.info(f"Preparing batch delete for {len(chunk)} events (chunk {i // BATCH_SIZE + 1})...")
            
            for event_id in chunk:
                batch.add(service.events().delete(calendarId=calendar_id, eventId=event_id))
                
            try:
                logger.info(f"Executing batch delete for chunk {i // BATCH_SIZE + 1} ({len(chunk)} events).")
                batch.execute()
                logger.info(f"Batch chunk {i // BATCH_SIZE + 1} executed.")
            except Exception as e:
                capture_exception(e)
                logger.error(f"Error executing batch delete chunk {i // BATCH_SIZE + 1}: {str(e)}")
                failed_deletions += len(chunk)  # Mark all as failed if batch execution fails
                
        transaction.set_data("successful_deletions", successful_deletions)
        transaction.set_data("failed_deletions", failed_deletions)
        
        logger.info(f"Batch delete complete: {successful_deletions} successful, {failed_deletions} failed")
        return successful_deletions, failed_deletions

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

def get_synced_gcal_events(service: Any, calendar_id: str) -> List[Dict]:
    """Get all events from Google Calendar that were synced from Notion.
    
    This function fetches all events from the specified calendar that have
    the notionPageId property set in their extendedProperties.
    
    Args:
        service: Authenticated Google Calendar service
        calendar_id: ID of the calendar to fetch events from
        
    Returns:
        List of Google Calendar events that have a Notion Page ID
    """
    with start_transaction(op="google", name="get_synced_gcal_events") as transaction:
        try:
            # Fetch all events from the calendar
            now_utc = datetime.now(timezone.utc).isoformat()
            all_events = get_all_gcal_events_for_sync(service, calendar_id, time_min=now_utc)
            
            # Filter to only include events with a notionPageId
            synced_events = [
                event for event in all_events
                if event.get('extendedProperties', {}).get('private', {}).get('notionPageId')
            ]
            
            transaction.set_data("total_events", len(all_events))
            transaction.set_data("synced_events", len(synced_events))
            
            logger.info(f"Found {len(synced_events)} synced events out of {len(all_events)} total events")
            return synced_events
            
        except Exception as e:
            capture_exception(e)
            logger.error(f"Error fetching synced events: {str(e)}")
            return []

def clear_synced_events() -> None: # Renamed function
    """Clear all Google Calendar events previously synced from Notion using batch delete."""
    with start_transaction(op="google", name="clear_synced_events") as transaction: # Renamed transaction name
        service = get_google_calendar_service()
        if not service:
            logger.error("Failed to get Google Calendar service for clearing events.")
            set_tag("google_service", "failed")
            return

        try:
            logger.info(f"Fetching synced events from calendar {config.GOOGLE_CALENDAR_ID} for clearing.")
            set_context("clear_synced_events", {
                "calendar_id": config.GOOGLE_CALENDAR_ID
            })

            # Use the new function to get only synced events
            with transaction.start_child(op="fetch", description="get_synced_gcal_events") as fetch_span:
                events_to_delete = get_synced_gcal_events(service, config.GOOGLE_CALENDAR_ID)
                fetch_span.set_data("synced_events_found", len(events_to_delete))

            if not events_to_delete:
                logger.info("No synced events found to clear.")
                return

            logger.info(f"Found {len(events_to_delete)} synced events to clear.")
            
            # Extract event IDs
            event_ids = [event['id'] for event in events_to_delete]
            
            # Use the helper function to perform the batch delete
            with transaction.start_child(op="delete", description="batch_delete") as delete_span:
                successful, failed = batch_delete_events(
                    service,
                    config.GOOGLE_CALENDAR_ID,
                    event_ids,
                    description="clear_synced"
                )
                
                delete_span.set_data("successful_deletions", successful)
                delete_span.set_data("failed_deletions", failed)
                
                if failed > 0:
                    logger.warning(f"Failed to delete {failed} events during clear operation")

        except HttpError as e:
            capture_exception(e)
            logger.error(f"HTTP error clearing managed events: {e.resp.status} - {e.error_details}")
            set_context("http_error", {"status": e.resp.status, "details": e.error_details})
        except Exception as e:
            capture_exception(e)
            logger.error(f"Unexpected error clearing managed events: {str(e)}")
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
                    
                    # gcal_id from Notion is no longer used
                    # gcal_id_text = extract_property(properties, 'gcal_id', 'rich_text')

                    # --- Date/Time Parsing ---
                    date_prop = properties.get('Date', {}).get('date', {})
                    start_str = date_prop.get('start')
                    end_str = date_prop.get('end') # Might be None

                    parsed_start = parse_single_date_string(start_str)
                    parsed_end = parse_single_date_string(end_str) # Try parsing end string first

                    # If start is invalid/missing, we cannot proceed with this event
                    if not parsed_start:
                        failed_events += 1
                        span.set_data("parse_status", "missing_start_date")
                        logger.warning(f"Skipping event {notion_page_id}: Missing or invalid start date string: {start_str}")
                        continue # Skip to the next event in the loop

                    # If end is missing or invalid, handle based on start type
                    if not parsed_end:
                        if 'date' in parsed_start:
                            # All-day event: End date should be the day after the start date for Google Calendar
                            try:
                                start_date_obj = datetime.strptime(parsed_start['date'], '%Y-%m-%d')
                                end_date_obj = start_date_obj + timedelta(days=1)
                                parsed_end = {"date": end_date_obj.strftime('%Y-%m-%d')}
                                logger.debug(f"End date missing for all-day event {notion_page_id}. Setting end date to {parsed_end['date']}.")
                            except ValueError as e_date:
                                logger.error(f"Error calculating end date for all-day event {notion_page_id}: {e_date}")
                                capture_exception(e_date)
                                # Fallback: If calculation fails, skip event? Or use start date? Using start date for now.
                                parsed_end = parsed_start.copy()
                                logger.warning(f"Falling back to using start date as end date for all-day event {notion_page_id}.")

                        elif 'dateTime' in parsed_start:
                            # Specific time event: Calculate a default 1-hour duration
                            logger.debug(f"End dateTime missing or invalid ('{end_str}') for event {notion_page_id}. Calculating default 1-hour duration.")
                            try:
                                # Parse the start dateTime string directly. fromisoformat handles 'Z' and offsets.
                                start_dt_iso = parsed_start['dateTime']
                                start_dt_aware = datetime.fromisoformat(start_dt_iso.replace('Z', '+00:00'))

                                # Ensure it's timezone-aware (it should be after fromisoformat with offset/Z)
                                # If somehow it's still naive, use the default timezone. This is a fallback.
                                if start_dt_aware.tzinfo is None or start_dt_aware.tzinfo.utcoffset(start_dt_aware) is None:
                                    logger.warning(f"Parsed start datetime '{start_dt_iso}' resulted in a naive object for {notion_page_id}. Applying default timezone '{config.TIMEZONE}'.")
                                    # Ensure config.TIMEZONE is a valid pytz timezone name before using it
                                    try:
                                        default_tz = pytz.timezone(config.TIMEZONE)
                                        start_dt_aware = default_tz.localize(start_dt_aware)
                                    except pytz.UnknownTimeZoneError:
                                        logger.error(f"Default timezone '{config.TIMEZONE}' is invalid. Cannot localize naive datetime for {notion_page_id}.")
                                        # If default TZ is bad, we can't proceed reliably. Skip end calculation or use UTC?
                                        # For now, let's re-raise or handle as appropriate for the application logic.
                                        # Re-raising might be safer to signal a config issue.
                                        raise ValueError(f"Invalid default timezone configured: {config.TIMEZONE}")


                                # Default duration is 1 hour
                                end_dt_aware = start_dt_aware + timedelta(hours=1)

                                # Use the timezone information derived from the start datetime object for the end timeZone field.
                                # Google Calendar API expects an IANA timeZone ID.
                                # If start_dt_aware.tzinfo doesn't provide a standard name (e.g., fixed offset),
                                # fall back to the original tz_str from parsed_start or the default config.TIMEZONE.
                                # This preserves the original behavior regarding the timeZone field value,
                                # while fixing the crash caused by pytz.timezone('UTC-07:00').
                                end_tz_str = getattr(start_dt_aware.tzinfo, 'zone', None) # Try to get IANA name if available (e.g., from pytz)
                                if not end_tz_str:
                                     # Fallback to original logic's source for tz string
                                     end_tz_str = parsed_start.get('timeZone', config.TIMEZONE)

                                parsed_end = {
                                    # Format end time in ISO 8601, preserving timezone offset
                                    "dateTime": end_dt_aware.isoformat(),
                                    "timeZone": end_tz_str # Use derived/fallback timezone string
                                }
                                logger.debug(f"Calculated default end dateTime: {parsed_end['dateTime']} with timeZone: {parsed_end['timeZone']}")

                            except Exception as e_calc:
                                logger.error(f"Error calculating default 1-hour end time for event {notion_page_id} based on start '{parsed_start}': {e_calc}")
                                capture_exception(e_calc)
                                # Fallback: Use start time as end time to satisfy API requirement
                                parsed_end = parsed_start.copy() # Use a copy
                                logger.warning(f"Falling back to using start time as end time for event {notion_page_id}.")
                        else:
                             # Should not happen if parsed_start is valid
                             logger.error(f"Parsed start date object for {notion_page_id} is in an unexpected format: {parsed_start}. Skipping end date calculation.")
                             # Fallback: Use start time as end time
                             parsed_end = parsed_start.copy()

                    # --- Assemble Final Payload ---
                    event_data = {
                        'summary': extract_property(properties, 'Name', 'title'),
                        'location': extract_property(properties, 'Location', 'select'),
                        'description': extract_property(properties, 'Description', 'rich_text'),
                        'start': parsed_start,
                        'end': parsed_end, # Now guaranteed to have a value
                        # Keep internal IDs separate until the end
                        '_internal_notion_page_id': notion_page_id,
                        '_internal_gcal_id': None,  # No longer using gcal_id from Notion
                    }

                    # Remove keys with None values before sending to Google API, but keep internal ones
                    # Ensure 'end' is handled correctly if it ended up being None
                    # Remove keys with None values AND internal keys before sending to Google API
                    google_api_payload = {
                        k: v for k, v in event_data.items()
                        if v is not None and not k.startswith('_internal_')
                    }

                    # Check required fields (summary, start, end) before proceeding
                    if google_api_payload.get('summary') and google_api_payload.get('start') and google_api_payload.get('end'):
                        # Add default reminders
                        google_api_payload['reminders'] = {"useDefault": True}

                        # Create the entry for our internal list, including internal IDs
                        parsed_event_entry = google_api_payload.copy() # Start with the API payload
                        parsed_event_entry['notion_page_id'] = event_data['_internal_notion_page_id']
                        parsed_event_entry['gcal_id'] = event_data['_internal_gcal_id']

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


def parse_single_date_string(date_str: Optional[str]) -> Optional[Dict]:
    """Parse a single Notion date string into Google Calendar format.

    Handles both all-day ('YYYY-MM-DD') and specific time (ISO 8601) formats.

    Args:
        date_str: The date string from Notion (e.g., '2024-05-10' or '2024-05-10T10:00:00Z').

    Returns:
        A dictionary formatted for Google API ({"date": ...} or {"dateTime": ..., "timeZone": ...})
        or None if the input string is invalid or None.
    """
    if not date_str:
        return None

    # Clean the input string: remove leading/trailing whitespace and potential trailing commas
    cleaned_date_str = date_str.strip().rstrip(',')

    try:
        # Attempt to parse as just a date ('YYYY-MM-DD') first
        datetime.strptime(cleaned_date_str, '%Y-%m-%d')
        # If successful, it's an all-day date
        return {"date": cleaned_date_str} # Use the cleaned string
    except ValueError:
        # If date parse fails, attempt to parse as a full ISO 8601 dateTime string
        try:
            # Parse as ISO 8601 dateTime string
            dt_obj = datetime.fromisoformat(cleaned_date_str.replace('Z', '+00:00'))
            # Determine timezone: Use original if present, otherwise default
            tz_info = dt_obj.tzinfo
            time_zone_str = tz_info.tzname(None) if tz_info else config.TIMEZONE
            return {
                "dateTime": cleaned_date_str, # Use the original cleaned string
                "timeZone": time_zone_str
            }
        except ValueError:
            # If both parsing attempts fail, log warning and return None
            logger.warning(f"Invalid or unsupported date format encountered after cleaning: '{cleaned_date_str}' (original: '{date_str}')")
            return None
    except Exception as e:
        # Catch any other unexpected errors during parsing
        logger.error(f"Unexpected error parsing date string '{date_str}': {str(e)}")
        capture_exception(e)
        return None

# Note: The logic for calculating default end times is handled
# in the calling function (parse_event_data). This helper only parses a single provided string.

# Removed placeholder function and orphaned code block
# Removed delete_duplicate_synced_gcal_events function as requested.
# The logic in update_google_calendar already handles deleting "straggler" events
# (GCal events whose Notion counterpart is missing or unlinked).
@calendar_blueprint.route("/events", methods=["GET"])
def get_calendar_events_for_frontend():
    """API endpoint to fetch published Notion events for frontend display."""
    with start_transaction(op="api", name="get_frontend_events_notion") as transaction:
        try:
            database_id = config.NOTION_DATABASE_ID
            if not database_id:
                 logger.error("Required configuration NOTION_DATABASE_ID is missing in .env")
                 set_tag("config_error", "missing_database_id")
                 return jsonify({"status": "error", "message": "Notion database ID not configured."}), 500

            set_context("notion_fetch", {"database_id": database_id})
            logger.info(f"Fetching published events from Notion database ID: {database_id}")

            # 1. Fetch events from Notion
            with transaction.start_child(op="fetch", description="fetch_notion_events") as span:
                notion_events_raw = fetch_notion_events(database_id)
                if notion_events_raw is None: # Check if fetch failed
                    logger.error("Failed to fetch events from Notion for /events endpoint.")
                    set_tag("api_status", "notion_fetch_failed")
                    return jsonify({"status": "error", "message": "Could not fetch events from Notion."}), 500
                span.set_data("raw_event_count", len(notion_events_raw))

            # 2. Parse Notion events
            with transaction.start_child(op="parse", description="parse_notion_events") as span:
                # parse_event_data returns events formatted for Google Calendar API,
                # including internal 'notion_page_id' and 'gcal_id'.
                # We need to adapt this format for the frontend.
                parsed_events = parse_event_data(notion_events_raw)
                span.set_data("parsed_event_count", len(parsed_events))

            # 3. Format for Frontend
            with transaction.start_child(op="format", description="format_events_for_frontend") as span:
                frontend_events = []
                for event_data in parsed_events:
                    # Extract start/end times (handle both date and dateTime)
                    start_obj = event_data.get('start', {})
                    end_obj = event_data.get('end', {})
                    start = start_obj.get('dateTime', start_obj.get('date'))
                    end = end_obj.get('dateTime', end_obj.get('date'))

                    # Construct frontend event object
                    frontend_event = {
                        'id': event_data.get('notion_page_id'), # Use Notion page ID as the unique ID
                        'title': event_data.get('summary'),
                        'start': start,
                        'end': end,
                        'location': event_data.get('location'),
                        'description': event_data.get('description'),
                        'url': None # Notion events don't have a direct Google Calendar URL
                        # Add other relevant fields if needed, e.g., event type?
                    }
                    # Remove keys with None values
                    frontend_events.append({k: v for k, v in frontend_event.items() if v is not None})

                span.set_data("formatted_event_count", len(frontend_events))

            logger.info(f"Successfully fetched and formatted {len(frontend_events)} events from Notion for frontend")
            set_tag("api_status", "success")
            return jsonify({"status": "success", "events": frontend_events}), 200

        except APIResponseError as e: # Catch Notion specific errors
            capture_exception(e)
            logger.error(f"Notion API error fetching events: {e.code} - {str(e)}")
            set_context("notion_error", {"code": e.code, "message": str(e)})
            set_tag("api_status", "notion_api_error")
            return jsonify({"status": "error", "message": f"Error fetching events from Notion: {str(e)}"}), 500
        except Exception as e:
            capture_exception(e)
            logger.error(f"Error fetching calendar events for frontend from Notion: {str(e)}")
            set_tag("api_status", "unexpected_error")
            set_tag("error_type", "unexpected")
            return jsonify({"status": "error", "message": f"An unexpected error occurred: {str(e)}"}), 500


@calendar_blueprint.route("/delete-all-events", methods=["POST"])
def delete_all_calendar_events():
    """
    Endpoint to delete ALL events from the configured Google Calendar.
    USE WITH CAUTION. This is intended for hard resets.
    """
    with start_transaction(op="admin", name="delete_all_events") as transaction:
        logger.warning("Received request to DELETE ALL Google Calendar events. THIS IS A DESTRUCTIVE OPERATION.")
        service = get_google_calendar_service()
        if not service:
            set_tag("google_service", "failed")
            logger.error("Failed to get Google Calendar service. Aborting delete.")
            return jsonify({"status": "error", "message": "Failed to connect to Google Calendar."}), 500

        calendar_id = config.GOOGLE_CALENDAR_ID
        if not calendar_id:
            logger.error("GOOGLE_CALENDAR_ID not configured. Aborting delete.")
            return jsonify({"status": "error", "message": "Google Calendar ID not configured."}), 500

        # --- SAFETY CHECK ---
        # Add a configuration flag or environment check to prevent accidental execution in production
        if not getattr(config, 'ALLOW_DELETE_ALL', False): # Check for a config flag (defaults to False)
            logger.error("Execution of delete_all_calendar_events prevented by configuration (ALLOW_DELETE_ALL is not True).")
            set_tag("delete_status", "prevented_by_config")
            return jsonify({"status": "error", "message": "Operation prevented by server configuration."}), 403 # Forbidden

        logger.warning(f"ALLOW_DELETE_ALL is True. Proceeding with deletion for calendar: {calendar_id}")
        set_context("delete_all", {"calendar_id": calendar_id, "safety_check_passed": True})

        all_event_ids = []
        page_token = None
        deleted_count = 0
        fetch_errors = 0
        delete_errors = 0

        try:
            # 1. Fetch all event IDs
            with transaction.start_child(op="fetch", description="fetch_all_event_ids") as fetch_span:
                while True:
                    try:
                        events_result = service.events().list(
                            calendarId=calendar_id,
                            pageToken=page_token,
                            fields="nextPageToken,items(id)" # Only fetch IDs
                        ).execute()
                        items = events_result.get('items', [])
                        all_event_ids.extend([item['id'] for item in items])
                        page_token = events_result.get('nextPageToken')
                        if not page_token:
                            break
                    except HttpError as e:
                        fetch_errors += 1
                        logger.error(f"HTTP error fetching event page: {e.resp.status} - {e.error_details}")
                        # Decide whether to continue or abort based on error (e.g., break on 403/404)
                        if e.resp.status in [403, 404]:
                            raise e # Re-raise critical errors
                        # Continue for transient errors? Maybe add retry logic later.
                        break # Stop fetching on error for now
                    except Exception as e:
                        fetch_errors += 1
                        logger.error(f"Unexpected error fetching event page: {str(e)}")
                        break # Stop fetching on error

                fetch_span.set_data("fetched_ids", len(all_event_ids))
                fetch_span.set_data("fetch_errors", fetch_errors)
                logger.info(f"Fetched {len(all_event_ids)} event IDs to delete.")

            if fetch_errors > 0:
                 logger.warning(f"Encountered {fetch_errors} errors while fetching event IDs.")

            if not all_event_ids:
                logger.info("No events found in the calendar to delete.")
                return jsonify({"status": "success", "message": "No events found to delete."}), 200

            # 2. Batch delete events
            with transaction.start_child(op="delete", description="batch_delete_all") as delete_span:
                total_intended_deletions = len(all_event_ids)
                
                # Use our helper function to perform the batch delete
                successful, failed = batch_delete_events(
                    service,
                    calendar_id,
                    all_event_ids,
                    description="delete_all"
                )
                
                deleted_count = successful
                delete_errors = failed
                
                delete_span.set_data("intended_deletions", total_intended_deletions)
                delete_span.set_data("successful_deletions", successful)
                delete_span.set_data("delete_errors", failed)

            logger.info(f"Delete process finished. Total intended: {total_intended_deletions}, Successfully deleted (via callback): {deleted_count}, Errors (via callback): {delete_errors}")

            # Check if the number of successful deletions + errors matches the intended count
            if deleted_count + delete_errors != total_intended_deletions:
                 logger.warning(f"Mismatch in deletion count: intended={total_intended_deletions}, success={deleted_count}, errors={delete_errors}. Some operations might be unaccounted for.")
                 set_tag("delete_status", "count_mismatch")

            if delete_errors > 0:
                set_tag("delete_status", "partial_error")
                return jsonify({
                    "status": "partial_error",
                    "message": f"Attempted to delete {total_intended_deletions} events. Successfully deleted {deleted_count}, encountered {delete_errors} errors during deletion.",
                    "deleted_count": deleted_count,
                    "errors": delete_errors
                }), 207 # Multi-Status
            else:
                set_tag("delete_status", "success")
                return jsonify({
                    "status": "success",
                    "message": f"Successfully deleted {deleted_count} events.",
                    "deleted_count": deleted_count
                }), 200

        except HttpError as e: # Catch errors during event ID fetching primarily
            capture_exception(e)
            logger.error(f"Critical HTTP error during event ID fetching: {e.resp.status} - {e.error_details}")
            set_tag("delete_status", "critical_http_error_fetching")
            return jsonify({"status": "error", "message": f"HTTP Error during event fetching: {e.resp.status} - {e.error_details}"}), 500
        except Exception as e: # Catch other unexpected errors (e.g., during service init or fetching)
            capture_exception(e)
            logger.error(f"Unexpected critical error during delete process: {str(e)}")
            set_tag("delete_status", "critical_unexpected_error")
            return jsonify({"status": "error", "message": f"Unexpected Error: {str(e)}"}), 500
