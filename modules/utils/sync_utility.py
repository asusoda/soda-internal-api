import logging
from typing import Dict, Any, Optional
from datetime import datetime
from sentry_sdk import capture_exception, set_context, start_transaction

from shared import config, logger
from modules.calendar.service import CalendarService
from modules.ocp.notion_sync_service import NotionOCPSyncService
from modules.calendar.utils import operation_span
from .sync_common import SyncCommonUtils

class UnifiedSyncService:
    """
    Unified service for syncing Notion data to both Google Calendar and OCP database.
    Coordinates both sync operations to ensure data consistency.
    """
    
    def __init__(self, logger_instance=None):
        """Initialize the unified sync service with logger and sub-services."""
        self.logger = logger_instance or logger
        self.calendar_service = CalendarService(self.logger)
        self.ocp_sync_service = NotionOCPSyncService(self.logger)
        self.common_utils = SyncCommonUtils(self.logger)
        
        self.logger.info("UnifiedSyncService initialized")
        
    def sync_notion_to_all(self, transaction=None) -> Dict[str, Any]:
        """
        Orchestrates the complete sync process from Notion to both Google Calendar and OCP database.
        
        This method:
        1. Fetches events from Notion
        2. Syncs to Google Calendar
        3. Syncs to OCP database
        4. Provides comprehensive results from both operations
        
        Args:
            transaction: Optional existing Sentry transaction.
            
        Returns:
            A dictionary containing the status and results of both sync operations.
        """
        op_name = "sync_notion_to_all"
        # Use common utils for transaction management
        transaction, own_transaction = self.common_utils.create_sync_transaction(op_name, transaction)
            
        result = {
            "status": "success",
            "message": "",
            "calendar_sync": {},
            "ocp_sync": {},
            "summary": {
                "total_events_processed": 0,
                "calendar_events_created": 0,
                "calendar_events_updated": 0,
                "ocp_points_added": 0,
                "ocp_officers_added": 0
            }
        }
        
        try:
            # Validate prerequisites using common utils
            validation = self.common_utils.validate_sync_prerequisites()
            if not validation["valid"]:
                error_msg = f"Sync prerequisites not met: {', '.join(validation['issues'])}"
                self.logger.error(f"{op_name}: {error_msg}")
                return self.common_utils.create_error_result(error_msg, op_name, transaction)
                
            self.logger.info(f"Starting {op_name} with database ID: {config.NOTION_DATABASE_ID}")
            
            # Step 1: Perform Calendar Sync
            with operation_span(transaction, op="calendar_sync", description="sync_notion_to_google_calendar", logger=self.logger) as calendar_span:
                self.logger.info("Starting calendar sync...")
                calendar_result = self.calendar_service.sync_notion_to_google(transaction)
                result["calendar_sync"] = calendar_result
                
                # Update summary with calendar results
                if calendar_result.get("status") == "success":
                    events_processed = calendar_result.get("events_processed", [])
                    result["summary"]["total_events_processed"] = len(events_processed)
                    
                    # Count created and updated events
                    created_count = sum(1 for event in events_processed if event.get("status") == "created")
                    updated_count = sum(1 for event in events_processed if event.get("status") == "updated")
                    result["summary"]["calendar_events_created"] = created_count
                    result["summary"]["calendar_events_updated"] = updated_count
                    
                    calendar_span.set_data("calendar_sync_success", True)
                    calendar_span.set_data("events_processed", len(events_processed))
                    calendar_span.set_data("events_created", created_count)
                    calendar_span.set_data("events_updated", updated_count)
                else:
                    self.logger.warning(f"Calendar sync completed with status: {calendar_result.get('status')}")
                    calendar_span.set_data("calendar_sync_success", False)
                    if result["status"] == "success":
                        result["status"] = "warning"
            
            # Step 2: Perform OCP Sync
            with operation_span(transaction, op="ocp_sync", description="sync_notion_to_ocp_database", logger=self.logger) as ocp_span:
                self.logger.info("Starting OCP sync...")
                ocp_result = self.ocp_sync_service.sync_notion_to_ocp(transaction)
                result["ocp_sync"] = ocp_result
                
                # Update summary with OCP results
                if ocp_result.get("status") == "success":
                    result["summary"]["ocp_points_added"] = ocp_result.get("added_points_count", 0)
                    result["summary"]["ocp_officers_added"] = ocp_result.get("added_officers_count", 0)
                    
                    ocp_span.set_data("ocp_sync_success", True)
                    ocp_span.set_data("points_added", ocp_result.get("added_points_count", 0))
                    ocp_span.set_data("officers_added", ocp_result.get("added_officers_count", 0))
                else:
                    self.logger.warning(f"OCP sync completed with status: {ocp_result.get('status')}")
                    ocp_span.set_data("ocp_sync_success", False)
                    if result["status"] == "success":
                        result["status"] = "warning"
            
            # Step 3: Generate comprehensive result message
            calendar_status = calendar_result.get("status", "unknown")
            ocp_status = ocp_result.get("status", "unknown")
            
            if calendar_status == "success" and ocp_status == "success":
                result["message"] = f"Complete sync successful. Calendar: {result['summary']['total_events_processed']} events processed, OCP: {result['summary']['ocp_points_added']} points added."
            elif calendar_status == "success" and ocp_status != "success":
                result["message"] = f"Calendar sync successful ({result['summary']['total_events_processed']} events), but OCP sync had issues: {ocp_result.get('message', 'Unknown error')}"
            elif calendar_status != "success" and ocp_status == "success":
                result["message"] = f"OCP sync successful ({result['summary']['ocp_points_added']} points), but Calendar sync had issues: {calendar_result.get('message', 'Unknown error')}"
            else:
                result["message"] = f"Both syncs had issues. Calendar: {calendar_result.get('message', 'Unknown error')}, OCP: {ocp_result.get('message', 'Unknown error')}"
                result["status"] = "error"
            
            # Use common utils to handle result processing
            return self.common_utils.handle_sync_result(result, op_name, transaction, own_transaction)
            
        except Exception as e:
            error_msg = f"An unexpected error occurred during unified sync: {str(e)}"
            return self.common_utils.create_error_result(error_msg, op_name, transaction, e)
    
    def get_sync_status(self) -> Dict[str, Any]:
        """
        Get the current status of both sync services.
        
        Returns:
            Dictionary with status information for both calendar and OCP syncs.
        """
        return {
            "calendar_service": "available" if self.calendar_service else "unavailable",
            "ocp_service": "available" if self.ocp_sync_service else "unavailable",
            "last_sync": datetime.utcnow().isoformat(),
            "config": {
                "notion_database_id": bool(config.NOTION_DATABASE_ID),
                "google_calendar_id": bool(getattr(config, 'GOOGLE_CALENDAR_ID', None))
            }
        } 