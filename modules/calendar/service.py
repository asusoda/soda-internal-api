# modules/calendar/service.py
import logging
from typing import List, Dict, Optional, Any, Tuple
from datetime import datetime, timezone

from sentry_sdk import capture_exception, set_tag, set_context, start_transaction
from cachetools import TTLCache, cached, keys

# Assuming shared resources are correctly set up
from shared import config, logger

# Import custom modules
from .clients import GoogleCalendarClient, NotionCalendarClient
from .models import CalendarEventDTO
from .utils import operation_span
from .errors import APIErrorHandler # Import for potential direct use if needed
from googleapiclient.errors import HttpError # Import HttpError for specific handling

# If logger is not in shared, initialize it here:
# logger = logging.getLogger(__name__)

# Create a global cache for the frontend events with a 5-minute TTL
_FRONTEND_CACHE = TTLCache(maxsize=1, ttl=300)

class CalendarService:
    """Service layer for calendar operations involving Notion and Google Calendar."""

    def __init__(self, logger_instance=None):
        self.logger = logger_instance or logger
        self.gcal_client = GoogleCalendarClient(self.logger)
        self.notion_client = NotionCalendarClient(self.logger)
        # Optional: Initialize error handler for service-level errors if needed
        # self.error_handler = APIErrorHandler(self.logger, "CalendarService")

    def parse_notion_events(self, notion_events_raw: List[Dict]) -> List[CalendarEventDTO]:
        """Parse raw Notion events into CalendarEventDTO objects."""
        parsed_events = []
        failed_count = 0
        if not notion_events_raw:
            return []

        # Use a transaction span if called within a larger transaction context
        # This assumes parse_notion_events is called within an existing transaction (like sync)
        # If it can be called independently, it might need its own transaction start.
        # For now, assume it's part of a larger flow.
        # with start_transaction(op="parse", name="parse_all_notion_events") as transaction:
        #     transaction.set_data("raw_event_count", len(notion_events_raw))

        self.logger.info(f"Parsing {len(notion_events_raw)} raw Notion events.")
        for event_data in notion_events_raw:
            # The DTO's from_notion method handles parsing and logging errors for individual events
            parsed_dto = CalendarEventDTO.from_notion(event_data)
            if parsed_dto:
                parsed_events.append(parsed_dto)
            else:
                failed_count += 1
                # Error/warning is logged within from_notion

        self.logger.info(f"Successfully parsed {len(parsed_events)} events, failed to parse {failed_count}.")
        # Set context within the calling transaction if available
        set_context("parse_results", {
            "successful_parses": len(parsed_events),
            "failed_parses": failed_count,
            "total_raw_events": len(notion_events_raw)
        })
        return parsed_events


    def update_google_calendar(self, parsed_notion_dtos: List[CalendarEventDTO], transaction) -> List[Dict]:
        """
        Updates Google Calendar based on a list of parsed Notion Event DTOs.
        Handles creation, updates, and deletion of GCal events to match Notion state.

        Args:
            parsed_notion_dtos: List of CalendarEventDTO objects from Notion.
            transaction: The active Sentry transaction.

        Returns:
            List of dictionaries representing processed events (e.g., {"summary": ..., "jump_url": ...}).
        """
        results = []
        op_name = "update_google_calendar"
        self.logger.info(f"Starting {op_name} with {len(parsed_notion_dtos)} parsed Notion events.")

        # 1. Fetch existing Google Calendar events that might be relevant
        # Fetch events potentially created by this sync (e.g., future events)
        # Using time_min='now' helps limit the scope but might miss past events if needed.
        # Consider fetching all events if full past sync is required.
        now_utc_iso = datetime.now(timezone.utc).isoformat()
        with operation_span(transaction, op="fetch_gcal", description="fetch_existing_gcal_events", logger=self.logger) as span:
            # Fetch all events managed by this sync (identified by notionPageId property)
            # We need to fetch all, then filter, as GCal API doesn't filter on extendedProperties directly.
            all_gcal_events_raw = self.gcal_client.get_all_events(config.GOOGLE_CALENDAR_ID, time_min=None, parent_transaction=transaction) # Pass transaction
            if all_gcal_events_raw is None:
                self.logger.error(f"{op_name}: Failed to fetch existing Google Calendar events. Aborting update.")
                # Set transaction status?
                transaction.set_status("internal_error")
                return [] # Cannot proceed without existing events

            # Filter for events managed by this sync
            managed_gcal_events = [
                ev for ev in all_gcal_events_raw
                if ev.get('extendedProperties', {}).get('private', {}).get('notionPageId')
            ]
            span.set_data("fetched_total_gcal_event_count", len(all_gcal_events_raw))
            span.set_data("fetched_managed_gcal_event_count", len(managed_gcal_events))
            self.logger.info(f"Fetched {len(managed_gcal_events)} managed GCal events (out of {len(all_gcal_events_raw)} total).")


        # 2. Build lookup dictionaries for GCal events & handle duplicates
        gcal_events_by_gcal_id: Dict[str, Dict] = {}
        gcal_events_by_notion_id: Dict[str, Dict] = {} # Store only the *one* event to keep per Notion ID
        duplicates_to_delete: set[str] = set()

        with operation_span(transaction, op="process_gcal", description="build_gcal_lookups_handle_duplicates", logger=self.logger) as span:
            temp_gcal_by_notion_id: Dict[str, List[Dict]] = {} # Temporary store for finding duplicates

            for event in managed_gcal_events:
                gcal_id = event.get('id')
                notion_page_id = event.get('extendedProperties', {}).get('private', {}).get('notionPageId')

                if not gcal_id or not notion_page_id:
                    self.logger.warning(f"Skipping GCal event due to missing ID ('{gcal_id}') or Notion Page ID ('{notion_page_id}'). Summary: '{event.get('summary')}'")
                    continue # Skip events missing critical identifiers

                gcal_events_by_gcal_id[gcal_id] = event

                if notion_page_id not in temp_gcal_by_notion_id:
                    temp_gcal_by_notion_id[notion_page_id] = []
                temp_gcal_by_notion_id[notion_page_id].append(event)

            # Identify and mark duplicates for deletion
            for notion_id, events in temp_gcal_by_notion_id.items():
                if len(events) > 1:
                    sorted_events = sorted(events, key=lambda e: e.get('updated', ''), reverse=True)
                    kept_event = sorted_events[0]
                    gcal_events_by_notion_id[notion_id] = kept_event # Keep the most recent
                    duplicate_ids_to_delete_list = [d['id'] for d in sorted_events[1:]] # Explicit list
                    for dup_id in duplicate_ids_to_delete_list:
                        duplicates_to_delete.add(dup_id)
                    self.logger.warning(
                        f"Found {len(events)-1} duplicate GCal events for Notion ID {notion_id}. "
                        f"Keeping event ID: {kept_event['id']} (summary: '{kept_event.get('summary')}', updated: {kept_event.get('updated')}). "
                        f"Marking for deletion IDs: {duplicate_ids_to_delete_list}" # Log the list
                    )
                elif events:
                    gcal_events_by_notion_id[notion_id] = events[0] # Only one event

            span.set_data("unique_notion_ids_in_gcal", len(gcal_events_by_notion_id))
            span.set_data("duplicates_marked_for_deletion", len(duplicates_to_delete))


        # 3. Build lookup for parsed Notion DTOs
        notion_dtos_by_id: Dict[str, CalendarEventDTO] = {
            dto.notion_page_id: dto for dto in parsed_notion_dtos
        }
        self.logger.info(f"Built lookup for {len(notion_dtos_by_id)} unique Notion event DTOs.")

        # 4. Process Notion DTOs: Create or Update GCal events
        processed_gcal_ids: set[str] = set() # Track GCal events processed (updated/confirmed)
        created_count = 0
        updated_count = 0
        failed_count = 0

        with operation_span(transaction, op="sync_to_gcal", description="create_update_gcal_events", logger=self.logger) as sync_span:
            for notion_page_id, notion_dto in notion_dtos_by_id.items():
                gcal_payload = notion_dto.to_gcal_format()
                existing_gcal_event = gcal_events_by_notion_id.get(notion_page_id)

                try:
                    if existing_gcal_event:
                        # --- Update Existing Event ---
                        existing_gcal_id = existing_gcal_event['id']
                        # Simple check: Only update if necessary? (Requires comparing payloads, complex)
                        # For simplicity, update always for now. Add change detection later if needed.
                        self.logger.info(f"Updating GCal event {existing_gcal_id} for Notion page {notion_page_id} ('{notion_dto.summary}').")
                        jump_url = self.gcal_client.update_event(
                            calendar_id=config.GOOGLE_CALENDAR_ID,
                            event_id=existing_gcal_id,
                            event_data=gcal_payload,
                            notion_page_id=notion_page_id,
                            parent_transaction=transaction # Pass transaction
                        )
                        if jump_url:
                            results.append({"summary": notion_dto.summary, "status": "updated", "jump_url": jump_url, "notion_page_id": notion_page_id})
                            updated_count += 1
                        else:
                            # Error handled and logged within gcal_client.update_event
                            results.append({"summary": notion_dto.summary, "status": "update_failed", "notion_page_id": notion_page_id})
                            failed_count += 1
                        processed_gcal_ids.add(existing_gcal_id) # Mark as processed
                    else:
                        # --- Create New Event ---
                        self.logger.info(f"Creating new GCal event for Notion page {notion_page_id} ('{notion_dto.summary}').")
                        create_result = self.gcal_client.create_event(
                            calendar_id=config.GOOGLE_CALENDAR_ID,
                            event_data=gcal_payload,
                            notion_page_id=notion_page_id,
                            parent_transaction=transaction # Pass transaction
                        )
                        if create_result:
                            jump_url, new_gcal_id = create_result
                            results.append({"summary": notion_dto.summary, "status": "created", "jump_url": jump_url, "gcal_id": new_gcal_id, "notion_page_id": notion_page_id})
                            created_count += 1
                            # Update Notion back with the new GCal ID and link
                            self.notion_client.update_page_with_gcal_id(notion_page_id, new_gcal_id, jump_url, parent_transaction=transaction) # Pass transaction
                            # Note: The new event isn't in our initial fetch, so no need to add to processed_gcal_ids
                        else:
                            # Error handled and logged within gcal_client.create_event
                            results.append({"summary": notion_dto.summary, "status": "create_failed", "notion_page_id": notion_page_id})
                            failed_count += 1

                except Exception as e:
                    # Catch unexpected errors during the create/update loop for a specific event
                    capture_exception(e)
                    self.logger.error(f"Unexpected error processing Notion event {notion_page_id} ('{notion_dto.summary}') for GCal update: {e}")
                    results.append({"summary": notion_dto.summary, "status": "processing_error", "error": str(e), "notion_page_id": notion_page_id})
                    failed_count += 1
                    # Ensure the corresponding GCal event (if exists) isn't marked as processed if we failed
                    if existing_gcal_event and existing_gcal_event['id'] in processed_gcal_ids:
                         processed_gcal_ids.remove(existing_gcal_event['id'])


            sync_span.set_data("created_count", created_count)
            sync_span.set_data("updated_count", updated_count)
            sync_span.set_data("failed_count", failed_count)
            self.logger.info(f"GCal sync process: {created_count} created, {updated_count} updated, {failed_count} failed.")


        # 5. Handle Deletions: Delete GCal events that are duplicates, orphaned, or unmanaged
        #    (Assumes this GCal is exclusively managed by this Notion sync)
        ids_to_delete: set[str] = set(duplicates_to_delete) # Start with known duplicates from managed events
        orphaned_or_unmanaged_count = 0

        with operation_span(transaction, op="deletion_check", description="check_for_deleted_or_unmanaged_events", logger=self.logger) as del_check_span:
            current_notion_ids = set(notion_dtos_by_id.keys())
            # Iterate through ALL events fetched from the calendar, not just managed ones identified earlier
            self.logger.info(f"Checking {len(all_gcal_events_raw)} total fetched GCal events against {len(current_notion_ids)} current Notion events for deletions (strict sync).")

            for gcal_event in all_gcal_events_raw: # Iterate through ALL raw events
                gcal_id = gcal_event.get('id')
                if not gcal_id:
                    self.logger.warning(f"Skipping GCal event during deletion check due to missing ID. Summary: '{gcal_event.get('summary')}'")
                    continue # Cannot delete without an ID

                if gcal_id in ids_to_delete:
                    continue # Already marked as duplicate among managed events

                notion_page_id = gcal_event.get('extendedProperties', {}).get('private', {}).get('notionPageId')
                summary = gcal_event.get('summary', 'Unknown Event')

                # Check if the event should exist based on Notion data
                should_delete = False
                if notion_page_id:
                    # It's a managed event, check if its Notion counterpart is gone
                    if notion_page_id not in current_notion_ids:
                        self.logger.info(
                            f"Marking managed GCal event '{summary}' (ID: {gcal_id}, linked Notion ID: {notion_page_id}) "
                            f"for deletion because its Notion event is missing or unpublished in the current fetch."
                        )
                        should_delete = True
                else:
                    # It's an unmanaged event (no notionPageId), delete it as the calendar should be exclusive
                    self.logger.info(
                        f"Marking unmanaged GCal event '{summary}' (ID: {gcal_id}) for deletion "
                        f"because it lacks a notionPageId and the calendar is treated as exclusive."
                    )
                    should_delete = True

                if should_delete:
                    ids_to_delete.add(gcal_id)
                    orphaned_or_unmanaged_count += 1

            del_check_span.set_data("total_to_delete", len(ids_to_delete))
            # Note: This count now includes duplicates, orphans, and unmanaged events
            del_check_span.set_data("orphaned_or_unmanaged_deletions", orphaned_or_unmanaged_count)
            del_check_span.set_data("duplicate_deletions", len(duplicates_to_delete)) # This remains the count of duplicates specifically identified earlier


        # 6. Execute Batch Deletion
        if ids_to_delete:
            # Convert set to list for logging and API call
            event_ids_list = list(ids_to_delete)
            self.logger.info(f"Attempting to batch delete {len(event_ids_list)} GCal events (duplicates/orphaned). IDs: {event_ids_list}")
            # The batch_delete_events method handles its own transaction span internally
            successful_deletions, failed_deletions = self.gcal_client.batch_delete_events(
                calendar_id=config.GOOGLE_CALENDAR_ID,
                event_ids=event_ids_list, # Pass the list
                description="sync_cleanup",
                parent_transaction=transaction # Pass transaction
            )
            # Log results of deletion
            self.logger.info(f"Batch deletion result: {successful_deletions} successful, {failed_deletions} failed.")
            # Optionally add deletion results to the main transaction context
            transaction.set_data("deletion_results", {
                 "attempted": len(ids_to_delete),
                 "successful": successful_deletions,
                 "failed": failed_deletions
            })
        else:
            self.logger.info("No GCal events marked for deletion.")

        self.logger.info(f"Finished {op_name}.")
        return results # Return the list of create/update results


    def clear_synced_events(self, transaction) -> Tuple[int, int]:
        """
        Clears all Google Calendar events previously synced from Notion.
        Fetches all events with the notionPageId property and deletes them.

        Args:
            transaction: The active Sentry transaction.

        Returns:
            Tuple of (successful_deletions, failed_deletions).
        """
        op_name = "clear_synced_events"
        self.logger.warning(f"Starting {op_name}: Clearing all Notion-synced events from Google Calendar {config.GOOGLE_CALENDAR_ID}.")
        successful_deletions = 0
        failed_deletions = 0

        with operation_span(transaction, op="clear_gcal", description="fetch_and_delete_synced_events", logger=self.logger) as span:
            # 1. Fetch all GCal events (no time filter needed for full clear)
            all_gcal_events_raw = self.gcal_client.get_all_events(config.GOOGLE_CALENDAR_ID, time_min=None, parent_transaction=transaction) # Pass transaction

            if all_gcal_events_raw is None:
                self.logger.error(f"{op_name}: Failed to fetch Google Calendar events for clearing.")
                span.set_status("internal_error")
                # Cannot determine how many failed if fetch failed. Return 0, -1?
                return 0, -1 # Indicate fetch failure

            # 2. Filter for events managed by this sync
            synced_event_ids_to_delete = [
                ev['id'] for ev in all_gcal_events_raw
                if ev.get('id') and ev.get('extendedProperties', {}).get('private', {}).get('notionPageId')
            ]
            span.set_data("synced_events_found_for_deletion", len(synced_event_ids_to_delete))

            if not synced_event_ids_to_delete:
                self.logger.info(f"{op_name}: No synced events found to clear.")
                return 0, 0

            # 3. Execute Batch Deletion
            self.logger.info(f"{op_name}: Attempting to batch delete {len(synced_event_ids_to_delete)} synced GCal events.")
            successful_deletions, failed_deletions = self.gcal_client.batch_delete_events(
                calendar_id=config.GOOGLE_CALENDAR_ID,
                event_ids=synced_event_ids_to_delete,
                description="clear_all_synced",
                parent_transaction=transaction # Pass transaction
            )
            span.set_data("successful_deletions", successful_deletions)
            span.set_data("failed_deletions", failed_deletions)

            self.logger.warning(f"{op_name} finished. Deleted: {successful_deletions}, Failed: {failed_deletions}.")
            return successful_deletions, failed_deletions


    def sync_notion_to_google(self, transaction=None) -> Dict[str, Any]:
        """
        Orchestrates the full sync process from Notion to Google Calendar.

        Args:
            transaction: Optional existing Sentry transaction.

        Returns:
            A dictionary containing the status and results of the sync.
        """
        op_name = "sync_notion_to_google"
        # Start a new transaction if one isn't provided
        own_transaction = transaction is None
        if own_transaction:
            transaction = start_transaction(op="sync", name=op_name)

        result = {
            "status": "success",
            "message": "",
            "events_processed": [],
            "details": {}
        }

        try:
            # Don't use with transaction: if passed from API route
            # This avoids the AttributeError: 'Transaction' object has no attribute '_context_manager_state'
                # 1. Fetch Notion events
                with operation_span(transaction, op="fetch_notion", description="fetch_published_notion_events", logger=self.logger) as span:
                    notion_events_raw = self.notion_client.fetch_events(config.NOTION_DATABASE_ID, parent_transaction=transaction) # Pass transaction
                    # fetch_events returns None on error, list (possibly empty) on success
                    if notion_events_raw is not None:
                         span.set_data("fetched_notion_event_count", len(notion_events_raw))
                    else:
                         span.set_status("internal_error")


                # 2. Handle Notion fetch results
                if notion_events_raw is None:
                    result["status"] = "error"
                    result["message"] = "Failed to fetch events from Notion. Sync aborted."
                    self.logger.error(f"{op_name}: Notion fetch failed. Skipping GCal update/clear.")
                    set_tag("sync_status", "notion_fetch_failed")
                    transaction.set_status("internal_error")
                    return result

                elif not notion_events_raw:
                    # No published events in Notion, clear GCal
                    self.logger.warning(f"{op_name}: No published events found in Notion. Clearing synced events from Google Calendar.")
                    set_tag("sync_status", "no_notion_events_clearing_gcal")
                    # clear_synced_events handles its own span within the transaction
                    deleted_count, failed_count = self.clear_synced_events(transaction)
                    result["message"] = f"Successfully fetched 0 events from Notion. Cleared {deleted_count} events from Google Calendar (failed: {failed_count})."
                    result["details"]["cleared_count"] = deleted_count
                    result["details"]["clear_failed_count"] = failed_count
                    # Status remains 'success' as the operation completed, even if nothing synced.
                    return result

                # 3. Parse Notion events
                # parse_notion_events handles its own logging/context setting
                parsed_dtos = self.parse_notion_events(notion_events_raw)
                result["details"]["parsed_count"] = len(parsed_dtos)
                result["details"]["parse_failed_count"] = len(notion_events_raw) - len(parsed_dtos)

                if not parsed_dtos:
                     # Parsing failed for all events, maybe clear GCal? Or report error?
                     # Let's clear GCal similar to the 'no events' case for consistency.
                     self.logger.warning(f"{op_name}: Failed to parse any valid events from {len(notion_events_raw)} raw Notion events. Clearing synced events from Google Calendar.")
                     set_tag("sync_status", "all_parse_failed_clearing_gcal")
                     deleted_count, failed_count = self.clear_synced_events(transaction)
                     result["status"] = "warning" # Indicate potential issue
                     result["message"] = f"Failed to parse any valid events from Notion. Cleared {deleted_count} events from Google Calendar (failed: {failed_count})."
                     result["details"]["cleared_count"] = deleted_count
                     result["details"]["clear_failed_count"] = failed_count
                     return result


                # 4. Update Google Calendar
                # update_google_calendar handles its own spans within the transaction
                update_results = self.update_google_calendar(parsed_dtos, transaction)
                result["events_processed"] = update_results
                result["message"] = f"Calendar sync complete. Processed {len(update_results)} events."
                result["details"]["gcal_processed_count"] = len(update_results)
                # Add counts from update_results if needed (created, updated, failed)

                self.logger.info(f"{op_name} completed successfully.")
                set_tag("sync_status", "success")
                # Only finish the transaction if we created it
                if own_transaction and transaction:
                    transaction.finish()
                return result

        except Exception as e:
            capture_exception(e)
            self.logger.exception(f"Critical error during {op_name}: {e}") # Use logger.exception for stack trace
            result["status"] = "error"
            result["message"] = f"An unexpected error occurred during sync: {str(e)}"
            set_tag("sync_status", "critical_error")
            if transaction:
                 transaction.set_status("internal_error")
                 # Only finish the transaction if we created it
                 if own_transaction:
                     transaction.finish(exception=e)
            return result

    # Cache results for 5 minutes using class-level cache
    @cached(cache=_FRONTEND_CACHE, key=lambda self, transaction=None: keys.hashkey(id(self)))
    def get_events_for_frontend(self, transaction=None) -> Dict[str, Any]:
        """Fetches and formats Notion events for frontend display. Results are cached for 5 minutes in class-level cache."""
        op_name = "get_events_for_frontend"
        # This log message will only appear on cache misses
        self.logger.info("Cache miss for get_events_for_frontend. Fetching fresh data.")
        own_transaction = transaction is None
        if own_transaction:
            transaction = start_transaction(op="api", name=op_name)

        result = {"status": "success", "events": []}

        try:
            # Don't use with transaction: if passed from API route
            # This avoids the AttributeError: 'Transaction' object has no attribute '_context_manager_state'
            # 1. Fetch Notion events
            with operation_span(transaction, op="fetch_notion", description="fetch_published_notion_events", logger=self.logger) as span:
                notion_events_raw = self.notion_client.fetch_events(config.NOTION_DATABASE_ID, parent_transaction=transaction) # Pass transaction
                if notion_events_raw is None:
                    span.set_status("internal_error")
                    result["status"] = "error"
                    result["message"] = "Failed to fetch events from Notion."
                    self.logger.error(f"{op_name}: Notion fetch failed.")
                    return result
                span.set_data("fetched_notion_event_count", len(notion_events_raw))

            # 2. Parse Notion events
            # parse_notion_events handles its own logging/context
            parsed_dtos = self.parse_notion_events(notion_events_raw)

            # 3. Format for Frontend
            with operation_span(transaction, op="format", description="format_dtos_for_frontend", logger=self.logger) as span:
                frontend_events = [dto.to_frontend_format() for dto in parsed_dtos]
                result["events"] = frontend_events
                span.set_data("formatted_event_count", len(frontend_events))

            self.logger.info(f"{op_name}: Successfully fetched and formatted {len(frontend_events)} events.")
            # Only finish the transaction if we created it
            if own_transaction and transaction:
                transaction.finish()
            return result

        except Exception as e:
            capture_exception(e)
            self.logger.exception(f"Error during {op_name}: {e}")
            result["status"] = "error"
            result["message"] = f"An unexpected error occurred: {str(e)}"
            if transaction:
                transaction.set_status("internal_error")
                # Only finish the transaction if we created it
                if own_transaction:
                    transaction.finish(exception=e)
            return result


    def delete_all_events(self, transaction=None) -> Dict[str, Any]:
        """
        Deletes ALL events from the configured Google Calendar. Includes safety check.

        Args:
            transaction: Optional existing Sentry transaction.

        Returns:
            A dictionary containing the status and results of the deletion.
        """
        op_name = "delete_all_gcal_events"
        own_transaction = transaction is None
        if own_transaction:
            transaction = start_transaction(op="admin", name=op_name)

        result = {"status": "success", "message": "", "deleted_count": 0, "errors": 0}
        self.logger.warning(f"Received request for {op_name}. THIS IS A DESTRUCTIVE OPERATION.")

        try:
            # Don't use with transaction: if passed from API route
            # This avoids the AttributeError: 'Transaction' object has no attribute '_context_manager_state'
                # --- SAFETY CHECK ---
                if not getattr(config, 'ALLOW_DELETE_ALL', False):
                    self.logger.error(f"{op_name} prevented by configuration (ALLOW_DELETE_ALL is not True).")
                    set_tag("delete_all_status", "prevented_by_config")
                    transaction.set_status("permission_denied")
                    result["status"] = "error"
                    result["message"] = "Operation prevented by server configuration."
                    return result

                self.logger.warning(f"{op_name}: ALLOW_DELETE_ALL is True. Proceeding with deletion for calendar: {config.GOOGLE_CALENDAR_ID}")
                set_context("delete_all", {"calendar_id": config.GOOGLE_CALENDAR_ID, "safety_check_passed": True})

                # Get GCal Service once
                service = self.gcal_client.get_service(parent_transaction=transaction) # Pass transaction
                if not service:
                    self.logger.error(f"{op_name}: Failed to get GCal service for deletion.")
                    transaction.set_status("internal_error")
                    result["status"] = "error"
                    result["message"] = "Failed to get Google Calendar service."
                    return result

                # 1. Fetch all event IDs
                all_event_ids = []
                fetch_errors = 0
                with operation_span(transaction, op="fetch_ids", description="fetch_all_gcal_event_ids", logger=self.logger) as fetch_span:
                    # Need to paginate through list results to get all IDs
                    page_token = None
                    while True:
                        try:
                            events_result = service.events().list(
                                calendarId=config.GOOGLE_CALENDAR_ID,
                                pageToken=page_token,
                                fields="nextPageToken,items(id)" # Only fetch IDs
                            ).execute()
                            items = events_result.get('items', [])
                            all_event_ids.extend([item['id'] for item in items])
                            page_token = events_result.get('nextPageToken')
                            if not page_token:
                                break
                        except HttpError as e:
                            fetch_errors += 1
                            self.logger.error(f"HTTP error fetching event page for deletion: {e.resp.status} - {e.error_details}")
                            if e.resp.status in [403, 404]: raise # Re-raise critical errors
                            break # Stop fetching on other errors for now
                        except Exception as e:
                            fetch_errors += 1
                            self.logger.error(f"Unexpected error fetching event page for deletion: {str(e)}")
                            # Capture and potentially re-raise or break
                            capture_exception(e)
                            raise # Re-raise to stop the process if fetching fails critically

                    fetch_span.set_data("fetched_ids_count", len(all_event_ids))
                    fetch_span.set_data("fetch_errors", fetch_errors)
                    self.logger.info(f"{op_name}: Fetched {len(all_event_ids)} event IDs to delete.")

                if not all_event_ids:
                    result["message"] = "No events found in the calendar to delete."
                    set_tag("delete_all_status", "no_events_found")
                    return result

                # 2. Batch delete events
                # batch_delete_events handles its own transaction span
                successful_deletions, failed_deletions = self.gcal_client.batch_delete_events(
                    calendar_id=config.GOOGLE_CALENDAR_ID,
                    event_ids=all_event_ids,
                    description="admin_delete_all",
                    parent_transaction=transaction # Pass transaction
                )

                result["deleted_count"] = successful_deletions
                result["errors"] = failed_deletions
                transaction.set_data("deletion_results", {"successful": successful_deletions, "failed": failed_deletions, "total_attempted": len(all_event_ids)})

                if failed_deletions > 0:
                    result["status"] = "partial_error"
                    result["message"] = f"Attempted to delete {len(all_event_ids)} events. Successfully deleted {successful_deletions}, encountered {failed_deletions} errors."
                    set_tag("delete_all_status", "partial_error")
                else:
                    result["message"] = f"Successfully deleted {successful_deletions} events."
                    set_tag("delete_all_status", "success")

                # Only finish the transaction if we created it
                if own_transaction and transaction:
                    transaction.finish()
                return result

        except Exception as e:
            capture_exception(e)
            self.logger.exception(f"Critical error during {op_name}: {e}")
            result["status"] = "error"
            result["message"] = f"An unexpected critical error occurred: {str(e)}"
            set_tag("delete_all_status", "critical_error")
            if transaction:
                transaction.set_status("internal_error")
                # Only finish the transaction if we created it
                if own_transaction:
                    transaction.finish(exception=e)
            return result