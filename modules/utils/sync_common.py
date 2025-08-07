"""
Common sync utilities for Notion synchronization operations.
Provides shared functionality for calendar and OCP sync services.
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
from sentry_sdk import capture_exception, set_context, start_transaction

from shared import config, logger
from modules.calendar.utils import operation_span

class SyncCommonUtils:
    """Common utilities for sync operations."""
    
    def __init__(self, logger_instance=None):
        """Initialize the sync common utilities."""
        self.logger = logger_instance or logger
        
    def validate_notion_config(self, database_id: str = None) -> Dict[str, Any]:
        """
        Validate that required Notion configuration is available.
        If database_id is provided, check it; otherwise, skip database ID check (for multi-org calendar sync).
        Returns:
            Dict with validation status and any error messages.
        """
        errors = []
        # Only check NOTION_DATABASE_ID if a specific one is provided (OCP sync)
        if database_id is not None and not database_id:
            errors.append("NOTION_DATABASE_ID is not configured for this operation")
        if not hasattr(config, 'NOTION_TOKEN') or not config.NOTION_TOKEN:
            errors.append("NOTION_TOKEN is not configured")
        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "database_id": database_id
        }
    
    def create_sync_transaction(self, operation_name: str, transaction=None):
        """
        Create or use existing Sentry transaction for sync operations.
        
        Args:
            operation_name: Name of the sync operation
            transaction: Optional existing transaction
            
        Returns:
            Tuple of (transaction, own_transaction_flag)
        """
        own_transaction = transaction is None
        if own_transaction:
            transaction = start_transaction(op="sync", name=operation_name)
            
        return transaction, own_transaction
    
    def handle_sync_result(self, result: Dict[str, Any], operation_name: str, 
                          transaction=None, own_transaction=False) -> Dict[str, Any]:
        """
        Handle common sync result processing and logging.
        
        Args:
            result: The sync result dictionary
            operation_name: Name of the operation
            transaction: Sentry transaction
            own_transaction: Whether we created the transaction
            
        Returns:
            Processed result dictionary
        """
        status = result.get("status", "unknown")
        
        # Set transaction data based on result
        if transaction:
            if status == "success":
                transaction.set_data("sync_success", True)
                self.logger.info(f"{operation_name} completed successfully: {result.get('message', '')}")
            elif status == "warning":
                transaction.set_data("sync_success", "partial")
                self.logger.warning(f"{operation_name} completed with warnings: {result.get('message', '')}")
            else:
                transaction.set_data("sync_success", False)
                transaction.set_status("internal_error")
                self.logger.error(f"{operation_name} failed: {result.get('message', '')}")
        
        # Finish transaction if we created it
        if own_transaction and transaction:
            transaction.finish()
            
        return result
    
    def log_sync_summary(self, operation_name: str, summary: Dict[str, Any]):
        """
        Log a summary of sync operations.
        
        Args:
            operation_name: Name of the sync operation
            summary: Summary dictionary with counts and statistics
        """
        self.logger.info(f"{operation_name} Summary:")
        for key, value in summary.items():
            if isinstance(value, (int, float)):
                self.logger.info(f"  {key}: {value}")
            elif isinstance(value, dict):
                self.logger.info(f"  {key}:")
                for sub_key, sub_value in value.items():
                    self.logger.info(f"    {sub_key}: {sub_value}")
    
    def create_error_result(self, message: str, operation_name: str, 
                          transaction=None, exception: Exception = None) -> Dict[str, Any]:
        """
        Create a standardized error result.
        
        Args:
            message: Error message
            operation_name: Name of the operation
            transaction: Sentry transaction
            exception: Optional exception to capture
            
        Returns:
            Standardized error result dictionary
        """
        if exception:
            capture_exception(exception)
            
        if transaction:
            transaction.set_status("internal_error")
            
        return {
            "status": "error",
            "message": message,
            "operation": operation_name,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    def create_success_result(self, message: str, details: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Create a standardized success result.
        
        Args:
            message: Success message
            details: Optional details dictionary
            
        Returns:
            Standardized success result dictionary
        """
        result = {
            "status": "success",
            "message": message,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        if details:
            result["details"] = details
            
        return result
    
    def validate_sync_prerequisites(self, require_database_id: bool = False, database_id: str = None) -> Dict[str, Any]:
        """
        Validate all prerequisites for sync operations.
        If require_database_id is True, check for a specific database_id (OCP sync); otherwise, skip (calendar multi-org sync).
        Returns:
            Dict with validation status and any issues found.
        """
        validation = {
            "valid": True,
            "issues": [],
            "config": {}
        }
        # Check Notion configuration
        notion_config = self.validate_notion_config(database_id if require_database_id else None)
        validation["config"]["notion"] = notion_config
        if not notion_config["valid"]:
            validation["valid"] = False
            validation["issues"].extend(notion_config["errors"])
        # Check database connectivity (if applicable)
        try:
            from modules.utils.db import DBConnect
            db = DBConnect("sqlite:///./data/user.db")
            validation["config"]["database"] = {"available": True}
        except Exception as e:
            validation["valid"] = False
            validation["issues"].append(f"Database connectivity issue: {str(e)}")
            validation["config"]["database"] = {"available": False, "error": str(e)}
        return validation 