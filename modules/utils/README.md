# Utilities Module

The utilities module provides shared functionality and helper classes used across the SoDA Internal API.

## Structure

```
utils/
├── config.py         # Configuration management
├── TokenManager.py   # Token handling utilities
└── db.py            # Database utilities
```

## Features

### Configuration Management
- Environment variable handling
- Configuration validation
- Default value management
- Secret management
- Configuration reloading

### Database Utilities
- Connection pooling
- Query building
- Transaction management
- Error handling
- Connection retry logic

### Token Management
- Token generation
- Token validation
- Token storage
- Token rotation
- Token cleanup

## Components

### Config
- Environment loading
- Configuration validation
- Secret management
- Default values
- Type conversion

### Database
- Connection management
- Query execution
- Transaction handling
- Error recovery
- Connection pooling

### TokenManager
- Token generation
- Token validation
- Token storage
- Token rotation
- Token cleanup

## Usage Examples

### Configuration
```python
from modules.utils.config import config

# Access configuration values
db_url = config.DB_URL
api_key = config.API_KEY

# Set configuration values
config.set('DEBUG', True)
```

### Database
```python
from modules.utils.db import DBConnect

# Create database connection
db = DBConnect()

# Execute query
result = db.execute("SELECT * FROM users")

# Use context manager
with db.transaction():
    db.execute("INSERT INTO users (name) VALUES ('John')")
```

### Token Management
```python
from modules.utils.TokenManager import TokenManager

# Initialize token manager
token_manager = TokenManager()

# Generate token
token = token_manager.generate_token(user_id="123")

# Validate token
is_valid = token_manager.validate_token(token)
```

## Configuration

Required environment variables:
- `DATABASE_URL`: Database connection URL
- `TOKEN_SECRET`: Token signing secret
- `TOKEN_EXPIRY`: Token expiration time
- `ENVIRONMENT`: Application environment

## Error Handling

The module handles various utility-related errors:
- Configuration errors
- Database connection errors
- Token validation errors
- Environment errors
- Type conversion errors

## Security Considerations

1. **Configuration Security**
   - Secret encryption
   - Environment isolation
   - Access control
   - Audit logging

2. **Database Security**
   - Connection encryption
   - Query sanitization
   - Access control
   - Error masking

3. **Token Security**
   - Secure generation
   - Proper validation
   - Secure storage
   - Regular rotation

## Dependencies

- `python-dotenv`: Environment management
- `SQLAlchemy`: Database ORM
- `PyJWT`: Token handling
- `cryptography`: Encryption utilities 