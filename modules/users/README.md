# Users Module

The users module manages user accounts, profiles, and permissions in the SoDA Internal API.

## Structure

```
users/
├── api.py           # User API endpoints
└── user_reader.py   # User data access utilities
```

## Features

### User Management
- User account creation
- Profile management
- Role assignment
- Permission management
- Account deletion

### Profile Features
- Profile customization
- Contact information
- Preferences
- Activity history
- Achievement tracking

### Access Control
- Role-based permissions
- Permission inheritance
- Access level management
- Resource protection
- Audit logging

## API Endpoints

### User Management
- `POST /users/create`
  - Creates new user account
  - Sets initial profile
  - Assigns default role
  - Sends welcome email

- `POST /users/update`
  - Updates user information
  - Modifies profile
  - Changes preferences
  - Updates contact info

- `DELETE /users/delete`
  - Deactivates account
  - Archives data
  - Removes access
  - Sends confirmation

### Profile Management
- `GET /users/profile`
  - Returns user profile
  - Shows preferences
  - Displays activity
  - Lists achievements

- `PUT /users/profile`
  - Updates profile
  - Modifies preferences
  - Changes settings
  - Updates contact info

### Role Management
- `POST /users/roles`
  - Assigns roles
  - Updates permissions
  - Manages access
  - Tracks changes

- `GET /users/roles`
  - Lists user roles
  - Shows permissions
  - Displays hierarchy
  - Includes metadata

## Models

### User
- User ID
- Username
- Email
- Password hash
- Account status
- Created date
- Last login

### Profile
- Profile ID
- User ID
- Full name
- Contact info
- Preferences
- Bio
- Avatar

### Role
- Role ID
- Role name
- Permissions
- Description
- Created date
- Updated date

### Permission
- Permission ID
- Permission name
- Description
- Category
- Created date
- Updated date

## Configuration

Required environment variables:
- `USER_DATABASE_URL`: Database connection URL
- `USER_MIN_PASSWORD_LENGTH`: Minimum password length
- `USER_MAX_LOGIN_ATTEMPTS`: Maximum login attempts
- `USER_SESSION_TIMEOUT`: Session timeout duration

## Usage Example

```python
from modules.users.api import create_user, update_profile

# Create a new user
user = await create_user(
    username="john_doe",
    email="john@example.com",
    password="secure_password"
)

# Update user profile
await update_profile(
    user_id=user.id,
    full_name="John Doe",
    bio="Software Developer"
)
```

## Error Handling

The module handles various user-related errors:
- Invalid input data
- Duplicate accounts
- Permission denied
- Account locked
- Database errors

## Security Considerations

1. **Account Security**
   - Password hashing
   - Account locking
   - Session management
   - Two-factor auth

2. **Data Protection**
   - Data encryption
   - Access control
   - Audit logging
   - Backup systems

3. **Privacy**
   - Data minimization
   - Consent management
   - Data retention
   - Privacy controls

## Dependencies

- `SQLAlchemy`: Database ORM
- `bcrypt`: Password hashing
- `python-jose`: JWT handling
- `email-validator`: Email validation 