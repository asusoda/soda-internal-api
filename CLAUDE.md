# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

SoDA Internal API is a modular monolith for a university computer science student organization. It provides multiple services including:

- Member points tracking system
- Events calendar with Notion and Google Calendar integration
- Discord bot with Jeopardy game functionality
- User authentication and management
- Web-based control panel built with React

## Environment Setup

The project uses both Python (Poetry) and JavaScript (npm) dependencies:

```bash
# Python setup with Poetry
poetry install

# Alternatively, use pip
pip install -r requirements.txt

# Frontend setup
cd web
npm install
```

## Build Commands

```bash
# Build frontend
cd web
npm install
npm run build

# Complete build (frontend only)
./build.sh

# Build Docker image
docker build -t soda-internal-api .
```

## Run Commands

```bash
# Run development server
python main.py  

# Run with Gunicorn (production)
gunicorn --bind 0.0.0.0:8000 wsgi:app

# Run in Docker container
docker run -p 8000:8000 -v /path/to/data:/app/data soda-internal-api
```

## Project Architecture

### Backend Structure

The backend follows a modular structure with Flask blueprints for different features:

1. **Modules**: Separated into domain-specific components:
   - `auth`: Authentication and authorization
   - `bot`: Discord bot functionality and Jeopardy game
   - `calendar`: Notion and Google Calendar integration
   - `points`: Member points management system
   - `public`: Public-facing endpoints
   - `users`: User management
   - `utils`: Shared utilities

2. **Key Files**:
   - `main.py`: Application entry point
   - `shared.py`: Shared resources and configuration
   - `modules/utils/config.py`: Configuration management
   - `modules/utils/db.py`: Database connection

### Discord Bot

The Discord bot is implemented using py-cord (v2.6.1) and provides:
- Game management with teams
- Jeopardy game functionality
- Command handling through cogs
- Discord event handling

### Calendar Integration

The calendar service synchronizes events between Notion and Google Calendar:
- Runs on a 15-minute schedule via APScheduler
- Handles sync between Notion and Google Calendar
- Uses Notion and Google API clients

### Points System

Manages the organization's member points tracking:
- API endpoints for awarding and viewing points
- Models for storing point transactions
- Frontend integration for leaderboards

### Database

The application uses SQLite with SQLAlchemy ORM:
- Database file located at `./data/user.db`
- Migrations handled in `migrations/__init__.py`

### Deployment

The application is containerized with Docker:
- Multi-stage build for both backend and frontend
- Non-root user for security
- Volume mounting for persistent data

## Common Operations

1. **Adding a new API endpoint**:
   - Create/modify the relevant file in the appropriate module directory
   - Register the blueprint in `main.py` if it's a new module

2. **Modifying Discord bot commands**:
   - Update files in `modules/bot/discord_modules/cogs/`

3. **Working with calendar integration**:
   - Main service logic is in `modules/calendar/service.py`
   - API endpoints are in `modules/calendar/api.py`

4. **Database changes**:
   - Add migrations to `migrations/__init__.py`
   - Update models in the relevant module's `models.py`