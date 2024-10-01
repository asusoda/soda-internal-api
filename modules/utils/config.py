import os
from dotenv import load_dotenv


class Config:
    def __init__(self) -> None:
        load_dotenv()
        try:
            # OAuth2 Config
            self.SECRET_KEY = os.environ["SECRET_KEY"]
            self.CLIENT_ID = os.environ["CLIENT_ID"]
            self.CLIENT_SECRET = os.environ["CLIENT_SECRET"]
            self.REDIRECT_URI = os.environ["REDIRECT_URI"]
            self.CLIENT_URL = os.environ["CLIENT_URL"]

            # API Tokens
            self.BOT_TOKEN = os.environ["BOT_TOKEN"]
            self.NOTION_TOKEN = os.environ["NOTION_TOKEN"]
            # Database Config
            self.DB_TYPE = os.environ["DB_TYPE"]
            self.DB_URI = os.environ["DB_URI"]
            self.DB_NAME = os.environ["DB_NAME"]
            self.DB_USER = os.environ["DB_USER"]
            self.DB_PASSWORD = os.environ["DB_PASSWORD"]

            # App Config
            self.PROD = os.environ["PROD"]
            # self.USERNAME = os.environ["USERNAME"]
            # self.PASSWORD = os.environ["PASSWORD"]

        except KeyError as e:
            print(f"Missing environment variable: {e}")
            exit(1)

    def get(self, key: str) -> str:
        try:
            return getattr(self, key)
        except AttributeError:
            print(f"Key '{key}' not found in configuration.")
            exit(1)
