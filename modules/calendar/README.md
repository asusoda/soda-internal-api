# Notion to Google Calendar Sync Service

A Flask-based service module that automatically synchronizes events between a Notion database and Google Calendar.

![image](https://github.com/user-attachments/assets/eca21b10-f1a8-49aa-ad1e-cbc5e0555cd5)
![image](https://github.com/user-attachments/assets/8187e0a7-1bd3-4905-9f09-d2865d8dd42d)
![image](https://github.com/user-attachments/assets/47fb0d11-81c1-42cf-b4d8-48df8ad2caeb)
![image](https://github.com/user-attachments/assets/15b96b1d-6f92-4555-9b40-ce5d9f6fabc5)
![image](https://github.com/user-attachments/assets/cc6119e9-4644-4da5-a68a-3262e0d96a47)
![image](https://github.com/user-attachments/assets/03c41cdf-8a45-4973-89ec-c31f0a22debe)
![image](https://github.com/user-attachments/assets/0e0b9a6b-8639-4b9a-857e-0fc3f6a99df6)

## Purpose

The primary goal of this module is to automatically keep a designated Google Calendar updated based on events listed in a specific Notion database. It uses a webhook triggered by Notion updates (or manually) to initiate the synchronization process.

## Features

- Real-time synchronization of events from Notion to Google Calendar (triggered via webhook).
- Webhook support for automatic updates triggered by Notion changes (or manual calls).
- Creates, updates, or deletes Google Calendar events based on Notion entries.
- Clears synced Google Calendar events if no published events are found in Notion.
- Support for event locations, descriptions, and dates/times.
- Automatic timezone handling (configurable via `.env`).
- Comprehensive error logging and Sentry integration for easier debugging.
- Batch operations for efficient event deletion in Google Calendar.
- Provides an endpoint to fetch formatted Notion events for frontend use.
- Includes a protected endpoint for deleting all events from the target Google Calendar.

## Module Overview for AI Agents

This module implements a one-way synchronization from a Notion database to a Google Calendar. The core functionality is triggered by a `POST` request to the `/calendar/notion-webhook` endpoint.

The architecture follows a layered approach:
- **API Layer (`api.py`):** Handles incoming HTTP requests, defines routes using Flask Blueprint, and delegates business logic to the Service Layer. Manages top-level Sentry transactions.
- **Service Layer (`service.py`):** Orchestrates the main workflows (sync, fetch for frontend, clear events, delete all). Contains the core business logic and uses the Client Layer for external interactions.
- **Client Layer (`clients.py`):** Interacts directly with external APIs (Notion and Google Calendar). Encapsulates API calls, authentication, and low-level API error handling.
- **Data Modeling (`models.py`):** Defines the `CalendarEventDTO` (Data Transfer Object) used for processing event data. Also contains unused SQLAlchemy models.
- **Utilities (`utils.py`):** Provides helper functions for date parsing, property extraction, batch API operations, and Sentry span management.
- **Error Handling (`errors.py`):** Defines a standardized error handler (`APIErrorHandler`) for consistent logging and reporting of API errors to Sentry.

## Module Structure & Core Components

- **`api.py`**:
    - Defines the Flask Blueprint (`calendar_blueprint`) with the `/calendar` prefix.
    - Contains route handlers for:
        - `POST /notion-webhook`: Triggers the main Notion-to-Google sync process. Delegates to `CalendarService.sync_notion_to_google`.
        - `GET /events`: Fetches formatted Notion events for frontend display. Delegates to `CalendarService.get_events_for_frontend`. Does *not* interact with Google Calendar.
        - `POST /delete-all-events`: **Destructive**. Deletes *all* events from the configured Google Calendar (requires `ALLOW_DELETE_ALL=True` in config). Delegates to `CalendarService.delete_all_events`.
    - Handles top-level request validation, response formatting, and Sentry transaction management for each request.

- **`service.py` (`CalendarService`)**:
    - Orchestrates the core business logic of the module.
    - `sync_notion_to_google()`: Manages the end-to-end sync process: fetches Notion events, parses them, compares with Google Calendar, and performs creates/updates/deletes. Calls `clear_synced_events` if no Notion events are found.
    - `update_google_calendar()`: Compares Notion DTOs with existing Google Calendar events and calls appropriate `GoogleCalendarClient` methods (create, update, batch delete). Handles identification of duplicates and orphaned events.
    - `clear_synced_events()`: Fetches all Google Calendar events managed by this sync (using `notionPageId` property) and deletes them using `GoogleCalendarClient.batch_delete_events`.
    - `get_events_for_frontend()`: Fetches Notion events using `NotionCalendarClient`, parses them into DTOs, and formats them using `CalendarEventDTO.to_frontend_format()`.
    - `delete_all_events()`: Performs safety check (`ALLOW_DELETE_ALL`) then fetches all event IDs from Google Calendar and deletes them using `GoogleCalendarClient.batch_delete_events`.
    - `parse_notion_events()`: Converts raw Notion API data into a list of `CalendarEventDTO` objects.
    - Uses `NotionCalendarClient` and `GoogleCalendarClient` for external API interactions.
    - Uses `operation_span` from `utils.py` for detailed Sentry tracing.

- **`clients.py`**:
    - **`GoogleCalendarClient`**:
        - Handles all interactions with the Google Calendar API.
        - `get_service()`: Authenticates using service account credentials (from `config.GOOGLE_SERVICE_ACCOUNT`) and builds the Google API client resource.
        - `create_event()`: Creates a new event, adding `notionPageId` to extended properties. Returns the event URL and ID.
        - `update_event()`: Updates an existing event, ensuring `notionPageId` is present. Returns the event URL.
        - `get_all_events()`: Fetches Google Calendar events with pagination, optionally filtered by `timeMin`.
        - `batch_delete_events()`: Deletes multiple events efficiently using batch requests via the `batch_operation` utility.
        - Uses `APIErrorHandler` for handling `HttpError`.
    - **`NotionCalendarClient`**:
        - Handles all interactions with the Notion API (using the shared Notion client instance).
        - `fetch_events()`: Fetches all "Published" events from the configured Notion database (`config.NOTION_DATABASE_ID`) using pagination.
        - `update_page_with_gcal_id()`: Updates a Notion page property (`gcal_id` and optionally `NOTION_GCAL_LINK_PROPERTY`) with the corresponding Google Calendar event ID and link.
        - Uses `APIErrorHandler` for handling `APIResponseError`.

- **`models.py`**:
    - **`CalendarEventDTO`**: A `dataclass` representing a calendar event. Used as the primary data structure for transferring and processing event information within the service.
        - `from_notion()`: Class method to parse raw Notion API data into a `CalendarEventDTO`. Handles extraction of title, dates, location, description, etc., using helpers from `utils.py`. Performs basic validation (e.g., requires title and start date).
        - `to_gcal_format()`: Converts the DTO into the dictionary format required by the Google Calendar API for creating/updating events.
        - `to_frontend_format()`: Converts the DTO into a simplified dictionary format suitable for frontend consumption.
    - **SQLAlchemy Models (`CalendarEventLink`, etc.)**: Defines database models potentially intended for storing sync history or linking events. **Currently unused by the core synchronization logic.**

- **`utils.py`**:
    - **`operation_span`**: A context manager for creating detailed Sentry transaction spans with standardized logging and error capture.
    - **`batch_operation`**: A generic utility function for executing Google API batch requests (e.g., for deletions) with callback handling and error logging.
    - **`DateParser`**: A class with static methods (`parse_notion_date`, `ensure_end_date`) for parsing Notion date strings (handling all-day vs. specific times, timezones) and ensuring valid end dates (defaulting to 1-hour duration if needed). Uses `pytz` and relies on `config.TIMEZONE`.
    - **`extract_property`**: A helper function to safely extract and parse data from a specific Notion page property based on its expected type (title, rich_text, select, date, checkbox, etc.).

- **`errors.py` (`APIErrorHandler`)**:
    - Provides standardized methods (`handle_http_error`, `handle_notion_error`, `handle_generic_error`) for catching exceptions during API interactions or other operations.
    - Logs errors consistently and reports exceptions to Sentry via `capture_exception`, `set_context`, `set_tag`.

## Data Flow (Sync Process - `POST /notion-webhook`)

1.  **Trigger:** `POST /calendar/notion-webhook` route in `api.py` receives a request.
2.  **Delegate to Service:** The route handler calls `calendar_service.sync_notion_to_google()` in `service.py`.
3.  **Fetch Notion Events:** `sync_notion_to_google` calls `notion_client.fetch_events()` (in `clients.py`) to get all published events from the configured Notion database.
4.  **Check Notion Results:**
    *   **Error:** If `fetch_events` returns `None`, the sync aborts with an error.
    *   **No Events:** If `fetch_events` returns an empty list, `sync_notion_to_google` proceeds to clear previously synced events from Google Calendar (Step 5).
    *   **Events Found:** If events are returned, proceed to Step 6.
5.  **Clear Synced Events (if no Notion events):** `sync_notion_to_google` calls `service.clear_synced_events()`. This method fetches all GCal events with a `notionPageId` property using `gcal_client.get_all_events()` and deletes them using `gcal_client.batch_delete_events()` (both in `clients.py`). The sync process then finishes.
6.  **Parse Notion Events:** `sync_notion_to_google` calls `service.parse_notion_events()`. This uses `CalendarEventDTO.from_notion()` (in `models.py`) and helpers (`extract_property`, `DateParser`) from `utils.py` to convert the raw Notion data into a list of `CalendarEventDTO` objects.
7.  **Check Parse Results:** If parsing fails for all events, treat it similarly to "No Events" (Step 5) - clear GCal and finish with a warning.
8.  **Update Google Calendar:** `sync_notion_to_google` calls `service.update_google_calendar()` with the list of parsed `CalendarEventDTO`s.
9.  **Fetch Existing GCal Events:** `update_google_calendar` calls `gcal_client.get_all_events()` (in `clients.py`) to retrieve existing events managed by this sync (identified by the `notionPageId` extended property). It builds lookups and handles potential duplicate GCal events linked to the same Notion page.
10. **Compare & Sync:** `update_google_calendar` iterates through the parsed Notion DTOs and compares them against the fetched GCal events:
    *   **Create:** If a Notion event has no corresponding GCal event, `gcal_client.create_event()` (in `clients.py`) is called. If successful, `notion_client.update_page_with_gcal_id()` (in `clients.py`) is called to store the new GCal ID and link back in Notion.
    *   **Update:** If a Notion event matches an existing GCal event (via `notionPageId`), `gcal_client.update_event()` (in `clients.py`) is called to update the GCal event details. (Currently updates unconditionally, could be optimized to check for changes).
    *   **Delete:** After processing all Notion events, `update_google_calendar` identifies GCal events that no longer correspond to a valid, published Notion event (or were duplicates). It calls `gcal_client.batch_delete_events()` (in `clients.py`) to remove them.
11. **Response:** The result dictionary from `sync_notion_to_google` (containing status, message, and processed event details) is returned by the `api.py` route handler as a JSON response.

## Other API Endpoints

-   **`GET /calendar/events`**:
    -   Purpose: Provide a list of current, published Notion events formatted for frontend display.
    -   Process: Calls `CalendarService.get_events_for_frontend`, which uses `NotionCalendarClient` to fetch events and `CalendarEventDTO.to_frontend_format` for formatting.
    -   **Note:** This endpoint *only* reads from Notion; it does not interact with Google Calendar.

-   **`POST /calendar/delete-all-events`**:
    -   Purpose: **Destructive action** to remove *all* events from the configured Google Calendar. Intended for administrative use.
    -   Safety: Requires the environment variable `ALLOW_DELETE_ALL` to be set to `True` in the configuration. The operation will be rejected otherwise.
    -   Process: Calls `CalendarService.delete_all_events`, which performs the safety check, fetches all event IDs using `GoogleCalendarClient`, and then uses `GoogleCalendarClient.batch_delete_events` to delete them.

## Key Concepts for AI Contribution

-   **Sync Logic:** The core comparison and decision-making logic for creating, updating, or deleting Google Calendar events based on Notion data resides primarily within `CalendarService.update_google_calendar`.
-   **Notion Interaction:** All direct communication with the Notion API is handled by `NotionCalendarClient` in `clients.py`. To change how Notion data is fetched or updated, modify this class.
-   **Google Calendar Interaction:** All direct communication with the Google Calendar API is handled by `GoogleCalendarClient` in `clients.py`. To change how Google Calendar events are created, updated, fetched, or deleted, modify this class.
-   **Data Representation:** The `CalendarEventDTO` class in `models.py` is the central data structure used after parsing Notion data and before formatting for Google Calendar. Changes to event properties often involve modifying this DTO and its `from_notion` and `to_gcal_format` methods.
-   **Date/Time Handling:** Parsing and formatting of dates/times, including timezone considerations and default end times, are handled by the `DateParser` class in `utils.py`.
-   **Error Handling & Monitoring:** Errors are typically handled using `APIErrorHandler` (in `errors.py`) within the client classes. Sentry is used for monitoring, with detailed tracing provided by the `operation_span` context manager (in `utils.py`).
-   **Configuration:** The module relies heavily on environment variables accessed via `shared.config` (e.g., API keys, database IDs, calendar IDs, timezone). See the Configuration section below and `.env.template`.

## Database Integration

-   **Models Defined:** `models.py` defines SQLAlchemy models (`CalendarEventLink`) and `migrations/calendar/` contains Alembic scripts to set up corresponding database tables.
-   **Current Usage:** Despite the defined models and migrations, the core synchronization logic triggered by the `/notion-webhook` **does not currently interact with these database tables**.
-   **Sync Mechanism:** The sync process relies on fetching live data directly from the Notion and Google Calendar APIs and comparing them in memory (using the `notionPageId` stored in Google Calendar's extended properties as the primary link) to determine necessary actions (create, update, delete). The `gcal_id` property in Notion is primarily used for storing the link back and as a secondary check.
-   **Potential Purpose:** The database structure might be intended for future enhancements like logging synchronization history, storing metadata, caching, or supporting more complex bi-directional sync scenarios.

## Prerequisites

- Python 3.8+
- Google Cloud Platform account with Calendar API enabled
  ![image](https://github.com/user-attachments/assets/1021026e-e720-4f5b-9848-c70810913fb5)
- Notion API access (create an integration)
  ![image](https://github.com/user-attachments/assets/e2a6d53e-5fc8-42df-a53e-eba79cae3d14)
- Service account credentials (`.json` key file) from Google Cloud Platform
  ![image](https://github.com/user-attachments/assets/7d649e1a-e0a5-43fb-8165-b41aa22a1d2d)
- Google Calendar created and shared with the service account email address (with "Make changes to events" permission).
  ![image](https://github.com/user-attachments/assets/2d8076ce-76e9-4856-928b-0e25fe0139d9)
  ![image](https://github.com/user-attachments/assets/c7847205-5e9c-434f-ad65-31f2d9b93ccd)

## Configuration

Add the following variables to your `.env` file in the root directory (referencing `.env.template`):

```bash
# Calendar Integration
NOTION_API_KEY=your-notion-api-key
NOTION_DATABASE_ID=your-notion-database-id
# Paste the *entire content* of your Google Service Account JSON key file here
# Ensure it's valid JSON. Example structure:
GOOGLE_SERVICE_ACCOUNT_JSON={"type": "service_account", "project_id": "...", ...}
# The ID of the Google Calendar to sync with (find in Calendar settings)
GOOGLE_CALENDAR_ID=your-calendar-id@group.calendar.google.com
# Your local timezone (IANA format, e.g., America/New_York, Europe/London)
TIMEZONE=America/Phoenix
# Optional: The name of a URL property in your Notion database to store Google Calendar event links
NOTION_GCAL_LINK_PROPERTY=Calendar Link
# Optional: Set to "True" to enable the /delete-all-events endpoint. USE WITH EXTREME CAUTION.
ALLOW_DELETE_ALL=False

# General Server Settings (likely shared)
# SERVER_PORT=5000
# SERVER_DEBUG=false
# SENTRY_DSN=your-sentry-dsn
```

## Installation

1.  Clone the repository.
2.  Create and activate a virtual environment (recommended).
3.  Install dependencies using Poetry:
    ```bash
    poetry install
    ```
4.  Create a `.env` file in the root directory (copy from `.env.template`) and populate it with your configuration values (see Configuration section).
5.  Run database migrations (if using other modules that require the DB, or for future use of calendar models):
    ```bash
    poetry run alembic upgrade head
    ```
6.  Run the Flask application (from the root directory):
    ```bash
    poetry run python main.py
    ```

## Notion Database Requirements

Your Notion database must include the following properties:

-   `Name` (Type: `Title`): Event title. **(Required)**
-   `Date` (Type: `Date`): Event date and time. **Must include a start time.** End time is optional (defaults to 1 hour after start if missing). **(Required)**
-   `Published` (Type: `Checkbox`): Only checked events will be synced to Google Calendar. **(Required)**
-   `gcal_id` (Type: `Rich Text`): Stores the Google Calendar event ID. This field is automatically populated by the script when an event is created or updated in Google Calendar. Do not edit manually. **(Required for sync logic)**
-   `Location` (Type: `Select` or `Text`): Event location. (Code currently expects `Select` in `CalendarEventDTO.from_notion`, adjust `extract_property` call in `models.py` if using `Text`).
-   `Description` (Type: `Rich Text`): Event description.
-   Optional: `Calendar Link` (Type: `URL`) or custom name set via `NOTION_GCAL_LINK_PROPERTY`: Stores the link to the Google Calendar event, automatically populated by the script.
-   `Guests` (Type: `Text`): Comma-separated email addresses. *(See Limitations)*

*(Property names might be case-sensitive depending on how `extract_property` is used).*

## Limitations & Important Notes

-   **Guest Limitations**: Adding guests to Google Calendar events directly from Notion might not work reliably without a Google Workspace organizational account due to permission requirements needed to impersonate the user or add guests directly via the API. Mentioning a guest won't work since this is not an organizational account and Domain wide permission is required to add Guests to events, which can be only done with a google organizational account as super admin.
    ![image](https://github.com/user-attachments/assets/b7915db8-4137-4fce-8fd3-277985238788)
-   **Email Format**: Always separate guest emails with commas in the `Guests` property.
    ![image](https://github.com/user-attachments/assets/bd200bf3-dba2-4757-9e38-438a0aa723ef)
-   **Timezone**: The default timezone is set in the `.env` file (`TIMEZONE=America/Phoenix`). Ensure this matches your desired timezone for Google Calendar events. It's used when Notion doesn't provide explicit timezone info or as a fallback.
-   **Sync Trigger**: The `/notion-webhook` endpoint relies on an external trigger (like a Notion automation, a scheduled task, or a manual `curl` command) to initiate synchronization. It doesn't automatically detect Notion changes without the webhook being called.
-   **Database Usage**: The defined SQLAlchemy database models (`models.py`) are not currently used by the primary webhook synchronization logic.
-   **Duplicate Handling**: The sync logic attempts to identify and delete duplicate Google Calendar events linked to the same Notion page, keeping the most recently updated one.

## Security Considerations

-   Credentials (Notion API key, Google Service Account JSON) should be stored securely as environment variables (`.env` file) and **never** committed to version control. Ensure the `.env` file is included in your `.gitignore`.
-   Service account authentication provides a secure way to interact with the Google Calendar API without user passwords.
-   Restrict API key and service account permissions to the minimum required (e.g., only Calendar API access for the service account, specific database access for the Notion integration).
-   Consider adding authentication/authorization (e.g., a secret header check) to the `/notion-webhook` endpoint if it's exposed publicly.
-   Be extremely cautious when enabling and using the `/delete-all-events` endpoint. Ensure `ALLOW_DELETE_ALL` is `False` in production unless absolutely necessary.

## Error Handling

The service includes error handling and logging via Python's `logging` module and Sentry integration:

-   Uses `APIErrorHandler` (`errors.py`) for standardized handling of Google `HttpError` and Notion `APIResponseError`.
-   Uses `try...except` blocks for catching unexpected errors in service methods and API routes.
-   Uses `operation_span` (`utils.py`) to create detailed Sentry transaction spans, capturing errors within specific operations.
-   Logs errors with context and reports exceptions to Sentry.
-   Handles configuration issues (e.g., missing environment variables) where possible.

Check application logs and Sentry issues for diagnosing synchronization problems.

## Integration

The calendar module is registered as a Flask blueprint in the main application (`main.py`):

```python
# main.py
from modules.calendar.api import calendar_blueprint
# ... other imports and app setup ...

# Assuming 'app' is your Flask application instance
app.register_blueprint(calendar_blueprint, url_prefix="/calendar")

# ... rest of main.py ...
```

## Future Improvements

-   Investigate using a Google Workspace account to enable reliable guest adding.
-   Implement webhook validation (e.g., signature verification if provided by trigger) for security.
-   Potentially utilize the database models for logging sync history, caching API responses, or managing more complex state.
-   Add more robust handling for recurring events if needed (currently relies on Google Calendar's `singleEvents=True` expansion).
-   Optimize GCal updates by comparing event data before calling `update_event`.
-   Add configuration validation on startup.
