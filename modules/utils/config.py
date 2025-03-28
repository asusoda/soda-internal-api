import os
import json
from dotenv import load_dotenv

class Config:
    """Centralized configuration management for the application"""
    
    def __init__(self) -> None:
        load_dotenv()
        try:
            # Core Application Config
            self.SECRET_KEY = os.environ["SECRET_KEY"]
            self.CLIENT_ID = os.environ["CLIENT_ID"]
            self.CLIENT_SECRET = os.environ["CLIENT_SECRET"]
            self.REDIRECT_URI = os.environ["REDIRECT_URI"]
            self.CLIENT_URL = os.environ["CLIENT_URL"]
            self.PROD = os.environ.get("PROD", "false").lower() == "true"

            # Service Tokens
            self.BOT_TOKEN = os.environ["BOT_TOKEN"]
            
            # Database Configuration
            self.DB_TYPE = os.environ["DB_TYPE"]
            self.DB_URI = os.environ["DB_URI"]
            self.DB_NAME = os.environ["DB_NAME"]
            self.DB_USER = os.environ["DB_USER"]
            self.DB_PASSWORD = os.environ["DB_PASSWORD"]

            # Calendar Integration
            try:
                with open("google-secret.json", "r") as file:
                    print("Loading Google service account credentials")
                    self.GOOGLE_SERVICE_ACCOUNT = json.load(file)
                    print("Google service account credentials loaded successfully")
                    print("Google service account credentials:", self.GOOGLE_SERVICE_ACCOUNT)
            except Exception as e:
                raise RuntimeError(f"Google service account credentials file not found. Please create 'google-secret.json'. {e}")
                
            self.NOTION_API_KEY = os.environ["NOTION_API_KEY"]
            self.NOTION_DATABASE_ID = os.environ["NOTION_DATABASE_ID"]
            self.GOOGLE_CALENDAR_ID = os.environ["GOOGLE_CALENDAR_ID"]
            self.GOOGLE_USER_EMAIL = os.environ["GOOGLE_USER_EMAIL"]
            self.SERVER_PORT = int(os.environ.get("SERVER_PORT", "5000"))
            self.SERVER_DEBUG = os.environ.get("SERVER_DEBUG", "false").lower() == "true"
            self.TIMEZONE = os.environ.get("TIMEZONE", "America/Phoenix")

        except (KeyError, json.JSONDecodeError) as e:
            raise RuntimeError(f"Configuration error: {str(e)}") from e

    @property
    def google_calendar_config(self) -> dict:
        """Get Google Calendar configuration as a dictionary"""
        return {
            "service_account": self.GOOGLE_SERVICE_ACCOUNT,
            "calendar_id": self.GOOGLE_CALENDAR_ID,
            "user_email": self.GOOGLE_USER_EMAIL
        }
