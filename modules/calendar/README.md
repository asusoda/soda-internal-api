# Notion to Google Calendar Sync Service

A Flask-based service that automatically synchronizes events between a Notion database and Google Calendar.

![image](https://github.com/user-attachments/assets/eca21b10-f1a8-49aa-ad1e-cbc5e0555cd5)

![image](https://github.com/user-attachments/assets/8187e0a7-1bd3-4905-9f09-d2865d8dd42d)

![image](https://github.com/user-attachments/assets/47fb0d11-81c1-42cf-b4d8-48df8ad2caeb)

![image](https://github.com/user-attachments/assets/15b96b1d-6f92-4555-9b40-ce5d9f6fabc5)

![image](https://github.com/user-attachments/assets/cc6119e9-4644-4da5-a68a-3262e0d96a47)

![image](https://github.com/user-attachments/assets/03c41cdf-8a45-4973-89ec-c31f0a22debe)

![image](https://github.com/user-attachments/assets/0e0b9a6b-8639-4b9a-857e-0fc3f6a99df6)

## Purpose

The primary goal of this module is to automatically keep a designated Google Calendar updated based on events listed in a specific Notion database. It uses a webhook triggered by Notion updates to initiate the synchronization process.

## Features

- Real-time synchronization of events from Notion to Google Calendar
- Webhook support for automatic updates triggered by Notion changes
- Creates, updates, or deletes Google Calendar events based on Notion entries
- Clears future Google Calendar events if no published future events are found in Notion
- Support for event locations, descriptions, and dates/times
- Automatic timezone handling (configurable via `.env`)
- Comprehensive error logging for easier debugging
- Batch operations for efficient event deletion in Google Calendar

## Core Components

1.  **`api.py`**: Contains the main logic for the Flask API endpoint, interaction with Google Calendar API, fetching data from Notion, parsing event data, and performing the synchronization.
    *   **Flask Blueprint (`calendar_blueprint`)**: Defines the `/calendar` route prefix.
    *   **Webhook Endpoint (`/notion-webhook`)**:
        *   Handles `GET` requests for health checks.
        *   Handles `POST` requests triggered by Notion updates. It fetches relevant Notion events, parses them, and updates Google Calendar accordingly. If no published future events are found in Notion, it clears all future events from the Google Calendar.
    *   **Google Calendar Interaction**:
        *   `get_google_calendar_service()`: Authenticates and initializes the Google Calendar API client using service account credentials.
        *   `ensure_calendar_access()`: Verifies access to the target Google Calendar.
        *   `get_all_calendar_events()`: Fetches upcoming events from the specified Google Calendar.
        *   `update_google_calendar()`: Orchestrates the sync process. It compares Notion events with existing Google Calendar events, creating new ones, updating existing ones (matching by GCAL ID stored in Notion), and deleting those no longer present in Notion using batch requests.
        *   `create_event()`, `update_event()`: Functions to create or update individual events in Google Calendar and update the Notion page with the Google Calendar event ID (`gcal_id`).
        *   `clear_future_events()`: Deletes all future events from the Google Calendar using batch requests.
    *   **Notion Interaction**:
        *   `fetch_notion_events()`: Queries the specified Notion database for events that are marked as "Published" and occur on or after the current date, handling pagination.
    *   **Data Parsing**:
        *   `parse_event_data()`: Converts the raw event data fetched from Notion into the format required by the Google Calendar API. It extracts properties like title, location, description, start/end times, Notion Page ID, and GCAL ID.
        *   `extract_property()`, `parse_date()`: Helper functions for extracting specific data types from Notion properties. `extract_property` now concatenates multi-part rich text fields.

2.  **`models.py`**: Defines SQLAlchemy database models (`CalendarEvent`, `NotionEvent`, `GoogleEvent`) intended to represent and link events between Notion and Google Calendar. These models define a potential structure for storing event details and relationships persistently. *(See Database Integration section)*

## Data Flow

1.  **Trigger**: A change in the configured Notion database triggers a webhook call to the `/calendar/notion-webhook` endpoint.
2.  **Fetch**: The `notion_webhook` function calls `fetch_notion_events` to get all relevant (published, future) events from the Notion database using pagination.
3.  **Parse**: The fetched Notion events are processed by `parse_event_data` to extract key information (title, date, location, description, Notion Page ID, GCAL ID) and format it for Google Calendar.
4.  **Sync**:
    *   The `update_google_calendar` function retrieves existing future events from Google Calendar using `get_all_calendar_events`.
    *   It compares the parsed Notion events (using the `gcal_id` property) with the existing Google Calendar events.
    *   **Create**: New events found in Notion (without a `gcal_id` or with a `gcal_id` not found in Google Calendar) are created in Google Calendar using `create_event`. The Notion page is then updated with the new Google Calendar event ID.
    *   **Update**: Existing events found in both Notion and Google Calendar (matching `gcal_id`) are updated in Google Calendar using `update_event`.
    *   **Delete**: Google Calendar events whose `gcal_id` does not correspond to any fetched Notion event are deleted using a batch request.
    *   **Clear**: If `fetch_notion_events` returns no events, `clear_future_events` is called to remove all upcoming events from the Google Calendar using a batch request.
5.  **Response**: The webhook endpoint returns a JSON response indicating the status of the operation.

## Database Integration

*   **Models Defined:** `models.py` defines a database structure using SQLAlchemy (`CalendarEvent`, `NotionEvent`, `GoogleEvent`), and `migrations/calendar/` contains scripts to set up these tables.
*   **Current Usage:** Despite the defined models and migrations, the core synchronization logic triggered by the `/notion-webhook` in `api.py` **does not currently interact with these database tables**.
*   **Sync Mechanism:** The sync process relies on fetching live data directly from the Notion and Google Calendar APIs and comparing them in memory (using the `gcal_id` stored in Notion as the primary key) to determine necessary actions (create, update, delete).
*   **Potential Purpose:** The database structure might be intended for future enhancements like:
    *   Logging synchronization history.
    *   Storing metadata or relationships for more complex syncing scenarios.
    *   Use by other parts of the application.

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

Add the following variables to your `.env` file in the root directory:

```bash
# Calendar Integration
NOTION_API_KEY=your-notion-api-key
NOTION_DATABASE_ID=your-notion-database-id
# Paste the entire content of your Google Service Account JSON key file here
GOOGLE_SERVICE_ACCOUNT_JSON={"type": "service_account", "project_id": "...", ...}
# The ID of the Google Calendar to sync with (find in Calendar settings)
GOOGLE_CALENDAR_ID=your-calendar-id@group.calendar.google.com
# The email address of the user you want to share the calendar with (optional, for viewing)
GOOGLE_USER_EMAIL=your-email@domain.com
SERVER_PORT=5000
SERVER_DEBUG=false
# Your local timezone (e.g., America/New_York, Europe/London)
TIMEZONE=America/Phoenix
```

## Installation

1.  Clone the repository.
2.  Create and activate a virtual environment (recommended).
3.  Install dependencies:
    ```bash
    pip install -r requirements.txt
    # Or specifically for this module if requirements.txt is not exhaustive:
    # pip install flask google-auth google-api-python-client notion-client python-dotenv
    ```
4.  Create a `.env` file in the root directory and populate it with your configuration values (see Configuration section).
5.  Run database migrations if using the database features (currently not used by the core sync):
    ```bash
    # (Instructions for running migrations if applicable)
    ```
6.  Run the Flask application:
    ```bash
    python main.py
    ```

## Notion Database Requirements

Your Notion database must include the following properties (case-sensitive names might matter depending on implementation):

-   `Name` (Type: `Title`): Event title.
-   `Date` (Type: `Date`): Event date and time. **Must include a start time.** End time is optional (defaults to 1 hour after start if missing).
-   `Location` (Type: `Text` or `Select`): Event location. (Code currently expects `Select`, adjust `extract_property` in `api.py` if using `Text`).
-   `Description` (Type: `Rich Text`): Event description.
-   `Guests` (Type: `Text`): Comma-separated email addresses. *(See Limitations)*
-   `Published` (Type: `Checkbox`): Only checked events will be synced to Google Calendar.
-   `gcal_id` (Type: `Rich Text`): **(Required for sync logic)** Stores the Google Calendar event ID. This field is automatically populated by the script when an event is created in Google Calendar. Do not edit manually.

## API Endpoint

### `/calendar/notion-webhook`

-   `GET`: Health check endpoint. Returns `{"status": "success"}` if the service is running.
-   `POST`: Webhook endpoint intended to be triggered by Notion updates (e.g., via a Notion automation or a manual trigger). Initiates the full sync process described in Data Flow.

## Limitations & Important Notes

-   **Guest Limitations**: Adding guests to Google Calendar events directly from Notion might not work reliably without a Google Workspace organizational account due to permission requirements needed to impersonate the user or add guests directly via the API. Mentioning a guest won't work since this is not an organizational account and Domain wide permission is required to add Guests to events, which can be only done with a google organizational account as super admin.
    ![image](https://github.com/user-attachments/assets/b7915db8-4137-4fce-8fd3-277985238788)
-   **Email Format**: Always separate guest emails with commas in the `Guests` property.
    ![image](https://github.com/user-attachments/assets/bd200bf3-dba2-4757-9e38-438a0aa723ef)
-   **Timezone**: The default timezone is set in the `.env` file (`TIMEZONE=America/Phoenix`). Ensure this matches your desired timezone for Google Calendar events.
-   **Sync Trigger**: The current implementation relies on an external trigger (like a manual run or a separate automation calling the POST webhook) to initiate synchronization. It doesn't automatically detect Notion changes without the webhook being called.
-   **Database Usage**: The defined database models (`models.py`) are not currently used by the primary webhook synchronization logic.

## Security Considerations

-   Credentials (API keys, service account JSON) should be stored securely as environment variables (`.env` file) and not committed to version control. Ensure the `.env` file is included in your `.gitignore`.
-   Service account authentication provides a secure way to interact with the Google Calendar API without using user passwords.
-   Restrict API key and service account permissions to the minimum required (e.g., only Calendar API access).
-   Consider adding authentication/authorization to the webhook endpoint if it's exposed publicly.

## Error Handling

The service includes error handling and logging for:

-   Google API errors (`HttpError`) during authentication, fetching, creating, updating, or deleting events.
-   Notion API errors (`APIResponseError`) during database queries or page updates.
-   Configuration issues (e.g., missing environment variables).
-   Data parsing errors.
-   General unexpected errors.

Logs provide details to help diagnose synchronization issues.

## Integration

The calendar module is registered as a Flask blueprint in the main application (`main.py`):

```python
from modules.calendar.api import calendar_blueprint
# Assuming 'app' is your Flask application instance
app.register_blueprint(calendar_blueprint, url_prefix="/calendar")
```

## Future Improvements

-   Investigate using a Google Workspace account to enable reliable guest adding.
-   Implement webhook validation for security.
-   Potentially utilize the database models for logging, caching, or more complex state management.
-   Add more robust handling for recurring events if needed.
