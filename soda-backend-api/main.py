from flask import Flask, jsonify, request
import requests
from datetime import datetime, timedelta
import os
import json
import logging
from datetime import datetime, timezone, timedelta
from notion_client import Client

app = Flask(__name__)

# Configuration
NOTION_API_KEY = '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'
# 189e4acf846e80b4871bee29a06f0666
# 189e4acf846e802bbf35000c459e9a91
# 189e4acf846e80b4871bee29a06f0666
APYHUB_API_KEY =  'APY00sHaoPUmXU3goNgzt0C5fVadU6wjnmphgSKHiHfYwFt989HFeNM5uRoFYpslp'
APYHUB_ICAL_URL = 'https://api.apyhub.com/generate/ical/url?output=invite.ics'
ICAL_FILE = 'calendar.ics'
JSON_FILE = 'events.json'

notion = Client(auth=NOTION_API_KEY)

def fetch_notion_events(database_id: str) -> list:
    """Fetch filtered events from Notion database"""
    try:
        now = datetime.now(timezone.utc).isoformat()
        next_month = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
        
        response = notion.databases.query(
            database_id=database_id,
            filter={
                "or": [
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
                    },
                    {
                        "property": "Date",
                        "date": {
                            "on_or_before": next_month
                        }
                    }
                ]
            }
        )
        return response.get('results', [])
    except Exception as e:
        print(f"Notion API error: {str(e)}")
        return []
def parse_event_data(notion_events: list) -> list:
    """Parse Notion event data into standardized format"""
    parsed_events = []
    for event in notion_events:
        properties = event.get('properties', {})
        
        # Extract and validate description
        description = ''
        rich_text = properties.get('description', {}).get('rich_text', [])
        if rich_text and isinstance(rich_text, list):
            description = rich_text[0].get('text', {}).get('content', '')
        description = description or "No description provided"

        # Extract date range and format properly
        date_obj = properties.get('Date', {}).get('date', {})
        start_date = date_obj.get('start', '').split('T')[0] if date_obj.get('start') else ''
        end_date = date_obj.get('end', '').split('T')[0] if date_obj.get('end') else ''
        
        # Convert date format from YYYY-MM-DD to DD-MM-YYYY
        if start_date:
            year, month, day = start_date.split('-')
            start_date = f"{day}-{month}-{year}"
        if end_date:
            year, month, day = end_date.split('-')
            end_date = f"{day}-{month}-{year}"

        # Extract and validate emails
        guests = properties.get('guests', {}).get('rich_text', [{}])[0].get('text', {}).get('content', '')
        attendees_emails = [email.strip() for email in guests.split(',') if '@' in email]
        
        parsed_events.append({
            "summary": properties.get('Name', {}).get('title', [{}])[0].get('text', {}).get('content', ''),
            "description": description,
            "organizer_email": "somwrks@gmail.com",  # Using email from screenshot
            "attendees_emails": attendees_emails,
            "location": properties.get('Location', {}).get('rich_text', [{}])[0].get('text', {}).get('content', ''),
            "time_zone": "America/Phoenix",  # Correct timezone for Arizona
            "start_time": "12:00",  # From screenshot
            "end_time": "23:59",    # End of day
            "meeting_date": start_date,
            "end_date": end_date
        })
    return parsed_events

@app.route('/ical/update', methods=['POST'])
def update_ical():
    events = request.json.get('events', [])
    
    headers = {
        'Content-Type': 'application/json',
        'apy-token': APYHUB_API_KEY
    }
    
    ical_events = []
    for event in events:
        ical_event = {
            "summary": event['summary'],
            "description": event['description'],
            "organizer_email": "organizer@example.com",
            "attendees_emails": event['attendees_emails'],
            "location": event['location'],
            "time_zone": "MST",
            "meeting_date": event['meeting_date'],
            "end_date": event['end_date']
        }
        ical_events.append(ical_event)
    
    response = requests.post(APYHUB_ICAL_URL, headers=headers, json=ical_events)
    
    if response.status_code == 200:
        with open(ICAL_FILE, 'w') as f:
            f.write(response.text)
        with open(JSON_FILE, 'w') as f:
            json.dump(events, f)
        return jsonify({
            "status": "success",
            "message": "iCAL updated",
            "ical_link": "/ical/feed"
        })
    else:
        return jsonify({"error": "Failed to update iCAL"}), 500



@app.route('/events/json', methods=['GET'])
def get_events_json():
    try:
        with open(JSON_FILE, 'r') as f:
            events = json.load(f)
        return jsonify(events)
    except FileNotFoundError:
        return jsonify([])
    
@app.route('/sync', methods=['GET'])
def sync_events():
    database_id = request.args.get('database_id')
    if not database_id:
        return jsonify({"error": "Missing database_id parameter"}), 400
    
    notion_events = fetch_notion_events(database_id)
    if not notion_events:
        return jsonify({"error": "Failed to fetch events from Notion"}), 500
    print("notion api successfully fetched")
    parsed_events = parse_event_data(notion_events)
    print("successfully parsed\n", parsed_events)
    
    headers = {
        'Content-Type': 'application/json',
        'apy-token': APYHUB_API_KEY
    }
    
    # Format events for ApyHub API
    ical_events = []
    for event in parsed_events:
        ical_event = {
            "summary": event['summary'],
            "description": event['description'],
            "organizer_email": event['organizer_email'],
            "attendees_emails": event['attendees_emails'],
            "location": event['location'],
            "time_zone": event['time_zone'],
            "start_time": event['start_time'],
            "end_time": event['end_time'],
            "meeting_date": event['meeting_date']
        }
        ical_events.append(ical_event)
        
    print(f"Formatted events for ApyHub API:\n {ical_events}")
    print("Sending request to ApyHub API...")
    print(f"Headers:\n {headers}", )
    
    response = requests.post(APYHUB_ICAL_URL, headers=headers, json=ical_events[0])
    
    if response.status_code == 200:
        with open(ICAL_FILE, 'w') as f:
            f.write(response.text)
        with open(JSON_FILE, 'w') as f:
            json.dump(parsed_events, f)
        return jsonify({
            "status": "success",
            "message": "Calendar synced successfully",
            "events_count": len(parsed_events),
            "ical_link": "/ical/feed"
        })
    else:
        print(f"API Error {response.status_code}: {response.text}")
        return jsonify({"error": "Failed to update iCal calendar"}), 500

    
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
