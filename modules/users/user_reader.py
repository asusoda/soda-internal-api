import os.path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from modules.utils.db import DBConnect
from modules.points.models import User

def check_gForm_for_distinguished_members():
    SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
    SAMPLE_SPREADSHEET_ID = "1gfrify0x3EUf-acZc1b-Ib0dRkMWUGd_rbUqTRF-dFM"
    SAMPLE_RANGE_NAME = "Form Responses 1!A:I"  # Adjust according to your sheet, now includes the new asu_id field

    creds = None
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
        print("Loaded credentials from token.json")
    else:
        print("Token not found. Please run the generate_token.py script to create one.")
        return

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            print("Refreshed credentials")
        else:
            print("Invalid or expired token. Please run the generate_token.py script to create a new one.")
            return

    try:
        service = build("sheets", "v4", credentials=creds)
        sheet = service.spreadsheets()
        result = sheet.values().get(spreadsheetId=SAMPLE_SPREADSHEET_ID, range=SAMPLE_RANGE_NAME).execute()
        values = result.get("values", [])
        print(f"Retrieved {len(values)} rows from Google Sheets")

        if not values:
            print("No data found.")
            return

        db_connect = DBConnect('sqlite:///user.db')  # Use the existing database
        print("Connected to the database")

        for i, row in enumerate(values[1:], start=2):  # Skip header row and enumerate for easier debugging
            print(f"Processing row {i}: {row}")
            timestamp, asu_id, name, email, year, major, distinguished_member, *_ = row
            if distinguished_member.lower() == "yes":
                print(f"Adding user {name} ({email}) with ASU ID {asu_id} to the database")
                add_user_to_db(db_connect, asu_id, name, email, year, major)
            else:
                print(f"Skipping user {name} ({email}) - Not a distinguished member")

    except HttpError as err:
        print(f"HTTP error occurred: {err}")

def add_user_to_db(db_connect, asu_id, name, email, year, major):
    db = next(db_connect.get_db())
    try:
        user = User(
            asu_id=asu_id,
            name=name,
            email=email,
            academic_standing=year
        )
        db_user = db_connect.create_user(db, user)
        print(f"Successfully added user: {db_user.name} ({db_user.email}) with ASU ID {db_user.asu_id}")
    except Exception as e:
        print(f"Error adding user: {e}")
    finally:
        db.close()
        print("Database connection closed")
