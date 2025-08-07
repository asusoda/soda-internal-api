# modules/calendar/service.py
import logging
from typing import List, Dict, Optional, Any, Tuple
from datetime import datetime, timezone

from sentry_sdk import capture_exception, set_tag, set_context, start_transaction
from cachetools import TTLCache, cached, keys

# Assuming shared resources are correctly set up
from shared import config, logger, db_connect

# Import custom modules
from .clients import GoogleCalendarClient, NotionCalendarClient
from .models import CalendarEventDTO
from .utils import operation_span
from .errors import APIErrorHandler
from googleapiclient.errors import HttpError

# Import organization models
from modules.organizations.models import Organization

# Create a global cache for the frontend events with a 5-minute TTL
_FRONTEND_CACHE = TTLCache(maxsize=100, ttl=300)  # Increased maxsize for multiple orgs

class MultiOrgCalendarService:
    """Service layer for multi-organization calendar operations."""

    def __init__(self, logger_instance=None):
        self.logger = logger_instance or logger
        self.gcal_client = GoogleCalendarClient(self.logger)
        self.notion_client = NotionCalendarClient(self.logger)
        self.db_connect = db_connect
        
    def ensure_organization_calendar(self, organization_id: int, organization_name: str, parent_transaction=None) -> Optional[str]:
        """Ensure a Google Calendar exists for the organization, create if needed."""
        op_name = "ensure_organization_calendar"
        
        current_transaction = parent_transaction or start_transaction(op="calendar", name=op_name)
        
        with operation_span(current_transaction, op="org_calendar", description=op_name, logger=self.logger) as transaction:
            
            try:
                # Get organization from database
                db = next(self.db_connect.get_db())
                org = db.query(Organization).filter(Organization.id == organization_id).first()
                if not org:
                    self.logger.error(f"Organization {organization_id} not found")
                    return None
                
                # If organization already has a calendar, return it
                if org.google_calendar_id:
                    self.logger.info(f"Organization {organization_id} already has calendar: {org.google_calendar_id}")
                    return org.google_calendar_id
                
                # Create new calendar for organization
                calendar_name = f"{organization_name} Events"
                calendar_description = f"Events for {organization_name} organization"
                
                calendar_data = self.gcal_client.create_calendar(
                    calendar_name=calendar_name,
                    description=calendar_description,
                    timezone=config.TIMEZONE,
                    parent_transaction=transaction
                )
                
                if calendar_data:
                    calendar_id = calendar_data['id']
                    
                    # Update organization with new calendar ID
                    org.google_calendar_id = calendar_id
                    db.commit()
                    
                    self.logger.info(f"Created calendar {calendar_id} for organization {organization_id}")
                    return calendar_id
                else:
                        self.logger.error(f"Failed to create calendar for organization {organization_id}")
                        return None
                    
            except Exception as e:
                self.logger.error(f"Error ensuring organization calendar: {e}")
                return None
            finally:
                if transaction:
                    transaction.finish()
    
    def sync_organization_notion_to_google(self, organization_id: int, parent_transaction=None) -> Dict[str, Any]:
        """Sync Notion events to Google Calendar for a specific organization."""
        op_name = "sync_organization_notion_to_google"
        
        current_transaction = parent_transaction or start_transaction(op="calendar", name=op_name)
        
        with operation_span(current_transaction, op="org_sync", description=op_name, logger=self.logger) as transaction:
            try:
                # Get organization
                db = next(self.db_connect.get_db())
                org = db.query(Organization).filter(Organization.id == organization_id).first()
                if not org:
                    return {"status": "error", "message": f"Organization {organization_id} not found"}
                
                if not org.notion_database_id:
                    return {"status": "error", "message": f"Organization {organization_id} has no Notion database configured"}
                
                if not org.google_calendar_id:
                    # Try to create calendar if it doesn't exist
                    calendar_id = self.ensure_organization_calendar(organization_id, org.name, transaction)
                    if not calendar_id:
                        return {"status": "error", "message": f"Failed to create calendar for organization {organization_id}"}
                    org.google_calendar_id = calendar_id
                
                # Fetch events from Notion
                notion_events = self.notion_client.fetch_events(org.notion_database_id, transaction)
                if notion_events is None:
                    return {"status": "error", "message": "Failed to fetch events from Notion"}
                
                # Parse events
                parsed_events = self.parse_notion_events(notion_events)
                
                # Update Google Calendar
                results = self.update_organization_google_calendar(parsed_events, org.google_calendar_id, org.notion_database_id, transaction)
                
                # Update organization sync timestamp
                org.last_sync_at = datetime.now()
                db.commit()
                
                return {
                    "status": "success",
                    "message": f"Synced {len(results)} events for organization {organization_id}",
                    "organization_id": organization_id,
                    "events_processed": results
                }
                
            except Exception as e:
                self.logger.error(f"Error syncing organization {organization_id}: {e}")
                return {"status": "error", "message": str(e)}
            finally:
                if transaction:
                    transaction.finish()
    
    def update_organization_google_calendar(self, parsed_events: List[CalendarEventDTO], calendar_id: str, notion_database_id: str, parent_transaction=None) -> List[Dict]:
        """Update Google Calendar for a specific organization."""
        results = []
        op_name = "update_organization_google_calendar"
        self.logger.info(f"Starting {op_name} with {len(parsed_events)} parsed Notion events for calendar {calendar_id}.")

        # Fetch existing Google Calendar events
        with operation_span(parent_transaction, op="fetch_gcal", description="fetch_existing_gcal_events", logger=self.logger) as span:
            all_gcal_events_raw = self.gcal_client.get_all_events(calendar_id, time_min=None, parent_transaction=parent_transaction)
            if all_gcal_events_raw is None:
                self.logger.error(f"{op_name}: Failed to fetch existing Google Calendar events. Aborting update.")
                return []

            # Filter for events managed by this sync
            managed_gcal_events = [
                ev for ev in all_gcal_events_raw
                if ev.get('extendedProperties', {}).get('private', {}).get('notionPageId')
            ]
            span.set_data("fetched_total_gcal_event_count", len(all_gcal_events_raw))
            span.set_data("fetched_managed_gcal_event_count", len(managed_gcal_events))
            self.logger.info(f"Fetched {len(managed_gcal_events)} managed GCal events (out of {len(all_gcal_events_raw)} total).")

        # Build lookup dictionaries for GCal events & handle duplicates
        gcal_events_by_gcal_id: Dict[str, Dict] = {}
        gcal_events_by_notion_id: Dict[str, Dict] = {}
        duplicates_to_delete: set[str] = set()

        with operation_span(parent_transaction, op="process_gcal", description="build_gcal_lookups_handle_duplicates", logger=self.logger) as span:
            temp_gcal_by_notion_id: Dict[str, List[Dict]] = {}

            for event in managed_gcal_events:
                gcal_id = event.get('id')
                notion_page_id = event.get('extendedProperties', {}).get('private', {}).get('notionPageId')

                if gcal_id:
                    gcal_events_by_gcal_id[gcal_id] = event

                if notion_page_id:
                    if notion_page_id not in temp_gcal_by_notion_id:
                        temp_gcal_by_notion_id[notion_page_id] = []
                    temp_gcal_by_notion_id[notion_page_id].append(event)

            # Handle duplicates - keep the first one, mark others for deletion
            for notion_id, events in temp_gcal_by_notion_id.items():
                if len(events) > 1:
                    self.logger.warning(f"Found {len(events)} duplicate events for Notion page {notion_id}")
                    # Keep the first one, mark the rest for deletion
                    gcal_events_by_notion_id[notion_id] = events[0]
                    for duplicate_event in events[1:]:
                        duplicates_to_delete.add(duplicate_event['id'])
                else:
                    gcal_events_by_notion_id[notion_id] = events[0]

            span.set_data("duplicates_found", len(duplicates_to_delete))

        # Process each Notion event
        for event_dto in parsed_events:
            result = self._process_single_event(event_dto, gcal_events_by_notion_id, calendar_id, parent_transaction)
            if result:
                results.append(result)

        # Clean up duplicates
        if duplicates_to_delete:
            with operation_span(parent_transaction, op="cleanup", description="delete_duplicate_events", logger=self.logger) as span:
                deleted_count, failed_count = self.gcal_client.batch_delete_events(
                    calendar_id, list(duplicates_to_delete), "delete_duplicates", parent_transaction
                )
                span.set_data("duplicates_deleted", deleted_count)
                span.set_data("duplicates_failed", failed_count)
                self.logger.info(f"Cleaned up {deleted_count} duplicate events, {failed_count} failed.")

        # Clean up orphaned events (events in GCal but not in Notion)
        orphaned_events = set(gcal_events_by_gcal_id.keys()) - set(gcal_events_by_notion_id.keys())
        if orphaned_events:
            with operation_span(parent_transaction, op="cleanup", description="delete_orphaned_events", logger=self.logger) as span:
                deleted_count, failed_count = self.gcal_client.batch_delete_events(
                    calendar_id, list(orphaned_events), "delete_orphaned", parent_transaction
                )
                span.set_data("orphaned_deleted", deleted_count)
                span.set_data("orphaned_failed", failed_count)
                self.logger.info(f"Cleaned up {deleted_count} orphaned events, {failed_count} failed.")

        return results

    def _process_single_event(self, event_dto: CalendarEventDTO, gcal_events_by_notion_id: Dict[str, Dict], calendar_id: str, parent_transaction=None) -> Optional[Dict]:
        """Process a single event DTO."""
        notion_page_id = event_dto.notion_page_id
        existing_gcal_event = gcal_events_by_notion_id.get(notion_page_id)

        event_data = event_dto.to_gcal_format()
        
        if existing_gcal_event:
            # Update existing event
            gcal_event_id = existing_gcal_event['id']
            result = self.gcal_client.update_event(calendar_id, gcal_event_id, event_data, notion_page_id, parent_transaction)
            if result:
                return {
                    "notion_page_id": notion_page_id,
                    "gcal_event_id": gcal_event_id,
                    "status": "updated",
                    "summary": event_dto.summary
                }
        else:
            # Create new event
            result = self.gcal_client.create_event(calendar_id, event_data, notion_page_id, parent_transaction)
            if result:
                gcal_event_id, jump_url = result
                return {
                    "notion_page_id": notion_page_id,
                    "gcal_event_id": gcal_event_id,
                    "status": "created",
                    "summary": event_dto.summary,
                    "jump_url": jump_url
                }
        
        return None

    @cached(cache=_FRONTEND_CACHE, key=lambda self, org_id, transaction=None: keys.hashkey(org_id))
    def get_organization_events_for_frontend(self, organization_id: int, parent_transaction=None) -> Dict[str, Any]:
        """Get events for frontend display for a specific organization."""
        op_name = "get_organization_events_for_frontend"
        
        current_transaction = parent_transaction or start_transaction(op="calendar", name=op_name)
        
        with operation_span(current_transaction, op="org_frontend", description=op_name, logger=self.logger) as transaction:
            try:
                # Get organization
                db = next(self.db_connect.get_db())
                org = db.query(Organization).filter(Organization.id == organization_id).first()
                if not org:
                    return {"status": "error", "message": f"Organization {organization_id} not found"}
                
                if not org.notion_database_id:
                    return {"status": "error", "message": f"Organization {organization_id} has no Notion database configured"}
                
                # Fetch events from Notion
                notion_events = self.notion_client.fetch_events(org.notion_database_id, transaction)
                if notion_events is None:
                    return {"status": "error", "message": "Failed to fetch events from Notion"}
                
                # Parse events
                parsed_events = self.parse_notion_events(notion_events)
                
                # Convert to frontend format
                frontend_events = [event.to_frontend_format() for event in parsed_events]
                
                return {
                    "status": "success",
                    "organization_id": organization_id,
                    "organization_name": org.name,
                    "events": frontend_events,
                    "total_events": len(frontend_events)
                }
                
            except Exception as e:
                self.logger.error(f"Error getting organization events: {e}")
                return {"status": "error", "message": str(e)}
            finally:
                if transaction:
                    transaction.finish()
    
    def parse_notion_events(self, notion_events_raw: List[Dict]) -> List[CalendarEventDTO]:
        """Parse raw Notion events into CalendarEventDTO objects."""
        parsed_events = []
        failed_count = 0
        if not notion_events_raw:
            return []

        self.logger.info(f"Parsing {len(notion_events_raw)} raw Notion events.")
        for event_data in notion_events_raw:
            parsed_dto = CalendarEventDTO.from_notion(event_data)
            if parsed_dto:
                parsed_events.append(parsed_dto)
        else:
                failed_count += 1

        self.logger.info(f"Successfully parsed {len(parsed_events)} events, failed to parse {failed_count}.")
        return parsed_events

    def sync_all_organizations(self, parent_transaction=None) -> Dict[str, Any]:
        """Sync all organizations that have calendar sync enabled and a valid Notion database ID."""
        op_name = "sync_all_organizations"
        current_transaction = parent_transaction or start_transaction(op="calendar", name=op_name)
        with operation_span(current_transaction, op="multi_org_sync", description=op_name, logger=self.logger) as transaction:
            try:
                # Get all active organizations with calendar sync enabled
                db = next(self.db_connect.get_db())
                organizations = db.query(Organization).filter(
                    Organization.is_active == True,
                    Organization.calendar_sync_enabled == True
                ).all()
                self.logger.info(f"Found {len(organizations)} organizations with calendar sync enabled")
                results = {
                    "status": "success",
                    "total_organizations": len(organizations),
                    "organizations_processed": 0,
                    "organizations_failed": 0,
                    "organizations_skipped": 0,
                    "organization_results": []
                }
                for org in organizations:
                    try:
                        self.logger.info(f"Processing organization: {org.name} (ID: {org.id})")
                        if not org.notion_database_id:
                            self.logger.warning(f"Skipping organization {org.name} (ID: {org.id}) - No Notion database ID configured.")
                            results["organizations_skipped"] += 1
                            results["organization_results"].append({
                                "organization_id": org.id,
                                "organization_name": org.name,
                                "status": "skipped",
                                "message": "No Notion database ID configured"
                            })
                            continue
                        # Ensure calendar exists
                        if not org.google_calendar_id:
                            calendar_id = self.ensure_organization_calendar(org.id, org.name, transaction)
                            if not calendar_id:
                                self.logger.error(f"Failed to create calendar for organization {org.id}")
                                results["organizations_failed"] += 1
                                results["organization_results"].append({
                                    "organization_id": org.id,
                                    "organization_name": org.name,
                                    "status": "failed",
                                    "message": "Failed to create calendar"
                                })
                                continue
                        # Sync organization
                        self.logger.info(f"Starting sync for organization {org.name} (ID: {org.id})")
                        sync_result = self.sync_organization_notion_to_google(org.id, transaction)
                        if sync_result.get("status") == "success":
                            results["organizations_processed"] += 1
                            self.logger.info(f"Successfully synced organization {org.name} (ID: {org.id})")
                        else:
                            results["organizations_failed"] += 1
                            self.logger.error(f"Failed to sync organization {org.name} (ID: {org.id}): {sync_result.get('message')}")
                        results["organization_results"].append({
                            "organization_id": org.id,
                            "organization_name": org.name,
                            "status": sync_result.get("status"),
                            "message": sync_result.get("message"),
                            "events_processed": len(sync_result.get("events_processed", []))
                        })
                    except Exception as e:
                        self.logger.error(f"Error processing organization {org.id}: {e}")
                        results["organizations_failed"] += 1
                        results["organization_results"].append({
                            "organization_id": org.id,
                            "organization_name": org.name,
                            "status": "error",
                            "message": str(e)
                        })
                # Update overall status
                if results["organizations_failed"] > 0:
                    results["status"] = "partial_success" if results["organizations_processed"] > 0 else "failed"
                self.logger.info(f"Multi-org sync completed: {results['organizations_processed']} successful, {results['organizations_failed']} failed, {results['organizations_skipped']} skipped.")
                return results
            except Exception as e:
                self.logger.error(f"Error in multi-org sync: {e}")
                return {"status": "error", "message": str(e)}
            finally:
                if transaction:
                    transaction.finish()

# Legacy CalendarService for backward compatibility (deprecated)
class CalendarService:
    """Legacy single-organization calendar service (deprecated)."""
    
    def __init__(self, logger_instance=None):
        self.logger = logger_instance or logger
        self.multi_org_service = MultiOrgCalendarService(logger_instance)
        self.logger.warning("CalendarService is deprecated. Use MultiOrgCalendarService instead.")
    
    def sync_notion_to_google(self, transaction=None) -> Dict[str, Any]:
        """Legacy method - delegates to multi-org service."""
        self.logger.warning("sync_notion_to_google is deprecated. Use MultiOrgCalendarService.sync_all_organizations instead.")
        return self.multi_org_service.sync_all_organizations(transaction)
    
    def get_events_for_frontend(self, transaction=None) -> Dict[str, Any]:
        """Legacy method - returns error as this requires organization context."""
        return {"status": "error", "message": "This method requires organization context. Use MultiOrgCalendarService.get_organization_events_for_frontend instead."}