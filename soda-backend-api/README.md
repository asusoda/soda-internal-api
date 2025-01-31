# Notion to Google Calendar Sync Service

A Flask-based service that automatically synchronizes events between a Notion database and Google Calendar.

![image](https://github.com/user-attachments/assets/eca21b10-f1a8-49aa-ad1e-cbc5e0555cd5)

![image](https://github.com/user-attachments/assets/8187e0a7-1bd3-4905-9f09-d2865d8dd42d)

![image](https://github.com/user-attachments/assets/47fb0d11-81c1-42cf-b4d8-48df8ad2caeb)

![image](https://github.com/user-attachments/assets/15b96b1d-6f92-4555-9b40-ce5d9f6fabc5)

![image](https://github.com/user-attachments/assets/cc6119e9-4644-4da5-a68a-3262e0d96a47)

![image](https://github.com/user-attachments/assets/03c41cdf-8a45-4973-89ec-c31f0a22debe)

![image](https://github.com/user-attachments/assets/0e0b9a6b-8639-4b9a-857e-0fc3f6a99df6)

### Mentioning a guest won't work since this is not an organizational account and Domain wide permission is required to add guests to events, which can be only done with a google organizational account as super admin

#### Always seperate guest's emails with comma
![image](https://github.com/user-attachments/assets/b7915db8-4137-4fce-8fd3-277985238788)

![image](https://github.com/user-attachments/assets/bd200bf3-dba2-4757-9e38-438a0aa723ef)


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
  ![image](https://github.com/user-attachments/assets/1021026e-e720-4f5b-9848-c70810913fb5)

- Notion API access
  ![image](https://github.com/user-attachments/assets/e2a6d53e-5fc8-42df-a53e-eba79cae3d14)

- Service account credentials from Google Cloud Platform
  ![image](https://github.com/user-attachments/assets/7d649e1a-e0a5-43fb-8165-b41aa22a1d2d)

- Calender permissions
  ![image](https://github.com/user-attachments/assets/2d8076ce-76e9-4856-928b-0e25fe0139d9)

  ![image](https://github.com/user-attachments/assets/c7847205-5e9c-434f-ad65-31f2d9b93ccd)


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
