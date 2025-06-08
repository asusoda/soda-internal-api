import logging
from typing import List, Dict, Optional, Any
from datetime import datetime
from sentry_sdk import capture_exception, set_context, start_transaction

from .models import Officer, OfficerPoints
from shared import ocp_db_manager, logger
from .utils import parse_notion_event_for_officers, calculate_points_for_role, calculate_points_for_event_type, normalize_name
from ..clients import NotionCalendarClient
from ..utils import operation_span
from modules.utils.db import OCPDBManager

# Remove duplicate logger initialization
# logger = logging.getLogger(__name__)

class OCPService:
    """Service for Officer Contribution Points (OCP) management."""
    
    def __init__(self, db_connect=None, notion_client=None):
        """Initialize the OCP service with database connection and Notion client."""
        # If db_connect is None and the shared ocp_db_manager is None, create a new one
        if db_connect is None and ocp_db_manager is None:
            logger.warning("Shared OCP database manager is None. Creating a new instance.")
            try:
                self.db = OCPDBManager("sqlite:///./data/ocp.db")
                logger.info("Created new OCP database manager instance for service")
            except Exception as e:
                logger.error(f"Failed to create OCP database manager: {str(e)}")
                self.db = None
        else:
            self.db = db_connect or ocp_db_manager
            
        self.notion_client = notion_client or NotionCalendarClient()
        
        # Check if database is properly initialized
        if self.db is None:
            logger.error("OCP service initialized with no database manager")
        else:
            logger.info("OCP service initialized with database manager")
        
    def sync_notion_to_ocp(self, database_id: str, transaction=None) -> Dict[str, Any]:
        """
        Sync officers and contribution points from Notion events.
        
        Fetches events from the specified Notion database, extracts officer
        assignments, and updates the OCP database accordingly.
        
        Args:
            database_id: Notion database ID to fetch events from
            transaction: Optional Sentry transaction for performance monitoring
            
        Returns:
            Dict with status and result information
        """
        current_transaction = transaction or start_transaction(op="sync", name="sync_notion_to_ocp")
        
        with operation_span(current_transaction, op="sync", description="sync_notion_to_ocp", logger=logger) as span:
            try:
                # Check if database is available
                if self.db is None:
                    logger.error("Cannot sync to OCP: No database manager available")
                    return {"status": "error", "message": "No database manager available"}
                
                # Fetch events from Notion
                notion_events = self.notion_client.fetch_events(database_id, parent_transaction=current_transaction)
                if not notion_events:
                    logger.warning("No events found in Notion database")
                    return {"status": "warning", "message": "No events found in Notion database"}
                
                span.set_data("fetched_events_count", len(notion_events))
                logger.info(f"Fetched {len(notion_events)} events from Notion")
                
                # Debug: Print raw Notion event data
                for i, event in enumerate(notion_events[:6]):  # Show first 3 events as examples
                    print(f"\n========= RAW NOTION EVENT #{i+1} =========")
                    print(f"Event ID: {event.get('id')}")
                    print(f"Event URL: {event.get('url')}")
                    print("Properties:")
                    for prop_name, prop_value in event.get('properties', {}).items():
                        print(f"  {prop_name}: {type(prop_value).__name__}")
                        # Print a sample of the property if it's not too complex
                        if prop_name == "Name" and "title" in prop_value:
                            title_text = " ".join([t.get("plain_text", "") for t in prop_value.get("title", [])])
                            print(f"    Value: {title_text}")
                        elif "people" in prop_value:
                            people = prop_value.get("people", [])
                            if people:
                                print(f"    People count: {len(people)}")
                                for i, person in enumerate(people):  # Show ALL people
                                    print(f"      Person #{i+1}: {person.get('name', 'Unknown')}, Email: {person.get('email', 'Not provided')}")
                                    # Also show any other data in the person object that might be useful
                                    if "person" in person:
                                        person_obj = person.get("person", {})
                                        print(f"        Person Object Keys: {list(person_obj.keys())}")
                                        if "name" in person_obj:
                                            print(f"        Name from Person Object: {person_obj.get('name')}")
                                        if "email" in person_obj:
                                            print(f"        Email from Person Object: {person_obj.get('email')}")
                    print("=========================================\n")
                
                # Also show how officer contributions are extracted
                for i, event in enumerate(notion_events[:1]):  # Just for the first event
                    officer_contributions = parse_notion_event_for_officers(event, debug=True)
                    print(f"\n========= EXTRACTED OFFICER CONTRIBUTIONS FOR EVENT #{i+1} =========")
                    print(f"Total contributions found: {len(officer_contributions)}")
                    for j, contribution in enumerate(officer_contributions[:3]):  # Show first 3 contributions
                        print(f"  Contribution #{j+1}:")
                        print(f"    Officer Name: {contribution.get('name')}")
                        print(f"    Officer Email: {contribution.get('email')}")
                        print(f"    Role: {contribution.get('role')}")
                        print(f"    Points: {contribution.get('points')}")
                        print(f"    Event: {contribution.get('event')}")
                        print(f"    Event Type: {contribution.get('event_type')}")
                        print(f"    Department: {contribution.get('department')}")
                        print(f"    Title: {contribution.get('title')}")
                    print("=================================================================\n")
                
                # Process events, get officer contributions
                total_points_records = 0
                added_officers = set()
                updated_points = 0
                
                # Get DB session
                try:
                    db_session = next(self.db.get_db())
                except Exception as e:
                    logger.error(f"Failed to get database session: {str(e)}")
                    return {"status": "error", "message": f"Database session error: {str(e)}"}
                
                # Process each event
                for event in notion_events:
                    officer_contributions = parse_notion_event_for_officers(event)
                    
                    if not officer_contributions:
                        continue
                        
                    for contribution in officer_contributions:
                        # First ensure the officer exists
                        officer_name = contribution.get("name")
                        officer_email = contribution.get("email")
                        
                        if not officer_name or officer_name == "Unknown":
                            logger.warning(f"Skipping contribution with missing or Unknown officer name: {contribution}")
                            continue
                            
                        # Find officer primarily by name, then by email if available
                        officer = self.get_officer_by_name(db_session, officer_name)
                        
                        # If not found by name, try email
                        if not officer and officer_email:
                            officer = self.get_officer_by_email(db_session, officer_email)
                        
                        if not officer:
                            # Extract department and title from Notion if available
                            department = contribution.get("department", "Unknown")
                            title = contribution.get("title", "Unknown")
                            
                            # Create new officer record with better defaults
                            new_officer = Officer(
                                name=officer_name,
                                email=officer_email,
                                title=title,
                                department=department
                            )
                            try:
                                officer = self.db.create_officer(db_session, new_officer)
                                added_officers.add(officer.uuid)
                                logger.info(f"Created new officer: {officer_name}, Email: {officer_email if officer_email else 'Not provided'}")
                            except Exception as e:
                                logger.error(f"Failed to create officer {officer_name}: {str(e)}")
                                continue
                        elif officer_email and not officer.email:
                            # Update officer record with email if it's missing
                            officer.email = officer_email
                            db_session.commit()
                            logger.info(f"Updated officer {officer_name} with email {officer_email}")
                        
                        # Now add the points record
                        # Check if points for this event already exist for this officer
                        try:
                            existing_points = db_session.query(OfficerPoints).filter(
                                OfficerPoints.officer_uuid == officer.uuid,
                                OfficerPoints.notion_page_id == contribution.get("notion_page_id"),
                                OfficerPoints.role == contribution.get("role")
                            ).first()
                            
                            if existing_points:
                                # Update existing record
                                existing_points.points = contribution.get("points")
                                existing_points.event = contribution.get("event")
                                existing_points.event_type = contribution.get("event_type", "Default")
                                db_session.commit()
                                updated_points += 1
                            else:
                                # Create new points record
                                points_record = OfficerPoints(
                                    points=contribution.get("points"),
                                    event=contribution.get("event"),
                                    role=contribution.get("role"),
                                    event_type=contribution.get("event_type", "Default"),
                                    timestamp=contribution.get("event_date") or datetime.utcnow(),
                                    officer_uuid=officer.uuid,
                                    notion_page_id=contribution.get("notion_page_id"),
                                    event_metadata={"source": "notion_sync"}
                                )
                                self.db.create_officer_points(db_session, points_record)
                                total_points_records += 1
                        except Exception as e:
                            logger.error(f"Error processing points for {officer_name}: {str(e)}")
                            continue
                
                # Close the DB session
                db_session.close()
                
                # Update span with results
                span.set_data("results", {
                    "total_points_records_added": total_points_records,
                    "officers_added": len(added_officers),
                    "points_records_updated": updated_points
                })
                
                logger.info(f"Added {total_points_records} new points records, updated {updated_points} existing records")
                logger.info(f"Added {len(added_officers)} new officers")
                
                return {
                    "status": "success", 
                    "message": f"Sync completed. Added {total_points_records} new points records, updated {updated_points} existing records",
                    "added_officers_count": len(added_officers),
                    "added_points_count": total_points_records,
                    "updated_points_count": updated_points
                }
                
            except Exception as e:
                logger.error(f"Error syncing Notion to OCP: {str(e)}")
                capture_exception(e)
                return {"status": "error", "message": f"Error syncing Notion to OCP: {str(e)}"}
    
    def get_officer_by_email(self, db_session, email):
        """Get an officer by email."""
        if not email:
            return None
        return db_session.query(Officer).filter(Officer.email == email).first()
    
    def get_officer_by_name(self, db_session, name):
        """Get an officer by name using case-insensitive matching."""
        if not name:
            return None
        # Use case-insensitive matching instead of exact matching
        return db_session.query(Officer).filter(Officer.name.ilike(f"%{name}%")).first()
    
    def get_officer_contributions(self, officer_id: str, start_date=None, end_date=None) -> List[Dict]:
        """Get all contributions for a specific officer by ID (can be email or UUID), with optional date filtering."""
        try:
            db_session = next(self.db.get_db())
            officer = None
            
            # Try to find by UUID first
            officer = db_session.query(Officer).filter(Officer.uuid == officer_id).first()
            
            # If not found, try by email
            if not officer:
                officer = self.get_officer_by_email(db_session, officer_id)
                
            # If still not found, try by name
            if not officer:
                officer = self.get_officer_by_name(db_session, officer_id)
            
            if not officer:
                logger.warning(f"No officer found with identifier {officer_id}")
                db_session.close()
                return []
                
            # Build query with optional date filtering
            points_query = db_session.query(OfficerPoints).filter(OfficerPoints.officer_uuid == officer.uuid)
            
            # Apply date filtering if provided
            if start_date:
                points_query = points_query.filter(OfficerPoints.timestamp >= start_date)
            if end_date:
                points_query = points_query.filter(OfficerPoints.timestamp <= end_date)
            
            points = points_query.all()
            
            result = []
            for point in points:
                result.append({
                    "id": point.id,
                    "points": point.points,
                    "event": point.event,
                    "role": point.role,
                    "event_type": point.event_type,
                    "timestamp": point.timestamp.isoformat() if point.timestamp else None,
                    "notion_page_id": point.notion_page_id
                })
                
            db_session.close()
            return result
            
        except Exception as e:
            logger.error(f"Error getting officer contributions: {str(e)}")
            capture_exception(e)
            return []
    
    def get_all_officers(self, start_date=None, end_date=None) -> List[Dict]:
        """Get all officers with their total points for the leaderboard, with optional date filtering."""
        try:
            db_session = next(self.db.get_db())
            officers = db_session.query(Officer).all()
            
            result = []
            for officer in officers:
                # Calculate total points with optional date filtering
                points_query = db_session.query(OfficerPoints).filter(OfficerPoints.officer_uuid == officer.uuid)
                
                # Apply date filtering if provided
                if start_date:
                    points_query = points_query.filter(OfficerPoints.timestamp >= start_date)
                if end_date:
                    points_query = points_query.filter(OfficerPoints.timestamp <= end_date)
                
                points = points_query.all()
                total_points = sum(point.points for point in points)
                
                # Count contributions by type
                contribution_counts = {
                    "GBM": 0,
                    "Special Event": 0,
                    "Special Contribution": 0,
                    "Unique Contribution": 0,
                    "Other": 0
                }
                
                for point in points:
                    event_type = point.event_type or "Other"
                    if event_type in contribution_counts:
                        contribution_counts[event_type] += 1
                    else:
                        contribution_counts["Other"] += 1
                
                result.append({
                    "uuid": officer.uuid,
                    "email": officer.email,
                    "name": officer.name,
                    "title": officer.title,
                    "department": officer.department,
                    "total_points": total_points,
                    "contribution_counts": contribution_counts
                })
                
            # Sort by total points descending (for leaderboard)
            result.sort(key=lambda x: x["total_points"], reverse=True)
            
            db_session.close()
            return result
            
        except Exception as e:
            logger.error(f"Error getting all officers: {str(e)}")
            capture_exception(e)
            return []
    
    def add_officer_points(self, data: Dict) -> Dict[str, Any]:
        """
        Add custom contribution points for an officer.
        
        Args:
            data: Dictionary containing:
                - email: Officer's email (optional)
                - name: Officer's name (required)
                - points: Number of points (default 1)
                - event: Event name/description
                - role: Role (optional)
                - event_type: Type of event (optional)
                - timestamp: When it occurred (optional, defaults to now)
                
        Returns:
            Dict with status and result information
        """
        try:
            db_session = next(self.db.get_db())
            
            # Validate required fields
            if not data.get("name"):
                db_session.close()
                return {"status": "error", "message": "Officer name is required"}
                
            if not data.get("event"):
                db_session.close()
                return {"status": "error", "message": "Event name/description is required"}
            
            # Get or create officer
            officer = None
            if data.get("email"):
                officer = self.get_officer_by_email(db_session, data["email"])
            
            if not officer:
                officer = self.get_officer_by_name(db_session, data["name"])
            
            if not officer:
                # Set defaults for new officer
                officer = Officer(
                    email=data.get("email"),  
                    name=data["name"],
                    title=data.get("title", "Unknown"),
                    department=data.get("department", "Unknown")
                )
                officer = self.db.create_officer(db_session, officer)
                logger.info(f"Created new officer: {data['name']}")
            
            # Calculate points if role or event_type is provided
            points = data.get("points", 1)
            if not points and data.get("role"):
                points = calculate_points_for_role(data["role"])
            if not points and data.get("event_type"):
                points = calculate_points_for_event_type(data["event_type"])
            
            # Create points record
            points_record = OfficerPoints(
                points=points,
                event=data["event"],
                role=data.get("role", "Custom"),
                event_type=data.get("event_type", "Default"),
                timestamp=data.get("timestamp", datetime.utcnow()),
                officer_uuid=officer.uuid,
                notion_page_id=data.get("notion_page_id"),
                event_metadata={"source": "manual_entry"}
            )
            
            record = self.db.create_officer_points(db_session, points_record)
            db_session.close()
            
            return {
                "status": "success",
                "message": f"Added {points} points for {data['name']}",
                "record_id": record.id
            }
            
        except Exception as e:
            logger.error(f"Error adding officer points: {str(e)}")
            capture_exception(e)
            return {"status": "error", "message": f"Error adding officer points: {str(e)}"}
    
    def update_officer_points(self, point_id: int, data: Dict) -> Dict[str, Any]:
        """
        Update existing contribution points record.
        
        Args:
            point_id: ID of the points record to update
            data: Dictionary containing fields to update
                
        Returns:
            Dict with status and result information
        """
        try:
            db_session = next(self.db.get_db())
            
            # Find the record
            record = db_session.query(OfficerPoints).filter(OfficerPoints.id == point_id).first()
            if not record:
                db_session.close()
                return {"status": "error", "message": f"Points record with ID {point_id} not found"}
            
            # Update fields
            if "points" in data:
                record.points = data["points"]
            if "event" in data:
                record.event = data["event"]
            if "role" in data:
                record.role = data["role"]
            if "event_type" in data:
                record.event_type = data["event_type"]
            if "timestamp" in data:
                record.timestamp = data["timestamp"]
            if "event_metadata" in data:
                if record.event_metadata:
                    record.event_metadata.update(data["event_metadata"])
                else:
                    record.event_metadata = data["event_metadata"]
            
            db_session.commit()
            db_session.close()
            
            return {
                "status": "success",
                "message": f"Updated points record {point_id}"
            }
            
        except Exception as e:
            logger.error(f"Error updating officer points: {str(e)}")
            capture_exception(e)
            return {"status": "error", "message": f"Error updating officer points: {str(e)}"}
    
    def delete_officer_points(self, point_id: int) -> Dict[str, Any]:
        """
        Delete an officer contribution points record.
        
        Args:
            point_id: ID of the points record to delete
                
        Returns:
            Dict with status and result information
        """
        try:
            db_session = next(self.db.get_db())
            
            # Attempt to delete
            record = db_session.query(OfficerPoints).filter(OfficerPoints.id == point_id).first()
            if record:
                db_session.delete(record)
                db_session.commit()
                db_session.close()
                return {
                    "status": "success",
                    "message": f"Deleted points record {point_id}"
                }
            else:
                db_session.close()
                return {
                    "status": "error",
                    "message": f"Points record with ID {point_id} not found or could not be deleted"
                }
            
        except Exception as e:
            logger.error(f"Error deleting officer points: {str(e)}")
            capture_exception(e)
            return {"status": "error", "message": f"Error deleting officer points: {str(e)}"}
    
    def get_officer_leaderboard(self, start_date=None, end_date=None) -> List[Dict]:
        """Get a leaderboard of officers sorted by total points, with optional date filtering."""
        return self.get_all_officers(start_date=start_date, end_date=end_date)
    
    def get_officer_details(self, officer_id: str, start_date=None, end_date=None) -> Dict:
        """
        Get detailed information about a specific officer including their points and events.
        
        Args:
            officer_id: Can be UUID, email, or name of the officer
            start_date: Optional start date for filtering points
            end_date: Optional end date for filtering points
            
        Returns:
            Dict containing officer details and their points history
        """
        try:
            db_session = next(self.db.get_db())
            officer = None
            
            # Try to find by UUID first
            officer = db_session.query(Officer).filter(Officer.uuid == officer_id).first()
            
            # If not found, try by email
            if not officer:
                officer = self.get_officer_by_email(db_session, officer_id)
                
            # If still not found, try by name
            if not officer:
                officer = self.get_officer_by_name(db_session, officer_id)
            
            if not officer:
                logger.warning(f"No officer found with identifier {officer_id}")
                db_session.close()
                return None
                
            # Get all points records for this officer with optional date filtering
            points_query = db_session.query(OfficerPoints).filter(OfficerPoints.officer_uuid == officer.uuid)
            
            # Apply date filtering if provided
            if start_date:
                points_query = points_query.filter(OfficerPoints.timestamp >= start_date)
            if end_date:
                points_query = points_query.filter(OfficerPoints.timestamp <= end_date)
            
            points = points_query.all()
            
            # Calculate total points and organize by event type
            total_points = sum(point.points for point in points)
            points_by_type = {}
            for point in points:
                event_type = point.event_type or "Other"
                if event_type not in points_by_type:
                    points_by_type[event_type] = {
                        "total_points": 0,
                        "events": []
                    }
                points_by_type[event_type]["total_points"] += point.points
                points_by_type[event_type]["events"].append({
                    "id": point.id,
                    "points": point.points,
                    "event": point.event,
                    "role": point.role,
                    "timestamp": point.timestamp.isoformat() if point.timestamp else None,
                    "notion_page_id": point.notion_page_id
                })
            
            # Prepare the response
            result = {
                "uuid": officer.uuid,
                "email": officer.email,
                "name": officer.name,
                "title": officer.title,
                "department": officer.department,
                "total_points": total_points,
                "points_by_type": points_by_type,
                "all_events": [{
                    "id": point.id,
                    "points": point.points,
                    "event": point.event,
                    "role": point.role,
                    "event_type": point.event_type,
                    "timestamp": point.timestamp.isoformat() if point.timestamp else None,
                    "notion_page_id": point.notion_page_id
                } for point in points]
            }
            
            db_session.close()
            return result
            
        except Exception as e:
            logger.error(f"Error getting officer details: {str(e)}")
            capture_exception(e)
            return None
    
    def get_all_events(self) -> List[Dict]:
        """
        Get all contribution events from all officers.
        
        Returns:
            List of all events with officer details attached
        """
        try:
            db_session = next(self.db.get_db())
            
            # Query all events
            events = db_session.query(OfficerPoints).order_by(OfficerPoints.timestamp.desc()).all()
            
            result = []
            for event in events:
                # Get officer details for each event
                officer = db_session.query(Officer).filter(Officer.uuid == event.officer_uuid).first()
                
                # If officer not found by UUID, try to find by name from the event
                if not officer and event.event:
                    # Extract potential officer name from the event title or metadata
                    possible_officer_name = event.event.split(" - ")[0] if " - " in event.event else None
                    if possible_officer_name:
                        officer = self.get_officer_by_name(db_session, possible_officer_name)
                        
                        # If found, update the event's officer_uuid for future lookups
                        if officer:
                            event.officer_uuid = officer.uuid
                            db_session.commit()
                            logger.info(f"Updated event {event.id} with correct officer UUID {officer.uuid}")
                
                event_data = {
                    "id": event.id,
                    "points": event.points,
                    "event": event.event,
                    "role": event.role,
                    "event_type": event.event_type,
                    "timestamp": event.timestamp.isoformat() if event.timestamp else None,
                    "notion_page_id": event.notion_page_id,
                    "officer": {
                        "uuid": officer.uuid if officer else "unknown",
                        "name": officer.name if officer else "Unknown Officer",
                        "email": officer.email if officer else "unknown",
                        "title": officer.title if officer else "Unknown",
                        "department": officer.department if officer else "Unknown"
                    }
                }
                
                result.append(event_data)
                
            db_session.close()
            return result
            
        except Exception as e:
            logger.error(f"Error getting all events: {str(e)}")
            capture_exception(e)
            return []
    
    def repair_unknown_officers(self) -> Dict[str, Any]:
        """
        Repair events with missing or unknown officers.
        
        This function will:
        1. Find events with no officer UUID
        2. Find events with officers named "Unknown"
        3. Attempt to fix these issues by linking to the correct officers
        4. Ignore department information issues
        
        Returns:
            Dict with repair results
        """
        try:
            db_session = next(self.db.get_db())
            
            # Find events with orphaned officers or unknown names
            orphaned_events = []  # Events without a valid officer UUID
            unknown_events = []   # Events with "Unknown" officer names
            
            events = db_session.query(OfficerPoints).all()
            for event in events:
                officer = db_session.query(Officer).filter(Officer.uuid == event.officer_uuid).first()
                if not officer:
                    # If officer UUID doesn't exist at all
                    orphaned_events.append(event)
                elif officer.name == "Unknown":
                    # If officer exists but is marked as "Unknown"
                    unknown_events.append((event, officer))
            
            # Try to repair orphaned events
            repaired_orphans = 0
            for event in orphaned_events:
                # Look for clues in the event name
                event_parts = event.event.split(" - ")
                if len(event_parts) > 1:
                    possible_officer_name = event_parts[0].strip()
                    
                    # Try to find a matching officer
                    matched_officer = self.get_officer_by_name(db_session, possible_officer_name)
                    if matched_officer:
                        # Update the event with the correct officer
                        event.officer_uuid = matched_officer.uuid
                        repaired_orphans += 1
                        logger.info(f"Repaired orphaned event {event.id} by linking to officer {matched_officer.name}")
            
            # Try to repair unknown officers
            repaired_unknowns = 0
            for event, officer in unknown_events:
                # Check if there's another officer with a similar name but more info
                if "Unknown" in officer.name:
                    # Skip truly unknown officers
                    continue
                    
                # Changed to focus on finding officers with valid names only, ignoring department
                better_officer = db_session.query(Officer).filter(
                    Officer.name.ilike(f"%{officer.name}%"),
                    Officer.name != "Unknown"
                ).first()
                
                if better_officer and better_officer.uuid != officer.uuid:
                    # Update event to point to the better officer
                    event.officer_uuid = better_officer.uuid
                    repaired_unknowns += 1
                    logger.info(f"Repaired event {event.id} by linking to better officer {better_officer.name}")
                    
                    # Optionally, we could remove the "Unknown" officer, but that might cause issues
                    # Let's just log it for now
                    logger.info(f"Consider removing officer {officer.uuid} with name {officer.name}")
            
            # Commit all changes
            db_session.commit()
            db_session.close()
            
            return {
                "status": "success",
                "message": f"Repair completed. Fixed {repaired_orphans} orphaned events and {repaired_unknowns} events with unknown officers.",
                "repaired_orphans": repaired_orphans,
                "repaired_unknowns": repaired_unknowns,
                "remaining_orphans": len(orphaned_events) - repaired_orphans,
                "remaining_unknowns": len(unknown_events) - repaired_unknowns
            }
        
        except Exception as e:
            logger.error(f"Error repairing unknown officers: {str(e)}")
            capture_exception(e)
            return {
                "status": "error",
                "message": f"Error during repair: {str(e)}"
            }
    
    def diagnose_unknown_officers(self) -> Dict[str, Any]:
        """
        Diagnose the "Unknown" officer issue by identifying all events with missing or unknown officers.
        
        This function will focus on:
        1. Finding events with no officer UUID (missing UUID)
        2. Finding events with officers named "Unknown"
        3. Ignoring issues about missing emails or department information
        
        Returns:
            Dict with diagnostic information
        """
        try:
            db_session = next(self.db.get_db())
            
            # Track issues by category
            missing_uuid_events = []
            unknown_name_officers = []
            # We won't track unknown_dept_officers anymore as requested
            
            # Get all events
            events = db_session.query(OfficerPoints).all()
            
            print("\n=========== DIAGNOSING UNKNOWN OFFICER ISSUES ===========")
            print(f"Total events in database: {len(events)}")
            
            # Check each event's officer
            for event in events:
                officer = db_session.query(Officer).filter(Officer.uuid == event.officer_uuid).first()
                if not officer:
                    missing_uuid_events.append({
                        "event_id": event.id,
                        "event_name": event.event,
                        "missing_uuid": event.officer_uuid,
                        "timestamp": event.timestamp.isoformat() if event.timestamp else None
                    })
                elif officer.name == "Unknown":
                    unknown_name_officers.append({
                        "event_id": event.id,
                        "event_name": event.event,
                        "officer_id": officer.uuid,
                        "officer_name": officer.name,
                        # Still include officer_email in data output but we don't consider it an issue
                        "officer_email": officer.email
                    })
                # Removed the check for unknown department
            
            # Print summary
            print(f"\nIssues found:")
            print(f"- Events with missing officer UUID: {len(missing_uuid_events)}")
            print(f"- Events with 'Unknown' officer name: {len(unknown_name_officers)}")
            # Removed line about unknown department issues
            
            # Print details for each category
            if missing_uuid_events:
                print("\n1. Events with missing officer UUID:")
                for i, event in enumerate(missing_uuid_events[:10]):  # Show first 10
                    print(f"  {i+1}. Event ID: {event['event_id']}")
                    print(f"     Event Name: {event['event_name']}")
                    print(f"     Missing UUID: {event['missing_uuid']}")
                    print(f"     Timestamp: {event['timestamp']}")
                if len(missing_uuid_events) > 10:
                    print(f"  ... and {len(missing_uuid_events) - 10} more")
            
            if unknown_name_officers:
                print("\n2. Events with 'Unknown' officer name:")
                for i, event in enumerate(unknown_name_officers[:10]):
                    print(f"  {i+1}. Event ID: {event['event_id']}")
                    print(f"     Event Name: {event['event_name']}")
                    print(f"     Officer ID: {event['officer_id']}")
                    print(f"     Officer Email: {event['officer_email']}")
                if len(unknown_name_officers) > 10:
                    print(f"  ... and {len(unknown_name_officers) - 10} more")
            
            # Removed section for unknown department officers
            
            # Check for name patterns in events with missing officer UUID
            name_patterns = {}
            for event in missing_uuid_events:
                event_name = event['event_name']
                if " - " in event_name:
                    possible_name = event_name.split(" - ")[0].strip()
                    if possible_name not in name_patterns:
                        name_patterns[possible_name] = 0
                    name_patterns[possible_name] += 1
            
            # Print potential name patterns that could be officers
            if name_patterns:
                print("\nPotential officer names found in event titles:")
                for name, count in sorted(name_patterns.items(), key=lambda x: x[1], reverse=True)[:10]:
                    print(f"  '{name}' appears in {count} events")
                
                # Check if these names match existing officers
                for name in list(name_patterns.keys())[:10]:
                    officer = self.get_officer_by_name(db_session, name)
                    if officer:
                        print(f"  '{name}' matches existing officer: {officer.name} (UUID: {officer.uuid})")
            
            print("\n==========================================================")
            
            db_session.close()
            
            # Calculate total issues - now excluding unknown departments
            total_issues = len(missing_uuid_events) + len(unknown_name_officers)
            
            return {
                "status": "success",
                "missing_uuid_count": len(missing_uuid_events),
                "unknown_name_count": len(unknown_name_officers),
                "unknown_dept_count": 0,  # We're ignoring department issues, so always 0
                "total_issues": total_issues
            }
            
        except Exception as e:
            logger.error(f"Error diagnosing unknown officers: {str(e)}")
            capture_exception(e)
            return {
                "status": "error",
                "message": f"Error during diagnosis: {str(e)}"
            }  