import logging
from typing import Dict, Any, Optional
from datetime import datetime
from sentry_sdk import capture_exception, set_context, start_transaction

from shared import config, logger
from modules.calendar.service import MultiOrgCalendarService
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
        self.calendar_service = MultiOrgCalendarService(self.logger)
        self.ocp_sync_service = NotionOCPSyncService(self.logger)
        self.common_utils = SyncCommonUtils(self.logger)
        
        self.logger.info("UnifiedSyncService initialized with MultiOrgCalendarService")
        
    def sync_notion_to_all(self, transaction=None) -> Dict[str, Any]:
        """
        Orchestrates the complete sync process from Notion to both Google Calendar and OCP database.
        
        This method:
        1. Syncs all organizations' calendars from Notion to Google Calendar
        2. Syncs to OCP database
        3. Provides comprehensive results from both operations
        
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
                "total_organizations_processed": 0,
                "total_events_processed": 0,
                "calendar_events_created": 0,
                "calendar_events_updated": 0,
                "ocp_points_added": 0,
                "ocp_officers_added": 0
            }
        }
        
        try:
            # Validate prerequisites for calendar sync (multi-org: only require NOTION_TOKEN)
            validation = self.common_utils.validate_sync_prerequisites(require_database_id=False)
            if not validation["valid"]:
                error_msg = f"Sync prerequisites not met: {', '.join(validation['issues'])}"
                self.logger.error(f"{op_name}: {error_msg}")
                return self.common_utils.create_error_result(error_msg, op_name, transaction)
                
            self.logger.info(f"Starting {op_name} for all organizations")
            
            # Step 1: Perform Multi-Organization Calendar Sync
            with operation_span(transaction, op="calendar_sync", description="sync_all_organizations_calendar", logger=self.logger) as calendar_span:
                self.logger.info("Starting multi-organization calendar sync...")
                calendar_result = self.calendar_service.sync_all_organizations(transaction)
                result["calendar_sync"] = calendar_result
                
                # Update summary with calendar results
                if calendar_result.get("status") in ["success", "partial_success"]:
                    organizations_processed = calendar_result.get("organizations_processed", 0)
                    organizations_failed = calendar_result.get("organizations_failed", 0)
                    total_organizations = calendar_result.get("total_organizations", 0)
                    
                    result["summary"]["total_organizations_processed"] = organizations_processed
                    
                    # Count events from organization results
                    total_events = 0
                    created_events = 0
                    updated_events = 0
                    
                    for org_result in calendar_result.get("organization_results", []):
                        events_processed = org_result.get("events_processed", 0)
                        total_events += events_processed
                        # Note: We can't easily distinguish created vs updated events per org
                        # This is a limitation of the current implementation
                    
                    result["summary"]["total_events_processed"] = total_events
                    result["summary"]["calendar_events_created"] = created_events
                    result["summary"]["calendar_events_updated"] = updated_events
                    
                    calendar_span.set_data("calendar_sync_success", True)
                    calendar_span.set_data("organizations_processed", organizations_processed)
                    calendar_span.set_data("organizations_failed", organizations_failed)
                    calendar_span.set_data("total_organizations", total_organizations)
                    calendar_span.set_data("total_events", total_events)
                    
                    if organizations_failed > 0:
                        result["status"] = "warning"
                        result["message"] = f"Calendar sync completed with {organizations_failed} organizations failing"
                else:
                    self.logger.warning(f"Calendar sync completed with status: {calendar_result.get('status')}")
                    calendar_span.set_data("calendar_sync_success", False)
                    if result["status"] == "success":
                        result["status"] = "warning"
            
            # Step 2: Perform OCP Sync (unchanged, but can require database_id if needed)
            with operation_span(transaction, op="ocp_sync", description="sync_notion_to_ocp_database", logger=self.logger) as ocp_span:
                self.logger.info("Starting OCP sync...")
                # For OCP sync, you may want to validate prerequisites with require_database_id=True and pass the relevant database_id
                ocp_result = self.ocp_sync_service.sync_notion_to_ocp(transaction)
                result["ocp_sync"] = ocp_result
                
                # Update summary with OCP results
                if ocp_result.get("status") == "success":
                    result["summary"]["ocp_points_added"] = ocp_result.get("points_added", 0)
                    result["summary"]["ocp_officers_added"] = ocp_result.get("officers_added", 0)
                    
                    ocp_span.set_data("ocp_sync_success", True)
                    ocp_span.set_data("points_added", ocp_result.get("points_added", 0))
                    ocp_span.set_data("officers_added", ocp_result.get("officers_added", 0))
                else:
                    self.logger.warning(f"OCP sync completed with status: {ocp_result.get('status')}")
                    ocp_span.set_data("ocp_sync_success", False)
                    if result["status"] == "success":
                        result["status"] = "warning"
            
            # Set overall message
            if result["status"] == "success":
                result["message"] = f"Unified sync completed successfully. Processed {result['summary']['total_organizations_processed']} organizations, {result['summary']['total_events_processed']} events, {result['summary']['ocp_points_added']} OCP points."
            elif result["status"] == "warning":
                result["message"] = f"Unified sync completed with warnings. Check individual sync results for details."
            else:
                result["message"] = "Unified sync failed. Check individual sync results for details."
            
            self.logger.info(f"Unified sync completed with status: {result['status']}")
            return result
            
        except Exception as e:
            error_msg = f"Unexpected error during unified sync: {str(e)}"
            self.logger.error(f"{op_name}: {error_msg}", exc_info=True)
            return self.common_utils.create_error_result(error_msg, op_name, transaction)
        finally:
            if own_transaction:
                transaction.finish()
    
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