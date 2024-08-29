# soda-internal-api
This project provides a web-based control panel for managing a Jeopardy-themed Discord bot. The control panel, built with React, allows authorized users to toggle the bot's status and schedule new Jeopardy games by uploading a JSON file. The server side, developed using Flask, handles API requests, Discord bot interactions, and game management.

## Requirements

#### Server (Flask App)
- Python 3.8 or newer
- Dependencies as listed in `requirements.txt`


## Server Setup
1. Clone the repository:
   ```bash
   git clone https://github.com/asusoda/soda-internal-api.git
   ```
2. Create a new virtual environment eihter conda or venv
    If using conda:
    ```bash
    conda create --name soda-internal-api python=3.8
    conda activate soda-internal-api
    ```
    if usning venv:
    ```bash
    python3 -m venv venv
    source venv/bin/activate  # On Windows use `venv\Scripts\activate`
    ```
3. Install the dependencies:
    ```bash
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
      python3 main.py
      ```

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
