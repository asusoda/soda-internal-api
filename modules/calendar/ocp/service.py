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
                        
                        # Find officer by email if available, otherwise by name
                        officer = None
                        if officer_email:
                            officer = self.get_officer_by_email(db_session, officer_email)
                        
                        if not officer:
                            # Try to find by name if no email or no officer found by email
                            officer = self.get_officer_by_name(db_session, officer_name)
                        
                        if not officer:
                            # Create new officer record
                            new_officer = Officer(
                                name=officer_name,
                                email=officer_email,  
                                title="Unknown",  
                                department="Unknown"  
                            )
                            try:
                                officer = self.db.create_officer(db_session, new_officer)
                                added_officers.add(officer.uuid)
                                logger.info(f"Created new officer: {officer_name}")
                            except Exception as e:
                                logger.error(f"Failed to create officer {officer_name}: {str(e)}")
                                continue
                        
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
        """Get an officer by name."""
        if not name:
            return None
        return db_session.query(Officer).filter(Officer.name == name).first()
    
    def get_officer_contributions(self, officer_id: str) -> List[Dict]:
        """Get all contributions for a specific officer by ID (can be email or UUID)."""
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
                
            points = db_session.query(OfficerPoints).filter(OfficerPoints.officer_uuid == officer.uuid).all()
            
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
    
    def get_all_officers(self) -> List[Dict]:
        """Get all officers with their total points for the leaderboard."""
        try:
            db_session = next(self.db.get_db())
            officers = db_session.query(Officer).all()
            
            result = []
            for officer in officers:
                # Calculate total points
                points = db_session.query(OfficerPoints).filter(OfficerPoints.officer_uuid == officer.uuid).all()
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
    
    def get_officer_leaderboard(self) -> List[Dict]:
        """Get a leaderboard of officers sorted by total points."""
        return self.get_all_officers()  