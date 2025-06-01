import logging
from typing import Dict, Any, Optional
from datetime import datetime
from sentry_sdk import capture_exception, set_context, start_transaction

from shared import config, logger
from .service import OCPService
from ..utils import operation_span

class NotionOCPSyncService:
    """Service for syncing Notion database with Officer Contribution Points (OCP) system."""
    
    def __init__(self, logger_instance=None, ocp_service=None):
        """Initialize the NotionOCPSync service with logger and OCP service."""
        self.logger = logger_instance or logger
        self.ocp_service = ocp_service or OCPService()
        
        self.logger.info("NotionOCPSync service initialized")
        
    def sync_notion_to_ocp(self, transaction=None) -> Dict[str, Any]:
        """
        Orchestrates the sync process from Notion to OCP database.
        
        Args:
            transaction: Optional existing Sentry transaction.
            
        Returns:
            A dictionary containing the status and results of the sync.
        """
        op_name = "sync_notion_to_ocp"
        # Start a new transaction if one isn't provided
        own_transaction = transaction is None
        if own_transaction:
            transaction = start_transaction(op="sync", name=op_name)
            
        result = {
            "status": "success",
            "message": "",
            "details": {}
        }
        
        try:
            # Check if Notion database ID is configured
            if not config.NOTION_DATABASE_ID:
                self.logger.error(f"{op_name}: Required configuration NOTION_DATABASE_ID is missing")
                result["status"] = "error"
                result["message"] = "Notion database ID not configured"
                return result
                
            # Perform the sync using the OCPService
            with operation_span(transaction, op="sync", description="perform_ocp_sync", logger=self.logger) as span:
                self.logger.info(f"Starting {op_name} with database ID: {config.NOTION_DATABASE_ID}")
                
                sync_result = self.ocp_service.sync_notion_to_ocp(config.NOTION_DATABASE_ID, transaction)
                
                # Update the result with the service response
                result.update(sync_result)
                
                # Add more detailed information for logging
                if sync_result.get("status") == "success":
                    self.logger.info(f"{op_name} completed successfully: {sync_result.get('message')}")
                    span.set_data("sync_success", True)
                elif sync_result.get("status") == "warning":
                    self.logger.warning(f"{op_name} completed with warning: {sync_result.get('message')}")
                    span.set_data("sync_success", "partial")
                    if result["status"] == "success":
                        result["status"] = "warning"
                else:
                    self.logger.error(f"{op_name} failed: {sync_result.get('message')}")
                    span.set_data("sync_success", False)
                    span.set_status("internal_error")
            
            # Only finish the transaction if we created it
            if own_transaction and transaction:
                transaction.finish()
            return result
            
        except Exception as e:
            capture_exception(e)
            self.logger.exception(f"Critical error during {op_name}: {e}")
            result["status"] = "error"
            result["message"] = f"An unexpected error occurred during sync: {str(e)}"
            
            if transaction:
                transaction.set_status("internal_error")
                # Only finish the transaction if we created it
                if own_transaction:
                    transaction.finish(exception=e)
            return result 