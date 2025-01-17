# Modules

Each module in this project handles a specific need for SoDA's internal tools. As a general rule of practice, all modules hosting public-facing endpoints must have an `api.py` for hosting public APIs and a `models.py` for declaring any models that need to be stored in the database.

## Module Descriptions

### auth
The `auth` module handles authentication and authorization for the application. It includes endpoints for user login, logout, and token management, as well as decorators for protecting routes.

### bot
The `bot` module manages the Discord bot interactions. It includes the bot's main functionality, command handling, and integration with Discord's API. This module also contains the bot's cogs and other related components.

### points
The `points` module manages the points for the Distinguished Members program. It includes endpoints for awarding, deducting, and querying points for users. It also defines the models for storing points-related data in the database.

### public
The `public` module hosts public-facing APIs that do not require authentication. These endpoints provide general information and services that are accessible to all users.

### users
The `users` module handles user management, including endpoints for creating, updating, and deleting user accounts. It also includes functionality for reading user data and managing user roles and permissions.

### utils
The `utils` module contains utility functions and helper classes that are used across the application. This includes configuration management, database utilities, and token management.