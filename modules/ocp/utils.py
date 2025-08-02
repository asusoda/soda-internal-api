import logging
from typing import Dict, Optional, List, Any
from datetime import datetime
import re

# Setup logger
logger = logging.getLogger(__name__)

# Point values for different roles
POINT_VALUES = {
    "Event Lead": 1,
    "Event Staff": 1,
    "Logistics Staff": 1,
    "Logistics Lead": 1,
    "Special Contribution": 2,
    "Unique Contribution": 3,
    "Default": 1  # Default points if role not specified
}

# Point values based on event type
EVENT_TYPE_POINTS = {
    "GBM": 1,           # General Body Meeting (default)
    "Special Event": 2,  # Special events
    "Default": 1         # Default if event type is not specified
}

def extract_property(properties: Dict, name: str, type_key: str) -> Any:
    """Extract a property value from Notion properties dictionary."""
    if not properties or name not in properties:
        return None
    
    prop = properties.get(name, {})
    
    if type_key == "title" and prop.get("title"):
        title_parts = [text_obj.get("plain_text", "") for text_obj in prop.get("title", [])]
        return " ".join(title_parts).strip()
    
    elif type_key == "rich_text" and prop.get("rich_text"):
        text_parts = [text_obj.get("plain_text", "") for text_obj in prop.get("rich_text", [])]
        return " ".join(text_parts).strip()
    
    elif type_key == "select" and prop.get("select"):
        return prop.get("select", {}).get("name")
    
    elif type_key == "multi_select" and prop.get("multi_select"):
        return [item.get("name") for item in prop.get("multi_select", [])]
    
    elif type_key == "date" and prop.get("date"):
        return prop.get("date")
    
    elif type_key == "people" and prop.get("people"):
        return [person for person in prop.get("people", [])]
    
    elif type_key == "checkbox":
        return prop.get("checkbox", False)
    
    elif type_key == "number":
        return prop.get("number")
    
    return None

def get_event_officers(properties: Dict) -> Dict[str, List[Dict]]:
    """
    Extract officers assigned to different roles from event properties.
    
    Returns a dictionary with roles as keys and lists of officers as values.
    Each officer is a dictionary with name, email, etc. from the Notion Person object.
    """
    roles = {}
    
    # Extract Event Lead
    event_lead = extract_property(properties, "Event Lead", "people")
    if event_lead:
        roles["Event Lead"] = event_lead
        
    # Extract Event Staff
    event_staff = extract_property(properties, "Event Staff", "people")
    if event_staff:
        roles["Event Staff"] = event_staff
        
    # Extract Logistics Staff
    logistics_staff = extract_property(properties, "Logistics Staff", "people")
    if logistics_staff:
        roles["Logistics Staff"] = logistics_staff
    
    # Extract Logistics Lead
    logistics_lead = extract_property(properties, "Logistics Lead", "people")
    if logistics_lead:
        roles["Logistics Lead"] = logistics_lead
    
    return roles

def calculate_points_for_role(role: str) -> int:
    """Calculate points based on the officer's role in the event."""
    return POINT_VALUES.get(role, POINT_VALUES["Default"])

def calculate_points_for_event_type(event_type: str) -> int:
    """Calculate points based on the event type."""
    return EVENT_TYPE_POINTS.get(event_type, EVENT_TYPE_POINTS["Default"])

def normalize_name(name: str) -> str:
    """Normalize a name to create a consistent identifier."""
    if not name:
        return "unknown"
    # Remove special characters, convert to lowercase
    return re.sub(r'[^a-z0-9]', '', name.lower())

def parse_notion_event_for_officers(notion_event: Dict, debug=False) -> List[Dict]:
    """
    Parse a Notion event and extract all officers and their roles.
    
    Args:
        notion_event: Raw Notion event data
        debug: Whether to print debug information
    
    Returns:
        List of dictionaries, each containing:
        {
            "name": str,
            "email": str or None,
            "role": str,
            "points": int,
            "event": str,
            "event_type": str,
            "notion_page_id": str,
            "event_date": datetime,
            "department": str,
            "title": str
        }
    """
    result = []
    # No longer tracking officers without email
    
    properties = notion_event.get("properties", {})
    notion_page_id = notion_event.get("id")
    
    if debug:
        print("\n========= NOTION EVENT PARSING DEBUG =========")
        print(f"Notion Page ID: {notion_page_id}")
        print(f"Available properties: {', '.join(properties.keys())}")
    
    # Extract event name
    event_name = extract_property(properties, "Name", "title")
    if not event_name:
        logger.warning(f"Event without a name found, id: {notion_page_id}")
        event_name = "Unnamed Event"
    
    if debug:
        print(f"Event Name: {event_name}")
    
    # Extract event type (to determine points)
    event_type = extract_property(properties, "Event Type", "select") or "Default"
    
    if debug:
        print(f"Event Type: {event_type}")
    
    # Extract event date
    date_prop = extract_property(properties, "Date", "date")
    event_date = None
    if date_prop and date_prop.get("start"):
        try:
            event_date = datetime.fromisoformat(date_prop["start"].replace("Z", "+00:00"))
            if debug:
                print(f"Event Date: {event_date}")
        except (ValueError, TypeError):
            logger.warning(f"Could not parse date for event {event_name}, id: {notion_page_id}")
            if debug:
                print(f"Failed to parse date: {date_prop}")
    elif debug:
        print("No event date found")
    
    # Get all officers by role
    officers_by_role = get_event_officers(properties)
    
    if debug:
        print("\nOfficers by Role:")
        for role, officers in officers_by_role.items():
            print(f"  Role: {role}, Officers: {len(officers)}")
            for i, officer in enumerate(officers):
                print(f"    Officer #{i+1} ID: {officer.get('id', 'No ID')}")
                print(f"    Officer #{i+1} Name: {officer.get('name', 'Unknown')}")
                print(f"    Officer #{i+1} Object Type: {type(officer).__name__}")
                
                # If the officer object contains a 'person' subobject, examine that too
                if 'person' in officer:
                    person = officer.get('person', {})
                    print(f"      Person Object Keys: {list(person.keys())}")
    
    # Process each role and its officers
    for role, officers in officers_by_role.items():
        # Calculate base points for the role
        role_points = calculate_points_for_role(role)
        
        # Add bonus points for special event types
        event_type_points = calculate_points_for_event_type(event_type)
        
        # Calculate final points - for now we'll use the higher of the two
        points = max(role_points, event_type_points)
        
        if debug:
            print(f"\nProcessing role: {role}")
            print(f"  Base points for role: {role_points}")
            print(f"  Points for event type '{event_type}': {event_type_points}")
            print(f"  Final points: {points}")
        
        for officer in officers:
            if debug:
                print("\n  Officer Raw Data:")
                # Pretty print all keys and non-nested values
                for key, value in officer.items():
                    if isinstance(value, dict):
                        print(f"    {key}: {type(value).__name__} with keys {list(value.keys())}")
                    elif isinstance(value, list):
                        print(f"    {key}: {type(value).__name__} with {len(value)} items")
                    else:
                        print(f"    {key}: {value}")
                        
                # If there's a person object, show its contents in detail
                if "person" in officer:
                    person_data = officer.get("person", {})
                    print(f"    person object details:")
                    for person_key, person_value in person_data.items():
                        print(f"      {person_key}: {person_value}")
            
            # Person objects from Notion have name and id, might have email or person objects
            officer_name = officer.get("name", "Unknown")
            
            # Skip if officer name is empty or unknown
            if not officer_name or officer_name.lower() == "unknown":
                if debug:
                    print(f"  Skipping officer with missing/unknown name: {officer_name}")
                logger.warning(f"Skipping officer with missing name in event {event_name}")
                continue
                
            # Make sure we're using a real name, not just "Unknown"
            if officer_name.lower() in ["unknown", "unnamed", "no name", "none", ""]:
                if debug:
                    print(f"  Skipping officer with placeholder name: {officer_name}")
                logger.warning(f"Skipping officer with placeholder name in event {event_name}")
                continue
                
            # Clean up officer name (remove extra spaces, normalize case)
            officer_name = " ".join(officer_name.strip().split())
            
            if debug:
                print(f"  Officer Name (cleaned): {officer_name}")
            
            # Try to get email in different ways
            officer_email = None
            if "email" in officer:
                officer_email = officer["email"]
                if debug:
                    print(f"  Email (from officer object): {officer_email}")
            elif "person" in officer and "email" in officer["person"]:
                officer_email = officer["person"]["email"]
                if debug:
                    print(f"  Email (from person object): {officer_email}")
            elif debug:
                print("  No email found for officer")
                
            # Try to extract department and title if available
            department = "Unknown"
            title = "Unknown"
            
            # Try to extract from officer object
            if "person" in officer:
                person_data = officer["person"]
                if "department" in person_data:
                    department = person_data["department"]
                    if debug:
                        print(f"  Department: {department}")
                if "title" in person_data:
                    title = person_data["title"]
                    if debug:
                        print(f"  Title: {title}")
            
            # Remove tracking of officers without email
            
            contribution = {
                "name": officer_name,
                "email": officer_email,
                "role": role,
                "points": points,
                "event": event_name,
                "event_type": event_type,
                "notion_page_id": notion_page_id,
                "event_date": event_date,
                "department": department,
                "title": title
            }
            
            if debug:
                print("  Final contribution data:")
                for key, value in contribution.items():
                    print(f"    {key}: {value}")
            
            result.append(contribution)
    
    # Remove logging about missing emails
    
    if debug:
        print(f"\nTotal contributions extracted: {len(result)}")
        print("========= END NOTION EVENT PARSING DEBUG =========\n")
    
    return result 