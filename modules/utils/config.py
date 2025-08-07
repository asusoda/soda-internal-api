import os
import json
from dotenv import load_dotenv

class Config:
    """Centralized configuration management for the application"""
    
    def __init__(self, testing: bool = False) -> None:
        load_dotenv()
        self.testing = testing
        try:
            if testing:
                # Set test defaults for all required variables
                self.SECRET_KEY = os.environ.get("SECRET_KEY", "test-secret-key")
                self.CLIENT_ID = os.environ.get("CLIENT_ID", "test-client-id")
                self.CLIENT_SECRET = os.environ.get("CLIENT_SECRET", "test-client-secret")
                self.REDIRECT_URI = os.environ.get("REDIRECT_URI", "http://localhost:5000/callback")
                self.CLIENT_URL = os.environ.get("CLIENT_URL", "http://localhost:3000")
                self.PROD = False
                
                # Service Tokens
                self.BOT_TOKEN = os.environ.get("BOT_TOKEN", "test-bot-token")
                self.AVERY_BOT_TOKEN = os.environ.get("AVERY_BOT_TOKEN", "test-avery-token")
                self.AUTH_BOT_TOKEN = os.environ.get("AUTH_BOT_TOKEN", "test-auth-token")
                
                # Database Configuration
                self.DB_TYPE = os.environ.get("DB_TYPE", "sqlite")
                self.DB_URI = os.environ.get("DB_URI", "sqlite:///test.db")
                self.DB_NAME = os.environ.get("DB_NAME", "test")
                self.DB_USER = os.environ.get("DB_USER", "test")
                self.DB_PASSWORD = os.environ.get("DB_PASSWORD", "test")
                self.DB_HOST = os.environ.get("DB_HOST", "localhost")
                self.DB_PORT = os.environ.get("DB_PORT", "5432")
                
                # Google service account - use dummy data for tests
                self.GOOGLE_SERVICE_ACCOUNT = {"type": "service_account", "project_id": "test"}
                
                self.NOTION_API_KEY = os.environ.get("NOTION_API_KEY", "test-notion-key")
                self.NOTION_DATABASE_ID = os.environ.get("NOTION_DATABASE_ID", "test-db-id")
                self.NOTION_TOKEN = os.environ.get("NOTION_TOKEN", "test-notion-token")
                self.GOOGLE_CALENDAR_ID = os.environ.get("GOOGLE_CALENDAR_ID", "test@calendar.google.com")
                self.GOOGLE_USER_EMAIL = os.environ.get("GOOGLE_USER_EMAIL", "test@example.com")
                self.SERVER_PORT = 5000
                self.SERVER_DEBUG = True
                self.TIMEZONE = "America/Phoenix"
                
                # Optional configs
                self.SENTRY_DSN = None
                self.GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "test-gemini-key")

                # Superadmin config
                self.SUPERADMIN_USER_ID = os.environ.get("SYS_ADMIN", "test-superadmin-id")
            else:
                # Core Application Config
                self.SECRET_KEY = os.environ["SECRET_KEY"]
                self.CLIENT_ID = os.environ["CLIENT_ID"]
                self.CLIENT_SECRET = os.environ["CLIENT_SECRET"]
                self.REDIRECT_URI = os.environ["REDIRECT_URI"]
                self.CLIENT_URL = os.environ["CLIENT_URL"]
                self.PROD = os.environ.get("PROD", "false").lower() == "true"

                # Service Tokens
                self.BOT_TOKEN = os.environ.get("BOT_TOKEN")  # Legacy token
                self.AVERY_BOT_TOKEN = os.environ.get("AVERY_BOT_TOKEN")  # AVERY bot token
                self.AUTH_BOT_TOKEN = os.environ.get("AUTH_BOT_TOKEN")  # Auth bot token
                
                # Database Configuration
                self.DB_TYPE = os.environ["DB_TYPE"]
                self.DB_URI = os.environ["DB_URI"]
                self.DB_NAME = os.environ["DB_NAME"]
                self.DB_USER = os.environ["DB_USER"]
                self.DB_PASSWORD = os.environ["DB_PASSWORD"]
                self.DB_HOST = os.environ["DB_HOST"]
                self.DB_PORT = os.environ["DB_PORT"]
                # Calendar Integration

                try:
                    with open("google-secret.json", "r") as file:
                        print("Loading Google service account credentials")
                        self.GOOGLE_SERVICE_ACCOUNT = json.load(file)
                        print("Google service account credentials loaded successfully")
                        # Redact sensitive information
                        masked_credentials = {
                            **self.GOOGLE_SERVICE_ACCOUNT,
                            "private_key": "[REDACTED]"
                        } if self.GOOGLE_SERVICE_ACCOUNT else None
                        print("Google service account credentials loaded")
                except FileNotFoundError:
                    print("Warning: google-secret.json not found. Google Calendar features will be disabled.")
                    self.GOOGLE_SERVICE_ACCOUNT = None
                except Exception as e:
                    print(f"Warning: Error loading Google credentials: {e}. Google Calendar features will be disabled.")
                    self.GOOGLE_SERVICE_ACCOUNT = None
                    
                self.NOTION_API_KEY = os.environ["NOTION_API_KEY"]
                self.NOTION_DATABASE_ID = os.environ["NOTION_DATABASE_ID"]
                self.GOOGLE_CALENDAR_ID = os.environ["GOOGLE_CALENDAR_ID"]
                self.GOOGLE_USER_EMAIL = os.environ["GOOGLE_USER_EMAIL"]
                self.SERVER_PORT = int(os.environ.get("SERVER_PORT", "5000"))
                self.SERVER_DEBUG = os.environ.get("SERVER_DEBUG", "false").lower() == "true"
                self.TIMEZONE = os.environ.get("TIMEZONE", "America/Phoenix")

                # Monitoring Configuration (Optional)
                self.SENTRY_DSN = os.environ.get("SENTRY_DSN")
                self.SYS_ADMIN = os.environ.get("ADMIN_USER_ID")
                # AI Service Keys
                self.GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
                self.NOTION_TOKEN = os.environ.get("NOTION_TOKEN")

                # Superadmin config
                self.SUPERADMIN_USER_ID = os.environ.get("SYS_ADMIN")

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
