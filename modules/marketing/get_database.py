import json
import os
import sqlite3
from datetime import datetime
import threading
from typing import List, Dict, Optional, Union

# For thread safety when accessing the database
db_lock = threading.Lock()

# Database constants
DB_TYPE = "json"  # or "sqlite"
JSON_DB_PATH = "events_data.json"
SQLITE_DB_PATH = "events.db"

def initialize_database() -> None:
    """
    Initialize the database if it doesn't exist
    """
    if DB_TYPE == "sqlite":
        _init_sqlite_db()
    else:
        _init_json_db()

def _init_json_db() -> None:
    """Initialize the JSON database if it doesn't exist"""
    if not os.path.exists(JSON_DB_PATH):
        # Create an empty events database
        initial_data = {
            "events": {},
            "completed_events": {},
            "last_updated": datetime.now().isoformat()
        }
        with open(JSON_DB_PATH, 'w') as f:
            json.dump(initial_data, f, indent=2)

def _init_sqlite_db() -> None:
    """Initialize the SQLite database if it doesn't exist"""
    conn = sqlite3.connect(SQLITE_DB_PATH)
    cursor = conn.cursor()
    
    # Create events table if it doesn't exist
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS events (
        event_id TEXT PRIMARY KEY,
        name TEXT,
        date TEXT,
        location TEXT,
        info TEXT,
        content TEXT,
        html TEXT,
        css TEXT,
        status TEXT,
        created_at TEXT
    )
    ''')
    
    # Create completed_events table if it doesn't exist
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS completed_events (
        event_id TEXT PRIMARY KEY,
        name TEXT,
        completed_at TEXT
    )
    ''')
    
    conn.commit()
    conn.close()

def get_all_events() -> List[Dict]:
    """
    Retrieve all events from the database
    
    Returns:
        List of event dictionaries
    """
    with db_lock:
        if DB_TYPE == "sqlite":
            return _get_all_events_sqlite()
        else:
            return _get_all_events_json()

def _get_all_events_json() -> List[Dict]:
    """Retrieve all events from JSON storage"""
    try:
        with open(JSON_DB_PATH, 'r') as f:
            data = json.load(f)
            # Convert dictionary to list of events
            return list(data.get("events", {}).values())
    except (FileNotFoundError, json.JSONDecodeError):
        _init_json_db()
        return []

def _get_all_events_sqlite() -> List[Dict]:
    """Retrieve all events from SQLite storage"""
    try:
        conn = sqlite3.connect(SQLITE_DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM events')
        rows = cursor.fetchall()
        
        events = []
        for row in rows:
            event = dict(row)
            # Parse JSON content fields
            if event.get('content'):
                event['content'] = json.loads(event['content'])
            # Create grapes_code structure
            event['grapes_code'] = {
                'html': event.pop('html', ''),
                'css': event.pop('css', '')
            }
            events.append(event)
            
        conn.close()
        return events
    except sqlite3.Error:
        _init_sqlite_db()
        return []

def get_event_by_id(event_id: str) -> Optional[Dict]:
    """
    Retrieve a specific event by ID
    
    Args:
        event_id: The unique identifier for the event
        
    Returns:
        Event dictionary or None if not found
    """
    with db_lock:
        if DB_TYPE == "sqlite":
            return _get_event_by_id_sqlite(event_id)
        else:
            return _get_event_by_id_json(event_id)

def _get_event_by_id_json(event_id: str) -> Optional[Dict]:
    """Retrieve event by ID from JSON storage"""
    try:
        with open(JSON_DB_PATH, 'r') as f:
            data = json.load(f)
            return data.get("events", {}).get(event_id)
    except (FileNotFoundError, json.JSONDecodeError):
        return None

def _get_event_by_id_sqlite(event_id: str) -> Optional[Dict]:
    """Retrieve event by ID from SQLite storage"""
    try:
        conn = sqlite3.connect(SQLITE_DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM events WHERE event_id = ?', (event_id,))
        row = cursor.fetchone()
        
        if row:
            event = dict(row)
            # Parse JSON content field
            if event.get('content'):
                event['content'] = json.loads(event['content'])
            # Create grapes_code structure
            event['grapes_code'] = {
                'html': event.pop('html', ''),
                'css': event.pop('css', '')
            }
            conn.close()
            return event
        else:
            conn.close()
            return None
    except sqlite3.Error:
        return None

def save_event(event: Dict) -> bool:
    """
    Save or update an event in the database
    
    Args:
        event: Event dictionary with all required fields
        
    Returns:
        Success status
    """
    with db_lock:
        if DB_TYPE == "sqlite":
            return _save_event_sqlite(event)
        else:
            return _save_event_json(event)

def _save_event_json(event: Dict) -> bool:
    """Save event to JSON storage"""
    try:
        with open(JSON_DB_PATH, 'r') as f:
            data = json.load(f)
        
        # Add or update event
        data["events"][event["id"]] = event
        data["last_updated"] = datetime.now().isoformat()
        
        with open(JSON_DB_PATH, 'w') as f:
            json.dump(data, f, indent=2)
        
        return True
    except (FileNotFoundError, json.JSONDecodeError):
        _init_json_db()
        return _save_event_json(event)  # Try again after initialization
    except Exception:
        return False

def _save_event_sqlite(event: Dict) -> bool:
    """Save event to SQLite storage"""
    try:
        conn = sqlite3.connect(SQLITE_DB_PATH)
        cursor = conn.cursor()
        
        # Extract grapes_code for storing HTML and CSS separately
        grapes_code = event.get('grapes_code', {})
        html = grapes_code.get('html', '')
        css = grapes_code.get('css', '')
        
        # Convert content to JSON string
        content_json = json.dumps(event.get('content', {}))
        
        cursor.execute('''
        INSERT OR REPLACE INTO events 
        (event_id, name, date, location, info, content, html, css, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            event["id"],
            event["name"],
            event["date"],
            event["location"],
            event["info"],
            content_json,
            html,
            css,
            event.get("status", "pending"),
            event.get("created_at", datetime.now().isoformat())
        ))
        
        conn.commit()
        conn.close()
        return True
    except sqlite3.Error:
        return False

def mark_event_completed(event_id: str, name: str = None) -> bool:
    """
    Mark an event as completed
    
    Args:
        event_id: The unique identifier for the event
        name: Optional name if not already stored
        
    Returns:
        Success status
    """
    with db_lock:
        if DB_TYPE == "sqlite":
            return _mark_event_completed_sqlite(event_id, name)
        else:
            return _mark_event_completed_json(event_id, name)

def _mark_event_completed_json(event_id: str, name: str = None) -> bool:
    """Mark event as completed in JSON storage"""
    try:
        with open(JSON_DB_PATH, 'r') as f:
            data = json.load(f)
        
        # Get event name if not provided
        if name is None and event_id in data.get("events", {}):
            name = data["events"][event_id].get("name", "Unknown Event")
        
        # Update event status if it exists
        if event_id in data.get("events", {}):
            data["events"][event_id]["status"] = "completed"
        
        # Add to completed events
        data.setdefault("completed_events", {})[event_id] = {
            "id": event_id,
            "name": name or "Unknown Event",
            "completed_at": datetime.now().isoformat()
        }
        
        data["last_updated"] = datetime.now().isoformat()
        
        with open(JSON_DB_PATH, 'w') as f:
            json.dump(data, f, indent=2)
        
        return True
    except (FileNotFoundError, json.JSONDecodeError):
        _init_json_db()
        return False
    except Exception:
        return False

def _mark_event_completed_sqlite(event_id: str, name: str = None) -> bool:
    """Mark event as completed in SQLite storage"""
    try:
        conn = sqlite3.connect(SQLITE_DB_PATH)
        cursor = conn.cursor()
        
        # Get event name if not provided
        if name is None:
            cursor.execute('SELECT name FROM events WHERE event_id = ?', (event_id,))
            row = cursor.fetchone()
            if row:
                name = row[0]
            else:
                name = "Unknown Event"
        
        # Update event status
        cursor.execute('UPDATE events SET status = ? WHERE event_id = ?', 
                      ('completed', event_id))
        
        # Add to completed_events
        cursor.execute('''
        INSERT OR REPLACE INTO completed_events 
        (event_id, name, completed_at)
        VALUES (?, ?, ?)
        ''', (event_id, name, datetime.now().isoformat()))
        
        conn.commit()
        conn.close()
        return True
    except sqlite3.Error:
        return False

def get_all_completed_events() -> Dict[str, Dict]:
    """
    Retrieve all completed events
    
    Returns:
        Dictionary of completed event IDs to event data
    """
    with db_lock:
        if DB_TYPE == "sqlite":
            return _get_all_completed_events_sqlite()
        else:
            return _get_all_completed_events_json()

def _get_all_completed_events_json() -> Dict[str, Dict]:
    """Retrieve completed events from JSON storage"""
    try:
        with open(JSON_DB_PATH, 'r') as f:
            data = json.load(f)
            return data.get("completed_events", {})
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def _get_all_completed_events_sqlite() -> Dict[str, Dict]:
    """Retrieve completed events from SQLite storage"""
    try:
        conn = sqlite3.connect(SQLITE_DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM completed_events')
        rows = cursor.fetchall()
        
        completed = {}
        for row in rows:
            event_dict = dict(row)
            completed[event_dict["event_id"]] = event_dict
            
        conn.close()
        return completed
    except sqlite3.Error:
        return {}

def is_event_completed(event_id: str) -> bool:
    """
    Check if an event is already completed
    
    Args:
        event_id: The unique identifier for the event
        
    Returns:
        True if completed, False otherwise
    """
    completed_events = get_all_completed_events()
    return event_id in completed_events

def get_all_event_ids() -> List[str]:
    """
    Get all event IDs currently in the database
    
    Returns:
        List of event IDs
    """
    with db_lock:
        if DB_TYPE == "sqlite":
            return _get_all_event_ids_sqlite()
        else:
            return _get_all_event_ids_json()

def _get_all_event_ids_json() -> List[str]:
    """Get all event IDs from JSON storage"""
    try:
        with open(JSON_DB_PATH, 'r') as f:
            data = json.load(f)
            return list(data.get("events", {}).keys())
    except (FileNotFoundError, json.JSONDecodeError):
        return []

def _get_all_event_ids_sqlite() -> List[str]:
    """Get all event IDs from SQLite storage"""
    try:
        conn = sqlite3.connect(SQLITE_DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute('SELECT event_id FROM events')
        rows = cursor.fetchall()
        
        conn.close()
        return [row[0] for row in rows]
    except sqlite3.Error:
        return []

# Initialize the database on module import
initialize_database()