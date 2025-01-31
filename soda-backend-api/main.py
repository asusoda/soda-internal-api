import logging
from flask import Flask, jsonify, request
from google.oauth2 import service_account
from googleapiclient.discovery import build
from notion_client import Client
from datetime import datetime, timezone
import json
import os
import uuid

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def load_config():
    """
    Load configuration from appConfig.json
    
    Returns:
        dict: Configuration dictionary
    """
    try:
        config_path = os.path.join(os.path.dirname(__file__), 'appConfig.json')
        with open(config_path, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load configuration: {str(e)}")
        raise RuntimeError("Configuration file not found or invalid")
def validate_config(config):
    """
    Validate required configuration parameters
    """
    required_fields = {
        'notion': ['api_key', 'database_id'],
        'google': ['service_account_file', 'calendar_id', 'user_email'],
        'server': ['port', 'debug', 'timezone']
    }
    
    try:
        for section, fields in required_fields.items():
            if section not in config:
                raise ValueError(f"Missing section: {section}")
            for field in fields:
                if field not in config[section]:
                    raise ValueError(f"Missing field: {section}.{field}")
        return True
    except Exception as e:
        logger.error(f"Configuration validation failed: {str(e)}")
        raise

# Load configuration at startup
CONFIG = load_config()
# Add validation call after loading config
validate_config(CONFIG)


# Update the configuration variables
app = Flask(__name__)

# Configuration
NOTION_API_KEY = CONFIG['notion']['api_key']
NOTION_DATABASE_ID = CONFIG['notion']['database_id']
SERVICE_ACCOUNT_FILE = CONFIG['google']['service_account_file']
CALENDAR_ID = CONFIG['google']['calendar_id']
YOUR_EMAIL = CONFIG['google']['user_email']
TIMEZONE = CONFIG['server']['timezone']

notion = Client(auth=NOTION_API_KEY)


def track_event_changes(events, filename='event_state.json'):
    """
    Track changes in events by comparing with previously stored state.
    
    Args:
        events (list): List of current events.
        filename (str): Name of the file to store event state.
    
    Returns:
        tuple: New events, updated events, and removed events.
    """
    try:
        current_events = {event.get('id', str(uuid.uuid4())): event for event in events}
        
        if os.path.exists(filename):
            with open(filename, 'r') as f:
                previous_events = json.load(f)
        else:
            previous_events = {}
        
        new_events = {k: v for k, v in current_events.items() if k not in previous_events}
        updated_events = {k: v for k, v in current_events.items() if k in previous_events and v != previous_events[k]}
        removed_events = {k: v for k, v in previous_events.items() if k not in current_events}
        
        with open(filename, 'w') as f:
            json.dump(current_events, f)
        
        return new_events, updated_events, removed_events
    except Exception as e:
        logger.error(f"Error tracking event changes: {str(e)}")
        return {}, {}, {}

def get_google_calendar_service():
    """
    Create and return a Google Calendar service object.
    
    Returns:
        googleapiclient.discovery.Resource: Google Calendar service object.
    """
    try:
        SCOPES = [
            'https://www.googleapis.com/auth/calendar',
            'https://www.googleapis.com/auth/calendar.events'
        ]
        credentials = service_account.Credentials.from_service_account_file(
            SERVICE_ACCOUNT_FILE, 
            scopes=SCOPES
        )
        return build('calendar', 'v3', credentials=credentials)
    except Exception as e:
        logger.error(f"Error creating Google Calendar service: {str(e)}")
        return None

def share_calendar_with_user(service, calendar_id):
    """
    Share the calendar with the specified user.
    
    Args:
        service (googleapiclient.discovery.Resource): Google Calendar service object.
        calendar_id (str): ID of the calendar to share.
    """
    try:
        rule = {
            'scope': {
                'type': 'user',
                'value': YOUR_EMAIL
            },
            'role': 'writer'
        }
        service.acl().insert(calendarId=calendar_id, body=rule).execute()
        logger.info(f"Calendar shared with {YOUR_EMAIL}")
    except Exception as e:
        logger.error(f"Error sharing calendar: {str(e)}")

def ensure_calendar_access():
    """
    Ensure the calendar exists and is accessible.
    
    Returns:
        str: Calendar ID if successful, None otherwise.
    """
    service = get_google_calendar_service()
    if not service:
        return None

    try:
        calendar = {
            'summary': 'Notion Events',
            'timeZone': CONFIG['server']['timezone']

        }
        created_calendar = service.calendars().insert(body=calendar).execute()
        calendar_id = created_calendar['id']
        logger.info(f"Created new calendar: {calendar_id}")
        
        share_calendar_with_user(service, calendar_id)
        return calendar_id
    except Exception as e:
        logger.error(f"Error creating calendar: {str(e)}")
        return None

def fetch_notion_events(database_id: str) -> list:
    """
    Fetch events from Notion database.
    
    Args:
        database_id (str): ID of the Notion database.
    
    Returns:
        list: List of Notion events.
    """
    try:
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        logger.info(f"Fetching Notion events from {now}")
        
        response = notion.databases.query(
            database_id=database_id,
            filter={
                "and": [
                    {
                        "property": "availability",
                        "checkbox": {
                            "equals": True
                        }
                    },
                    {
                        "property": "Date",
                        "date": {
                            "on_or_after": now
                        }
                    }
                ]
            }
        )
        events = response.get('results', [])
        logger.info(f"Fetched {len(events)} Notion events")
        return events
    except Exception as e:
        logger.error(f"Notion API error: {str(e)}")
        return []

def get_all_calendar_events(service, calendar_id):
    """
    Get all future events from Google Calendar.
    
    Args:
        service (googleapiclient.discovery.Resource): Google Calendar service object.
        calendar_id (str): ID of the calendar.
    
    Returns:
        list: List of calendar events.
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

def find_matching_event(existing_events, notion_event):
    """
    Find a matching event in existing calendar events.
    
    Args:
        existing_events (list): List of existing calendar events.
        notion_event (dict): Notion event to match.
    
    Returns:
        dict: Matching event if found, None otherwise.
    """
    for event in existing_events:
        if (event['summary'] == notion_event['summary'] and
            event['start']['dateTime'] == notion_event['start']['dateTime']):
            return event
    return None

def update_event(service, calendar_id, event_id, event_data):
    """
    Update an existing event in Google Calendar.
    
    Args:
        service (googleapiclient.discovery.Resource): Google Calendar service object.
        calendar_id (str): ID of the calendar.
        event_id (str): ID of the event to update.
        event_data (dict): Updated event data.
    
    Returns:
        str: Jump URL of the updated event.
    """
    try:
        updated_event = service.events().update(
            calendarId=calendar_id,
            eventId=event_id,
            body=event_data
        ).execute()
        jump_url = updated_event.get('htmlLink')
        logger.info(f"Event updated: {updated_event['id']}, Jump URL: {jump_url}")
        return jump_url
    except Exception as e:
        logger.error(f"Error updating event: {str(e)}")
        return None

def create_event(service, calendar_id, event_data):
    """
    Create a new event in Google Calendar.
    
    Args:
        service (googleapiclient.discovery.Resource): Google Calendar service object.
        calendar_id (str): ID of the calendar.
        event_data (dict): Event data to create.
    
    Returns:
        str: Jump URL of the created event.
    """
    try:
        event = service.events().insert(calendarId=calendar_id, body=event_data).execute()
        jump_url = event.get('htmlLink')
        logger.info(f"Event created: {event['id']}, Jump URL: {jump_url}")
        return jump_url
    except Exception as e:
        logger.error(f"Error creating event: {str(e)}")
        return None

def update_google_calendar(notion_events):
    """
    Update Google Calendar with Notion events.
    
    Args:
        notion_events (list): List of Notion events.
    
    Returns:
        list: List of updated/created events with their jump URLs.
    """
    service = get_google_calendar_service()
    if not service:
        return []

    results = []
    
    try:
        existing_events = get_all_calendar_events(service, CALENDAR_ID)
        
        for notion_event in notion_events:
            try:
                existing_event = find_matching_event(existing_events, notion_event)
                
                if existing_event:
                    jump_url = update_event(service, CALENDAR_ID, existing_event['id'], notion_event)
                    existing_events.remove(existing_event)
                else:
                    jump_url = create_event(service, CALENDAR_ID, notion_event)
                
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
                service.events().delete(calendarId=CALENDAR_ID, eventId=outdated_event['id']).execute()
                logger.info(f"Removed event: {outdated_event.get('summary')}")
            except Exception as e:
                logger.error(f"Error removing event {outdated_event.get('summary')}: {str(e)}")
        
        return results
    except Exception as e:
        logger.error(f"Error updating Google Calendar: {str(e)}")
        return []

@app.route('/notion-webhook', methods=['POST', 'GET'])
def notion_webhook():
    """
    Handle Notion webhook requests.
    """
    if request.method == 'GET':
        return jsonify({"status": "success"}), 200

    try:
        data = request.json
        database_id = data.get('database_id', NOTION_DATABASE_ID)
        
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

def clear_future_events():
    """
    Clear all future events from Google Calendar starting from the current date.
    """
    service = get_google_calendar_service()
    if not service:
        logger.error("Failed to get Google Calendar service")
        return

    try:
        now = datetime.now(timezone.utc).isoformat()
        events_result = service.events().list(
            calendarId=CALENDAR_ID,
            timeMin=now,
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        events = events_result.get('items', [])

        for event in events:
            service.events().delete(calendarId=CALENDAR_ID, eventId=event['id']).execute()
            logger.info(f"Deleted event: {event.get('summary')}")

        logger.info("All future events cleared from Google Calendar")
    except Exception as e:
        logger.error(f"Error clearing future events: {str(e)}")

def parse_event_data(notion_events: list) -> list:
    """
    Parse Notion events into a format suitable for Google Calendar.
    
    Args:
        notion_events (list): List of Notion events.
    
    Returns:
        list: List of parsed events ready for Google Calendar.
    """
    logger.info(f"Parsing {len(notion_events)} Notion events")
    parsed_events = []
    for event in notion_events:
        try:
            properties = event.get('properties', {})
            event_data = {}
            
            # Extract event details
            title = next((item.get('text', {}).get('content') for item in properties.get('Name', {}).get('title', []) if item.get('text', {}).get('content')), None)
            if title:
                event_data['summary'] = title
            
            # Extract location and add it to event data
            location = next((item.get('text', {}).get('content') for item in properties.get('Location', {}).get('rich_text', []) if item.get('text', {}).get('content')), None)
            if location:
                event_data['location'] = location
            
            description = next((item.get('text', {}).get('content') for item in properties.get('description', {}).get('rich_text', []) if item.get('text', {}).get('content')), None)
            if description:
                event_data['description'] = description
            
            # Handle date and time
            date_obj = properties.get('Date', {}).get('date', {})
            start_date = date_obj.get('start')
            if start_date:
                event_data['start'] = {
                    "dateTime": start_date,
                    "timeZone": CONFIG['server']['timezone']

                }
                end_date = date_obj.get('end') or start_date
                event_data['end'] = {
                    "dateTime": end_date,
                    "timeZone": CONFIG['server']['timezone']

                }
            
            # Handle attendees
            guests = next((item.get('text', {}).get('content') for item in properties.get('guests', {}).get('rich_text', []) if item.get('text', {}).get('content')), None)
            if guests:
                attendees = [{"email": email.strip()} for email in guests.split(',') if '@' in email]
                if attendees:
                    event_data['attendees'] = attendees
            
            # Add reminders if there's at least a summary and date
            if 'summary' in event_data and 'start' in event_data:
                event_data['reminders'] = {"useDefault": True}
            
            if event_data:
                parsed_events.append(event_data)
        except Exception as e:
            logger.error(f"Error parsing event: {str(e)}")
    
    logger.info(f"Parsed {len(parsed_events)} events successfully")
    return parsed_events

if __name__ == '__main__':
    app.run(
        debug=CONFIG['server']['debug'],
        port=CONFIG['server']['port']
    )

