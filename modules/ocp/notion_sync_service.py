import logging
from typing import Dict, Any, Optional
from datetime import datetime
from sentry_sdk import capture_exception, set_context, start_transaction

from shared import config, logger
from .service import OCPService
from modules.calendar.utils import operation_span

class NotionOCPSyncService:
    """Service for syncing Notion database with Officer Contribution Points (OCP) system."""
    
    def __init__(self, logger_instance=None, ocp_service=None):
        """Initialize the NotionOCPSync service with logger and OCP service."""
        self.logger = logger_instance or logger
        self.ocp_service = ocp_service or OCPService()
        
        self.logger.info("NotionOCPSync service initialized")
        
    def sync_notion_to_ocp(self, transaction=None) -> Dict[str, Any]:
        """
        Orchestrates the sync process from Notion to OCP database for all organizations with OCP sync enabled.
        Returns a summary of results per org.
        """
        op_name = "sync_notion_to_ocp"
        own_transaction = transaction is None
        if own_transaction:
            transaction = start_transaction(op="sync", name=op_name)
        result = {"status": "success", "message": "", "details": {}}
        try:
            from modules.organizations.models import Organization
            from shared import db_connect
            db = next(db_connect.get_db())
            organizations = db.query(Organization).filter(
                Organization.is_active == True,
                Organization.notion_database_id != None,
                Organization.notion_database_id != "",
                Organization.ocp_sync_enabled == True  # You may need to add this field
            ).all()
            summary = []
            self.logger.info(f"Found {len(organizations)} organizations with OCP sync enabled")
            for org in organizations:
                self.logger.info(f"Starting OCP sync for organization: {org.name} (ID: {org.id})")
                try:
                    sync_result = self.ocp_service.sync_notion_to_ocp(org.notion_database_id, org.id, transaction)
                    self.logger.info(f"OCP sync result for {org.name} (ID: {org.id}): {sync_result}")
                except Exception as e:
                    self.logger.error(f"Exception during OCP sync for {org.name} (ID: {org.id}): {e}")
                    sync_result = {"status": "error", "message": str(e)}
                summary.append({
                    "organization_id": org.id,
                    "organization_name": org.name,
                    "status": sync_result.get("status"),
                    "message": sync_result.get("message")
                })
            result["details"] = summary
            self.logger.info(f"OCP sync summary: {summary}")
            if any(r["status"] != "success" for r in summary):
                result["status"] = "warning"
                result["message"] = "Some organizations failed to sync."
            else:
                result["message"] = "All organizations synced successfully."
            return result
        except Exception as e:
            self.logger.error(f"Exception in NotionOCPSyncService.sync_notion_to_ocp: {e}")
            result["status"] = "error"
            result["message"] = str(e)
            return result
        finally:
            if own_transaction and transaction:
                transaction.finish() 