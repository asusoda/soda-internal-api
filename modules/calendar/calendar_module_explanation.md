# Explanation of the Calendar Module

This document explains the functionality of the `calendar` module, which synchronizes events between a Notion database and Google Calendar.

## Purpose

The primary goal of this module is to automatically keep a designated Google Calendar updated based on events listed in a specific Notion database. It uses a webhook triggered by Notion updates to initiate the synchronization process.

## Core Components

1.  **`api.py`**: Contains the main logic for the Flask API endpoint, interaction with Google Calendar API, fetching data from Notion, parsing event data, and performing the synchronization.
    *   **Flask Blueprint (`calendar_blueprint`)**: Defines the `/calendar` route prefix.
    *   **Webhook Endpoint (`/notion-webhook`)**:
        *   Handles `GET` requests for health checks.
        *   Handles `POST` requests triggered by Notion updates. It fetches relevant Notion events, parses them, and updates Google Calendar accordingly. If no published future events are found in Notion, it clears all future events from the Google Calendar.
    *   **Google Calendar Interaction**:
        *   `get_google_calendar_service()`: Authenticates and initializes the Google Calendar API client using service account credentials.
        *   `ensure_calendar_access()`: Creates the target Google Calendar if it doesn't exist and shares it with the configured user email.
        *   `get_all_calendar_events()`: Fetches all upcoming events from the specified Google Calendar.
        *   `update_google_calendar()`: Orchestrates the sync process. It compares Notion events with existing Google Calendar events, creating new ones, updating existing ones, and deleting those no longer present in Notion.
        *   `create_event()`, `update_event()`: Functions to create or update individual events in Google Calendar.
        *   `clear_future_events()`: Deletes all future events from the Google Calendar.
    *   **Notion Interaction**:
        *   `fetch_notion_events()`: Queries the specified Notion database for events that are marked as "Published" and occur on or after the current date.
    *   **Data Parsing**:
        *   `parse_event_data()`: Converts the raw event data fetched from Notion into the format required by the Google Calendar API. It extracts properties like title, location, description, start/end times.
        *   `extract_property()`, `parse_date()`: Helper functions for extracting specific data types from Notion properties.

2.  **`models.py`**: Defines SQLAlchemy database models (`CalendarEvent`, `NotionEvent`, `GoogleEvent`) intended to represent and link events between Notion and Google Calendar. These models define a potential structure for storing event details and relationships persistently.
    *   **`CalendarEvent`**: A central table linking the other two.
    *   **`NotionEvent`**: Stores Notion-specific details.
    *   **`GoogleEvent`**: Stores Google Calendar-specific details.

3.  **`README.md`**: Provides setup instructions, feature list, prerequisites, configuration details (environment variables), Notion database requirements, and important notes (like limitations on adding guests without a Google Workspace account).

## Data Flow

1.  **Trigger**: A change in the configured Notion database triggers a webhook call to the `/calendar/notion-webhook` endpoint.
2.  **Fetch**: The `notion_webhook` function calls `fetch_notion_events` to get all relevant (published, future) events from the Notion database.
3.  **Parse**: The fetched Notion events are processed by `parse_event_data` to extract key information (title, date, location, etc.) and format it for Google Calendar.
4.  **Sync**:
    *   The `update_google_calendar` function retrieves existing future events from Google Calendar using `get_all_calendar_events`.
    *   It compares the parsed Notion events with the existing Google Calendar events.
    *   **Create**: New events found in Notion are created in Google Calendar using `create_event`.
    *   **Update**: Existing events found in both Notion and Google Calendar are updated in Google Calendar using `update_event` (matching is based on summary and start time).
    *   **Delete**: Google Calendar events that don't have a corresponding match in the fetched Notion events are deleted.
    *   **Clear**: If `fetch_notion_events` returns no events, `clear_future_events` is called to remove all upcoming events from the Google Calendar.
5.  **Response**: The webhook endpoint returns a JSON response indicating the status of the operation.

## Database Integration

*   **Models Defined:** As mentioned, `models.py` defines the database structure using SQLAlchemy, and `migrations/calendar/` contains scripts to set up these tables.
*   **Current Usage:** Despite the defined models and migrations, the core synchronization logic triggered by the `/notion-webhook` in `api.py` **does not currently interact with these database tables**.
*   **Sync Mechanism:** The sync process relies on fetching live data directly from the Notion and Google Calendar APIs and comparing them in memory to determine necessary actions (create, update, delete).
*   **Potential Purpose:** The database structure might be intended for future enhancements like:
    *   Logging synchronization history.
    *   Storing metadata or relationships for more complex syncing scenarios.
    *   Use by other parts of the application.

## Setup & Configuration

*   Requires Python, Google Cloud Platform account (Calendar API enabled), Notion API access, and Google service account credentials.
*   Configuration is done via environment variables (`.env` file) for API keys, database/calendar IDs, timezone, etc.
*   The Notion database needs specific properties: `Name` (title), `Date` (date), `Location` (text), `Description` (text), `Guests` (text - comma-separated emails), `Published` (checkbox).

## Limitations

*   Adding guests to Google Calendar events directly from Notion might not work reliably without a Google Workspace organizational account due to permission requirements.