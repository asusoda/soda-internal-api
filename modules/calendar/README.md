# calendar

Syncs an org's Notion events database to its Google Calendar, and serves the org's published events, past and upcoming. Each org can use its own Notion token and Google service account as org secrets.

## Files

| File | Holds |
| --- | --- |
| `api.py` | Open events, officer sync and setup, sync of all orgs, and legacy routes that return errors |
| `service.py` | `MultiOrgCalendarService`, `list_events`, `sync_organization`, `setup_calendar`, `sync_all`, the calendar settings; declares `calendar:read` and `calendar:manage` |
| `integrations.py` | The Notion and Google integrations, their keys and tests |
| `clients/` | `GoogleCalendarClient` (`google.py`) and `NotionCalendarClient` (`notion.py`) |
| `sync.py` | Makes a Google Calendar match the Notion events |
| `events.py`, `dates.py` | `CalendarEventDTO` and Notion property reads; `DateParser` |
| `errors.py`, `tracing.py` | `APIErrorHandler` for Google and Notion errors; Sentry spans |
| `models.py`, `tools.py`, `jobs.py` | The event link table; the `events.list` and `calendar.*` tools; the sync job |

## Surface

- Routes: `/api/calendar`, behind the `calendar` switch. `/<org_prefix>/events` is open. `/<org_prefix>/sync` and `/setup` need an officer of the org. `/sync-all` needs a platform token. `/debug/organizations` needs an officer of any org.
- Jobs: `calendar.sync_all`, on the `CALENDAR_SYNC_CRON` schedule. No schedule if it is not set.
- Tools: `events.list`, `calendar.settings` (scope `calendar:read`); `calendar.update_settings`, `calendar.sync`, `calendar.setup` (scope `calendar:manage`).
- Tables: `calendar_event_links` (not used by the sync).

See [docs/modules/calendar.md](../../docs/modules/calendar.md).

## Known gaps

- `api.py` has legacy routes (`/events`, `/delete-all-events`, `/notion-webhook`) that return errors. `/sync-all` queries the orgs in the view.
- Views use `error_handler` and open their own session. They do not use `officer_route`.
