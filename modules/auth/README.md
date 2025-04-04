# Authentication Module

The authentication module handles all aspects of user authentication and authorization in the SoDA Internal API.

## Structure

```
auth/
├── api.py           # Authentication endpoints
└── decorators.py    # Authentication decorators
```

## Features

### Authentication
- JWT-based authentication
- Session management
- Token refresh mechanism
- OAuth2 integration
- Role-based access control

### Security
- Secure token storage
- Token expiration
- CSRF protection
- Rate limiting
- Secure password handling

## API Endpoints

### Authentication
- `POST /auth/login`
  - Authenticates a user
  - Returns JWT tokens
  - Sets session cookies

- `POST /auth/logout`
  - Invalidates current session
  - Clears session cookies
  - Revokes tokens

- `POST /auth/refresh`
  - Refreshes expired tokens
  - Returns new access token
  - Maintains session

- `GET /auth/verify`
  - Validates current token
  - Returns user information
  - Checks permissions

## Decorators

### @requires_auth
- Validates JWT token
- Checks token expiration
- Verifies user permissions

### @requires_role(role)
- Checks user role
- Validates permissions
- Handles role hierarchy

## Configuration

Required environment variables:
- `JWT_SECRET_KEY`: Secret key for JWT tokens
- `JWT_ACCESS_TOKEN_EXPIRES`: Access token expiration time
- `JWT_REFRESH_TOKEN_EXPIRES`: Refresh token expiration time
- `OAUTH_CLIENT_ID`: OAuth client ID
- `OAUTH_CLIENT_SECRET`: OAuth client secret

## Usage Example

```python
from modules.auth.decorators import requires_auth, requires_role

@requires_auth
def protected_route():
    # Route logic here
    pass

@requires_role('admin')
def admin_route():
    # Admin-only logic here
    pass
```

## Error Handling

The module handles various authentication errors:
- Invalid tokens
- Expired tokens
- Missing permissions
- Invalid credentials
- Rate limit exceeded

## Security Considerations

1. **Token Security**
   - Tokens are signed with a secure key
   - Access tokens have short expiration
   - Refresh tokens are stored securely

2. **Password Security**
   - Passwords are hashed using bcrypt
   - Salt is generated for each password
   - Password strength requirements

3. **Session Security**
   - Sessions are tied to IP addresses
   - Session timeouts are enforced
   - Concurrent sessions are limited

## Dependencies

- `PyJWT`: JWT token handling
- `bcrypt`: Password hashing
- `Flask-JWT-Extended`: JWT integration
- `oauthlib`: OAuth2 implementation 