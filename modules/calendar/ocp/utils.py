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

def parse_notion_event_for_officers(notion_event: Dict) -> List[Dict]:
    """
    Parse a Notion event and extract all officers and their roles.
    
    Returns a list of dictionaries, each containing:
    {
        "name": str,
        "email": str or None,  # Now can be None if not available
        "role": str,
        "points": int,
        "event": str,
        "event_type": str,
        "notion_page_id": str,
        "event_date": datetime
    }
    """
    result = []
    officers_without_email = []
    
    properties = notion_event.get("properties", {})
    notion_page_id = notion_event.get("id")
    
    # Extract event name
    event_name = extract_property(properties, "Name", "title")
    if not event_name:
        logger.warning(f"Event without a name found, id: {notion_page_id}")
        event_name = "Unnamed Event"
    
    # Extract event type (to determine points)
    event_type = extract_property(properties, "Event Type", "select") or "Default"
    
    # Extract event date
    date_prop = extract_property(properties, "Date", "date")
    event_date = None
    if date_prop and date_prop.get("start"):
        try:
            event_date = datetime.fromisoformat(date_prop["start"].replace("Z", "+00:00"))
        except (ValueError, TypeError):
            logger.warning(f"Could not parse date for event {event_name}, id: {notion_page_id}")
    
    # Get all officers by role
    officers_by_role = get_event_officers(properties)
    
    # Process each role and its officers
    for role, officers in officers_by_role.items():
        # Calculate base points for the role
        role_points = calculate_points_for_role(role)
        
        # Add bonus points for special event types
        event_type_points = calculate_points_for_event_type(event_type)
        
        # Calculate final points - for now we'll use the higher of the two
        # This could be adjusted to add them together or use other logic
        points = max(role_points, event_type_points)
        
        for officer in officers:
            # Person objects from Notion have name and id, might have email or person objects
            officer_name = officer.get("name", "Unknown")
            
            # Try to get email in different ways
            officer_email = None
            if "email" in officer:
                officer_email = officer["email"]
            elif "person" in officer and "email" in officer["person"]:
                officer_email = officer["person"]["email"]
            
            # Track officers without email instead of logging each one
            if not officer_email:
                officers_without_email.append(officer_name)
            
            result.append({
                "name": officer_name,
                "email": officer_email,
                "role": role,
                "points": points,
                "event": event_name,
                "event_type": event_type,
                "notion_page_id": notion_page_id,
                "event_date": event_date
            })
    
    # Log a summary of officers without emails
    if officers_without_email:
        logger.info(f"Event '{event_name}': {len(officers_without_email)} officers have no email addresses")
    
    return result 