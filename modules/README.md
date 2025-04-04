# Modules

This directory contains the core modules that power SoDA's internal tools. Each module is designed to handle a specific domain of functionality while following consistent architectural patterns.

## Module Structure

Each module follows a standard structure:
```
module_name/
├── api.py           # Public API endpoints and route handlers
├── models.py        # Database models and schemas
├── migrations/      # Database migrations (if needed)
└── README.md        # Module-specific documentation
```

### Required Files
- `api.py`: Contains all public-facing endpoints and route handlers
- `models.py`: Defines database models using SQLAlchemy
- `README.md`: Documents the module's purpose, setup, and usage

## Module Descriptions

### auth
The authentication module handles all aspects of user authentication and authorization.

**Key Features:**
- User login/logout functionality
- JWT token management
- Role-based access control
- Session management
- OAuth2 integration

**Endpoints:**
- `/auth/login` - User authentication
- `/auth/logout` - Session termination
- `/auth/refresh` - Token refresh
- `/auth/verify` - Token validation

### bot
The Discord bot module manages all Discord-related functionality.

**Key Features:**
- Discord bot initialization and management
- Command handling system
- Event listeners
- Cog management
- Integration with other modules

**Components:**
- Bot core functionality
- Command cogs
- Event handlers
- Utility functions
- Configuration management

### points
The points module manages the Distinguished Members program's point system.

**Key Features:**
- Point awarding and deduction
- Point history tracking
- User point balances
- Point transaction validation
- Leaderboard functionality

**Models:**
- `PointTransaction`
- `PointBalance`
- `PointRule`

**Endpoints:**
- `/points/award` - Award points to users
- `/points/deduct` - Deduct points from users
- `/points/balance` - Get user point balance
- `/points/history` - Get point transaction history
- `/points/leaderboard` - Get current leaderboard

### public
The public module hosts endpoints accessible without authentication.

**Key Features:**
- Public information endpoints
- Status checks
- Documentation endpoints
- Health monitoring
- Public statistics

**Endpoints:**
- `/status` - System status
- `/health` - Health check
- `/docs` - API documentation
- `/stats` - Public statistics

### users
The users module manages user accounts and profiles.

**Key Features:**
- User account management
- Profile management
- Role management
- Permission handling
- User search and filtering

**Models:**
- `User`
- `Profile`
- `Role`
- `Permission`

**Endpoints:**
- `/users/create` - Create new user
- `/users/update` - Update user details
- `/users/delete` - Delete user account
- `/users/search` - Search users
- `/users/roles` - Manage user roles

### utils
The utilities module provides shared functionality across the application.

**Key Features:**
- Database utilities
- Configuration management
- Logging setup
- Error handling
- Common helper functions

**Components:**
- Database connection management
- Configuration loading
- Logging configuration
- Error handlers
- Utility functions

## Best Practices

1. **Module Independence:**
   - Each module should be self-contained
   - Minimize cross-module dependencies
   - Use clear interfaces for inter-module communication

2. **API Design:**
   - Follow RESTful principles
   - Use consistent endpoint naming
   - Document all endpoints
   - Include proper error handling

3. **Database Models:**
   - Use SQLAlchemy for models
   - Follow naming conventions
   - Include proper indexes
   - Document relationships

4. **Error Handling:**
   - Use consistent error responses
   - Include proper logging
   - Handle edge cases
   - Provide helpful error messages



## Adding New Modules

To add a new module:

1. Create a new directory under `modules/`
2. Add required files (`api.py`, `models.py`, `README.md`)
3. Follow the module structure
4. Document the module's purpose and functionality
5. Add necessary tests

## Dependencies

Each module may have its own dependencies, which should be:
- Listed in the module's README
- Added to the main `requirements.txt`
- Documented with version numbers
- Kept up to date