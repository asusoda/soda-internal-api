# TANAY API
This project provides a modular internal API and Discord bots for SoDA. 

The server side is developed using Flask, handling API requests, Discord bot interactions, and data management across all modules.

See the READMEs for more detailed documentation on the respective modules in `./modules`

## Development Setup
1. Clone the repository:
   ```bash
   git clone https://github.com/asusoda/soda-internal-api.git
   ```
2. Install dependencies using Poetry:
   ```bash
   # Install Poetry if you don't have it yet
   # See https://python-poetry.org/docs/#installation for more details
   curl -sSL https://install.python-poetry.org | python3 -
   
   # Install project dependencies
   poetry install
   
   # Activate the virtual environment
   poetry shell
   ```

4. Edit the secret values
  Copy the .env.template to .env
      ```bash
      cp .env.template .env
      ```
      Edit the .env file to provide the necessary configuration values, such as API keys, Discord bot token, and other credentials.

5. Run the program 
      ```bash
      poetry run python main.py
      
      # If using activated virtual environment
      python main.py
      ```

## Testing

This project uses pytest for automated testing. To run the tests:

1. Make sure you have the development dependencies installed:
   ```bash
   poetry install
   ```

2. Run all tests:
   ```bash
   pytest          # If pytest is in your PATH
   # OR
   poetry run pytest  # If using Poetry
   ```

## Deployment

### Using Docker Compose (Recommended)

The project now uses Docker Compose for easier deployment and management.

#### Quick Start

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

# Production deployment with overrides
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

#### Deployment Process

The `make deploy` command automates the entire deployment:

1. Pulls latest changes from git
2. Builds the Docker image
3. Manages container lifecycle
4. Performs health checks
5. Shows deployment status

You can customize the deployment with environment variables:
```bash
# Deploy from a different directory
make deploy PROJECT_DIR=/path/to/project

# Deploy a different branch
make deploy BRANCH=develop
```

### Docker Configuration Files

- `docker-compose.yml` - Base configuration
- `docker-compose.override.yml` - Development overrides (auto-loaded)
- `docker-compose.prod.yml` - Production-specific settings
- `.dockerignore` - Optimizes build context

### Data Persistence

The application data is stored in the `./data` directory, which is mounted as a volume in the container. This ensures data persistence across container restarts.

## License

This project is licensed under the MIT License. 

## Contact

For any questions or feedback, feel free to reach out:

- **Tanay Upreti** - [GitHub](https://github.com/code-wolf-byte)
