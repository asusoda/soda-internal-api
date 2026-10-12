import json
from collections.abc import Hashable
from datetime import UTC, datetime, timedelta
from typing import Any, cast

from cachetools import TTLCache, cachedmethod, keys
from sentry_sdk import start_transaction

from core import secrets
from core.config import config
from core.db import db_connect
from core.errors import ServiceError
from core.log import get_logger
from modules.auth import scopes
from modules.organizations import service as organizations
from modules.organizations.models import Organization

from . import sync
from .clients import GoogleCalendarClient, NotionCalendarClient
from .events import CalendarEventDTO
from .integrations import GOOGLE_SECRET, NOTION_SECRET
from .tracing import operation_span

logger = get_logger(__name__)

scopes.declare("calendar:read", "Read the org's events and calendar settings", uses=("notion",))
scopes.declare(
    "calendar:manage",
    "Change the calendar settings, make the org's Google Calendar, and sync Notion to it now",
    uses=("notion", "google"),
)


def _lookup_start(frontend_events: list[dict[str, Any]]) -> str | None:
    """One day before the earliest event start, as an RFC 3339 time, or None without events.

    The Google lookup for the links reads only from this time. The day covers all-day events and time zones.
    """
    starts = []
    for event in frontend_events:
        try:
            start = datetime.fromisoformat(str(event["start"]).replace("Z", "+00:00"))
        except (KeyError, ValueError):
            continue
        starts.append(start if start.tzinfo else start.replace(tzinfo=UTC))
    if not starts:
        return None
    return (min(starts) - timedelta(days=1)).astimezone(UTC).isoformat().replace("+00:00", "Z")


# Events per org for the website, kept 5 minutes
_FRONTEND_CACHE: TTLCache[tuple[Hashable, ...], dict[str, Any]] = TTLCache(maxsize=100, ttl=300)


class MultiOrgCalendarService:
    """Service layer for multi-organization calendar operations."""

    def __init__(self, logger_instance=None):
        self.logger = logger_instance or logger
        self.gcal_client = GoogleCalendarClient(self.logger)
        self.notion_client = NotionCalendarClient(self.logger)
        self.db_connect = db_connect

    def notion_for(self, db, org) -> NotionCalendarClient:
        """The org's own Notion integration if it has saved a token, else the instance-wide one."""
        token = secrets.get_secret(db, org.id, NOTION_SECRET)
        return NotionCalendarClient(self.logger, token=token) if token else self.notion_client

    def gcal_for(self, db, org) -> GoogleCalendarClient:
        """The org's own Google service account if it has saved one, else the instance-wide one."""
        raw = secrets.get_secret(db, org.id, GOOGLE_SECRET)
        if not raw:
            return self.gcal_client
        try:
            info = json.loads(raw)
        except ValueError:
            info = None
        if not isinstance(info, dict):
            # A broken key fails the sync instead of writing with the instance account
            self.logger.error(f"Organization {org.id} google_service_account secret is not a JSON object")
            info = {}
        return GoogleCalendarClient(self.logger, service_account_info=info)

    def ensure_organization_calendar(
        self, organization_id: int, organization_name: str, parent_transaction=None
    ) -> str | None:
        """Ensure a Google Calendar exists for the organization, create if needed."""
        op_name = "ensure_organization_calendar"

        current_transaction = parent_transaction or start_transaction(op="calendar", name=op_name)

        with operation_span(
            current_transaction, op="org_calendar", description=op_name, logger=self.logger
        ) as transaction:
            try:
                db = next(self.db_connect.get_db())
                org = db.query(Organization).filter(Organization.id == organization_id).first()
                if not org:
                    self.logger.error(f"Organization {organization_id} not found")
                    return None

                if org.google_calendar_id:
                    self.logger.info(f"Organization {organization_id} already has calendar: {org.google_calendar_id}")
                    return org.google_calendar_id

                calendar_name = f"{organization_name} Events"
                calendar_description = f"Events for {organization_name} organization"

                calendar_data = self.gcal_for(db, org).create_calendar(
                    calendar_name=calendar_name,
                    description=calendar_description,
                    timezone=config.TIMEZONE,
                    parent_transaction=transaction,
                )

                if calendar_data:
                    calendar_id = calendar_data["id"]

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
                if db:
                    db.close()

    def sync_organization_notion_to_google(self, organization_id: int, parent_transaction=None) -> dict[str, Any]:
        """Sync Notion events to Google Calendar for a specific organization."""
        op_name = "sync_organization_notion_to_google"

        current_transaction = parent_transaction or start_transaction(op="calendar", name=op_name)

        with operation_span(current_transaction, op="org_sync", description=op_name, logger=self.logger) as transaction:
            try:
                db = next(self.db_connect.get_db())
                org = db.query(Organization).filter(Organization.id == organization_id).first()
                if not org:
                    return {"status": "error", "message": f"Organization {organization_id} not found"}

                if not org.notion_database_id:
                    return {
                        "status": "error",
                        "message": f"Organization {organization_id} has no Notion database configured",
                    }

                if not org.google_calendar_id:
                    calendar_id = self.ensure_organization_calendar(organization_id, org.name, transaction)
                    if not calendar_id:
                        return {
                            "status": "error",
                            "message": f"Failed to create calendar for organization {organization_id}",
                        }
                    org.google_calendar_id = calendar_id

                notion_events = self.notion_for(db, org).fetch_events(org.notion_database_id, transaction)
                if notion_events is None:
                    return {"status": "error", "message": "Failed to fetch events from Notion"}

                parsed_events = self.parse_notion_events(notion_events)

                results = self.update_organization_google_calendar(
                    parsed_events,
                    org.google_calendar_id,
                    org.notion_database_id,
                    transaction,
                    gcal=self.gcal_for(db, org),
                )

                org.last_sync_at = datetime.now()
                db.commit()

                return {
                    "status": "success",
                    "message": f"Synced {len(results)} events for organization {organization_id}",
                    "organization_id": organization_id,
                    "events_processed": results,
                }

            except Exception as e:
                self.logger.error(f"Error syncing organization {organization_id}: {e}")
                return {"status": "error", "message": str(e)}
            finally:
                if transaction:
                    transaction.finish()
                if db:
                    db.close()

    def update_organization_google_calendar(
        self,
        parsed_events: list[CalendarEventDTO],
        calendar_id: str,
        notion_database_id: str,
        parent_transaction=None,
        gcal: GoogleCalendarClient | None = None,
    ) -> list[dict]:
        """Make the Google Calendar match parsed_events. See sync.update_google_calendar."""
        return sync.update_google_calendar(
            gcal or self.gcal_client, parsed_events, calendar_id, parent_transaction, self.logger
        )

    @cachedmethod(cache=lambda _self: _FRONTEND_CACHE, key=lambda _self, org_id, transaction=None: keys.hashkey(org_id))
    def get_organization_events_for_frontend(self, organization_id: int, parent_transaction=None) -> dict[str, Any]:
        """Get events for frontend display for a specific organization."""
        op_name = "get_organization_events_for_frontend"

        current_transaction = parent_transaction or start_transaction(op="calendar", name=op_name)

        with operation_span(
            current_transaction, op="org_frontend", description=op_name, logger=self.logger
        ) as transaction:
            try:
                db = next(self.db_connect.get_db())
                org = db.query(Organization).filter(Organization.id == organization_id).first()
                if not org:
                    return {"status": "error", "message": f"Organization {organization_id} not found"}

                if not org.notion_database_id:
                    return {
                        "status": "error",
                        "message": f"Organization {organization_id} has no Notion database configured",
                    }

                notion_events = self.notion_for(db, org).fetch_events(org.notion_database_id, transaction)
                if notion_events is None:
                    return {"status": "error", "message": "Failed to fetch events from Notion"}

                parsed_events = self.parse_notion_events(notion_events)

                frontend_events = [event.to_frontend_format() for event in parsed_events]
                self._add_event_links(db, org, frontend_events, transaction)

                return {
                    "status": "success",
                    "organization_id": organization_id,
                    "organization_name": org.name,
                    "events": frontend_events,
                    "total_events": len(frontend_events),
                }

            except Exception as e:
                self.logger.error(f"Error getting organization events: {e}")
                return {"status": "error", "message": str(e)}
            finally:
                if transaction:
                    transaction.finish()
                if "db" in locals():
                    db.close()

    def _add_event_links(self, db, org: Organization, frontend_events: list[dict[str, Any]], transaction) -> None:
        """Set jump_url on each event that the sync copied to the org's Google Calendar, from the event's htmlLink."""
        time_min = _lookup_start(frontend_events)
        if not org.google_calendar_id or time_min is None:
            return
        try:
            links = sync.event_links(self.gcal_for(db, org), cast(str, org.google_calendar_id), time_min, transaction)
        except Exception as e:
            # The events are still useful without the links
            self.logger.warning(f"Could not read Google Calendar links for organization {org.id}: {e}")
            return
        for event in frontend_events:
            link = links.get(event["id"])
            if link:
                event["jump_url"] = link

    def parse_notion_events(self, notion_events_raw: list[dict]) -> list[CalendarEventDTO]:
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

    def sync_all_organizations(self, parent_transaction=None) -> dict[str, Any]:
        """Sync all organizations that have calendar sync enabled and a valid Notion database ID."""
        op_name = "sync_all_organizations"
        current_transaction = parent_transaction or start_transaction(op="calendar", name=op_name)
        with operation_span(
            current_transaction, op="multi_org_sync", description=op_name, logger=self.logger
        ) as transaction:
            try:
                db = next(self.db_connect.get_db())
                organizations = (
                    db.query(Organization).filter(Organization.is_active, Organization.calendar_sync_enabled).all()
                )
                self.logger.info(f"Found {len(organizations)} organizations with calendar sync enabled")
                results: dict[str, Any] = {
                    "status": "success",
                    "total_organizations": len(organizations),
                    "organizations_processed": 0,
                    "organizations_failed": 0,
                    "organizations_skipped": 0,
                    "organization_results": [],
                }
                for org in organizations:
                    try:
                        self.logger.info(f"Processing organization: {org.name} (ID: {org.id})")
                        if not org.notion_database_id:
                            self.logger.warning(
                                f"Skipping organization {org.name} (ID: {org.id}) - No Notion database ID configured."
                            )
                            results["organizations_skipped"] += 1
                            results["organization_results"].append(
                                {
                                    "organization_id": org.id,
                                    "organization_name": org.name,
                                    "status": "skipped",
                                    "message": "No Notion database ID configured",
                                }
                            )
                            continue
                        if not org.google_calendar_id:
                            calendar_id = self.ensure_organization_calendar(
                                cast(int, org.id), cast(str, org.name), transaction
                            )
                            if not calendar_id:
                                self.logger.error(f"Failed to create calendar for organization {org.id}")
                                results["organizations_failed"] += 1
                                results["organization_results"].append(
                                    {
                                        "organization_id": org.id,
                                        "organization_name": org.name,
                                        "status": "failed",
                                        "message": "Failed to create calendar",
                                    }
                                )
                                continue
                        self.logger.info(f"Starting sync for organization {org.name} (ID: {org.id})")
                        sync_result = self.sync_organization_notion_to_google(cast(int, org.id), transaction)
                        if sync_result.get("status") == "success":
                            results["organizations_processed"] += 1
                            self.logger.info(f"Successfully synced organization {org.name} (ID: {org.id})")
                        else:
                            results["organizations_failed"] += 1
                            self.logger.error(
                                f"Failed to sync organization {org.name} (ID: {org.id}): {sync_result.get('message')}"
                            )
                        results["organization_results"].append(
                            {
                                "organization_id": org.id,
                                "organization_name": org.name,
                                "status": sync_result.get("status"),
                                "message": sync_result.get("message"),
                                "events_processed": len(sync_result.get("events_processed", [])),
                            }
                        )
                    except Exception as e:
                        self.logger.error(f"Error processing organization {org.id}: {e}")
                        results["organizations_failed"] += 1
                        results["organization_results"].append(
                            {
                                "organization_id": org.id,
                                "organization_name": org.name,
                                "status": "error",
                                "message": str(e),
                            }
                        )
                if results["organizations_failed"] > 0:
                    results["status"] = "partial_success" if results["organizations_processed"] > 0 else "failed"
                self.logger.info(
                    f"Multi-org sync completed: {results['organizations_processed']} successful, {results['organizations_failed']} failed, {results['organizations_skipped']} skipped."
                )
                return results
            except Exception as e:
                self.logger.error(f"Error in multi-org sync: {e}")
                return {"status": "error", "message": str(e)}
            finally:
                if transaction:
                    transaction.finish()
                if "db" in locals():
                    db.close()


# The calendar's functions for every caller (REST, MCP tools, jobs). They take a database session and an org.

_service: MultiOrgCalendarService | None = None


def get_service() -> MultiOrgCalendarService:
    """The process-wide calendar service, created on first use."""
    global _service
    if _service is None:
        _service = MultiOrgCalendarService(logger)
    return _service


class CalendarError(ServiceError):
    """A calendar request that cannot be served."""


def find_organization(db, org_prefix: str) -> Organization:
    """The active organization with this prefix. Raises CalendarError (404, or 403 if inactive)."""
    org = organizations.find_by_prefix(db, org_prefix, active_only=True)
    if org:
        return org
    if organizations.find_by_prefix(db, org_prefix):
        raise CalendarError(f"Organization '{org_prefix}' exists but is inactive", 403)
    raise CalendarError(f"Organization '{org_prefix}' not found", 404)


def list_events(db, org: Organization, transaction=None) -> dict[str, Any]:
    """The published events of the org's Notion calendar, past and upcoming, as the website shows them."""
    if not org.notion_database_id:
        raise CalendarError(f"Organization '{org.prefix}' has no Notion database configured", 400)
    return get_service().get_organization_events_for_frontend(org.id, transaction)


def sync_organization(db, org: Organization, transaction=None) -> dict[str, Any]:
    """Copy the org's Notion events into its Google Calendar."""
    return get_service().sync_organization_notion_to_google(org.id, transaction)


def setup_calendar(db, org: Organization, transaction=None) -> str | None:
    """Create the org's Google Calendar if it has none. Returns the calendar id."""
    return get_service().ensure_organization_calendar(org.id, org.name, transaction)


def sync_all(transaction=None) -> dict[str, Any]:
    """Sync every active org with calendar sync turned on."""
    return get_service().sync_all_organizations(transaction)


def calendar_settings(org: Organization) -> dict[str, Any]:
    """The org's Notion database, Google Calendar, sync switch and last sync time."""
    return {
        "notion_database_id": org.notion_database_id,
        "calendar_sync_enabled": org.calendar_sync_enabled,
        "google_calendar_id": org.google_calendar_id,
        "last_sync_at": org.last_sync_at.isoformat() if org.last_sync_at else None,
    }


def save_calendar_settings(db, org: Organization, data: dict) -> dict[str, Any]:
    """Set the keys that data has. An empty id clears it. Commits."""
    if "notion_database_id" in data:
        org.notion_database_id = data["notion_database_id"].strip() if data["notion_database_id"] else None
    if "calendar_sync_enabled" in data:
        org.calendar_sync_enabled = bool(data["calendar_sync_enabled"])
    if "google_calendar_id" in data:
        org.google_calendar_id = data["google_calendar_id"].strip() if data["google_calendar_id"] else None
    db.commit()
    return calendar_settings(org)
