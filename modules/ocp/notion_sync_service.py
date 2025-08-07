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
            self.logger.info(f"[NotionOCPSyncService] Starting multi-org OCP sync...")
            db = next(db_connect.get_db())
            self.logger.info(f"[NotionOCPSyncService] Querying organizations with OCP sync enabled...")
            organizations = db.query(Organization).filter(
                Organization.is_active == True,
                Organization.notion_database_id != None,
                Organization.notion_database_id != "",
                Organization.ocp_sync_enabled == True
            ).all()
            self.logger.info(f"[NotionOCPSyncService] Found {len(organizations)} organizations with OCP sync enabled")
            for org in organizations:
                self.logger.info(f"[NotionOCPSyncService] Organization: {org.name} (ID: {org.id}, DB: {org.notion_database_id})")
            summary = []
            for org in organizations:
                self.logger.info(f"[NotionOCPSyncService] Starting OCP sync for organization: {org.name} (ID: {org.id})")
                try:
                    self.logger.info(f"[NotionOCPSyncService] Calling ocp_service.sync_notion_to_ocp for {org.name}")
                    sync_result = self.ocp_service.sync_notion_to_ocp(org.notion_database_id, org.id, transaction)
                    self.logger.info(f"[NotionOCPSyncService] OCP sync result for {org.name} (ID: {org.id}): {sync_result}")
                except Exception as e:
                    self.logger.error(f"[NotionOCPSyncService] Exception during OCP sync for {org.name} (ID: {org.id}): {e}", exc_info=True)
                    sync_result = {"status": "error", "message": str(e)}
                summary.append({
                    "organization_id": org.id,
                    "organization_name": org.name,
                    "status": sync_result.get("status"),
                    "message": sync_result.get("message")
                })
            result["details"] = summary
            self.logger.info(f"[NotionOCPSyncService] OCP sync summary: {summary}")
            if any(r["status"] != "success" for r in summary):
                result["status"] = "warning"
                result["message"] = "Some organizations failed to sync."
                self.logger.warning(f"[NotionOCPSyncService] Some organizations failed to sync: {[r for r in summary if r['status'] != 'success']}")
            else:
                result["message"] = "All organizations synced successfully."
                self.logger.info(f"[NotionOCPSyncService] All organizations synced successfully")
            return result
        except Exception as e:
            self.logger.error(f"[NotionOCPSyncService] Exception in sync_notion_to_ocp: {e}", exc_info=True)
            result["status"] = "error"
            result["message"] = str(e)
            return result 
        finally:
            if own_transaction and transaction:
                transaction.finish() 