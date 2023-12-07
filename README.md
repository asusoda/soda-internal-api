# soda-bot
This project provides a web-based control panel for managing a Jeopardy-themed Discord bot. The control panel, built with React, allows authorized users to toggle the bot's status and schedule new Jeopardy games by uploading a JSON file. The server side, developed using Flask, handles API requests, Discord bot interactions, and game management.

## Requirements

#### Server (Flask App)
- Python 3.8 or newer
- Dependencies as listed in `server/requirements.txt`

#### Client (React App)
- Node.js and npm
- React and related dependencies

## Server Setup
1. Clone the repository:
   ```bash
   git clone https://github.com/asusoda/soda-bot.git
   ```
2. Navigate into `server` using
      ```
      cd server
      ```
3. Install the required Python packages:
   ```bash
   pip install -r requirements.txt
   ```

## Client Setup
1. Clone the repository if not already:
   ```bash
   git clone https://github.com/asusoda/soda-bot.git
   ```
2. Navigate into `client` using
      ```
      cd client
      ```
3. Install the required npm packages:
   ```bash
   npm install
   ```


## Discord Package Overview

The Discord package in the `soda-bot` repository is designed to facilitate a Jeopardy-style game within a Discord server. It consists of several Python files that work together to manage game interactions, handle Discord commands, and maintain game state.

### Key Components

#### Jeopardy.py
- **JeopardyQuestion Class**: Represents individual Jeopardy questions, including attributes like category, question text, answer, value, and a unique identifier. It can be serialized into JSON format.
- **JeopardyGame Class**: Manages the overall Jeopardy game within Discord. It handles:
  - Game initialization and state tracking (e.g., whether the game has started or been announced).
  - Team and player management.
  - Question handling, including creating and organizing questions by category.

#### Team.py
- **Team Class**: Represents teams participating in the game. Key features include:
  - Team name, members, and score tracking.
  - Methods for adding/removing points and team members.
  - JSON serialization of team data.

#### bot.py
- **BotFork Class**: An extension of the `discord.ext.commands.Bot` class, adding functionalities specific to the Jeopardy game. It includes:
  - Management of cogs for different functionalities.
  - Methods to start, stop, and manage the bot's online status.
  - Handling of the active game instance.

#### Cogs
- **GameCog.py**: A cog dedicated to game-related commands and interactions within Discord.
- **HelperCog.py**: A cog for auxiliary functions and utilities to assist in the bot's operations.

#### API Integration (server/routes)
- **api.py**: Defines routes for user information retrieval, bot status checks, game feature access, channel creation, and game cleanup.
- **auth_types.py**: Implements decorators for token-based and admin-only route access.
- **game_api.py**: Manages game data, including retrieval, upload, and control of game states and bot operations.
- **views.py**: Renders web views for user interaction, including login, logout, and admin panels.

### How It Works

1. **Game Setup and Management**: The `JeopardyGame` class initializes and manages the game, while `Team` class handles team operations. These are integrated with Discord commands through `bot.py` and its cogs.
2. **API Interaction**: 
   - User authentication and information retrieval are handled via Discord OAuth in `api.py`.
   - Game data management, including fetching available games and uploading new game data, is facilitated through `game_api.py`.
   - Bot control routes in `game_api.py` allow starting, stopping, and checking the status of the Discord bot.
3. **Web Interface**: The `views.py` file uses Flask to render web pages for user interaction, providing a seamless integration between the Discord bot and the web interface.

## API Overview for Soda-Bot

The API in the `soda-bot` repository plays a crucial role in integrating the Discord bot with the Jeopardy-style game, handling user interactions, and managing game data. This section provides an overview of the API endpoints and their functionalities.

### Key Components

#### api.py
- **User Information and Authentication**: 
  - Routes for Discord OAuth2 authentication and user information retrieval.
  - Error handling for unauthorized access, redirecting users to the login page.
- **Bot and Game Management**: 
  - Endpoints to check the bot's status, create game channels, and clean up active games.
  - Feature access points providing details about the application's capabilities.

#### auth_types.py
- **Access Control Decorators**: 
  - `token_required`: Ensures routes are accessed with a valid authorization token.
  - `admin_only`: Restricts access to certain routes to admin users only.

#### game_api.py
- **Game Data Handling**: 
  - Routes to retrieve available games and specific game data.
  - Endpoints for starting and stopping games.
- **Bot Control**: 
  - Endpoints to control the bot's operation, including starting and stopping the bot.
- **Game Interaction**: 
  - Routes for uploading game data, setting and getting the active game, and managing the game state.

#### views.py
- **Web Interface Rendering**: 
  - Routes for rendering web pages using Flask, including login, logout, panel, and unauthorized access pages.
  - Integration with Discord OAuth for user authentication and session management.

### API Functionality

1. **User Authentication and Management**: 
   - The API handles user authentication via Discord OAuth, providing secure access to the application.
   - User-specific data is retrieved and managed through dedicated endpoints.

2. **Game Setup and Control**: 
   - The API provides endpoints for setting up new games, uploading game data, and managing active game sessions.
   - It allows for starting and stopping both the game and the Discord bot, facilitating smooth game flow.

3. **Bot Interaction**: 
   - The API interacts with the Discord bot to relay commands and control the game's progress.
   - It includes endpoints for bot status checks and operational commands.

4. **Web Interface Integration**: 
   - The API works in tandem with Flask to render dynamic web pages for user interaction.
   - It ensures a seamless user experience from the web interface to the Discord bot interactions.



# Contributing to soda-bot

We welcome contributions to the soda-bot project! If you're looking to contribute, here's how you can help.
