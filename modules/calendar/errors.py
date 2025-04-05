import logging
from notion_client import APIErrorCode, APIResponseError
from googleapiclient.errors import HttpError
from sentry_sdk import capture_exception, set_tag, set_context

# Assuming logger is configured elsewhere, e.g., in shared.py
# If not, initialize a default logger:
# logger = logging.getLogger(__name__)

class APIErrorHandler:
    """Standardized error handling for API operations."""

    def __init__(self, logger, operation_name, transaction=None):
        self.logger = logger
        self.operation_name = operation_name
        self.transaction = transaction # Optional transaction context for Sentry

    def handle_http_error(self, error: HttpError, context_data=None):
        """Handle HttpError consistently."""
        capture_exception(error)
        details = getattr(error, 'error_details', str(error)) # Get details if available
        status = error.resp.status if hasattr(error, 'resp') else 'Unknown'
        self.logger.error(f"HTTP error during {self.operation_name}: {status} - {details}")

        error_context = {
            "status": status,
            "details": details,
            **(context_data or {})
        }
        set_context("http_error", error_context)

        if hasattr(error, 'resp'):
            if error.resp.status == 404:
                set_tag("error_type", "not_found")
            elif error.resp.status == 403:
                set_tag("error_type", "permission_denied")
            else:
                set_tag("error_type", "http_error")
        else:
             set_tag("error_type", "http_error_unknown_status")
        return None # Indicate error handled, return None

    def handle_notion_error(self, error: APIResponseError, context_data=None):
        """Handle Notion API errors consistently."""
        capture_exception(error)
        self.logger.error(f"Notion API Error during {self.operation_name}: {error.code} - {str(error)}")
        set_context("notion_error", {
            "code": error.code,
            "message": str(error),
            **(context_data or {})
        })

        if error.code == APIErrorCode.ObjectNotFound:
            set_tag("error_type", "database_not_found") # Or object_not_found depending on context
        elif error.code == APIErrorCode.Unauthorized:
             set_tag("error_type", "notion_unauthorized")
        elif error.code == APIErrorCode.RateLimited:
             set_tag("error_type", "notion_rate_limited")
        else:
             set_tag("error_type", "notion_api_error")
        return None # Indicate error handled, return None

    def handle_generic_error(self, error: Exception, context_data=None):
        """Handle general exceptions consistently."""
        capture_exception(error)
        self.logger.error(f"Unexpected error during {self.operation_name}: {str(error)}")
        set_tag("error_type", "unexpected")
        if context_data:
            set_context("error_context", context_data)
        return None # Indicate error handled, return None