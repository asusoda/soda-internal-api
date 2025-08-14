import logging
from typing import List, Dict, Optional, Any
from datetime import datetime
from sentry_sdk import capture_exception, set_context, start_transaction

from .models import Officer, OfficerPoints
import shared
from shared import logger
from .utils import parse_notion_event_for_officers, calculate_points_for_role, calculate_points_for_event_type, normalize_name
from modules.calendar.clients import NotionCalendarClient
from modules.calendar.utils import operation_span
from modules.utils.db import DBConnect


class OCPService:
    """Service for Officer Contribution Points (OCP) management."""
    
    def __init__(self, db_connect=None, notion_client=None):
        """Initialize the OCP service with database connection and Notion client."""
        # If db_connect is None and the shared db_connect is None, create a new one
        if db_connect is None and shared.db_connect is None:
            logger.warning("Shared database manager is None. Creating a new instance.")
            try:
                self.db = DBConnect("sqlite:///./data/user.db")
                logger.info("Created new database manager instance for service")
            except Exception as e:
                logger.error(f"Failed to create database manager: {str(e)}")
                self.db = None
        else:
            self.db = db_connect or shared.db_connect
            
        self.notion_client = notion_client or NotionCalendarClient()
        
        # Check if database is properly initialized
        if self.db is None:
            logger.error("OCP service initialized with no database manager")
        else:
            logger.info("OCP service initialized with database manager")
    
    def sync_notion_to_ocp(self, database_id: str, organization_id: int, transaction=None) -> Dict[str, Any]:
        """
        Sync officers and contribution points from Notion events for a specific organization.
        Args:
            database_id: Notion database ID to fetch events from
            organization_id: Organization ID to scope the sync
            transaction: Optional Sentry transaction for performance monitoring
        Returns:
            Dict with status and result information
        """
        logger.info(f"[OCPService] sync_notion_to_ocp called for org_id={organization_id}, db_id={database_id}")
        current_transaction = transaction or start_transaction(op="sync", name="sync_notion_to_ocp")
        with operation_span(current_transaction, op="sync", description="sync_notion_to_ocp", logger=logger) as span:
            try:
                # Check if database is available
                if not database_id or not organization_id:
                    logger.error(f"[OCPService] Missing Notion database ID or organization ID (db_id={database_id}, org_id={organization_id})")
                    return {"status": "error", "message": "Missing Notion database ID or organization ID"}
                
                logger.info(f"[OCPService] Fetching Notion events for org_id={organization_id}")
                notion_events = self.notion_client.fetch_events(database_id)
                logger.info(f"[OCPService] Fetched {len(notion_events) if notion_events else 0} events from Notion for org_id={organization_id}")
                
                if not notion_events:
                    logger.warning(f"[OCPService] No events found in Notion database {database_id}")
                    return {"status": "warning", "message": "No events found in Notion database"}
                
                # Process each event and extract officers
                total_officers_processed = 0
                total_points_created = 0
                officers_created = 0
                
                for i, event in enumerate(notion_events):
                    logger.info(f"[OCPService] Processing event {i+1}/{len(notion_events)}: {event.get('id', 'unknown')}")
                    
                    # Parse officers from this event
                    officers_from_event = parse_notion_event_for_officers(event, debug=True)
                    logger.info(f"[OCPService] Extracted {len(officers_from_event)} officers from event {i+1}")
                    
                    for j, officer_data in enumerate(officers_from_event):
                        logger.info(f"[OCPService] Processing officer {j+1}/{len(officers_from_event)}: {officer_data.get('name', 'Unknown')}")
                        
                        try:
                            # Get or create officer in database
                            db_session = next(self.db.get_db())
                            
                            # Check if officer already exists
                            existing_officer = self.get_officer_by_name(db_session, officer_data['name'])
                            if existing_officer:
                                logger.info(f"[OCPService] Found existing officer: {existing_officer.name} (UUID: {existing_officer.uuid})")
                                officer = existing_officer
                            else:
                                logger.info(f"[OCPService] Creating new officer: {officer_data['name']}")
                                officer = Officer(
                                    organization_id=organization_id,
                                    email=officer_data.get('email'),
                                    name=officer_data['name'],
                                    title=officer_data.get('title', 'Unknown'),
                                    department=officer_data.get('department', 'Unknown')
                                )
                                officer = self.db.create_officer(db_session, officer, organization_id)
                                officers_created += 1
                                logger.info(f"[OCPService] Created officer: {officer.name} (UUID: {officer.uuid})")
                            
                            # Create points record
                            # Check if points record already exists for this officer, event, and role
                            existing_points = db_session.query(OfficerPoints).filter(
                                OfficerPoints.officer_uuid == officer.uuid,
                                OfficerPoints.notion_page_id == officer_data.get('notion_page_id'),
                                OfficerPoints.role == officer_data.get('role', 'Unknown'),
                                OfficerPoints.organization_id == organization_id
                            ).first()
                            
                            if existing_points:
                                logger.info(f"[OCPService] Points record already exists for officer {officer.name} in event {officer_data.get('event', 'Unknown Event')} with role {officer_data.get('role', 'Unknown')}. Skipping creation.")
                                total_officers_processed += 1
                                db_session.close()
                                continue
                            
                            points_record = OfficerPoints(
                                organization_id=organization_id,
                                points=officer_data.get('points', 1),
                                event=officer_data.get('event', 'Unknown Event'),
                                role=officer_data.get('role', 'Unknown'),
                                event_type=officer_data.get('event_type', 'Default'),
                                timestamp=officer_data.get('event_date', datetime.utcnow()),
                                officer_uuid=officer.uuid,
                                notion_page_id=officer_data.get('notion_page_id'),
                                event_metadata={"source": "notion_sync"}
                            )
                            
                            created_points = self.db.create_officer_points(db_session, points_record, organization_id)
                            total_points_created += 1
                            logger.info(f"[OCPService] Created points record: {created_points.id} for officer {officer.name}")
                            
                            total_officers_processed += 1
                            db_session.close()
                        
                        except Exception as e:
                            logger.error(f"[OCPService] Error processing officer {officer_data.get('name', 'Unknown')}: {str(e)}")
                            if 'db_session' in locals():
                                db_session.close()
                
                logger.info(f"[OCPService] Sync completed for org {organization_id}: {total_officers_processed} officers processed, {officers_created} new officers created, {total_points_created} points records created")
                return {
                    "status": "success", 
                    "message": f"Synced OCP data for org {organization_id}: {total_officers_processed} officers, {total_points_created} points",
                    "officers_processed": total_officers_processed,
                    "officers_created": officers_created,
                    "points_created": total_points_created
                }
            except Exception as e:
                logger.error(f"[OCPService] Error syncing OCP for org {organization_id}: {e}", exc_info=True)
                return {"status": "error", "message": str(e)}
    
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
    
    def add_officer_points(self, data: Dict, organization_id=None) -> Dict[str, Any]:
        """
        Add custom contribution points for one or more officers.
        Args:
            data: Dictionary containing:
                - names: List of officer names (required) OR
                - name: Single officer name (required)
                - email: Officer's email (optional)
                - points: Number of points (default 1)
                - event: Event name/description
                - role: Role (optional)
                - event_type: Type of event (optional)
                - timestamp: When it occurred (optional, defaults to now)
            organization_id: The organization to which the contribution belongs
        Returns:
            Dict with status and result information
        """
        try:
            db_session = next(self.db.get_db())
            officer_names = []
            if data.get("names") and isinstance(data["names"], list):
                officer_names = data["names"]
            elif data.get("name"):
                officer_names = [data["name"]]
            else:
                db_session.close()
                return {"status": "error", "message": "Officer name(s) required"}
                
            if not data.get("event"):
                db_session.close()
                return {"status": "error", "message": "Event name/description is required"}
            
            created_records = []
            created_officers = []
            
            for officer_name in officer_names:
                officer_name = officer_name.strip()
                if not officer_name:
                    continue
                
                # Get or create officer (org-aware)
                officer = self.db.get_officer_by_name(db_session, officer_name, organization_id)
                if not officer and data.get("email"):
                    officer = self.db.get_officer_by_email(db_session, data["email"], organization_id)
                
                if not officer:
                    officer = Officer(
                        organization_id=organization_id,
                        email=data.get("email") if len(officer_names) == 1 else None,
                        name=officer_name,
                        title=data.get("title", "Unknown"),
                        department=data.get("department", "Unknown")
                    )
                    officer = self.db.create_officer(db_session, officer, organization_id)
                    created_officers.append(officer_name)
                    logger.info(f"Created new officer: {officer_name}")
                
                points = data.get("points", 1)
                if not points and data.get("role"):
                    points = calculate_points_for_role(data["role"])
                if not points and data.get("event_type"):
                    points = calculate_points_for_event_type(data["event_type"])
                
                timestamp = data.get("timestamp")
                if timestamp:
                    if isinstance(timestamp, str):
                        try:
                            timestamp_str = timestamp.replace('Z', '')
                            if '.' in timestamp_str:
                                timestamp = datetime.strptime(timestamp_str, "%Y-%m-%dT%H:%M:%S.%f")
                            else:
                                timestamp = datetime.strptime(timestamp_str, "%Y-%m-%dT%H:%M:%S")
                        except ValueError as e:
                            logger.warning(f"Could not parse timestamp {timestamp}: {str(e)}, using current time")
                            timestamp = datetime.utcnow()
                else:
                    timestamp = datetime.utcnow()
                
                # Check for duplicate
                existing_points = db_session.query(OfficerPoints).filter(
                    OfficerPoints.officer_uuid == officer.uuid,
                    OfficerPoints.event == data["event"],
                    OfficerPoints.role == data.get("role", "Custom"),
                    OfficerPoints.organization_id == organization_id
                ).first()
                
                if existing_points:
                    logger.info(f"Points record already exists for officer {officer.name} in event {data['event']} with role {data.get('role', 'Custom')}. Skipping creation.")
                    continue
                
                points_record = OfficerPoints(
                    organization_id=organization_id,
                    points=points,
                    event=data["event"],
                    role=data.get("role", "Custom"),
                    event_type=data.get("event_type", "Default"),
                    timestamp=timestamp,
                    officer_uuid=officer.uuid,
                    notion_page_id=data.get("notion_page_id"),
                    event_metadata={"source": "manual_entry"}
                )
                
                record = self.db.create_officer_points(db_session, points_record, organization_id)
                if record:
                    created_records.append(record.id)
            
            db_session.close()
            
            officer_count = len(officer_names)
            points_per_officer = data.get("points", 1)
            total_points = officer_count * points_per_officer
            
            if officer_count == 1:
                message = f"Added {points_per_officer} points for {officer_names[0]}"
            else:
                message = f"Added {points_per_officer} points each for {officer_count} officers (total: {total_points} points)"
            
            if created_officers:
                message += f". Created new officers: {', '.join(created_officers)}"
            
            return {
                "status": "success",
                "message": message,
                "record_ids": created_records,
                "officers_processed": officer_count,
                "new_officers_created": len(created_officers)
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