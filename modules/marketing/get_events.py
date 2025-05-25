# gets latest events 
# from internal api 
# and considers which 
# one to take 
# [ latest events ]

#  example events structure : [ name , date, location , info ]

# Monitor /events endpoint in T’NAY API for new events one week into the future

    # mock_api_response = {
    #     "events": [
    #         {
    #             "end": (now + timedelta(days=2, hours=2)).isoformat(),
    #             "id": "event-001",
    #             "location": "PSH 150",
    #             "start": (now + timedelta(days=2)).isoformat(),
    #             "title": "Amazon ML Specialist Guest Lecture"
    #         },
    #         {
    #             "end": (now + timedelta(days=5, hours=24)).isoformat(),
    #             "id": "event-002",
    #             "location": "COOR Hall 174",
    #             "start": (now + timedelta(days=5)).isoformat(),
    #             "title": "SoDA Hackathon"
    #         },
    #         {
    #             "end": (now + timedelta(days=10, hours=2)).isoformat(),
    #             "id": "event-003",
    #             "location": "CAVC 101",
    #             "start": (now + timedelta(days=10)).isoformat(),
    #             "title": "Resume Workshop with Microsoft"
    #         }
    #     ],
    #     "status": "success"
    # }

import requests
from datetime import datetime, timedelta
import json
import os

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
        print("Using mock events for testing")
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
        return mock_events
    
    # Real API implementation
    try:
        response = requests.get(api_url)
        if response.status_code == 200:
            response_data = response.json()
            
            print(f"API response: {response_data}")
            
            # Check if the response has the expected structure
            if "status" in response_data and response_data["status"] == "success" and "events" in response_data:
                all_events = response_data["events"]
                
                # Filter events within time window
                upcoming_events = filter_upcoming_events(all_events, days_window)
                
                print(f"Found {len(upcoming_events)} upcoming events in the next {days_window} days")
                return upcoming_events
            else:
                print("Invalid API response format")
                return []
        else:
            print(f"Error fetching events: HTTP {response.status_code}")
            return []
    except Exception as e:
        print(f"Exception while fetching events: {str(e)}")
        return []
    
    
def filter_upcoming_events(events, days_window):
    """Filter events to include only those occurring within specified days"""
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
            print(f"Error parsing event: {str(e)}")
            continue
    
    return upcoming

def format_event_info(event):
    """Generate a more detailed info field if not provided"""
    if 'info' in event and event['info']:
        return event['info']
    
    # Try to create a description based on event title
    title = event['title'].lower()
    
    if 'lecture' in title or 'talk' in title:
        return f"Join us for an informative session on {event['title']}. Don't miss this opportunity to learn from industry experts."
    
    elif 'workshop' in title:
        return f"Participate in our {event['title']} and gain hands-on experience. Bring your laptop and be ready to learn!"
    
    elif 'hackathon' in title:
        return f"Join us for {event['title']} - a coding marathon where you can build amazing projects, win prizes, and meet fellow developers."
    
    elif 'gbm' in title or 'general' in title:
        return f"Join us for our General Body Meeting. We'll discuss upcoming events, opportunities, and more!"
    
    elif 'social' in title or 'mixer' in title or 'hours' in title:
        return f"Come hang out with fellow SoDA members, make new friends, and enjoy some refreshments!"
    
    else:
        return f"Join us for {event['title']}. More details will be announced soon!"

# if __name__ == "__main__":
#     # Test the function
#     events = get_upcoming_events()
#     print(json.dumps(events, indent=2))