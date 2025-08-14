# modules/calendar/clients.py
import logging
from typing import List, Dict, Optional, Any, Tuple

from google.oauth2 import service_account
from googleapiclient.discovery import build, Resource # Added Resource type hint
from googleapiclient.errors import HttpError
from notion_client import Client as NotionClient # Alias to avoid confusion
from notion_client.helpers import collect_paginated_api
from notion_client import APIErrorCode, APIResponseError
from sentry_sdk import capture_exception, set_context, start_transaction

# Assuming shared resources are correctly set up
from shared import config, notion as notion_shared_client, logger

# Import custom modules
from .errors import APIErrorHandler
from .utils import batch_operation, operation_span

# If logger is not in shared, initialize it here:
# logger = logging.getLogger(__name__)

class GoogleCalendarClient:
    """Client for Google Calendar API operations."""

    SCOPES = ['https://www.googleapis.com/auth/calendar', 'https://www.googleapis.com/auth/calendar.events']

    def __init__(self, logger_instance=None):
        self.logger = logger_instance or logger # Use shared logger by default
        self._service: Optional[Resource] = None # Type hint for service
        self.error_handler = APIErrorHandler(self.logger, "GoogleCalendarClient")

    def get_service(self, parent_transaction=None) -> Optional[Resource]: # Accept parent transaction
        """Get authenticated Google Calendar service with error handling."""
        if self._service:
            return self._service

        op_name = "get_calendar_service"
        self.error_handler.operation_name = op_name

        # Use parent transaction if available, otherwise start a new one (though ideally it's always passed)
        current_transaction = parent_transaction or start_transaction(op="google", name=f"{op_name}_independent")

        # Use operation_span within the current transaction
        with operation_span(current_transaction, op="google_auth", description=op_name, logger=self.logger) as transaction: # Use operation_span
            self.error_handler.transaction = transaction # Pass transaction to handler
            try:
                set_context("google_api", {
                    "scopes": self.SCOPES,
                    "service_account_provided": bool(config.GOOGLE_SERVICE_ACCOUNT)
                })

                if not config.GOOGLE_SERVICE_ACCOUNT:
                    self.logger.error("Google Service Account configuration is missing.")
                    raise ValueError("Google Service Account configuration is missing.")

                with operation_span(transaction, op="auth", description="create_credentials", logger=self.logger) as span:
                    credentials = service_account.Credentials.from_service_account_info(
                        config.GOOGLE_SERVICE_ACCOUNT, # Assuming this is the parsed dict
                        scopes=self.SCOPES
                    )
                    span.set_data("credentials_created", bool(credentials))

                with operation_span(transaction, op="build", description="build_service", logger=self.logger) as span:
                    self._service = build('calendar', 'v3', credentials=credentials, cache_discovery=False) # Added cache_discovery=False
                    span.set_data("service_created", bool(self._service))
                    self.logger.info("Google Calendar service initialized successfully.")
                    return self._service

            except ValueError as ve: # Catch specific config errors
                 self.logger.error(f"Configuration error during {op_name}: {ve}")
                 # No need to call error_handler here as it's a config issue, not API error
                 capture_exception(ve) # Still capture for visibility
                 return None
            except Exception as e:
                # Use the error handler for generic errors during initialization
                return self.error_handler.handle_generic_error(e)
            finally:
                self.error_handler.transaction = None # Clear transaction from handler if it was set


    def create_event(self, calendar_id: str, event_data: Dict, notion_page_id: str, parent_transaction=None) -> Optional[Tuple[str, str]]: # Accept parent transaction
       """Create calendar event with error handling. Returns (jump_url, gcal_event_id) or None."""
       op_name = "create_event"
       self.error_handler.operation_name = op_name

       current_transaction = parent_transaction or start_transaction(op="google", name=f"{op_name}_independent")

       with operation_span(current_transaction, op="google_api", description=op_name, logger=self.logger) as transaction: # Use operation_span
            self.error_handler.transaction = transaction
            service = self.get_service(parent_transaction=transaction) # Pass transaction down
            if not service:
                self.logger.error(f"{op_name}: Failed to get Google Calendar service.")
                return None # Service initialization failed

            # Add extended properties to store Notion ID
            event_data['extendedProperties'] = {
                'private': {
                    'notionPageId': notion_page_id
                }
            }

            context_data = {
                "calendar_id": calendar_id,
                "notion_page_id": notion_page_id,
                "summary": event_data.get("summary", "Unknown Event")
            }
            set_context("event_create", context_data)

            try:
                with operation_span(transaction, op="api_call", description="events.insert", logger=self.logger) as span:
                    self.logger.debug(f"Attempting to create Google Calendar event for Notion ID {notion_page_id} with data: {event_data}")
                    created_event = service.events().insert(
                        calendarId=calendar_id,
                        body=event_data
                    ).execute()

                    gcal_event_id = created_event['id']
                    jump_url = created_event.get('htmlLink')
                    span.set_data("event_details", {
                        "gcal_id": gcal_event_id,
                        "summary": created_event.get('summary'),
                        "jump_url_present": bool(jump_url)
                    })

                    self.logger.info(f"Created Google Calendar event: {gcal_event_id} for Notion page: {notion_page_id}")
                    return jump_url, gcal_event_id # Return both URL and ID

            except HttpError as e:
                return self.error_handler.handle_http_error(e, context_data)
            except Exception as e:
                return self.error_handler.handle_generic_error(e, context_data)
            finally:
                self.error_handler.transaction = None # Clear transaction from handler if it was set


    def update_event(self, calendar_id: str, event_id: str, event_data: Dict, notion_page_id: str, parent_transaction=None) -> Optional[str]: # Accept parent transaction
        """Update calendar event with error handling. Returns jump_url or None."""
        op_name = "update_event"
        self.error_handler.operation_name = op_name

        current_transaction = parent_transaction or start_transaction(op="google", name=f"{op_name}_independent")

        with operation_span(current_transaction, op="google_api", description=op_name, logger=self.logger) as transaction: # Use operation_span
            self.error_handler.transaction = transaction
            service = self.get_service(parent_transaction=transaction) # Pass transaction down
            if not service:
                 self.logger.error(f"{op_name}: Failed to get Google Calendar service.")
                 return None

            # Ensure extended properties structure exists and set Notion ID
            if 'extendedProperties' not in event_data:
                event_data['extendedProperties'] = {}
            if 'private' not in event_data['extendedProperties']:
                 event_data['extendedProperties']['private'] = {}
            event_data['extendedProperties']['private']['notionPageId'] = notion_page_id

            context_data = {
                "calendar_id": calendar_id,
                "event_id": event_id,
                "notion_page_id": notion_page_id,
                "summary": event_data.get("summary", "Unknown Event")
            }
            set_context("event_update", context_data)

            try:
                with operation_span(transaction, op="api_call", description="events.update", logger=self.logger) as span:
                    self.logger.debug(f"Attempting to update Google Calendar event {event_id} for Notion ID {notion_page_id} with data: {event_data}")
                    updated_event = service.events().update(
                        calendarId=calendar_id,
                        eventId=event_id,
                        body=event_data
                    ).execute()

                    jump_url = updated_event.get('htmlLink')
                    span.set_data("event_details", {
                        "id": updated_event['id'],
                        "summary": updated_event.get('summary'),
                        "status": "success",
                        "jump_url_present": bool(jump_url)
                    })
                    self.logger.info(f"Updated Google Calendar event: {updated_event['id']} for Notion page: {notion_page_id}")
                    return jump_url

            except HttpError as e:
                return self.error_handler.handle_http_error(e, context_data)
            except Exception as e:
                return self.error_handler.handle_generic_error(e, context_data)
            finally:
                self.error_handler.transaction = None # Clear transaction from handler if it was set


    def get_all_events(self, calendar_id: str, time_min: Optional[str] = None, parent_transaction=None) -> Optional[List[Dict]]: # Accept parent transaction
        """Get all events with pagination handling. Returns list of events or None on error."""
        op_name = "get_all_events"
        self.error_handler.operation_name = op_name

        current_transaction = parent_transaction or start_transaction(op="google", name=f"{op_name}_independent")

        with operation_span(current_transaction, op="google_api", description=op_name, logger=self.logger) as transaction: # Use operation_span
            self.error_handler.transaction = transaction
            service = self.get_service(parent_transaction=transaction) # Pass transaction down
            if not service:
                self.logger.error(f"{op_name}: Failed to get Google Calendar service.")
                return None

            all_events = []
            page_token = None
            context_data = {"calendar_id": calendar_id, "time_min": time_min}
            set_context("gcal_event_fetch", context_data)
            self.logger.info(f"Fetching events from calendar {calendar_id}" + (f" starting from {time_min}" if time_min else "") + ".")

            try:
                while True:
                    with operation_span(transaction, op="list_page", description="events.list page", logger=self.logger) as span:
                        events_result = service.events().list(
                            calendarId=calendar_id,
                            singleEvents=True, # Expand recurring events
                            showDeleted=False, # Don't include deleted events
                            pageToken=page_token,
                            timeMin=time_min,
                            maxResults=250 # Fetch in batches
                        ).execute()

                        items = events_result.get('items', [])
                        all_events.extend(items)
                        page_token = events_result.get('nextPageToken')

                        span.set_data("page_event_count", len(items))
                        span.set_data("has_next_page", bool(page_token))

                        if not page_token:
                            break # Exit loop if no more pages

                self.logger.info(f"Fetched a total of {len(all_events)} events from Google Calendar {calendar_id}.")
                transaction.set_data("total_fetched_events", len(all_events))
                return all_events

            except HttpError as e:
                return self.error_handler.handle_http_error(e, context_data)
            except Exception as e:
                return self.error_handler.handle_generic_error(e, context_data)
            finally:
                self.error_handler.transaction = None # Clear transaction from handler if it was set


    def batch_delete_events(self, calendar_id: str, event_ids: List[str], description: str = "batch_delete", parent_transaction=None) -> Tuple[int, int]: # Accept parent transaction
        """Delete events in batches using the utility function."""
        op_name = f"batch_delete_{description}"
        self.error_handler.operation_name = op_name # Set context for potential errors within batch_operation

        current_transaction = parent_transaction or start_transaction(op="google", name=f"{op_name}_independent")

        service = self.get_service(parent_transaction=current_transaction) # Pass transaction down
        if not service:
            self.logger.error(f"{op_name}: Failed to get Google Calendar service.")
            # If service fails, all deletions fail
            return 0, len(event_ids) if event_ids else 0

        if not event_ids:
            self.logger.info(f"{op_name}: No event IDs provided for deletion.")
            return 0, 0

        # Define the operation function for the utility
        # It takes the service and returns the method to call (service.events().delete)
        delete_operation_fn = lambda s: s.events().delete

        # Use operation_span for the batch operation within the current transaction
        with operation_span(current_transaction, op="google_batch", description=op_name, logger=self.logger) as transaction:
            # Pass the transaction down to batch_operation so it can create sub-spans if needed
            successful, failed = batch_operation(
                service=service,
                operation_fn=delete_operation_fn,
                items=event_ids,
                calendar_id=calendar_id,
                description=description,
                parent_transaction=transaction # Pass transaction to batch_operation
            )
            transaction.set_data("successful_deletions", successful)
            transaction.set_data("failed_deletions", failed)
            transaction.set_data("total_attempted", len(event_ids))

            return successful, failed


    def create_calendar(self, calendar_name: str, description: str = None, timezone: str = "America/Phoenix", parent_transaction=None) -> Optional[Dict]:
        """Create a new Google Calendar with error handling."""
        op_name = "create_calendar"
        self.error_handler.operation_name = op_name
        
        current_transaction = parent_transaction or start_transaction(op="google", name=f"{op_name}_independent")
        
        with operation_span(current_transaction, op="google_api", description=op_name, logger=self.logger) as transaction:
            self.error_handler.transaction = transaction
            service = self.get_service(parent_transaction=transaction)
            if not service:
                self.logger.error(f"{op_name}: Failed to get Google Calendar service.")
                return None
                
            calendar_body = {
                'summary': calendar_name,
                'timeZone': timezone
            }
            
            if description:
                calendar_body['description'] = description
                
            try:
                with operation_span(transaction, op="api_call", description="calendars.insert", logger=self.logger) as span:
                    created_calendar = service.calendars().insert(body=calendar_body).execute()
                    
                    calendar_id = created_calendar['id']
                    span.set_data("calendar_details", {
                        "calendar_id": calendar_id,
                        "summary": created_calendar.get('summary'),
                        "timezone": created_calendar.get('timeZone')
                    })
                    
                    self.logger.info(f"Successfully created calendar '{calendar_name}' with ID: {calendar_id}")
                    return created_calendar
                    
            except Exception as e:
                return self.error_handler.handle_generic_error(e)
            finally:
                self.error_handler.transaction = None

    def get_calendar(self, calendar_id: str, parent_transaction=None) -> Optional[Dict]:
        """Get calendar details by ID."""
        op_name = "get_calendar"
        self.error_handler.operation_name = op_name
        
        current_transaction = parent_transaction or start_transaction(op="google", name=f"{op_name}_independent")
        
        with operation_span(current_transaction, op="google_api", description=op_name, logger=self.logger) as transaction:
            self.error_handler.transaction = transaction
            service = self.get_service(parent_transaction=transaction)
            if not service:
                self.logger.error(f"{op_name}: Failed to get Google Calendar service.")
                return None
                
            try:
                with operation_span(transaction, op="api_call", description="calendars.get", logger=self.logger) as span:
                    calendar = service.calendars().get(calendarId=calendar_id).execute()
                    span.set_data("calendar_id", calendar_id)
                    return calendar
                    
            except Exception as e:
                return self.error_handler.handle_generic_error(e)
            finally:
                self.error_handler.transaction = None

    def list_calendars(self, parent_transaction=None) -> Optional[List[Dict]]:
        """List all calendars accessible to the service account."""
        op_name = "list_calendars"
        self.error_handler.operation_name = op_name
        
        current_transaction = parent_transaction or start_transaction(op="google", name=f"{op_name}_independent")
        
        with operation_span(current_transaction, op="google_api", description=op_name, logger=self.logger) as transaction:
            self.error_handler.transaction = transaction
            service = self.get_service(parent_transaction=transaction)
            if not service:
                self.logger.error(f"{op_name}: Failed to get Google Calendar service.")
                return None
                
            try:
                with operation_span(transaction, op="api_call", description="calendarList.list", logger=self.logger) as span:
                    calendar_list = service.calendarList().list().execute()
                    calendars = calendar_list.get('items', [])
                    span.set_data("calendar_count", len(calendars))
                    return calendars
                    
            except Exception as e:
                return self.error_handler.handle_generic_error(e)
            finally:
                self.error_handler.transaction = None

    def delete_calendar(self, calendar_id: str, parent_transaction=None) -> bool:
        """Delete a calendar (use with extreme caution)."""
        op_name = "delete_calendar"
        self.error_handler.operation_name = op_name
        
        current_transaction = parent_transaction or start_transaction(op="google", name=f"{op_name}_independent")
        
        with operation_span(current_transaction, op="google_api", description=op_name, logger=self.logger) as transaction:
            self.error_handler.transaction = transaction
            service = self.get_service(parent_transaction=transaction)
            if not service:
                self.logger.error(f"{op_name}: Failed to get Google Calendar service.")
                return False
                
            try:
                with operation_span(transaction, op="api_call", description="calendars.delete", logger=self.logger) as span:
                    service.calendars().delete(calendarId=calendar_id).execute()
                    span.set_data("calendar_id", calendar_id)
                    self.logger.warning(f"Successfully deleted calendar: {calendar_id}")
                    return True
                    
            except Exception as e:
                return self.error_handler.handle_generic_error(e)
            finally:
                self.error_handler.transaction = None


class NotionCalendarClient:
    """Client for Notion calendar-related operations."""

    def __init__(self, logger_instance=None):
        self.logger = logger_instance or logger # Use shared logger by default
        self.notion: NotionClient = notion_shared_client # Use shared Notion client instance
        self.error_handler = APIErrorHandler(self.logger, "NotionCalendarClient")

    def fetch_events(self, database_id: str, parent_transaction=None) -> Optional[List[Dict]]: # Accept parent transaction
        """Fetch published events from Notion with pagination and error handling."""
        op_name = "fetch_notion_events"
        self.error_handler.operation_name = op_name

        current_transaction = parent_transaction or start_transaction(op="notion", name=f"{op_name}_independent")

        with operation_span(current_transaction, op="notion_api", description=op_name, logger=self.logger) as transaction: # Use operation_span
            self.error_handler.transaction = transaction
            context_data = {"database_id": database_id}
            set_context("notion_query", context_data)
            self.logger.info(f"Fetching all published Notion events from database {database_id} using pagination.")

            try:
                # Define the filter - Fetch ALL published events
                query_filter = {
                    "property": "Published", # Make sure this property name is correct
                    "checkbox": {
                        "equals": True
                    }
                }

                # Use collect_paginated_api to handle pagination automatically
                with operation_span(transaction, op="api_call", description="notion.databases.query", logger=self.logger) as span:
                    all_events = collect_paginated_api(
                        self.notion.databases.query,
                        database_id=database_id,
                        filter=query_filter
                    )
                    span.set_data("event_count", len(all_events))

                self.logger.info(f"Fetched a total of {len(all_events)} Notion events via pagination from {database_id}.")
                return all_events

            except APIResponseError as error:
                # Use the error handler for Notion API errors
                return self.error_handler.handle_notion_error(error, context_data)
            except Exception as e:
                # Use the error handler for generic errors
                return self.error_handler.handle_generic_error(e, context_data)
            finally:
                self.error_handler.transaction = None # Clear transaction from handler if it was set


    def update_page_with_gcal_id(self, page_id: str, gcal_id: str, gcal_link: Optional[str] = None, parent_transaction=None) -> bool: # Accept parent transaction
        """Update Notion page with Google Calendar ID and optionally the HTML link."""
        op_name = "update_notion_page_gcal_id"
        self.error_handler.operation_name = op_name

        current_transaction = parent_transaction or start_transaction(op="notion", name=f"{op_name}_independent")

        # Use operation_span for this operation
        with operation_span(current_transaction, op="notion_api", description=op_name, logger=self.logger) as transaction: # Use operation_span
            context_data = {"notion_page_id": page_id, "gcal_id": gcal_id, "gcal_link": gcal_link}
            set_context("notion_update", context_data)
            # No need to set self.error_handler.transaction as it's not used within this method's error handling

            properties_to_update = {
                "gcal_id": { # Ensure this property name matches your Notion setup
                    "rich_text": [
                        {
                            "type": "text",
                            "text": {
                                "content": gcal_id
                            }
                        }
                    ]
                }
            }
            # Optionally add the Google Calendar link if provided
            if gcal_link:
                # Check if config has NOTION_GCAL_LINK_PROPERTY, otherwise skip adding the link
                gcal_link_property = getattr(config, 'NOTION_GCAL_LINK_PROPERTY', None)
                if gcal_link_property:
                    properties_to_update[gcal_link_property] = {
                        "url": gcal_link
                    }
                else:
                    self.logger.info(f"Skipping adding Google Calendar link to Notion page {page_id}: NOTION_GCAL_LINK_PROPERTY not configured")


            try:
                with operation_span(transaction, op="api_call", description="notion.pages.update", logger=self.logger) as span:
                    self.notion.pages.update(
                        page_id=page_id,
                        properties=properties_to_update
                    )
                    span.set_data("update_success", True)
                    self.logger.info(f"Successfully updated Notion page {page_id} with GCAL ID {gcal_id}" + (f" and link {gcal_link}" if gcal_link else ""))
                    return True

            except APIResponseError as e:
                # Log and capture directly as per strategy example (could also use handler)
                capture_exception(e)
                self.logger.error(f"Notion API error updating page {page_id} with GCAL ID {gcal_id}: {e.code} - {str(e)}")
                set_context("notion_error", {"code": e.code, "message": str(e), **context_data})
                transaction.set_status("internal_error")
                return False
            except Exception as e:
                 # Log and capture directly as per strategy example (could also use handler)
                capture_exception(e)
                self.logger.error(f"Unexpected error updating Notion page {page_id} with GCAL ID {gcal_id}: {str(e)}")
                set_context("unexpected_error", {"error": str(e), **context_data})
                transaction.set_status("internal_error")
                return False
            # No finally block needed here as we didn't assign transaction to handler in this method's scope