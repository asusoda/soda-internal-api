# modules/calendar/utils.py
import logging
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, List, Any, Tuple
import pytz

from sentry_sdk import capture_exception, set_context
from shared import config, logger # Assuming logger and config are available in shared

# If logger is not in shared, initialize it here:
# logger = logging.getLogger(__name__)

@contextmanager
def operation_span(transaction, op, description, logger=None):
    """Context manager for transaction spans with standardized logging."""
    # Ensure logger is available
    current_logger = logger if logger else logging.getLogger(__name__)

    span = transaction.start_child(op=op, description=description)
    try:
        yield span
    except Exception as e:
        current_logger.error(f"Error in operation {description}: {str(e)}")
        # Capture exception before setting data, in case set_data fails
        capture_exception(e)
        try:
            span.set_data("error", str(e))
            span.set_status("internal_error") # Set span status to error
        except Exception as data_err:
            current_logger.error(f"Failed to set error data on span {description}: {data_err}")
        raise # Re-raise the original exception
    finally:
        # Since we're no longer relying on parent transaction context managers,
        # we should explicitly finish the span here.
        try:
            span.finish()
        except Exception as finish_err:
            current_logger.error(f"Failed to finish span {description}: {finish_err}")
def batch_operation(service: Any, operation_fn: Any, items: List[Any], calendar_id: str, batch_size: int = 900, description: str = "batch_operation", parent_transaction=None) -> Tuple[int, int]: # Added parent_transaction
    """Generic batch operation handler for Google API calls.

    Args:
        service: Google API service object.
        operation_fn: Function that takes the service and returns the operation method
                      (e.g., lambda s: s.events().delete).
        items: List of items (e.g., event IDs) to process.
        calendar_id: The ID of the calendar for the operation.
        batch_size: Maximum batch size (stay under API limits).
        description: Description for logging and Sentry context.
        parent_transaction: Optional parent Sentry transaction (used for context).
        description: Description for logging and Sentry context.

    Returns:
        Tuple of (successful_count, failed_count).
    """
    if not items:
        logger.info(f"No items to process in batch {description}.")
        return 0, 0

    successful = 0
    failed = 0

    # Define the callback function locally
    def callback(request_id, response, exception):
        nonlocal successful, failed
        if exception:
            failed += 1
            capture_exception(exception)
            logger.error(f"Batch request {request_id} ({description}) failed: {exception}")
            set_context(f"batch_{description}_error", {
                "request_id": request_id,
                "error": str(exception)
            })
        else:
            successful += 1
            logger.debug(f"Batch request {request_id} ({description}) successful.")

    # Get the specific API operation method (e.g., service.events().delete)
    api_method = operation_fn(service)

    # Process in chunks to stay under API limits
    for i in range(0, len(items), batch_size):
        chunk = items[i:i + batch_size]
        if not chunk:
            continue

        batch = service.new_batch_http_request(callback=callback)
        logger.info(f"Preparing batch {description} for {len(chunk)} items (chunk {i // batch_size + 1})...")

        # Add requests to the batch based on the operation type
        # This assumes the operation needs calendarId and an item identifier (e.g., eventId)
        for item_id in chunk:
             # Example for delete: api_method(calendarId=calendar_id, eventId=item_id)
             # Adjust arguments based on the actual operation_fn provided
             request = api_method(calendarId=calendar_id, eventId=item_id)
             batch.add(request)


        try:
            logger.info(f"Executing batch {description} for chunk {i // batch_size + 1} ({len(chunk)} items).")
            batch.execute()
            logger.info(f"Batch chunk {i // batch_size + 1} executed for {description}.")
        except Exception as e:
            capture_exception(e)
            logger.error(f"Error executing batch {description} chunk {i // batch_size + 1}: {str(e)}")
            # If the whole batch execution fails, assume all items in the chunk failed
            failed += len(chunk)
            set_context(f"batch_{description}_execution_error", {
                "chunk_index": i // batch_size + 1,
                "chunk_size": len(chunk),
                "error": str(e)
            })

    logger.info(f"Batch {description} complete: {successful} successful, {failed} failed")
    return successful, failed


class DateParser:
    """Utilities for parsing and formatting dates."""

    @staticmethod
    def parse_notion_date(date_str: Optional[str]) -> Optional[Dict]:
        """Parse Notion date string into Google Calendar format.

        Handles both all-day ('YYYY-MM-DD') and specific time (ISO 8601) formats.

        Args:
            date_str: The date string from Notion (e.g., '2024-05-10' or '2024-05-10T10:00:00Z').

        Returns:
            A dictionary formatted for Google API ({"date": ...} or {"dateTime": ..., "timeZone": ...})
            or None if the input string is invalid or None.
        """
        if not date_str:
            return None

        # Clean the input string: remove leading/trailing whitespace and potential trailing commas
        cleaned_date_str = date_str.strip().rstrip(',')

        try:
            # Attempt to parse as just a date ('YYYY-MM-DD') first
            datetime.strptime(cleaned_date_str, '%Y-%m-%d')
            # If successful, it's an all-day date
            return {"date": cleaned_date_str} # Use the cleaned string
        except ValueError:
            # If date parse fails, attempt to parse as a full ISO 8601 dateTime string
            try:
                # Parse as ISO 8601 dateTime string, handling 'Z' for UTC
                dt_obj = datetime.fromisoformat(cleaned_date_str.replace('Z', '+00:00'))

                # Determine timezone string for Google Calendar API
                tz_info = dt_obj.tzinfo
                time_zone_str = None
                if tz_info:
                    # Try to get IANA name (e.g., 'America/Los_Angeles')
                    time_zone_str = getattr(tz_info, 'zone', None)
                    if not time_zone_str:
                        # If no IANA name, check if it's UTC
                        if tz_info.utcoffset(dt_obj) == timedelta(0):
                            time_zone_str = 'UTC'
                        # Otherwise, we might have a fixed offset timezone which Google Calendar might handle,
                        # but providing an IANA ID is preferred. Fallback to default if needed.
                        # For simplicity here, we'll use the default if no IANA name is found.
                        else:
                             time_zone_str = config.TIMEZONE # Fallback to default

                if not time_zone_str:
                     time_zone_str = config.TIMEZONE # Fallback if tzinfo was None

                return {
                    "dateTime": dt_obj.isoformat(), # Use standard ISO format
                    "timeZone": time_zone_str
                }
            except ValueError:
                # If both parsing attempts fail, log warning and return None
                logger.warning(f"Invalid or unsupported date format encountered after cleaning: '{cleaned_date_str}' (original: '{date_str}')")
                return None
            except Exception as e_iso:
                # Catch unexpected errors during ISO parsing
                logger.error(f"Unexpected error parsing ISO date string '{cleaned_date_str}': {str(e_iso)}")
                capture_exception(e_iso)
                return None
        except Exception as e_date:
            # Catch any other unexpected errors during date parsing
            logger.error(f"Unexpected error parsing date string '{date_str}': {str(e_date)}")
            capture_exception(e_date)
            return None

    @staticmethod
    def ensure_end_date(start_date_dict: Dict, end_date_dict: Optional[Dict] = None) -> Dict:
        """Ensure valid end date based on start date if end date is missing or invalid.

        Args:
            start_date_dict: Dictionary with 'date' or 'dateTime'/'timeZone' for start.
            end_date_dict: Optional dictionary with 'date' or 'dateTime'/'timeZone' for end.

        Returns:
            Dictionary with valid end date/time information.
        """
        # If a valid end_date_dict is provided, use it
        if end_date_dict and ('date' in end_date_dict or 'dateTime' in end_date_dict):
            return end_date_dict

        logger.debug(f"End date missing or invalid. Calculating based on start: {start_date_dict}")

        # Handle all-day events
        if 'date' in start_date_dict:
            try:
                start_date_obj = datetime.strptime(start_date_dict['date'], '%Y-%m-%d')
                # Google Calendar expects the end date for all-day events to be the day *after* the last day.
                end_date_obj = start_date_obj + timedelta(days=1)
                return {"date": end_date_obj.strftime('%Y-%m-%d')}
            except ValueError as e:
                logger.error(f"Error calculating end date for all-day event starting {start_date_dict['date']}: {e}")
                capture_exception(e)
                # Fallback: If calculation fails, return the start date dict (making it a single-day event)
                return start_date_dict.copy()

        # Handle datetime events (default 1-hour duration)
        elif 'dateTime' in start_date_dict:
            try:
                start_dt_iso = start_date_dict['dateTime']
                start_tz_str = start_date_dict.get('timeZone', config.TIMEZONE)

                # Parse the start dateTime string
                start_dt_aware = datetime.fromisoformat(start_dt_iso.replace('Z', '+00:00'))

                # Ensure timezone awareness using the provided/default timezone string if needed
                if start_dt_aware.tzinfo is None:
                    try:
                        tz_obj = pytz.timezone(start_tz_str)
                        start_dt_aware = tz_obj.localize(start_dt_aware)
                    except pytz.UnknownTimeZoneError:
                        logger.error(f"Timezone '{start_tz_str}' is invalid. Cannot localize naive datetime.")
                        # Fallback: Use start time as end time if timezone is invalid
                        return start_date_dict.copy()
                    except Exception as tz_err:
                         logger.error(f"Error applying timezone '{start_tz_str}': {tz_err}")
                         capture_exception(tz_err)
                         return start_date_dict.copy()


                # Default 1-hour duration
                end_dt_aware = start_dt_aware + timedelta(hours=1)

                # Use the same timezone as the start time
                end_tz_str = start_tz_str # Keep timezone consistent

                return {
                    "dateTime": end_dt_aware.isoformat(),
                    "timeZone": end_tz_str
                }
            except Exception as e:
                logger.error(f"Error calculating default end time for start {start_date_dict}: {e}")
                capture_exception(e)
                # Fallback: If calculation fails, return the start date dict
                return start_date_dict.copy()

        # Should not happen if start_date_dict is valid from parse_notion_date
        logger.error(f"Start date object is in an unexpected format: {start_date_dict}. Using start as end.")
        return start_date_dict.copy()


def extract_property(properties: Dict, name: str, prop_type: str) -> Optional[Any]:
    """Extract and parse content from Notion property based on its type.

    Args:
        properties: The dictionary of properties from a Notion page object.
        name: The name of the property to extract.
        prop_type: The expected type of the property (e.g., 'title', 'rich_text', 'select', 'date', 'checkbox').

    Returns:
        The parsed value of the property, or None if not found or on error.
        The return type depends on the prop_type (str, bool, dict, etc.).
    """
    try:
        prop_data = properties.get(name)
        if not prop_data:
            # logger.debug(f"Property '{name}' not found.")
            return None

        # Check the actual type stored in Notion data if available
        actual_type = prop_data.get('type')
        # if actual_type and actual_type != prop_type:
        #     logger.warning(f"Property '{name}' has type '{actual_type}' but expected '{prop_type}'. Attempting extraction anyway.")
            # Decide if you want to proceed or return None based on type mismatch

        if prop_type == 'title':
            title_array = prop_data.get('title', [])
            if not isinstance(title_array, list): return None
            return "".join(item.get('plain_text', '') for item in title_array).strip() or None
        elif prop_type == 'rich_text':
            rt_array = prop_data.get('rich_text', [])
            if not isinstance(rt_array, list): return None
            return "".join(item.get('plain_text', '') for item in rt_array).strip() or None
        elif prop_type == 'select':
            select_obj = prop_data.get('select')
            return select_obj.get('name') if isinstance(select_obj, dict) else None
        elif prop_type == 'checkbox':
            return prop_data.get('checkbox') # Returns True/False or None
        elif prop_type == 'date':
            # Return the raw date object for the DateParser to handle
            return prop_data.get('date') # Returns {'start': '...', 'end': '...', 'time_zone': '...'} or None
        elif prop_type == 'number':
            return prop_data.get('number')
        elif prop_type == 'url':
            return prop_data.get('url')
        elif prop_type == 'email':
            return prop_data.get('email')
        elif prop_type == 'phone_number':
            return prop_data.get('phone_number')
        # Add other Notion property types as needed:
        # 'multi_select', 'status', 'files', 'people', 'relation', 'formula', 'rollup', etc.
        else:
            logger.warning(f"Unhandled property type '{prop_type}' requested for property '{name}'.")
            return None

    except Exception as e:
        capture_exception(e)
        logger.error(f"Error extracting property '{name}' of type '{prop_type}': {str(e)}")
        set_context("property_error", {
            "property_name": name,
            "property_type": prop_type,
            "raw_data": properties.get(name),
            "error": str(e)
        })
        return None