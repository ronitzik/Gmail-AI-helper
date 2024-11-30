import os
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# Define the scopes for Gmail API
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


def get_gmail_service():
    """Authenticate and return the Gmail API service."""
    creds = None
    # Check if token.json exists to load existing credentials
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    # If there are no valid credentials, or credentials are expired, log in
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for future use
        with open("token.json", "w") as token:
            token.write(creds.to_json())
    return build("gmail", "v1", credentials=creds)


def get_emails():
    """Fetch emails from the Gmail inbox and print subject and sender."""
    service = get_gmail_service()
    # Fetch the first 10 messages in the inbox
    results = service.users().messages().list(userId="me", maxResults=10).execute()
    messages = results.get("messages", [])

    if not messages:
        print("No messages found.")
        return

    for message in messages:
        msg = service.users().messages().get(userId="me", id=message["id"]).execute()
        payload = msg.get("payload", {})
        headers = payload.get("headers", [])
        subject = sender = None
        for header in headers:
            if header["name"] == "Subject":
                subject = header["value"]
            if header["name"] == "From":
                sender = header["value"]
        print(f"Subject: {subject}")
        print(f"Sender: {sender}")
        print("-" * 40)


if __name__ == "__main__":
    get_emails()
