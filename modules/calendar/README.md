# Calendar Module - Multi-Organization Calendar System

## Overview

The calendar module provides a comprehensive multi-organization calendar synchronization system that integrates Notion databases with Google Calendar. Each organization can have its own Notion database and Google Calendar, with automatic synchronization between the two platforms.

## Architecture

### Multi-Organization Design

The system is designed to support multiple organizations, each with:
- **Independent Notion Database**: Each organization can have its own Notion database for events
- **Dedicated Google Calendar**: Each organization gets its own Google Calendar
- **Organization-Specific Configuration**: Calendar settings stored per organization
- **Public Event Endpoints**: Each organization has its own public event endpoint

### Key Components

#### 1. **MultiOrgCalendarService** (`service.py`)
The main service layer that handles:
- **Calendar Creation**: Automatically creates Google Calendars for new organizations
- **Event Synchronization**: Syncs events from Notion to Google Calendar per organization
- **Event Management**: Handles creation, updates, and deletion of events
- **Caching**: Caches frontend events for performance

#### 2. **GoogleCalendarClient** (`clients.py`)
Handles all Google Calendar API operations:
- **Calendar Management**: Create, list, get, and delete calendars
- **Event Operations**: Create, update, and delete events
- **Batch Operations**: Efficient batch processing for multiple events
- **Error Handling**: Comprehensive error handling and logging

#### 3. **NotionCalendarClient** (`clients.py`)
Manages Notion API interactions:
- **Event Fetching**: Retrieves events from organization-specific Notion databases
- **Property Extraction**: Extracts event properties from Notion pages
- **Error Handling**: Handles Notion API errors gracefully

#### 4. **CalendarEventDTO** (`models.py`)
Data transfer object for calendar events:
- **Notion Integration**: Parses Notion event data
- **Google Calendar Format**: Converts to Google Calendar format
- **Frontend Format**: Converts to frontend display format

## Database Schema

### Organizations Table
```sql
-- Calendar-related fields added to organizations table
google_calendar_id VARCHAR(255)     -- Google Calendar ID for this org
notion_database_id VARCHAR(255)     -- Notion database ID for this org
calendar_sync_enabled BOOLEAN       -- Whether calendar sync is enabled
last_sync_at DATETIME              -- Last successful sync timestamp
```

### Calendar Event Links Table
```sql
-- Links Notion events to Google Calendar events
organization_id INTEGER             -- Foreign key to organizations
notion_page_id VARCHAR(255)        -- Notion page ID
google_calendar_event_id VARCHAR(255) -- Google Calendar event ID
notion_database_id VARCHAR(255)    -- Which Notion database
google_calendar_id VARCHAR(255)    -- Which Google Calendar
```

## API Endpoints

### Organization-Specific Endpoints

#### Get Organization Events
```
GET /api/calendar/{org_prefix}/events
```
Returns events for a specific organization in frontend format.

**Response:**
```json
{
  "status": "success",
  "organization_id": 1,
  "organization_name": "ACM",
  "events": [
    {
      "id": "notion-page-id",
      "title": "Event Title",
      "start": "2024-01-01T10:00:00Z",
      "end": "2024-01-01T11:00:00Z",
      "location": "Room 101",
      "description": "Event description"
    }
  ],
  "total_events": 5
}
```

#### Sync Organization Calendar
```
POST /api/calendar/{org_prefix}/sync
```
Manually sync events from Notion to Google Calendar for a specific organization.

**Response:**
```json
{
  "status": "success",
  "message": "Synced 10 events for organization 1",
  "organization_id": 1,
  "events_processed": [...]
}
```

#### Setup Organization Calendar
```
POST /api/calendar/{org_prefix}/setup
```
Create a new Google Calendar for an organization.

**Response:**
```json
{
  "status": "success",
  "message": "Calendar set up for organization acm",
  "calendar_id": "calendar-id@group.calendar.google.com",
  "organization_id": 1
}
```

### Global Endpoints

#### Sync All Organizations
```
POST /api/calendar/sync-all
```
Sync all organizations that have calendar sync enabled.

**Response:**
```json
{
  "status": "success",
  "total_organizations": 3,
  "organizations_processed": 2,
  "organizations_failed": 1,
  "organization_results": [...]
}
```

### Legacy Endpoints (Deprecated)

The following endpoints are maintained for backward compatibility but return errors directing users to the new organization-specific endpoints:

- `POST /api/calendar/notion-webhook` → Delegates to sync-all
- `GET /api/calendar/events` → Returns error (requires org context)
- `POST /api/calendar/delete-all-events` → Returns error (requires org context)

## Configuration

### Environment Variables

The system uses a shared Google service account for all organizations:

```env
# Google Calendar (shared across all organizations)
GOOGLE_SERVICE_ACCOUNT=path/to/google-secret.json

# Notion API (shared)
NOTION_API_KEY=your-notion-api-key

# Timezone
TIMEZONE=America/Phoenix
```

### Organization Configuration

Each organization stores its configuration in the database:

```python
# Enable calendar sync for an organization
org.calendar_sync_enabled = True
org.notion_database_id = "notion-database-id"
org.google_calendar_id = "calendar-id@group.calendar.google.com"
```

## Usage Examples

### 1. Setting Up a New Organization

```python
# Create organization in database
org = Organization(
    name="ACM",
    prefix="acm",
    notion_database_id="notion-db-id",
    calendar_sync_enabled=True
)

# Setup calendar (creates Google Calendar)
POST /api/calendar/acm/setup
```

### 2. Getting Events for Frontend

```javascript
// Fetch events for ACM organization
fetch('/api/calendar/acm/events')
  .then(response => response.json())
  .then(data => {
    console.log(data.events); // Array of events
  });
```

### 3. Manual Sync

    ```bash
# Sync specific organization
curl -X POST http://localhost:8000/api/calendar/acm/sync

# Sync all organizations
curl -X POST http://localhost:8000/api/calendar/sync-all
```

## Scheduled Sync

The system includes a scheduled job that runs every 15 minutes to sync all organizations:

```python
# In main.py
scheduler.add_job(unified_sync_job, 'interval', minutes=15)
```

The sync job:
1. **Checks all organizations** with calendar sync enabled
2. **Creates missing calendars** for organizations that don't have one
3. **Syncs events** from Notion to Google Calendar
4. **Updates sync timestamps** for tracking

## Error Handling

### Comprehensive Logging

The system includes detailed logging for debugging:

```python
# Service-level logging
logger.info(f"Created calendar {calendar_id} for organization {organization_id}")
logger.error(f"Failed to sync organization {org_id}: {error}")

# API-level logging
logger.info(f"Received GET request for organization events: {org_prefix}")
logger.warning(f"Organization with prefix '{org_prefix}' not found")
```

### Error Responses

All endpoints return structured error responses:

```json
{
  "status": "error",
  "message": "Organization not found"
}
```

### Sentry Integration

The system integrates with Sentry for error tracking and monitoring:
- **Transaction Spans**: Detailed performance monitoring
- **Error Context**: Rich error context for debugging
- **Custom Tags**: Organization-specific tags for filtering

## Security Considerations

### Google Calendar Permissions

- **Service Account**: Uses a single service account for all organizations
- **Calendar Isolation**: Each organization has its own calendar
- **Permission Management**: Calendars are created with appropriate permissions

### API Security

- **Organization Validation**: All endpoints validate organization existence
- **Active Organization Check**: Only active organizations are processed
- **Error Sanitization**: Errors don't expose sensitive information

## Performance Optimizations

### Caching

- **Frontend Events**: 5-minute TTL cache for organization events
- **Calendar Service**: Reuses Google Calendar service instance
- **Database Connections**: Shared database connection pool

### Batch Operations

- **Event Processing**: Batch processing for multiple events
- **Error Handling**: Continues processing even if some events fail
- **Transaction Management**: Proper transaction handling for data consistency

## Migration Guide

### From Single-Organization to Multi-Organization

1. **Run Migration Script**:
   ```bash
   python scripts/migrate_calendar_multi_org.py
   ```

2. **Update Organization Records**:
   ```sql
   UPDATE organizations 
   SET calendar_sync_enabled = TRUE,
       notion_database_id = 'your-notion-db-id'
   WHERE id = 1;
   ```

3. **Setup Calendars**:
   ```bash
   curl -X POST http://localhost:8000/api/calendar/{org_prefix}/setup
   ```

4. **Test Sync**:
   ```bash
   curl -X POST http://localhost:8000/api/calendar/{org_prefix}/sync
   ```

## Troubleshooting

### Common Issues

1. **Missing Google Service Account**:
   ```
   Warning: google-secret.json not found. Google Calendar features will be disabled.
   ```
   **Solution**: Create `google-secret.json` with service account credentials

2. **Organization Not Found**:
   ```
   Organization with prefix 'acm' not found or inactive
   ```
   **Solution**: Ensure organization exists and is active in database

3. **Missing Notion Database**:
   ```
   Organization 1 has no Notion database configured
   ```
   **Solution**: Set `notion_database_id` for the organization

### Debugging

1. **Check Logs**: All operations are logged with detailed context
2. **Sentry Dashboard**: Monitor errors and performance in Sentry
3. **Database Queries**: Check organization configuration in database
4. **API Testing**: Use the provided endpoints to test functionality

## Future Enhancements

- **Calendar Sharing**: Allow organizations to share calendars
- **Event Templates**: Predefined event templates for common activities
- **Advanced Filtering**: Filter events by date, type, or location
- **Webhook Support**: Real-time sync via Notion webhooks
- **Calendar Analytics**: Usage statistics and reporting
