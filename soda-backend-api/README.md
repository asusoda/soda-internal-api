# Notion to Google Calendar Sync Service

A Flask-based service that automatically synchronizes events between a Notion database and Google Calendar.

## Features

- Real-time synchronization of events from Notion to Google Calendar
- Webhook support for automatic updates
- Bidirectional sync with change tracking
- Support for event locations, descriptions, and attendees
- Automatic timezone handling
- Comprehensive error logging

## Prerequisites

- Python 3.8+
- Google Cloud Platform account with Calendar API enabled
- Notion API access
- Service account credentials from Google Cloud Platform

## Configuration

1. Create `appConfig.json` in the root directory:
```json
{
    "notion": {
        "api_key": "your-notion-api-key",
        "database_id": "your-notion-database-id"
    },
    "google": {
        "service_account_file": "clientsecret.json",
        "calendar_id": "your-calendar-id",
        "user_email": "your-email@domain.com"
    },
    "server": {
        "port": 5000,
        "debug": true,
        "timezone": "America/Phoenix"
    }
}
```

2. Place your Google service account credentials in `clientsecret.json`

## Installation

1. Clone the repository
2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Notion Database Setup

Your Notion database should have the following properties:
- `Name` (title): Event title
- `Date` (date): Event date and time
- `Location` (text): Event location
- `description` (text): Event description
- `guests` (text): Comma-separated email addresses
- `availability` (checkbox): Whether to sync the event

## Usage

1. Start the server:
```bash
python main.py
```

2. Configure Notion webhook to point to:
```
http://your-domain/notion-webhook
```

## How It Works

1. **Event Tracking**: The service maintains a state file (`event_state.json`) to track changes between syncs

2. **Webhook Processing**:
   - Receives notifications from Notion
   - Fetches updated event data
   - Syncs changes to Google Calendar

3. **Sync Process**:
   - Fetches events from Notion database
   - Parses event data
   - Creates/updates/deletes events in Google Calendar
   - Handles attendees and notifications

4. **Error Handling**:
   - Comprehensive error logging
   - Automatic retry mechanisms
   - State preservation

## API Endpoints

### `/notion-webhook`
- `GET`: Health check
- `POST`: Webhook endpoint for Notion updates

## Security Considerations

- Store sensitive credentials in `appConfig.json` (not in version control)
- Use environment variables in production
- Implement proper webhook authentication
- Restrict API access using appropriate scopes

## Logging

Logs are written to console with the following format:
```
%(asctime)s - %(levelname)s - %(message)s
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Submit a pull request

## Error Handling

The service includes comprehensive error handling:
- API failures
- Configuration issues
- Data parsing errors
- Calendar sync failures

## Future Improvements

- Add Soda's organization google account to enable guests
- Always write guests emails seperated by comma
