from google_auth_oauthlib.flow import InstalledAppFlow

def generate_token():
    SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]

    flow = InstalledAppFlow.from_client_secrets_file(
        "credentials.json", SCOPES
    )
    creds = flow.run_local_server(port=4000) 

    with open("token.json", "w") as token:
        token.write(creds.to_json())
        print("Token generated and saved to token.json")

if __name__ == "__main__":
    generate_token()
