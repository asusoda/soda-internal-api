# gets latest events 
# from internal api 
# and considers which 
# one to take 
# [ latest events ]

import requests
from datetime import datetime, timedelta
from get_database import get_all_event_ids, get_all_completed_events
from shared import logger

def get_upcoming_events(api_url=None, days_window=7, mock=False):
    """
    Fetches upcoming events from the T'NAY API within specified time window
    
    Args:
        api_url (str): URL for the events API endpoint
        days_window (int): Number of days to look ahead for events
        mock (bool): Whether to return mock events for testing
        
    Returns:
        list: List of events within the window period
    """
    # Return mock events for testing if requested
    if mock:
        logger.info("Using mock events for testing")
        now = datetime.now()
        # Mock events with realistic data
        mock_events = [
            {
                "id": "event-001",
                "name": "Amazon ML Specialist Guest Lecture",
                "date": (now + timedelta(days=2)).isoformat(),
                "location": "PSH 150",
                "info": "Join us for an informative session on Amazon ML technologies. Don't miss this opportunity to learn from industry experts."
            },
            {
                "id": "event-002",
                "name": "SoDA Hackathon",
                "date": (now + timedelta(days=5)).isoformat(),
                "location": "COOR Hall 174",
                "info": "Join us for SoDA Hackathon - a coding marathon where you can build amazing projects, win prizes, and meet fellow developers."
            },
            {
                "id": "event-003",
                "name": "Resume Workshop with Microsoft",
                "date": (now + timedelta(days=6)).isoformat(),
                "location": "CAVC 101",
                "info": "Participate in our Resume Workshop with Microsoft and gain hands-on experience. Bring your laptop and be ready to learn!"
            }
        ]
        # Filter out events that are already completed
        return filter_new_events(mock_events)
    
    # Real API implementation
    try:
        response = requests.get(api_url)
        if response.status_code == 200:
            response_data = response.json()
            
            logger.info(f"API response: {response_data}")
            
            # Check if the response has the expected structure
            if "status" in response_data and response_data["status"] == "success" and "events" in response_data:
                all_events = response_data["events"]
                
                # Filter events within time window and check if they're new
                upcoming_events = filter_upcoming_events(all_events, days_window)
                
                # Filter out events that are already in the database or completed
                new_events = filter_new_events(upcoming_events)
                
                logger.info(f"Found {len(new_events)} new upcoming events in the next {days_window} days")
                return new_events
            else:
                logger.info("Invalid API response format")
                return []
        else:
            logger.info(f"Error fetching events: HTTP {response.status_code}")
            return []
    except Exception as e:
        logger.info(f"Exception while fetching events: {str(e)}")
        return []
    
def filter_new_events(events):
    """
    Filter out events that are already in the database or completed
    
    Args:
        events (list): List of event dictionaries
    
    Returns:
        list: List of new events not yet in the database or completed
    """
    # Get all existing event IDs and completed event IDs
    existing_ids = get_all_event_ids()
    completed_events = get_all_completed_events()
    
    new_events = []
    for event in events:
        event_id = event.get('id')
        if event_id and event_id not in existing_ids and event_id not in completed_events:
            new_events.append(event)
            
    return new_events
    
def filter_upcoming_events(events, days_window):
    """
    Filter events to include only those occurring within specified days
    
    Args:
        events (list): List of event dictionaries
        days_window (int): Number of days to look ahead
        
    Returns:
        list: List of events within the time window
    """
    now = datetime.now().replace(tzinfo=None)  # Ensure naive datetime
    cutoff = now + timedelta(days=days_window)
    
    upcoming = []
    for event in events:
        try:
            # Use 'start' field instead of 'date'
            event_date = datetime.fromisoformat(event['start'].replace('Z', '+00:00')).replace(tzinfo=None)  # Convert to naive datetime
            if now <= event_date <= cutoff:
                # Convert the event to our expected format
                formatted_event = {
                    "id": event['id'],
                    "name": event['title'],
                    "date": event['start'],
                    "location": event.get('location', 'TBD'),
                    "info": f"Join us for {event['title']} from {event['start']} to {event['end']}."
                }
                upcoming.append(formatted_event)
        except (ValueError, KeyError) as e:
            logger.info(f"Error parsing event: {str(e)}")
            continue
    
    return upcoming