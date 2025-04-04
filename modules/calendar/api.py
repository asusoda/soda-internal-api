from flask import Blueprint, jsonify, request
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import BatchHttpRequest # Added for batch operations
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional, Any
from notion_client.helpers import collect_paginated_api
from notion_client import APIErrorCode, APIResponseError
from shared import config, notion, logger

calendar_blueprint = Blueprint("calendar", __name__)

def get_google_calendar_service():
    """Initialize and return authenticated Google Calendar service"""
    SCOPES = ['https://www.googleapis.com/auth/calendar', 'https://www.googleapis.com/auth/calendar.events']
    try:
        credentials = service_account.Credentials.from_service_account_info(
            config.GOOGLE_SERVICE_ACCOUNT,
            scopes=SCOPES
        )
        return build('calendar', 'v3', credentials=credentials)
    except Exception as e:
        logger.error(f"Google API initialization failed: {str(e)}")
        return None

@calendar_blueprint.route("/notion-webhook", methods=["POST", "GET"])
def notion_webhook():
    if request.method == "GET":
        return jsonify({"status": "success"}), 200
    
    # POST request now triggers a full sync, ignoring any payload
    try:
        logger.info(f"Received POST request trigger for full Notion sync.")
        database_id = config.NOTION_DATABASE_ID # Use configured DB ID
        
        notion_events = fetch_notion_events(database_id)
        
        # Check the result of fetching Notion events
        if notion_events is None:
            # Fetch failed (error logged in fetch_notion_events)
            logger.error("Notion fetch failed. Skipping Google Calendar update and clearing.")
            return jsonify({"status": "error", "message": "Failed to fetch events from Notion. Calendar not updated."}), 500

        elif not notion_events:
            # Fetch succeeded, but returned zero events
            logger.warning("Successfully fetched 0 published future events from Notion. Clearing future Google Calendar events.")
            clear_future_events()
            return jsonify({
                "status": "success",
                "message": "Successfully fetched 0 events from Notion. Future Google Calendar events cleared."
            }), 200
            
        else:
            # Fetch succeeded and returned events
            parsed_events = parse_event_data(notion_events)
            logger.info(f"Parsed {len(parsed_events)} events from Notion.")
            results = update_google_calendar(parsed_events)
            logger.info(f"Google Calendar update process completed. Results: {len(results)} events processed.")
            return jsonify({
                "status": "success",
                "message": f"Calendar sync complete. Processed {len(results)} events.",
                "events_processed": results # Renamed for clarity
            }), 200

    except Exception as e:
        logger.error(f"Error processing webhook: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

def share_calendar_with_user(service, calendar_id: str):
    """Share the calendar with the specified user"""
    try:
        rule = {
            'scope': {
                'type': 'user',
                'value': config.GOOGLE_USER_EMAIL
            },
            'role': 'writer'
        }
        service.acl().insert(calendarId=calendar_id, body=rule).execute()
        logger.info(f"Calendar shared with {config.GOOGLE_USER_EMAIL}")
    except HttpError as e:
        logger.error(f"HTTP error sharing calendar: {e.resp.status} - {e.error_details}")
    except Exception as e: # Catch other potential errors
        logger.error(f"Unexpected error sharing calendar: {str(e)}")

def ensure_calendar_access() -> Optional[str]:
    """
    Ensure the calendar specified in config exists and is accessible.
    Returns the calendar ID if found and accessible, otherwise None.
    Does NOT create the calendar if it's missing.
    """
    service = get_google_calendar_service()
    if not service:
        return None

    calendar_id_to_check = config.GOOGLE_CALENDAR_ID
    if not calendar_id_to_check:
        logger.error("Required configuration GOOGLE_CALENDAR_ID is missing in .env")
        return None

    try:
        # Attempt to get the calendar by ID
        logger.info(f"Verifying access to Google Calendar with ID: {calendar_id_to_check}")
        calendar = service.calendars().get(calendarId=calendar_id_to_check).execute()
        logger.info(f"Successfully verified access to calendar: {calendar['summary']} ({calendar_id_to_check})")
        # Optional: Re-assert sharing permissions if needed, though get() implies read access.
        # share_calendar_with_user(service, calendar_id_to_check)
        return calendar_id_to_check

    except HttpError as e:
        if e.resp.status == 404:
            # Calendar not found - Log error and return None (as requested)
            logger.error(f"Google Calendar with ID '{calendar_id_to_check}' configured in .env was not found.")
            logger.error("Please ensure the ID is correct and the service account has access.")
            return None
        elif e.resp.status == 403:
             # Forbidden - Likely permissions issue
             logger.error(f"Access denied (403 Forbidden) for Google Calendar ID '{calendar_id_to_check}'.")
             logger.error("Please ensure the service account has been granted 'Make changes to events' permission for this calendar.")
             return None
        else:
            # Other HTTP error during get()
            logger.error(f"HTTP error checking for calendar '{calendar_id_to_check}': {e.resp.status} - {e.error_details}")
            return None
    except Exception as e_generic:
        # Other unexpected error during get()
        logger.error(f"Unexpected error checking for calendar '{calendar_id_to_check}': {str(e_generic)}")
        return None

def fetch_notion_events(database_id: str) -> Optional[List[Dict]]:
    """Fetch all relevant (published, future) events from Notion database using pagination."""
    try:
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        logger.info(f"Fetching all published Notion events on or after {now} using pagination.")
        
        # Define the filter
        query_filter = {
            "and": [
                {"property": "Published", "checkbox": {"equals": True}},
                {"property": "Date", "date": {"on_or_after": now}}
            ]
        }

        # Use collect_paginated_api to handle pagination automatically
        all_events = collect_paginated_api(
            notion.databases.query,
            database_id=database_id,
            filter=query_filter
        )
        
        # Note: collect_paginated_api returns full page objects.
        # The rest of the code expects the 'results' structure,
        # so we return the list directly. is_full_page checks are not needed here.
        
        logger.info(f"Fetched a total of {len(all_events)} Notion events via pagination.")
        return all_events
        
    except APIResponseError as error:
        logger.error(f"Notion API Error during fetch: {error.code} - {error.message}")
        # Handle specific errors if needed, e.g., ObjectNotFound
        if error.code == APIErrorCode.ObjectNotFound:
             logger.error(f"Database with ID {database_id} not found.")
        return None # Indicate failure
    except Exception as e:
        logger.error(f"Unexpected error fetching Notion events: {str(e)}")
        return None # Indicate failure

def update_google_calendar(parsed_notion_events: List[Dict]) -> List[Dict]:
    """Update Google Calendar with Notion events using GCAL ID for matching."""
    service = get_google_calendar_service()
    if not service:
        return []

    results = []
    
    try:
        # Fetch all future events from Google Calendar
        existing_gcal_events_raw = get_all_calendar_events(service, config.GOOGLE_CALENDAR_ID)
        # Create a dictionary for quick lookup by Google Calendar Event ID
        existing_gcal_events = {event['id']: event for event in existing_gcal_events_raw}
        
        processed_gcal_ids = set()

        for notion_event_data in parsed_notion_events:
            notion_page_id = notion_event_data.pop('notion_page_id', None) # Extract Notion page ID
            gcal_id = notion_event_data.pop('gcal_id', None) # Extract stored Google Calendar ID
            summary = notion_event_data.get('summary', 'Unknown Event')

            if not notion_page_id:
                logger.warning(f"Skipping event '{summary}' because Notion Page ID is missing.")
                continue

            try:
                jump_url = None
                if gcal_id and gcal_id in existing_gcal_events:
                    # Event exists in both Notion (has gcal_id) and Google Calendar
                    logger.info(f"Found matching event for '{summary}' using GCAL ID: {gcal_id}. Updating.")
                    jump_url = update_event(service, config.GOOGLE_CALENDAR_ID, gcal_id, notion_event_data)
                    processed_gcal_ids.add(gcal_id) # Mark this GCal ID as processed
                
                elif gcal_id and gcal_id not in existing_gcal_events:
                    # Event has gcal_id in Notion, but not found in Google Calendar (maybe deleted manually?)
                    logger.warning(f"Event '{summary}' has GCAL ID '{gcal_id}' in Notion but not found in Google Calendar. Recreating.")
                    # Pass notion_page_id to create_event so it can update Notion
                    jump_url = create_event(service, config.GOOGLE_CALENDAR_ID, notion_event_data, notion_page_id)

                else:
                    # No gcal_id in Notion, assume it's a new event
                    logger.info(f"No GCAL ID found for '{summary}'. Creating new event.")
                    # Pass notion_page_id to create_event so it can update Notion
                    jump_url = create_event(service, config.GOOGLE_CALENDAR_ID, notion_event_data, notion_page_id)

                if jump_url:
                    results.append({
                        "summary": summary,
                        "jump_url": jump_url
                    })

            except Exception as e:
                logger.error(f"Error processing event '{summary}' (Notion ID: {notion_page_id}): {str(e)}")

        # Remove events from Google Calendar that are no longer in the fetched Notion list
        gcal_ids_in_notion = {data.get('gcal_id') for data in parsed_notion_events if data.get('gcal_id')}
        ids_to_delete = set(existing_gcal_events.keys()) - processed_gcal_ids
        
        # Double check: Only delete if the ID wasn't just created/updated OR if it's truly gone from Notion
        # This handles cases where an event might have been deleted and recreated in the same run
        final_ids_to_delete = {id_ for id_ in ids_to_delete if id_ not in gcal_ids_in_notion}


        # Batch delete events from Google Calendar that are no longer in the fetched Notion list
        if final_ids_to_delete:
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
                 logger.error(f"HTTP error executing batch delete request: {e.resp.status} - {e.error_details}")
            except Exception as e:
                logger.error(f"Unexpected error executing batch delete request: {str(e)}")

        return results
    except Exception as e:
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
    try:
        events_result = service.events().list(
            calendarId=calendar_id,
            timeMin=datetime.now(timezone.utc).isoformat(),
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        return events_result.get('items', [])
    except HttpError as e:
        logger.error(f"HTTP error fetching calendar events: {e.resp.status} - {e.error_details}")
        return []
    except Exception as e: # Catch other potential errors
        logger.error(f"Unexpected error fetching calendar events: {str(e)}")
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
    try:
        updated_event = service.events().update(
            calendarId=calendar_id,
            eventId=event_id,
            body=event_data
        ).execute()
        jump_url = updated_event.get('htmlLink')
        logger.info(f"Updated event: {updated_event['id']}")
        return jump_url
    except HttpError as e:
        logger.error(f"HTTP error updating event {event_id}: {e.resp.status} - {e.error_details}")
        return None
    except Exception as e: # Catch other potential errors
        logger.error(f"Unexpected error updating event {event_id}: {str(e)}")
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
    try:
        created_event = service.events().insert(
            calendarId=calendar_id,
            body=event_data
        ).execute()
        
        gcal_event_id = created_event['id']
        jump_url = created_event.get('htmlLink')
        logger.info(f"Created Google Calendar event: {gcal_event_id} for Notion page: {notion_page_id}")

        # Update the Notion page with the new Google Calendar Event ID
        try:
            notion.pages.update(
                page_id=notion_page_id,
                properties={
                    "gcal_id": { # Use the actual property name confirmed by the user
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
            logger.info(f"Successfully updated Notion page {notion_page_id} with GCAL ID {gcal_event_id}")
        except APIResponseError as notion_e:
             logger.error(f"Notion API error updating page {notion_page_id} with GCAL ID {gcal_event_id}: {notion_e.code} - {notion_e.message}")
        except Exception as notion_e: # Catch other potential errors during Notion update
            logger.error(f"Unexpected error updating Notion page {notion_page_id} with GCAL ID {gcal_event_id}: {str(notion_e)}")
            # Decide if we should still return the jump_url or None if Notion update fails
            # For now, let's still return the jump_url as the GCal event was created.
            
        return jump_url
        
    except HttpError as e:
        logger.error(f"HTTP error creating Google Calendar event for Notion page {notion_page_id}: {e.resp.status} - {e.error_details}")
        return None
    except Exception as e: # Catch other potential errors during GCal creation
        logger.error(f"Unexpected error creating Google Calendar event for Notion page {notion_page_id}: {str(e)}")
        return None

def handle_batch_delete_response(request_id, response, exception):
    """Callback function for batch delete requests."""
    if exception:
        # Handle error
        logger.error(f"Batch delete request {request_id} failed: {exception}")
    else:
        # Process successful response if needed, often delete returns 204 No Content
        logger.debug(f"Batch delete request {request_id} successful.")

def clear_future_events() -> None:
    """Clear all future events from Google Calendar using batch delete."""
    service = get_google_calendar_service()
    if not service:
        logger.error("Failed to get Google Calendar service for clearing events.")
        return

    try:
        now = datetime.now(timezone.utc).isoformat()
        logger.info(f"Fetching future events from calendar {config.GOOGLE_CALENDAR_ID} for clearing.")
        
        events_to_delete = []
        page_token = None
        while True:
            events_result = service.events().list(
                calendarId=config.GOOGLE_CALENDAR_ID,
                timeMin=now,
                singleEvents=True,
                pageToken=page_token
                # No orderBy needed if just deleting all
            ).execute()
            
            items = events_result.get('items', [])
            if not items:
                break # No more events
                
            events_to_delete.extend(items)
            page_token = events_result.get('nextPageToken')
            if not page_token:
                break # Last page

        if not events_to_delete:
            logger.info("No future events found to clear.")
            return

        logger.info(f"Found {len(events_to_delete)} future events to clear. Preparing batch delete.")
        
        batch = service.new_batch_http_request(callback=handle_batch_delete_response)
        for event in events_to_delete:
            event_id = event['id']
            event_summary = event.get('summary', 'Unknown Event')
            logger.debug(f"Adding delete request for event '{event_summary}' (ID: {event_id}) to batch.")
            batch.add(service.events().delete(calendarId=config.GOOGLE_CALENDAR_ID, eventId=event_id))

        batch.execute()
        logger.info(f"Batch delete request executed for clearing {len(events_to_delete)} future events.")

    except HttpError as e:
         logger.error(f"HTTP error clearing events: {e.resp.status} - {e.error_details}")
    except Exception as e:
        logger.error(f"Unexpected error clearing events: {str(e)}")

def parse_event_data(notion_events: List[Dict]) -> List[Dict]:
    """Parse Notion events into Google Calendar format, including Notion Page ID and GCAL ID.
    
    Args:
        notion_events: Raw Notion database entries
    
    Returns:
        List of parsed events including 'notion_page_id' and 'gcal_id' keys,
        formatted for Google Calendar API.
    """
    parsed_events = []
    for event in notion_events:
        try:
            properties = event.get('properties', {})
            notion_page_id = event.get('id') # Get the Notion Page ID
            
            # Extract the gcal_id using the helper function
            gcal_id_text = extract_property(properties, 'gcal_id', 'rich_text')

            event_data = {
                'notion_page_id': notion_page_id, # Include Notion Page ID
                'gcal_id': gcal_id_text, # Include Google Calendar ID (might be None)
                'summary': extract_property(properties, 'Name', 'title'),
                'location': extract_property(properties, 'Location', 'select'), # Assuming Location is 'select' type
                'description': extract_property(properties, 'Description', 'rich_text'),
                'start': parse_date(properties.get('Date', {}).get('date', {}), 'start'),
                'end': parse_date(properties.get('Date', {}).get('date', {}), 'end'),
            }
            
            # Remove keys with None values before sending to Google API, but keep internal ones
            google_api_payload = {k: v for k, v in event_data.items() if v is not None and k not in ['notion_page_id', 'gcal_id']}
            
            if google_api_payload.get('summary') and google_api_payload.get('start'):
                google_api_payload['reminders'] = {"useDefault": True}
                
                # Add back the internal IDs to the dict we store in the list
                parsed_event_entry = google_api_payload.copy()
                parsed_event_entry['notion_page_id'] = notion_page_id
                parsed_event_entry['gcal_id'] = gcal_id_text
                
                parsed_events.append(parsed_event_entry)
                
        except Exception as e:
            notion_id = event.get('id', 'Unknown ID')
            logger.error(f"Error parsing Notion event (ID: {notion_id}): {str(e)}")
            # Optionally log the full event data for debugging: logger.debug(f"Failed event data: {event}")
    
    logger.info(f"Successfully parsed {len(parsed_events)}/{len(notion_events)} events")
    return parsed_events

# Helper functions
def extract_property(properties: Dict, name: str, prop_type: str) -> Optional[str]:
    """Extract text content from Notion property."""
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
    # Add other type handlers if necessary
    else:
        # Fallback for potentially simple types or unhandled ones
        # This might need adjustment based on actual Notion property types used
        return prop_data.get(prop_type)


def parse_date(date_obj: Dict, key: str) -> Optional[Dict]:
    """Parse datetime value from Notion date property."""
    date_str = date_obj.get(key)
    if not date_str:
        return None

    date_time_obj = datetime.fromisoformat(date_str.replace('Z', '+00:00'))

    if key == 'start':
        return {
            "dateTime": date_str,
            "timeZone": config.TIMEZONE
        }
    elif key == 'end':
        # If end time is missing, set it to one hour after the start time
        start_date_str = date_obj.get('start')
        if not start_date_str:
            return None

        start_date_time_obj = datetime.fromisoformat(start_date_str.replace('Z', '+00:00'))
        end_date_time_obj = start_date_time_obj + timedelta(hours=1)
        end_date_str = end_date_time_obj.isoformat()

        return {
            "dateTime": end_date_str,
            "timeZone": config.TIMEZONE
        }


@calendar_blueprint.route("/events", methods=["GET"])
def get_calendar_events_for_frontend():
    """API endpoint to fetch upcoming Google Calendar events for frontend display."""
    service = get_google_calendar_service()
    if not service:
        logger.error("Failed to get Google Calendar service for /events endpoint")
        return jsonify({"status": "error", "message": "Could not connect to Google Calendar"}), 500

    try:
        now = datetime.now(timezone.utc).isoformat()
        logger.info(f"Fetching upcoming events from Google Calendar ID: {config.GOOGLE_CALENDAR_ID}")
        
        events_result = service.events().list(
            calendarId=config.GOOGLE_CALENDAR_ID,
            timeMin=now,
            maxResults=50,  # Limit the number of results, adjust as needed
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        
        items = events_result.get('items', [])
        
        # Format events for frontend consumption
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
            
        logger.info(f"Successfully fetched {len(frontend_events)} events for frontend")
        return jsonify({"status": "success", "events": frontend_events}), 200

    except Exception as e:
        logger.error(f"Error fetching calendar events for frontend: {str(e)}")
        return jsonify({"status": "error", "message": f"Error fetching calendar events: {str(e)}"}), 500
