# TANAY API

![SoDA Logo](./web/public/logo-dark.svg)

## 📖 Overview

This project provides a modular internal API and Discord bots for the Software Developers Association (SoDA) at ASU. The server side is developed using Flask, handling API requests, Discord bot interactions, and data management across all modules.

## 📚 Documentation

- [Main Documentation](#) - This README file
- [Module Documentation](./modules/README.md) - Detailed information on available modules
  - [Auth Module](./modules/auth/README.md)
  - [Bot Module](./modules/bot/README.md)
  - [Calendar Module](./modules/calendar/README.md)
  - [Organizations Module](./modules/organizations/README.md)
  - [Points Module](./modules/points/README.md)
  - [Storefront Module](./modules/storefront/README.md)
  - [Users Module](./modules/users/README.md)

## 🚀 Getting Started

### Prerequisites

- Python 3.8+
- Poetry (dependency management)
- Docker and Docker Compose (for deployment)

### Development Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/asusoda/soda-internal-api.git
   cd soda-internal-api
   ```

2. **Install dependencies using Poetry:**
   ```bash
   # Install Poetry if you don't have it yet
   # See https://python-poetry.org/docs/#installation for more details
   curl -sSL https://install.python-poetry.org | python3 -
   
   # Install project dependencies
   poetry install
   
   # Activate the virtual environment
   poetry shell
   ```

3. **Configure environment variables:**
   ```bash
   # Copy the template environment file
   cp .env.template .env
   
   # Edit the .env file with your configuration values
   # This includes API keys, Discord bot token, etc.
   ```

4. **Run the application:**
   ```bash
   # Using Poetry
   poetry run python main.py
   
   # Or if already in Poetry shell
   python main.py
   ```

## 🧪 Testing

This project uses pytest for automated testing:

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_specific_module.py

# Run with coverage report
pytest --cov=modules
```

## 🔄 Discord Integration

### Bot Setup

The API integrates with Discord for notifications and interactions. To set up a Discord bot:

1. Create a new application in the [Discord Developer Portal](https://discord.com/developers/applications)
2. Add a bot to your application
3. Copy the bot token to your `.env` file
4. Invite the bot to your server using the OAuth2 URL generator


## 🚢 Deployment

### Using Docker Compose (Recommended)

The project uses Docker Compose for deployment and management.

#### Quick Start Commands

```bash
# Development environment
make dev

# Production deployment
make deploy

# View logs
make logs

# Stop services
make down
```

#### Manual Docker Compose Commands

```bash
# Build the Docker image
docker-compose build

# Start services
docker-compose up -d

# Stop services
docker-compose down

# View logs
docker-compose logs -f
```

#### Deployment Process

The `make deploy` command automates the entire deployment:

1. Pulls latest changes from git
2. Builds the Docker image
3. Manages container lifecycle
4. Performs health checks
5. Shows deployment status

#### Customizing Deployment

```bash
# Deploy from a different directory
make deploy PROJECT_DIR=/path/to/project

# Deploy a different branch
make deploy BRANCH=develop
```

### Docker Configuration

- `docker-compose.yml` - Main configuration for all environments
- `.dockerignore` - Optimizes build context

### Data Persistence

The application data is stored in the `./data` directory, which is mounted as a volume in the container for persistence across container restarts.

## 📝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License.


### Webhooks Configuration

To set up GitHub webhooks for Discord integration:

1. **Create a Discord webhook:**
   - Go to your Discord server settings
   - Select "Integrations" → "Webhooks"
   - Click "New Webhook"
   - Name your webhook and select the channel
   - Copy the webhook URL

2. **Configure GitHub repository webhooks:**
   - Go to your GitHub repository settings
   - Select "Webhooks" → "Add webhook"
   - Paste the Discord webhook URL with `/github` at the end
   - Set content type to `application/json`
   - Select "Let me select individual events"
   - Choose relevant events (push, pull requests, issues, etc.)
   - Click "Add webhook"

> **Note:** The `/github` path at the end of the Discord webhook URL enables GitHub's integration with Discord's message formatting.

## 📬 Contact

For any questions or feedback, please reach out:

- **Tanay Upreti** - [GitHub](https://github.com/code-wolf-byte)
- **SoDA Organization** - [Website](https://thesoda.io/)
