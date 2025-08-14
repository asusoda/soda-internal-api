# Organizations Module

The organizations module manages Discord organizations/guilds and their configurations in the SoDA Internal API.

## Structure

```
organizations/
├── models.py        # Organization models and relationships
└── config.py        # Organization configuration settings
```

## Features

### Organization Management
- Organization creation and deletion
- Basic organization information (name, description, icon)
- Organization status tracking
- Officer management
- Role-based access control

### Configuration Management
- Discord integration settings
- Points system configuration
- Event management settings
- Member management settings
- Calendar integration settings

## Models

### Organization
- `id`: Primary key
- `name`: Organization name
- `guild_id`: Discord guild ID
- `description`: Organization description
- `icon_url`: Organization icon URL
- `is_active`: Organization status
- `config`: JSON field for organization settings
- `created_at`: Creation timestamp
- `updated_at`: Last update timestamp
- `officers`: Relationship with officers

### OrganizationConfig
- `id`: Primary key
- `organization_id`: Foreign key to Organization
- `key`: Configuration key
- `value`: Configuration value (JSON)
- `created_at`: Creation timestamp
- `updated_at`: Last update timestamp

## Configuration Settings

### Discord Integration
- Enable/disable Discord integration
- Bot command prefix
- Admin roles
- Officer roles

### Points System
- Enable/disable points system
- Default points per event
- Maximum points per event
- Points decay rate

### Event Management
- Enable/disable event management
- Event approval requirements
- Maximum events per week

### Member Management
- Enable/disable member management
- Member verification requirements
- Verification methods

### Calendar Integration
- Enable/disable calendar integration
- Calendar sync interval

## Usage Example

```python
from modules.organizations.models import Organization
from modules.organizations.config import OrganizationSettings
from shared import db_connect

# Create a new organization
with db_connect.get_session() as session:
    org = Organization(
        name="My Organization",
        guild_id="123456789",
        description="A test organization"
    )
    session.add(org)
    session.commit()

# Get organization settings
settings = OrganizationSettings()
org.config = settings.to_dict()
session.commit()

# Update specific settings
settings.discord_bot_prefix = "?"
org.config = settings.to_dict()
session.commit()
```

## Database Schema

### organizations
```sql
CREATE TABLE organizations (
    id INTEGER PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    guild_id VARCHAR(50) NOT NULL UNIQUE,
    description VARCHAR(500),
    icon_url VARCHAR(255),
    is_active BOOLEAN DEFAULT TRUE,
    config JSON DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### organization_configs
```sql
CREATE TABLE organization_configs (
    id INTEGER PRIMARY KEY,
    organization_id INTEGER NOT NULL,
    key VARCHAR(100) NOT NULL,
    value JSON NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (organization_id) REFERENCES organizations(id)
);
```

### officer_org
```sql
CREATE TABLE officer_org (
    officer_id INTEGER NOT NULL,
    organization_id INTEGER NOT NULL,
    role VARCHAR(50) NOT NULL DEFAULT 'officer',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (officer_id, organization_id),
    FOREIGN KEY (officer_id) REFERENCES officers(id),
    FOREIGN KEY (organization_id) REFERENCES organizations(id)
);
``` 