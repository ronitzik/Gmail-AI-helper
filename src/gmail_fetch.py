# gmail_fetch.py
import os
import time
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from gpt4all import GPT4All
from tqdm import tqdm
import redis
import json
import matplotlib.pyplot as plt
import numpy as np


# Initialize Redis client
redis_client = redis.StrictRedis(
    host="localhost", port=6379, db=0, decode_responses=True
)

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


def get_emails(max_results):
    """Fetch emails from Gmail inbox and cache them in Redis."""
    # Check if emails are cached in Redis
    cached_emails = redis_client.get("cached_emails")
    if cached_emails:
        cached_emails = json.loads(cached_emails)
        if len(cached_emails) >= max_results:
            print("Using cached emails from Redis.")
            return cached_emails[:max_results]
    else:
        cached_emails = []

    print("Fetching additional emails from Gmail API.")
    service = get_gmail_service()
    results = (
        service.users().messages().list(userId="me", maxResults=max_results).execute()
    )
    messages = results.get("messages", [])
    email_data = []

    for message in messages:
        # Check if the message is already in the cache
        if any(msg.get("id") == message.get("id") for msg in cached_emails):
            continue

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
        email_data.append(
            {"id": message["id"], "subject": subject, "sender": sender, "body": body}
        )

    # Combine cached and newly fetched emails
    all_emails = cached_emails + email_data

    # Cache emails in Redis with a 4-hour expiration
    redis_client.setex("cached_emails", 4 * 60 * 60, json.dumps(all_emails))
    return all_emails[:max_results]


def get_email_body(payload):
    """Extract a snippet or body from the email payload."""
    parts = payload.get("parts", [])
    for part in parts:
        if part.get("mimeType") == "text/plain" and "data" in part.get("body", {}):
            try:
                return part["body"]["data"][
                    :500
                ]  # Only take a small part of the email body
            except KeyError:
                continue
    return "No body available"


def process_email_with_llm(email, llm):
    """
    Process an email using a local LLM with Redis caching.

    Args:
        email (dict): A dictionary containing email details with keys "subject", "sender", and "body".
        llm (object): A local LLM instance capable of generating responses.

    Returns:
        dict: The categorized email details with priority and response requirement.
    """
    try:
        # Validate the email structure
        if not all(key in email for key in ["subject", "sender", "body"]):
            raise ValueError(
                "Email dictionary must contain 'subject', 'sender', and 'body' keys."
            )

        # Create a unique cache key for the email
        cache_key = f"llm_response:{email['subject']}:{email['sender']}"

        # Check if the response is cached in Redis
        cached_response = redis_client.get(cache_key)
        if cached_response:
            print("Using cached LLM response from Redis.")
            return json.loads(cached_response)

        print("Calling LLM for response.")
        # Define the system prompt  
        system_prompt = """<start_header_id>system<end_header_id>
You are an AI email assistant. Your task is to:
1. Categorize emails into "Work," "School," "Shopping," or "Personal."
   - "Work" refers to professional communication.
   - "School" refers to anything related to academic activities, classes, or learning platforms like Piazza.
   - "Shopping" refers to promotional emails, advertisements, or purchase-related communications.
   - "Personal" refers to private, non-work/non-school emails.
2. Rank the priority as:
   - Urgent: Immediate attention required.
   - Important: Needs attention but not immediately.
   - Normal: No urgency or importance.
3. Decide if a response is required based on the content.

Always respond concisely and follow the specified format.<eot_id>"""

        # Define the prompt template
        prompt_template = """<start_header_id>user<end_header_id>
Email Subject: {subject}
Sender: {sender}
Body Snippet: {body}
Your Task:
1. Categorize the email (e.g., Work, School, Shopping, Personal).
2. Rank the priority (Urgent, Important, Normal).
3. Decide if a response is required (Yes/No).
You MUST respond in the format:
Category: <category>
Priority: <priority>
Response Required: <Yes OR No>

<eot_id><start_header_id>assistant<end_header_id>"""

        # Populate the prompt template with email details
        prompt = prompt_template.format(
            subject=email["subject"], sender=email["sender"], body=email["body"]
        )

        # Combine the system prompt and the user prompt
        full_prompt = f"{system_prompt}\n\n{prompt}"

        # Generate a response from the LLM
        response = llm.generate(full_prompt, max_tokens=90)

        # Ensure the response is properly parsed
        if isinstance(response, str):
            # Split the response into lines and extract the fields
            response_lines = response.strip().split("\n")
            response_data = {}
            for line in response_lines:
                if ":" in line:
                    key, value = line.split(":", 1)
                    response_data[key.strip()] = value.strip()

            # Validate the parsed response
            response_data = {
                "Category": response_data.get("Category", "Unknown").strip()
                or "Unknown",
                "Priority": response_data.get("Priority", "Normal").strip() or "Normal",
                "Response Required": response_data.get(
                    "Response Required", "No"
                ).strip()
                or "No",
            }

        else:
            raise ValueError("LLM response is not a string.")

        # Cache the LLM response in Redis with a 4-hour expiration
        redis_client.setex(cache_key, 4 * 60 * 60, json.dumps(response_data))

        return response_data

    except Exception as e:
        # Log or handle any errors
        print(f"Error processing email with LLM: {e}")
        return {"Category": "Error", "Priority": "Normal", "Response Required": "No"}


def show_all_charts(categorized_emails):
    """Generate charts and display them."""
    # Prepare data for charts
    category_counts = {}
    category_response_counts = {}
    category_priority_counts = {}

    for email in categorized_emails:
        category = email.get("Category", "Unknown")
        response_required = email.get("Response Required", "No").split()[
            0
        ]  # Sanitize field
        priority = (
            email.get("Priority", "Normal").strip() or "Normal"
        )

        # Count categories
        category_counts[category] = category_counts.get(category, 0) + 1

        # Count responses
        if category not in category_response_counts:
            category_response_counts[category] = {"Yes": 0, "No": 0}
        if response_required in ["Yes", "No"]:
            category_response_counts[category][response_required] += 1

        # Count priorities
        if category not in category_priority_counts:
            category_priority_counts[category] = {
                "Urgent": 0,
                "Important": 0,
                "Normal": 0,
            }
        category_priority_counts[category][priority] += 1

    # Prepare data for plotting
    categories = list(category_response_counts.keys())
    priorities = ["Urgent", "Important", "Normal"]
    response_counts = {
        "Yes": [category_response_counts[cat]["Yes"] for cat in categories],
        "No": [category_response_counts[cat]["No"] for cat in categories],
    }
    counts = {
        priority: [category_priority_counts[cat][priority] for cat in categories]
        for priority in priorities
    }

    # Create a figure with subplots
    fig, axes = plt.subplots(1, 3, figsize=(18, 6))

    axes[0].pie(
        category_counts.values(),
        labels=category_counts.keys(),
        autopct="%1.1f%%",
        startangle=90,
        wedgeprops={"edgecolor": "black"},
    )
    axes[0].set_title("Email Categories Distribution")

    x = np.arange(len(categories))  
    axes[1].bar(x, response_counts["Yes"], label="Yes")
    axes[1].bar(x, response_counts["No"], bottom=response_counts["Yes"], label="No")
    axes[1].set_xlabel("Email Categories")
    axes[1].set_ylabel("Count")
    axes[1].set_title("Response Requirements by Category")
    axes[1].set_xticks(x)
    axes[1].set_xticklabels(categories)
    axes[1].legend(title="Response Required")

    width = 0.25 
    for i, priority in enumerate(priorities):
        axes[2].bar(x + i * width, counts[priority], width, label=priority)
    axes[2].set_xlabel("Email Categories")
    axes[2].set_ylabel("Count")
    axes[2].set_title("Email Categories vs. Priority Counts")
    axes[2].set_xticks(x + width)
    axes[2].set_xticklabels(categories)
    axes[2].legend(title="Priority")

    # Adjust layout
    plt.tight_layout()
    plt.show()


def main():

    llm = GPT4All("Llama-3.2-3B-Instruct-Q4_0.gguf", allow_download=False)  
    # Get the last emails
    emails = get_emails(max_results=20)
    categorized_emails = []
    
    # Process each email 
    for i, email in enumerate(emails):
        print(f"Processing email {i + 1}/{len(emails)}...")
        with tqdm(total=100, desc=f"Processing Email {i + 1}", leave=False) as pbar:
            for _ in range(100): 
                time.sleep(0.02)  
                pbar.update(1)       
        response = process_email_with_llm(email, llm)
        categorized_emails.append(response)
        print(f"Email Subject: {email['subject']}")
        print(f"Email Sender: {email['sender']}")
        print(f"LLM Response:\n{response}")
        print("-" * 50)

    show_all_charts(categorized_emails)

if __name__ == "__main__":
    main()
