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

## Deployment

TODO. Tanay needs to fill us in on this.

## License

This project is licensed under the MIT License. 

## Contact

For any questions or feedback, feel free to reach out:

- **Tanay Upreti** - [GitHub](https://github.com/code-wolf-byte)
