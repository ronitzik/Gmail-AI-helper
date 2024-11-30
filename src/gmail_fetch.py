# gmail_fetch.py 
import os
import time
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from gpt4all import GPT4All
from tqdm import tqdm

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


def get_emails(max_results=100):
    """Fetch emails from Gmail inbox."""
    service = get_gmail_service()
    results = (
        service.users().messages().list(userId="me", maxResults=max_results).execute()
    )
    messages = results.get("messages", [])
    email_data = []

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
        body = get_email_body(payload)
        email_data.append({"subject": subject, "sender": sender, "body": body})
    return email_data


def get_email_body(payload):
    """Extract a snippet or body from the email payload."""
    if "body" in payload and payload["body"].get("data"):
        try:
            return payload["body"]["data"][
                :500
            ]  # Only take a small part of the email body
        except:
            pass
    return "No body available"


def process_email_with_llm(email, llm):
    """Process an email using a local LLM to categorize and prioritize."""
    # Define the system prompt
    system_prompt = """### System:
You are an AI assistant that categorizes emails into "Work," "School," "Shopping," or "Personal," ranks them and determines if a response is needed
based on the subject, sender, and a brief body snippet. Provide concise and accurate answers.
    """

    # Define the prompt template
    prompt_template = """### Human:
    Email Subject: {subject}
    Sender: {sender}
    Body Snippet: {body}
    Task:
    1. Categorize the email (e.g. Social Network, Work, School, Spam, Personal).
    2. Rank the priority (Urgent, Important, Normal).
    3. Decide if a response is required (Yes/No).
    Please respond with the format:
    Category: <category>
    Priority: <priority>
    Response Required: <Yes/No>

    ### Assistant:
    """

    # Populate the prompt template with email details
    prompt = prompt_template.format(
        subject=email["subject"], sender=email["sender"], body=email["body"]
    )

    # Combine the system prompt and the user prompt
    full_prompt = system_prompt + prompt

    # Generate a response from the LLM
    response = llm.generate(full_prompt)
    return response


def main():
    
    llm = GPT4All("orca-mini-3b-gguf2-q4_0", allow_download=False)    
    # Get the last 100 emails
    emails = get_emails(max_results=1)

    # Process each email and show a progress bar for each
    for i, email in enumerate(emails):
        print(f"Processing email {i + 1}/{len(emails)}...")
        with tqdm(total=100, desc=f"Processing Email {i + 1}", leave=False) as pbar:
            for _ in range(100):  # Simulate a processing bar for the LLM
                time.sleep(0.02)  # Adjust this based on the processing speed
                pbar.update(1)  # Update the bar incrementally
                
        response = process_email_with_llm(email, llm)
        print(f"Email Subject: {email['subject']}")
        print(f"Email Sender: {email['sender']}")
        print(f"LLM Response:\n{response}")
        print("-" * 50)


if __name__ == "__main__":
    main()
