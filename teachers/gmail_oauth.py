# utils/gmail_oauth.py
import os
import base64
from email.mime.text import MIMEText
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# Gmail send scope
SCOPES = ["https://www.googleapis.com/auth/gmail.send"]

def get_credentials():
    """
    Loads or creates valid Gmail API credentials.
    """
    creds = None
    # token.json stores the user's access and refresh tokens
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    # If there are no (valid) credentials available, let the user log in
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                "credentials.json", SCOPES
            )
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open("token.json", "w") as token:
            token.write(creds.to_json())
    return creds


def send_oauth_email(to_email, subject, text_content, html_content, reply_to=None):
    """
    Sends an email using Gmail API and OAuth2 credentials.
    """
    creds = get_credentials()
    service = build("gmail", "v1", credentials=creds)

    # Build message
    message = MIMEText(html_content, "html")
    message["to"] = to_email
    message["subject"] = subject
    if reply_to:
        message["reply-to"] = reply_to

    # Encode and send
    raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
    send_message = {"raw": raw_message}
    service.users().messages().send(userId="me", body=send_message).execute()
