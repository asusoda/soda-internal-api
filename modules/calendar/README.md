# Notion to Google Calendar Sync Service

A Flask-based service that automatically synchronizes events between a Notion database and Google Calendar.

![image](https://github.com/user-attachments/assets/eca21b10-f1a8-49aa-ad1e-cbc5e0555cd5)

![image](https://github.com/user-attachments/assets/8187e0a7-1bd3-4905-9f09-d2865d8dd42d)

![image](https://github.com/user-attachments/assets/47fb0d11-81c1-42cf-b4d8-48df8ad2caeb)

![image](https://github.com/user-attachments/assets/15b96b1d-6f92-4555-9b40-ce5d9f6fabc5)

![image](https://github.com/user-attachments/assets/cc6119e9-4644-4da5-a68a-3262e0d96a47)

![image](https://github.com/user-attachments/assets/03c41cdf-8a45-4973-89ec-c31f0a22debe)

![image](https://github.com/user-attachments/assets/0e0b9a6b-8639-4b9a-857e-0fc3f6a99df6)

### Mentioning a guest won't work since this is not an organizational account and Domain wide permission is required to add Guests to events, which can be only done with a google organizational account as super admin

#### Always seperate guest's emails with comma
![image](https://github.com/user-attachments/assets/b7915db8-4137-4fce-8fd3-277985238788)

![image](https://github.com/user-attachments/assets/bd200bf3-dba2-4757-9e38-438a0aa723ef)


## Features

- Real-time synchronization of events from Notion to Google Calendar
- Webhook support for automatic updates
- Bidirectional sync with change tracking
- Support for event locations, Descriptions, and attendees
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

Add the following variables to your `.env` file in the root directory:

```bash
# Calendar Integration
NOTION_API_KEY=your-notion-api-key
NOTION_DATABASE_ID=your-notion-database-id
GOOGLE_SERVICE_ACCOUNT_JSON={"type": "service_account", ...}
GOOGLE_CALENDAR_ID=your-calendar-id
GOOGLE_USER_EMAIL=your-email@domain.com
SERVER_PORT=5000
SERVER_DEBUG=false
TIMEZONE=America/Phoenix
```

## Installation

1. Install additional dependencies:
```bash
pip install flask google-auth google-api-python-client notion-client python-dotenv
```

## Notion Database Requirements

Your Notion database must include (otherwise):
- `Name` (title): Event title
- `Date` (date): Event date and time (Always include start time date and end date time)
- `Location` (text): Event location
- `Description` (text): Event Description
- `Guests` (text): Comma-separated email addresses
- `Published` (checkbox): events to show up in google cal

## API Endpoint

### `/calendar/notion-webhook`
- `GET`: Health check endpoint
- `POST`: Webhook endpoint for Notion updates

## Important Notes

- **Guest Limitations**: Adding Guests requires a Google Workspace account with domain-wide permissions
- **Email Format**: Always separate guest emails with commas
- **Timezone**: Default timezone set to America/Phoenix

## Security Considerations

- Credentials stored as environment variables
- Service account authentication for Google Calendar
- Webhook authentication ready
- API scope restrictions implemented

## Error Handling

The service includes comprehensive error handling for:
- API failures
- Configuration validation
- Data parsing errors
- Calendar synchronization issues

## Integration

The service is registered as a blueprint in `main.py`:
```python
from modules.calendar.api import calendar_blueprint
app.register_blueprint(calendar_blueprint, url_prefix="/calendar")
```

## Future Improvements

- Add Soda's organization google account to enable Guests
- Always write Guests emails seperated by comma
