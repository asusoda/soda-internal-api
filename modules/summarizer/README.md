# Summarizer Module

A Discord bot module that generates concise, on-demand summaries of recent channel activity. This bot helps users catch up on active Discord channels after being away by providing summaries of recent messages.

## Features

- Request summaries of the current channel's recent message history
- Summaries triggered via both message context menu ("Summarize Channel") and slash command (`/summarize`)
- Support for two summarization modes:
  - Duration-based: Specify a timeframe to look back from now (e.g., last 24 hours)
  - Timeline: Specify exact date ranges for more targeted summaries
- Utilizes Google Genai API with Gemini 2.5 Flash Preview to create accurate and informative summaries
- Presents summaries as ephemeral messages (visible only to the requesting user) with option for public visibility
- Markdown-formatted summaries with proper headers and bullet points, including key information like participants, topics discussed, arguments, actionables, and links to key messages
- Smart citation system that links to original messages for easy reference
- Automatic splitting of long summaries into multiple messages for better readability

## Commands

- **Slash Command**: `/summarize [mode] [duration] [start_date] [end_date] [public]`
  - `mode`: Choose between "duration" (default) or "timeline"
  - `duration`: When using duration mode, specify one of: `1h`, `24h` (default), `1d`, `3d`, `7d`, `1w`
  - `start_date`: When using timeline mode, specify start date in YYYY-MM-DD format
  - `end_date`: When using timeline mode, specify end date in YYYY-MM-DD format
  - `public`: Boolean flag to make the summary visible to everyone (default: false)

- **Context Menu**: Right-click a message -> Apps -> "Summarize Channel"
  - Presents a modal with options to select mode (Duration or Timeline)
  - For duration mode: select from predefined periods
  - For timeline mode: enter start and end dates manually

## Requirements

- Discord API permissions: Read Message History
- Gemini API key for AI-powered summarization
- Proper error handling for cases with no messages or API failures

## Technical Architecture

- `api.py`: Flask API endpoints for the summarizer module
- `models.py`: Data models for storing summary configurations
- `service.py`: Business logic for generating summaries using Gemini API
- `discord_modules/cog.py`: Discord commands implementation using py-cord