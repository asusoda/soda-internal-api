# soda-internal-api
This project provides a modular internal API and Discord bot for the SoDA (Software Developers Association) student organization. It includes several modules:

1. **Discord Bot with Jeopardy Game**: A Discord bot that allows members to play Jeopardy-style games in Discord channels
2. **Points Tracking System**: For tracking member participation and contributions
3. **Event Calendar Integration**: Syncs events between Notion and Google Calendar
4. **Summarizer Module**: Provides AI-powered summaries of Discord channel conversations using natural language date queries
5. **Web Control Panel**: Built with React, allows authorized users to manage the bot, games, and other features

The server side is developed using Flask, handling API requests, Discord bot interactions, and data management across all modules.

## Key Features

### Summarizer Module
The summarizer module provides AI-powered summaries of Discord channel conversations:

- **Natural Language Date Queries**: Users can request summaries with intuitive time expressions:
  - `/summarize last week`
  - `/summarize january to february`
  - `/summarize the past 3 days`

- **Smart Formatting**: Provides well-structured summaries with:
  - Action items with assignees
  - Conversation topics and key takeaways
  - Citations linking to original messages

See [Summarizer Module Documentation](modules/summarizer/README.md) for more details.

## Requirements

#### Server (Flask App)
- Python 3.9.2 or newer
- Poetry (recommended) or pip
- Dependencies as listed in `pyproject.toml`


## Server Setup
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
   
   Alternative methods:
   - Using venv:
     ```bash
     python3 -m venv venv
     source venv/bin/activate  # On Windows use `venv\Scripts\activate`
     pip install -r requirements.txt
     ```
4. Edit the secret values
  Copy the .env.template to .env
      ```bash
      cp .env.template .env
      ```
      Edit the .env file to provide the necessary configuration values, such as API keys, Discord bot token, and other credentials.

5. Run the program 
      ```bash
      # If using Poetry
      poetry run python main.py
      
      # If using activated virtual environment
      python main.py
      ```

## Development and Testing

### Running Tests

This project uses pytest for automated testing. To run the tests:

1. Make sure you have the development dependencies installed:
   ```bash
   # Using Poetry (recommended)
   poetry install
   
   # Or using pip
   pip install -r requirements.txt
   ```

2. Run all tests:
   ```bash
   ./run_tests.sh  # Simple shell script that runs pytest
   # OR
   pytest          # If pytest is in your PATH
   # OR
   poetry run pytest  # If using Poetry
   ```

3. Run specific tests:
   ```bash
   ./run_tests.sh tests/test_date_parsing.py  # Run specific test file
   ./run_tests.sh -k "month"                  # Run tests matching a keyword
   ```

### Ad-hoc Testing

For testing the date parsing functionality directly:

```bash
python check_date.py "last week" "january to february"
```

This will display the parsed date ranges for the given expressions, showing:
- Display format
- Start date/time
- End date/time

## Deployment

### Deploying Flask Server

1. **Configure production settings** in the `.env` file.
2. **Use a production-ready WSGI server** such as `gunicorn` or `uWSGI` to serve the Flask app.

   Example with `gunicorn`:
   ```bash
   gunicorn --bind 0.0.0.0:8000 wsgi:app
   ```

## License

This project is licensed under the MIT License. 

## Contact

For any questions or feedback, feel free to reach out:

- **Tanay Upreti** - [GitHub](https://github.com/code-wolf-byte)
