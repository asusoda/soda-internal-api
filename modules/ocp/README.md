# Officer Contribution Points (OCP) Module

The OCP module tracks contribution points for officers based on their involvement in events managed through Notion. It integrates with the existing calendar module to leverage Notion data for events and officer assignments.

## Overview

Officers can be assigned to various roles in events, such as:
- Event Lead
- Event Staff
- Logistics Staff
- Logistics Lead

These roles are pulled from Notion event properties and points are assigned automatically based on the role:
- Event Lead: 1 point
- Event Staff: 1 point
- Logistics Staff: 1 point
- Logistics Lead: 1 point
- Special Contribution: 2 points
- Unique Contribution: 3 points

Additionally, points can be awarded based on event types:
- GBM (General Body Meeting): 1 point
- Special Event: 2 points

## Database Structure

The OCP module maintains its own SQLite database (`officers.db`) with two main tables:

### Officers Table
Stores information about officers:
- email (primary key)
- uuid (unique ID)
- name
- title (officer role in the organization)
- department (which department they belong to)

### Officer Points Table
Tracks points earned by officers:
- id (primary key)
- points (number of points for this entry)
- event (name of the event)
- role (officer's role in the event)
- event_type (type of event - GBM, Special Event, etc.)
- timestamp (when the event occurred)
- officer_email (foreign key to officers table)
- notion_page_id (ID of the Notion page for this event)
- event_metadata (additional event data)

## Architecture

The OCP module follows a layered architecture:

1. **Models** (`models.py`): Defines the database schema using SQLAlchemy ORM
2. **Database** (`db.py`): Handles database connections and CRUD operations
3. **Utils** (`utils.py`): Utility functions for parsing Notion data and calculating points
4. **Service** (`service.py`): Business logic for syncing data and managing officer points
5. **API** (`api.py`): Flask endpoints that expose the OCP functionality
6. **NotionOCPSyncService** (`notion_sync_service.py`): Dedicated service for syncing Notion to OCP database

## Syncing Services

### OCPService (Base Service)
The core service that provides functionality to sync Notion data to the OCP database, as well as manage officer points records.

### NotionOCPSyncService (Dedicated Sync Service)
A specialized service that handles the orchestration of syncing between Notion and the OCP database:
- Provides a simplified interface for syncing
- Handles transaction management
- Provides detailed logging and error handling
- Used by both the scheduled job and the CalendarService

## Scheduled Synchronization

The system automatically syncs OCP data from Notion on a regular basis:

1. **Directly from main application**: Every 15 minutes, the application runs a scheduled job (`ocp_sync_job`) that calls the NotionOCPSyncService to sync Notion data to the OCP database.

2. **As part of Calendar sync**: When Google Calendar is synchronized with Notion (via `sync_job`), the OCP sync is also triggered as a follow-up action. This ensures that when calendar events are updated, officer contribution points are also updated accordingly.

## API Endpoints

The module provides the following API endpoints (as an extension of the calendar module):

- **POST /ocp/sync-from-notion**: Triggers a sync from Notion to update officer points
- **GET /ocp/officers**: Leaderboard of officers ranked by total points
- **GET /ocp/officer/{email}/contributions**: Gets detailed contribution history for a specific officer
- **POST /ocp/add-contribution**: Manually add contribution points for an officer
- **PUT /ocp/contribution/{id}**: Update an existing contribution record
- **DELETE /ocp/contribution/{id}**: Delete a contribution record

## How It Works

1. The Notion database contains events with "Event Lead", "Event Staff", and "Logistics Staff" properties, which contain officers assigned to these roles
2. The OCP module syncs with Notion, extracts these assignments, and calculates points based on the roles and event types
3. Points are stored in the OCP database, linked to both the officer and the originating Notion event
4. APIs provide access to this data for reporting and display purposes, including a leaderboard
5. Manual CRUD operations allow for custom point assignments outside of Notion events
6. Automated syncs run every 15 minutes to keep data fresh without manual intervention

## Integration

The OCP module integrates with:

1. **Calendar Module**: Reuses the Notion client to access event data and exposes endpoints as a sub-module
2. **Configuration**: Uses the same Notion database ID from the application config
3. **APScheduler**: Scheduled sync job runs automatically through the application's background scheduler
4. **Sentry**: Performance monitoring and error tracking for all sync operations

## Getting Started

1. Ensure your Notion database has the required properties for officer assignments
2. Configure the application with your Notion API key and database ID
3. Start the application, which will automatically begin syncing on the configured schedule
4. Access officer points data through the provided endpoints

## Example Usage

### Triggering a Sync Manually

```
POST /ocp/sync-from-notion
```

### Getting the Officer Leaderboard

```
GET /ocp/officers
```

Response:
```json
{
  "status": "success",
  "officers": [
    {
      "email": "officer1@example.com",
      "name": "Officer One",
      "title": "Vice President",
      "department": "Engineering",
      "total_points": 8,
      "contribution_counts": {
        "GBM": 4,
        "Special Event": 2,
        "Special Contribution": 0,
        "Unique Contribution": 0,
        "Other": 0
      }
    },
    {
      "email": "officer2@example.com",
      "name": "Officer Two",
      "title": "Secretary",
      "department": "Marketing",
      "total_points": 5,
      "contribution_counts": {
        "GBM": 3,
        "Special Event": 1,
        "Special Contribution": 0,
        "Unique Contribution": 0,
        "Other": 0
      }
    }
  ],
  "leaderboard_description": "Officers ranked by total contribution points"
}
```

### Getting Contributions for a Specific Officer

```
GET /ocp/officer/officer1@example.com/contributions
```

Response:
```json
{
  "status": "success",
  "contributions": [
    {
      "id": 1,
      "points": 1,
      "event": "Weekly Meeting",
      "role": "Event Lead",
      "event_type": "GBM",
      "timestamp": "2023-10-15T14:00:00",
      "notion_page_id": "abc123"
    },
    {
      "id": 2,
      "points": 2,
      "event": "Tech Workshop",
      "role": "Event Staff",
      "event_type": "Special Event",
      "timestamp": "2023-09-20T18:30:00",
      "notion_page_id": "def456"
    },
    {
      "id": 3,
      "points": 3,
      "event": "Website Redesign",
      "role": "Custom",
      "event_type": "Unique Contribution",
      "timestamp": "2023-11-05T16:00:00",
      "notion_page_id": null
    }
  ]
}
```

### Adding a Custom Contribution

```
POST /ocp/add-contribution
Content-Type: application/json

{
  "email": "officer1@example.com",
  "name": "Officer One",
  "event": "Website Redesign",
  "points": 3,
  "role": "Custom",
  "event_type": "Unique Contribution"
}
```

Response:
```json
{
  "status": "success",
  "message": "Added 3 points for officer1@example.com",
  "record_id": 4
}
```

### Updating a Contribution

```
PUT /ocp/contribution/4
Content-Type: application/json

{
  "points": 2,
  "event": "Website Redesign (Phase 1)"
}
```

Response:
```json
{
  "status": "success",
  "message": "Updated points record 4"
}
```

### Deleting a Contribution

```
DELETE /ocp/contribution/4
```

Response:
```json
{
  "status": "success",
  "message": "Deleted points record 4"
}
``` 