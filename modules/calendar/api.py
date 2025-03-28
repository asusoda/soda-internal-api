from flask import Blueprint, jsonify, request
from google.oauth2 import service_account
from googleapiclient.discovery import build
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional, Any
from shared import config, notion,logger

calendar_blueprint = Blueprint("calendar", __name__)

def get_google_calendar_service():
    """Initialize and return authenticated Google Calendar service"""
    SCOPES = ['https://www.googleapis.com/auth/calendar', 'https://www.googleapis.com/auth/calendar.events']
    try:
        logger.info("Initializing Google Calendar service...")
        credentials = service_account.Credentials.from_service_account_info(
            config.GOOGLE_SERVICE_ACCOUNT,
            scopes=SCOPES
        )
        logger.info("Google Calendar credentials obtained.")
        service = build('calendar', 'v3', credentials=credentials)
        logger.info("Google Calendar service built successfully.")

        # Log all calendars the service can access
        try:
            calendar_list = service.calendarList().list().execute()
            calendars = calendar_list.get('items', [])
            calendar_names = [calendar['summary'] for calendar in calendars]
            logger.info(f"Calendars the service can access: {calendar_names}")
        except Exception as e:
            logger.error(f"Error listing calendars: {str(e)}")

        return service
    except Exception as e:
        logger.error(f"Google API initialization failed: {str(e)}")
        return None

@calendar_blueprint.route("/notion-webhook", methods=["POST", "GET"])
def notion_webhook():
    if request.method == "GET":
        return jsonify({"status": "success"}), 200
    
    try:
        verification_token = request.args.get("verification_token")
        if verification_token:
            logger.info(f"Verification token: {verification_token}")
    except Exception as e:
        logger.error(f"Error retrieving verification token: {str(e)}")
    
    try:
        data = request.json
        database_id = data.get('database_id', config.NOTION_DATABASE_ID)
        
        notion_events = fetch_notion_events(database_id)
        
        if notion_events:
            parsed_events = parse_event_data(notion_events)
            logger.info(f"Parsed {len(parsed_events)} events")
            results = update_google_calendar(parsed_events)
            return jsonify({
                "status": "success", 
                "message": "Calendar updated",
                "events": results
            }), 200
        else:
            logger.warning("No events found in Notion database")
            clear_future_events()
            return jsonify({
                "status": "success", 
                "message": "No events found in Notion. All future events cleared from Google Calendar."
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
    except Exception as e:
        logger.error(f"Error sharing calendar: {str(e)}")

def ensure_calendar_access() -> Optional[str]:
    """Ensure the calendar exists and is accessible"""
    service = get_google_calendar_service()
    if not service:
        return None

    try:
        calendar = {
            'summary': 'Notion Events',
            'timeZone': config.TIMEZONE
        }
        created_calendar = service.calendars().insert(body=calendar).execute()
        calendar_id = created_calendar['id']
        logger.info(f"Created new calendar: {calendar_id}")
        
        share_calendar_with_user(service, calendar_id)
        return calendar_id
    except Exception as e:
        logger.error(f"Error creating calendar: {str(e)}")
        return None

def fetch_notion_events(database_id: str) -> List[Dict]:
    """Fetch events from Notion database"""
    try:
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        logger.info(f"Fetching Notion events from {now}")
        
        response = notion.databases.query(
            database_id=database_id,
            filter={
                "and": [
                    {"property": "Published", "checkbox": {"equals": True}},
                    {"property": "Date", "date": {"on_or_after": now}}
                ]
            }
        )
        events = response.get('results', [])
        logger.info(f"Fetched {len(events)} Notion events")
        return events
    except Exception as e:
        logger.error(f"Notion API error: {str(e)}")
        return []

def update_google_calendar(notion_events: List[Dict]) -> List[Dict]:
    """Update Google Calendar with Notion events"""
    service = get_google_calendar_service()
    if not service:
        return []

    results = []
    
    try:
        existing_events = get_all_calendar_events(service, config.GOOGLE_CALENDAR_ID)
        
        for notion_event in notion_events:
            try:
                existing_event = find_matching_event(existing_events, notion_event)
                
                if existing_event:
                    jump_url = update_event(service, config.GOOGLE_CALENDAR_ID, existing_event['id'], notion_event)
                    existing_events.remove(existing_event)
                else:
                    jump_url = create_event(service, config.GOOGLE_CALENDAR_ID, notion_event)
                
                if jump_url:
                    results.append({
                        "summary": notion_event.get('summary'),
                        "jump_url": jump_url
                    })
            except Exception as e:
                logger.error(f"Error processing event {notion_event.get('summary')}: {str(e)}")
        
        # Remove events that no longer exist in Notion
        for outdated_event in existing_events:
            try:
                service.events().delete(calendarId=config.GOOGLE_CALENDAR_ID, eventId=outdated_event['id']).execute()
                logger.info(f"Removed event: {outdated_event.get('summary')}")
            except Exception as e:
                logger.error(f"Error removing event {outdated_event.get('summary')}: {str(e)}")
        
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
    except Exception as e:
        logger.error(f"Error fetching calendar events: {str(e)}")
        return []

def find_matching_event(existing_events: List[Dict], notion_event: Dict) -> Optional[Dict]:
    """Find matching event in existing calendar events.
    
    Args:
        existing_events: List of events from Google Calendar
        notion_event: Parsed Notion event to match
    
    Returns:
        Matching event dict if found, None otherwise
    """
    return next(
        (
            event for event in existing_events
            if event['summary'] == notion_event['summary']
            and event['start']['dateTime'] == notion_event['start']['dateTime']
        ),
        None
    )

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
    except Exception as e:
        logger.error(f"Error updating event: {str(e)}")
        return None

def create_event(service: Any, calendar_id: str,
                event_data: Dict) -> Optional[str]:
    """Create new Google Calendar event.

    Args:
        service: Authenticated Google Calendar service
        calendar_id: Target calendar ID
        event_data: Event data to create

    Returns:
        Event HTML link if successful, None otherwise
    """
    try:
        logger.info(f"Creating event with data: {event_data}")  # Log event data

        # Validate event data
        if not event_data.get('start'):
            logger.error("Event start or end time is missing.")
            return None

        # If end time is missing, set it to one hour after the start time
        if not event_data.get('end'):
            logger.error("End date missing. Defaulting to one hour after start. @265")
            start_date_time_str = event_data['start']['dateTime']
            start_date_time_obj = datetime.fromisoformat(start_date_time_str.replace('Z', '+00:00'))
            end_date_time_obj = start_date_time_obj + timedelta(hours=1)
            end_date_time_str = end_date_time_obj.isoformat()
            event_data['end'] = {
                "dateTime": end_date_time_str,
                "timeZone": config.TIMEZONE
            }

        event = service.events().insert(
            calendarId=calendar_id,
            body=event_data
        ).execute()
        
        jump_url = event.get('htmlLink')
        logger.info(f"Created event: {event['id']}")
        return jump_url
    except Exception as e:
        logger.error(f"Error creating event: {str(e)}, Event Data: {event_data}")
        return None

def clear_future_events() -> None:
    """Clear all future events from Google Calendar."""
    service = get_google_calendar_service()
    if not service:
        logger.error("Failed to get Google Calendar service")
        return

    try:
        now = datetime.now(timezone.utc).isoformat()
        events_result = service.events().list(
            calendarId=config.GOOGLE_CALENDAR_ID,
            timeMin=now,
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        
        for event in events_result.get('items', []):
            service.events().delete(
                calendarId=config.GOOGLE_CALENDAR_ID,
                eventId=event['id']
            ).execute()
            logger.info(f"Deleted event: {event.get('summary')}")
            
        logger.info("All future events cleared")
    except Exception as e:
        logger.error(f"Error clearing events: {str(e)}")

def parse_event_data(notion_events: List[Dict]) -> List[Dict]:
    """Parse Notion events into Google Calendar format.
    
    Args:
        notion_events: Raw Notion database entries
    
    Returns:
        List of parsed events in Google Calendar format
    """
    parsed_events = []
    for event in notion_events:
        try:
            properties = event.get('properties', {})
            event_data = {
                'summary': extract_property(properties, 'Name', 'title'),
                'location': extract_property(properties, 'Location', 'select'),
                'description': extract_property(properties, 'Description', 'rich_text'),
                'start': parse_date(properties.get('Date', {}).get('date', {}), 'start'),
                'end': parse_date(properties.get('Date', {}).get('date', {}), 'end'),
            }
            
            event_data = {k: v for k, v in event_data.items() if v}
            
            if event_data.get('summary') and event_data.get('start'):
                event_data['reminders'] = {"useDefault": True}
                parsed_events.append(event_data)
                
        except Exception as e:
            logger.error(f"Error parsing event: {str(e)}")
    
    logger.info(f"Successfully parsed {len(parsed_events)}/{len(notion_events)} events")
    return parsed_events

# Helper functions
def extract_property(properties: Dict, name: str, prop_type: str) -> Optional[str]:
    """Extract text content from Notion property."""
    if prop_type == 'select':
        return properties.get(name, {}).get('select', {}).get('name')
    else:
        prop = properties.get(name, {}).get(prop_type, [])
        return next((item.get('text', {}).get('content') for item in prop if item.get('text')), None)


def parse_date(date_obj: Dict, key: str) -> Optional[Dict]:
    """Parse datetime value from Notion date property."""
    date_str = date_obj.get(key)
    if not date_str:
        return None

    datetime.fromisoformat(date_str.replace('Z', '+00:00'))

    if key == 'start':
        if 'T' not in date_str:
            date_str += 'T00:00:00'  # Add default time if missing
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
