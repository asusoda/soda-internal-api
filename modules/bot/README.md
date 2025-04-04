# Discord Bot Module

The Discord bot module manages all Discord-related functionality and interactions for the SoDA Internal API.

## Structure

```
bot/
├── api.py               # Bot API endpoints
├── models.py            # Bot-related models
└── discord_modules/     # Discord-specific components
    ├── cogs/           # Bot command modules
    ├── events/         # Event handlers
    └── utils/          # Bot utilities
```

## Features

### Bot Management
- Bot initialization and configuration
- Command registration and handling
- Event listening and processing
- State management
- Error handling

### Command System
- Slash commands
- Text commands
- Command permissions
- Command cooldowns
- Command help system

### Event Handling
- Message events
- Member events
- Voice events
- Reaction events
- Guild events

## API Endpoints

### Bot Control
- `POST /bot/start`
  - Initializes the bot
  - Registers commands
  - Starts event listeners

- `POST /bot/stop`
  - Gracefully shuts down the bot
  - Saves state
  - Cleans up resources

- `GET /bot/status`
  - Returns bot status
  - Shows connected servers
  - Displays command stats

## Models

### BotConfig
- Bot token
- Command prefix
- Allowed servers
- Admin roles
- Bot settings

### CommandStats
- Command usage
- User statistics
- Error rates
- Performance metrics

## Cogs

### Admin
- Server management
- User management
- Bot configuration
- System commands

### Points
- Point management
- Leaderboard
- Point transactions
- User stats

### Events
- Event creation
- Event management
- RSVP system
- Notifications

## Configuration

Required environment variables:
- `DISCORD_TOKEN`: Bot authentication token
- `DISCORD_CLIENT_ID`: Bot client ID
- `DISCORD_CLIENT_SECRET`: Bot client secret
- `DISCORD_GUILD_ID`: Primary guild ID

## Usage Example

```python
from modules.bot import bot
from discord.ext import commands

@bot.command()
async def ping(ctx):
    await ctx.send('Pong!')

@bot.event
async def on_ready():
    print(f'Bot is ready as {bot.user}')
```

## Error Handling

The module handles various bot-related errors:
- Command errors
- API rate limits
- Connection issues
- Permission errors
- Event processing errors

## Security Considerations

1. **Token Security**
   - Bot token is stored securely
   - Token rotation is supported
   - Access is restricted

2. **Command Security**
   - Permission checks
   - Rate limiting
   - Input validation
   - Error logging

3. **Data Security**
   - Secure storage
   - Data encryption
   - Access control
   - Audit logging

## Dependencies

- `discord.py`: Discord API wrapper
- `python-dotenv`: Environment management
- `aiohttp`: Async HTTP client
- `asyncio`: Async I/O support 