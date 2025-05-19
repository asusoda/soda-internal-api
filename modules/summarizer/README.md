# Summarizer Module

A Discord bot module that generates concise, on-demand summaries of recent channel activity and answers questions about conversations. This bot helps users catch up on active Discord channels after being away by providing summaries and targeted answers to questions about message history.

## Features

- Request summaries of the current channel's recent message history using `/summarize`
- Ask questions about conversations with natural language date detection using `/ask`
- Sophisticated natural language date parsing with support for:
  - Standard duration formats (`24h`, `3d`, `1w`)
  - Relative expressions (`last week`, `past 3 days`, `last month`)
  - Month references (`last january`, `this april`)
  - Date ranges (`january to february`, `from december to january`)
  - Time expressions embedded in questions (e.g., "What happened last month?")
- Support for two timeframe modes:
  - Duration-based: Specify a timeframe to look back from now (e.g., last 24 hours)
  - Timeline: Specify exact date ranges for more targeted analysis
- Utilizes Google Genai API with Gemini 2.5 Flash Preview to create accurate and informative summaries and answers
- Presents all responses as ephemeral messages (visible only to the requesting user) with option for public visibility
- Markdown-formatted responses with proper headers and bullet points, including key information like participants, topics discussed, arguments, actionables, and links to key messages
- Smart citation system that links to original messages for easy reference
- Automatic splitting of long responses into multiple messages for better readability

## Commands

- **Slash Command**: `/summarize [timeframe]`
  - `timeframe`: Optional natural language timeframe (defaults to 24h)
  - Examples:
    - `/summarize` - Summarizes the last 24 hours
    - `/summarize 3 days` - Summarizes the last 3 days
    - `/summarize last week` - Summarizes the past week
    - `/summarize last january` - Summarizes January of the current/previous year
    - `/summarize january to february` - Summarizes January through February
    - `/summarize from last april to last june` - Summarizes April through June

- **Slash Command**: `/ask [question] [timeframe]`
  - `question`: The question to ask about the conversation
  - `timeframe`: Optional natural language timeframe (defaults to 24h)
  - Smart detection of timeframes within questions
  - Examples:
    - `/ask "Who made the final decision?"` - Uses default 24h timeframe
    - `/ask "What happened last month?"` - Automatically detects "last month" as timeframe
    - `/ask "What was discussed?" timeframe: last week` - Explicitly sets timeframe to "last week"

- **Natural Language Date Parsing**
  Both commands support a wide range of natural language date expressions:
  - Standard durations: `24h`, `3d`, `1w`
  - Relative terms: `last week`, `past 3 days`, `last month`
  - Month names: `last january`, `this april`
  - Date ranges: `january to february`, `from last december to last january`
  - Time expressions embedded in questions (for `/ask` command)

- All summaries and answers are initially private (visible only to the requester) with a "Make Public" button to share with the channel

## Requirements

- Discord API permissions: Read Message History
- Gemini API key for AI-powered summarization
- Proper error handling for cases with no messages or API failures

## Technical Architecture

- `api.py`: Flask API endpoints for the summarizer module
- `models.py`: Data models for storing summary configurations
- `service.py`: Business logic for generating summaries using Gemini API
  - Contains the natural language date parsing functionality in the `parse_date_range` method
- `discord_modules/cog.py`: Discord commands implementation using py-cord

## Implementation Details

### Natural Language Date Parsing

The date parsing functionality in `service.py` handles the following cases:

1. Standard duration formats (`24h`, `3d`, `1w`)
2. Month references (`last january`, `this april`)
3. Date ranges (`january to february`, `from december to january`)
4. Relative expressions (`last week`, `past 3 days`)

The implementation uses a combination of:
- Regular expressions for pattern matching
- The `dateparser` library for general natural language parsing
- Custom logic for handling specific date range formats

When parsing month references, the code intelligently determines whether to use the current year or previous year based on the current month. For example, in May 2025:
- "last january" refers to January 2025 (current year, since January is before May)
- "last june" refers to June 2024 (previous year, since June is after May)