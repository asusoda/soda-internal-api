"""Google Calendar API client. An org can bring its own service account."""

from typing import Any

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from sentry_sdk import capture_exception, set_context, start_transaction

from core.config import config
from core.log import get_logger

from ..errors import APIErrorHandler
from ..tracing import operation_span

logger = get_logger(__name__)


def batch_operation(
    service: Any,
    operation_fn: Any,
    items: list[Any],
    calendar_id: str,
    batch_size: int = 900,
    description: str = "batch_operation",
    parent_transaction=None,
) -> tuple[int, int]:
    """Run operation_fn(service)(calendarId=calendar_id, eventId=item) for each item in Google batch requests.

    Sends at most batch_size requests in each batch. A batch that fails counts all its items as failed.
    Returns (successful, failed).
    """
    if not items:
        logger.info(f"No items to process in batch {description}.")
        return 0, 0

    successful = 0
    failed = 0

    def callback(request_id, response, exception):
        nonlocal successful, failed
        if exception:
            failed += 1
            capture_exception(exception)
            logger.error(f"Batch request {request_id} ({description}) failed: {exception}")
            set_context(f"batch_{description}_error", {"request_id": request_id, "error": str(exception)})
        else:
            successful += 1
            logger.debug(f"Batch request {request_id} ({description}) successful.")

    api_method = operation_fn(service)

    for i in range(0, len(items), batch_size):
        chunk = items[i : i + batch_size]
        if not chunk:
            continue

        batch = service.new_batch_http_request(callback=callback)
        logger.info(f"Preparing batch {description} for {len(chunk)} items (chunk {i // batch_size + 1})...")

        for item_id in chunk:
            request = api_method(calendarId=calendar_id, eventId=item_id)
            batch.add(request)

        try:
            logger.info(f"Executing batch {description} for chunk {i // batch_size + 1} ({len(chunk)} items).")
            batch.execute()
            logger.info(f"Batch chunk {i // batch_size + 1} executed for {description}.")
        except Exception as e:
            capture_exception(e)
            logger.error(f"Error executing batch {description} chunk {i // batch_size + 1}: {str(e)}")
            failed += len(chunk)
            set_context(
                f"batch_{description}_execution_error",
                {"chunk_index": i // batch_size + 1, "chunk_size": len(chunk), "error": str(e)},
            )

    logger.info(f"Batch {description} complete: {successful} successful, {failed} failed")
    return successful, failed


class GoogleCalendarClient:
    """Client for Google Calendar API operations."""

    SCOPES = ["https://www.googleapis.com/auth/calendar", "https://www.googleapis.com/auth/calendar.events"]

    def __init__(self, logger_instance=None, service_account_info: dict | None = None):
        self.logger = logger_instance or logger
        # build() adds the API methods at runtime, so the client has no static type
        self._service: Any = None
        # An org's own service account; None means the instance-wide GOOGLE_SERVICE_ACCOUNT.
        self.service_account_info = service_account_info
        self.error_handler = APIErrorHandler(self.logger, "GoogleCalendarClient")

    def get_service(self, parent_transaction=None) -> Any:
        """Get authenticated Google Calendar service with error handling."""
        if self._service:
            return self._service

        op_name = "get_calendar_service"
        self.error_handler.operation_name = op_name

        current_transaction = parent_transaction or start_transaction(op="google", name=f"{op_name}_independent")

        with operation_span(
            current_transaction, op="google_auth", description=op_name, logger=self.logger
        ) as transaction:
            self.error_handler.transaction = transaction
            try:
                info = config.GOOGLE_SERVICE_ACCOUNT if self.service_account_info is None else self.service_account_info
                set_context(
                    "google_api",
                    {
                        "scopes": self.SCOPES,
                        "service_account_provided": bool(info),
                        "org_service_account": self.service_account_info is not None,
                    },
                )

                if not info:
                    self.logger.error("Google Service Account configuration is missing.")
                    raise ValueError("Google Service Account configuration is missing.")

                with operation_span(
                    transaction, op="auth", description="create_credentials", logger=self.logger
                ) as span:
                    credentials = service_account.Credentials.from_service_account_info(
                        info,
                        scopes=self.SCOPES,
                    )
                    span.set_data("credentials_created", bool(credentials))

                with operation_span(transaction, op="build", description="build_service", logger=self.logger) as span:
                    self._service = build("calendar", "v3", credentials=credentials, cache_discovery=False)
                    span.set_data("service_created", bool(self._service))
                    self.logger.info("Google Calendar service initialized successfully.")
                    return self._service

            except ValueError as ve:
                self.logger.error(f"Configuration error during {op_name}: {ve}")
                capture_exception(ve)
                return None
            except Exception as e:
                return self.error_handler.handle_generic_error(e)
            finally:
                self.error_handler.transaction = None

    def create_event(
        self, calendar_id: str, event_data: dict, notion_page_id: str, parent_transaction=None
    ) -> tuple[str, str] | None:
        """Create calendar event with error handling. Returns (jump_url, gcal_event_id) or None."""
        op_name = "create_event"
        self.error_handler.operation_name = op_name

        current_transaction = parent_transaction or start_transaction(op="google", name=f"{op_name}_independent")

        with operation_span(
            current_transaction, op="google_api", description=op_name, logger=self.logger
        ) as transaction:
            self.error_handler.transaction = transaction
            service = self.get_service(parent_transaction=transaction)
            if not service:
                self.logger.error(f"{op_name}: Failed to get Google Calendar service.")
                return None

            event_data["extendedProperties"] = {"private": {"notionPageId": notion_page_id}}

            context_data = {
                "calendar_id": calendar_id,
                "notion_page_id": notion_page_id,
                "summary": event_data.get("summary", "Unknown Event"),
            }
            set_context("event_create", context_data)

            try:
                with operation_span(
                    transaction, op="api_call", description="events.insert", logger=self.logger
                ) as span:
                    self.logger.debug(
                        f"Attempting to create Google Calendar event for Notion ID {notion_page_id} with data: {event_data}"
                    )
                    created_event = service.events().insert(calendarId=calendar_id, body=event_data).execute()

                    gcal_event_id = created_event["id"]
                    jump_url = created_event.get("htmlLink")
                    span.set_data(
                        "event_details",
                        {
                            "gcal_id": gcal_event_id,
                            "summary": created_event.get("summary"),
                            "jump_url_present": bool(jump_url),
                        },
                    )

                    self.logger.info(
                        f"Created Google Calendar event: {gcal_event_id} for Notion page: {notion_page_id}"
                    )
                    return jump_url, gcal_event_id

            except HttpError as e:
                return self.error_handler.handle_http_error(e, context_data)
            except Exception as e:
                return self.error_handler.handle_generic_error(e, context_data)
            finally:
                self.error_handler.transaction = None

    def update_event(
        self, calendar_id: str, event_id: str, event_data: dict, notion_page_id: str, parent_transaction=None
    ) -> str | None:
        """Update calendar event with error handling. Returns jump_url or None."""
        op_name = "update_event"
        self.error_handler.operation_name = op_name

        current_transaction = parent_transaction or start_transaction(op="google", name=f"{op_name}_independent")

        with operation_span(
            current_transaction, op="google_api", description=op_name, logger=self.logger
        ) as transaction:
            self.error_handler.transaction = transaction
            service = self.get_service(parent_transaction=transaction)
            if not service:
                self.logger.error(f"{op_name}: Failed to get Google Calendar service.")
                return None

            if "extendedProperties" not in event_data:
                event_data["extendedProperties"] = {}
            if "private" not in event_data["extendedProperties"]:
                event_data["extendedProperties"]["private"] = {}
            event_data["extendedProperties"]["private"]["notionPageId"] = notion_page_id

            context_data = {
                "calendar_id": calendar_id,
                "event_id": event_id,
                "notion_page_id": notion_page_id,
                "summary": event_data.get("summary", "Unknown Event"),
            }
            set_context("event_update", context_data)

            try:
                with operation_span(
                    transaction, op="api_call", description="events.update", logger=self.logger
                ) as span:
                    self.logger.debug(
                        f"Attempting to update Google Calendar event {event_id} for Notion ID {notion_page_id} with data: {event_data}"
                    )
                    updated_event = (
                        service.events().update(calendarId=calendar_id, eventId=event_id, body=event_data).execute()
                    )

                    jump_url = updated_event.get("htmlLink")
                    span.set_data(
                        "event_details",
                        {
                            "id": updated_event["id"],
                            "summary": updated_event.get("summary"),
                            "status": "success",
                            "jump_url_present": bool(jump_url),
                        },
                    )
                    self.logger.info(
                        f"Updated Google Calendar event: {updated_event['id']} for Notion page: {notion_page_id}"
                    )
                    return jump_url

            except HttpError as e:
                return self.error_handler.handle_http_error(e, context_data)
            except Exception as e:
                return self.error_handler.handle_generic_error(e, context_data)
            finally:
                self.error_handler.transaction = None

    def get_all_events(
        self, calendar_id: str, time_min: str | None = None, parent_transaction=None
    ) -> list[dict] | None:
        """Get all events with pagination handling. Returns list of events or None on error."""
        op_name = "get_all_events"
        self.error_handler.operation_name = op_name

        current_transaction = parent_transaction or start_transaction(op="google", name=f"{op_name}_independent")

        with operation_span(
            current_transaction, op="google_api", description=op_name, logger=self.logger
        ) as transaction:
            self.error_handler.transaction = transaction
            service = self.get_service(parent_transaction=transaction)
            if not service:
                self.logger.error(f"{op_name}: Failed to get Google Calendar service.")
                return None

            all_events = []
            page_token = None
            context_data = {"calendar_id": calendar_id, "time_min": time_min}
            set_context("gcal_event_fetch", context_data)
            self.logger.info(
                f"Fetching events from calendar {calendar_id}"
                + (f" starting from {time_min}" if time_min else "")
                + "."
            )

            try:
                while True:
                    with operation_span(
                        transaction, op="list_page", description="events.list page", logger=self.logger
                    ) as span:
                        events_result = (
                            service.events()
                            .list(
                                calendarId=calendar_id,
                                singleEvents=True,
                                showDeleted=False,
                                pageToken=page_token,
                                timeMin=time_min,
                                maxResults=250,
                            )
                            .execute()
                        )

                        items = events_result.get("items", [])
                        all_events.extend(items)
                        page_token = events_result.get("nextPageToken")

                        span.set_data("page_event_count", len(items))
                        span.set_data("has_next_page", bool(page_token))

                        if not page_token:
                            break

                self.logger.info(f"Fetched a total of {len(all_events)} events from Google Calendar {calendar_id}.")
                transaction.set_data("total_fetched_events", len(all_events))
                return all_events

            except HttpError as e:
                return self.error_handler.handle_http_error(e, context_data)
            except Exception as e:
                return self.error_handler.handle_generic_error(e, context_data)
            finally:
                self.error_handler.transaction = None

    def batch_delete_events(
        self, calendar_id: str, event_ids: list[str], description: str = "batch_delete", parent_transaction=None
    ) -> tuple[int, int]:
        """Delete events in batches using the utility function."""
        op_name = f"batch_delete_{description}"
        self.error_handler.operation_name = op_name

        current_transaction = parent_transaction or start_transaction(op="google", name=f"{op_name}_independent")

        service = self.get_service(parent_transaction=current_transaction)
        if not service:
            self.logger.error(f"{op_name}: Failed to get Google Calendar service.")
            return 0, len(event_ids) if event_ids else 0

        if not event_ids:
            self.logger.info(f"{op_name}: No event IDs provided for deletion.")
            return 0, 0

        def delete_operation_fn(s):
            return s.events().delete

        with operation_span(
            current_transaction, op="google_batch", description=op_name, logger=self.logger
        ) as transaction:
            successful, failed = batch_operation(
                service=service,
                operation_fn=delete_operation_fn,
                items=event_ids,
                calendar_id=calendar_id,
                description=description,
                parent_transaction=transaction,
            )
            transaction.set_data("successful_deletions", successful)
            transaction.set_data("failed_deletions", failed)
            transaction.set_data("total_attempted", len(event_ids))

            return successful, failed

    def create_calendar(
        self,
        calendar_name: str,
        description: str | None = None,
        timezone: str = "America/Phoenix",
        parent_transaction=None,
    ) -> dict | None:
        """Create a new Google Calendar with error handling."""
        op_name = "create_calendar"
        self.error_handler.operation_name = op_name

        current_transaction = parent_transaction or start_transaction(op="google", name=f"{op_name}_independent")

        with operation_span(
            current_transaction, op="google_api", description=op_name, logger=self.logger
        ) as transaction:
            self.error_handler.transaction = transaction
            service = self.get_service(parent_transaction=transaction)
            if not service:
                self.logger.error(f"{op_name}: Failed to get Google Calendar service.")
                return None

            calendar_body = {"summary": calendar_name, "timeZone": timezone}

            if description:
                calendar_body["description"] = description

            try:
                with operation_span(
                    transaction, op="api_call", description="calendars.insert", logger=self.logger
                ) as span:
                    created_calendar = service.calendars().insert(body=calendar_body).execute()

                    calendar_id = created_calendar["id"]
                    span.set_data(
                        "calendar_details",
                        {
                            "calendar_id": calendar_id,
                            "summary": created_calendar.get("summary"),
                            "timezone": created_calendar.get("timeZone"),
                        },
                    )

                    self.logger.info(f"Successfully created calendar '{calendar_name}' with ID: {calendar_id}")
                    return created_calendar

            except Exception as e:
                return self.error_handler.handle_generic_error(e)
            finally:
                self.error_handler.transaction = None

    def get_calendar(self, calendar_id: str, parent_transaction=None) -> dict | None:
        """Get calendar details by ID."""
        op_name = "get_calendar"
        self.error_handler.operation_name = op_name

        current_transaction = parent_transaction or start_transaction(op="google", name=f"{op_name}_independent")

        with operation_span(
            current_transaction, op="google_api", description=op_name, logger=self.logger
        ) as transaction:
            self.error_handler.transaction = transaction
            service = self.get_service(parent_transaction=transaction)
            if not service:
                self.logger.error(f"{op_name}: Failed to get Google Calendar service.")
                return None

            try:
                with operation_span(
                    transaction, op="api_call", description="calendars.get", logger=self.logger
                ) as span:
                    calendar = service.calendars().get(calendarId=calendar_id).execute()
                    span.set_data("calendar_id", calendar_id)
                    return calendar

            except Exception as e:
                return self.error_handler.handle_generic_error(e)
            finally:
                self.error_handler.transaction = None

    def list_calendars(self, parent_transaction=None) -> list[dict] | None:
        """List all calendars accessible to the service account."""
        op_name = "list_calendars"
        self.error_handler.operation_name = op_name

        current_transaction = parent_transaction or start_transaction(op="google", name=f"{op_name}_independent")

        with operation_span(
            current_transaction, op="google_api", description=op_name, logger=self.logger
        ) as transaction:
            self.error_handler.transaction = transaction
            service = self.get_service(parent_transaction=transaction)
            if not service:
                self.logger.error(f"{op_name}: Failed to get Google Calendar service.")
                return None

            try:
                with operation_span(
                    transaction, op="api_call", description="calendarList.list", logger=self.logger
                ) as span:
                    calendar_list = service.calendarList().list().execute()
                    calendars = calendar_list.get("items", [])
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

        with operation_span(
            current_transaction, op="google_api", description=op_name, logger=self.logger
        ) as transaction:
            self.error_handler.transaction = transaction
            service = self.get_service(parent_transaction=transaction)
            if not service:
                self.logger.error(f"{op_name}: Failed to get Google Calendar service.")
                return False

            try:
                with operation_span(
                    transaction, op="api_call", description="calendars.delete", logger=self.logger
                ) as span:
                    service.calendars().delete(calendarId=calendar_id).execute()
                    span.set_data("calendar_id", calendar_id)
                    self.logger.warning(f"Successfully deleted calendar: {calendar_id}")
                    return True

            except Exception as e:
                return self.error_handler.handle_generic_error(e)
            finally:
                self.error_handler.transaction = None
