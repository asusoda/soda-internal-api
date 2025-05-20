import os.path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from modules.utils.db import DBConnect
from modules.points.models import User
from modules.utils.logging_config import get_logger

# Get module logger
logger = get_logger("users.reader")

def check_gForm_for_distinguished_members():
    SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
    SAMPLE_SPREADSHEET_ID = "1gfrify0x3EUf-acZc1b-Ib0dRkMWUGd_rbUqTRF-dFM"
    SAMPLE_RANGE_NAME = "Form Responses 1!A:I"  # Adjust according to your sheet, now includes the new asu_id field

    creds = None
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
        logger.info("Loaded credentials from token.json")
    else:
        logger.warning("Token not found. Please run the generate_token.py script to create one.")
        return

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            logger.info("Refreshed credentials")
        else:
            logger.error("Invalid or expired token. Please run the generate_token.py script to create a new one.")
            return

    try:
        service = build("sheets", "v4", credentials=creds)
        sheet = service.spreadsheets()
        result = (
            sheet.values()
            .get(spreadsheetId=SAMPLE_SPREADSHEET_ID, range=SAMPLE_RANGE_NAME)
            .execute()
        )
        values = result.get("values", [])
        logger.info(f"Retrieved {len(values)} rows from Google Sheets")

        if not values:
            logger.warning("No data found.")
            return

        db_connect = DBConnect("sqlite:///user.db")  # Use the existing database
        logger.debug("Connected to the database")

        for i, row in enumerate(
            values[1:], start=2
        ):  # Skip header row and enumerate for easier debugging
            logger.debug(f"Processing row {i}: {row}")
            timestamp, asu_id, name, email, year, major, distinguished_member, *_ = row
            if distinguished_member.lower() == "yes":
                logger.info(f"Adding user {name} ({email}) with ASU ID {asu_id} to the database")
                add_user_to_db(db_connect, asu_id, name, email, year, major)
            else:
                logger.debug(f"Skipping user {name} ({email}) - Not a distinguished member")

    except HttpError as err:
        logger.error(f"HTTP error occurred: {err}")


def add_user_to_db(db_connect, asu_id, name, email, year, major):
    db = next(db_connect.get_db())
    try:
        user = User(asu_id=asu_id, name=name, email=email, academic_standing=year)
        db_user = db_connect.create_user(db, user)
        logger.info(f"Successfully added user: {db_user.name} ({db_user.email}) with ASU ID {db_user.asu_id}")
    except Exception as e:
        logger.error(f"Error adding user: {e}", exc_info=True)
    finally:
        db.close()
        logger.debug("Database connection closed")
