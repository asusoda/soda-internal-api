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
  - The command internally extracts standardized timeframe references from the provided parameter
  - Examples:
    - `/summarize` - Summarizes the last 24 hours
    - `/summarize 3 days` - Summarizes the last 3 days
    - `/summarize last week` - Summarizes the past week
    - `/summarize the past week` - Summarizes the last 7 days
    - `/summarize last january` - Summarizes January of the current/previous year
    - `/summarize january to february` - Summarizes January through February
    - `/summarize from last april to last june` - Summarizes April through June

- **Slash Command**: `/ask [question]`
  - `question`: The question to ask about the conversation (include timeframe references directly in your question)
  - Smart detection of timeframes within questions (defaults to 24h if none is found)
  - Examples:
    - `/ask "Who made the final decision?"` - Uses default 24h timeframe
    - `/ask "What happened last month?"` - Automatically detects "last month" as timeframe
    - `/ask "What did Alice discuss the past week?"` - Automatically extracts "the past week" as timeframe

- **Natural Language Date Parsing**
  Both commands support a wide range of natural language date expressions:
  - Standard durations: `24h`, `3d`, `1w`
  - Relative terms: `last week`, `past 3 days`, `the past week`, `last month`
  - Month names: `last january`, `this april`
  - Date ranges: `january to february`, `from last december to last january`
  - Time expressions embedded in questions are automatically extracted

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

The date parsing functionality is implemented with a two-stage approach:

1. **Timeframe Extraction** (`extract_timeframe_from_text`):
   - Extracts standardized timeframe references from natural language text
   - Maps expressions like "the past week" to standard durations like "7d"
   - Preserves calendar-aligned expressions like "last week" as-is
   
2. **Date Range Parsing** (`parse_date_range`):
   - Processes the standardized timeframe references into actual date ranges
   - Handles calendar expressions (e.g., "last week", "this month")
   - Processes duration formats (e.g., "7d", "24h", "3d")
   - Handles date ranges and other complex expressions

#### Timeframe Formats Handled

1. **Standard duration formats**: `24h`, `3d`, `1w`
2. **Month references**: `last january`, `this april`
3. **Date ranges**: `january to february`, `from december to january`
4. **Calendar expressions**: `last week`, `this month`, `yesterday`
5. **Duration expressions**: `past 7 days`, `the past week`, `past month`

The implementation uses a combination of:
- Regular expressions for pattern matching
- The `dateparser` and `timefhuman` libraries for general natural language parsing
- Custom logic for handling specific date range formats

#### Consistent Behavior Between Commands

Both `/summarize` and `/ask` commands now use the same exact timeframe extraction logic:

1. First extract standardized timeframe references using `extract_timeframe_from_text`
2. Then parse the standardized references into date ranges using `parse_date_range`

This ensures that expressions like "the past week" are treated consistently in both commands, being properly translated to "7d" and handled as a 7-day duration.

#### Special Date Handling

When parsing month references, the code intelligently determines whether to use the current year or previous year based on the current month. For example, in May 2025:
- "last january" refers to January 2025 (current year, since January is before May)
- "last june" refers to June 2024 (previous year, since June is after May)