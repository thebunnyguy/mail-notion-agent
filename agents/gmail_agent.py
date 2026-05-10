"""
agents/gmail_agent.py — Fetches emails from Gmail using the Gmail API (OAuth2).

First run: opens a browser window for Google account login & consent.
Token is saved to credentials/token.json for future runs.
"""

import os
import base64
import email as email_lib
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from utils.logger import get_logger

log = get_logger("gmail_agent")

# Gmail read-only scope — we never modify your inbox
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CREDENTIALS_PATH = os.path.join(BASE_DIR, "credentials", "google_credentials.json")
TOKEN_PATH = os.path.join(BASE_DIR, "credentials", "token.json")


def _get_gmail_service():
    """Authenticate and return a Gmail API service client."""
    creds = None

    if os.path.exists(TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            log.info("Refreshing Gmail OAuth2 token...")
            creds.refresh(Request())
        else:
            log.info("No valid token found. Opening browser for Google login...")
            if not os.path.exists(CREDENTIALS_PATH):
                raise FileNotFoundError(
                    f"Google credentials not found at: {CREDENTIALS_PATH}\n"
                    "Please download your OAuth2 credentials from Google Cloud Console "
                    "and save as credentials/google_credentials.json"
                )
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_PATH, SCOPES)
            creds = flow.run_local_server(port=0)

        # Save token for future runs
        os.makedirs(os.path.dirname(TOKEN_PATH), exist_ok=True)
        with open(TOKEN_PATH, "w") as f:
            f.write(creds.to_json())
        log.info("Gmail token saved.")

    return build("gmail", "v1", credentials=creds)


def _decode_body(payload: Dict) -> str:
    """Recursively extract plain text body from a Gmail message payload."""
    body = ""
    if "parts" in payload:
        for part in payload["parts"]:
            body += _decode_body(part)
    else:
        mime_type = payload.get("mimeType", "")
        if "text/plain" in mime_type:
            data = payload.get("body", {}).get("data", "")
            if data:
                body = base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
    return body


def _get_header(headers: List[Dict], name: str) -> str:
    """Extract a specific header value from a list of header dicts."""
    for h in headers:
        if h["name"].lower() == name.lower():
            return h["value"]
    return ""


def fetch_emails(config: Dict) -> List[Dict[str, Any]]:
    """
    Fetch emails from Gmail based on the given config.

    Returns a list of dicts:
        {subject, sender, date, body, thread_id, message_id}
    """
    gmail_cfg = config.get("gmail", {})
    time_window_hours = gmail_cfg.get("time_window_hours", 4)
    labels = gmail_cfg.get("labels", ["INBOX"])
    exclude_senders = gmail_cfg.get("exclude_senders", [])
    priority_senders = gmail_cfg.get("priority_senders", [])
    max_emails = gmail_cfg.get("max_emails", 40)

    log.info(f"Fetching Gmail emails from the last {time_window_hours} hours...")
    service = _get_gmail_service()

    # Build Gmail search query
    since_dt = datetime.now(timezone.utc) - timedelta(hours=time_window_hours)
    after_epoch = int(since_dt.timestamp())
    query = f"after:{after_epoch}"

    # Add label filters
    if priority_senders:
        sender_q = " OR ".join(f"from:{s}" for s in priority_senders)
        query += f" ({sender_q})"

    try:
        results = service.users().messages().list(
            userId="me",
            q=query,
            labelIds=labels,
            maxResults=max_emails,
        ).execute()
    except Exception as e:
        log.error(f"Failed to list Gmail messages: {e}")
        return []

    messages = results.get("messages", [])
    log.info(f"Found {len(messages)} raw Gmail messages.")

    emails = []
    for msg_meta in messages:
        try:
            msg = service.users().messages().get(
                userId="me",
                id=msg_meta["id"],
                format="full",
            ).execute()

            headers = msg.get("payload", {}).get("headers", [])
            sender = _get_header(headers, "From")
            subject = _get_header(headers, "Subject")
            date_str = _get_header(headers, "Date")

            # Skip excluded senders
            if any(ex.lower() in sender.lower() for ex in exclude_senders):
                log.debug(f"Skipping excluded sender: {sender}")
                continue

            body = _decode_body(msg.get("payload", {}))

            emails.append({
                "subject": subject,
                "sender": sender,
                "date": date_str,
                "body": body[:3000],  # Limit body length
                "thread_id": msg.get("threadId", ""),
                "message_id": msg_meta["id"],
            })

        except Exception as e:
            log.warning(f"Failed to fetch message {msg_meta['id']}: {e}")
            continue

    log.info(f"Processed {len(emails)} valid emails.")
    return emails
