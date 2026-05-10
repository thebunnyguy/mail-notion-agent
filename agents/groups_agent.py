"""
agents/groups_agent.py — Dedicated Google Groups fetcher.

Strategy (for private groups):
  Uses the Gmail API to search for emails delivered FROM the Google Group
  (even if not in inbox — searches All Mail). This is the most reliable
  approach for private groups since it reuses the already-authenticated
  Gmail token.

  Gmail search query: list:{group}@googlegroups.com
  This matches on the List-ID mail header, which Google Groups always sets.
"""

import os
import base64
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from utils.logger import get_logger

log = get_logger("groups_agent")

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CREDENTIALS_PATH = os.path.join(BASE_DIR, "credentials", "google_credentials.json")
TOKEN_PATH = os.path.join(BASE_DIR, "credentials", "token.json")


def _get_gmail_service():
    """Reuse the same Gmail API service as gmail_agent."""
    creds = None
    if os.path.exists(TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(CREDENTIALS_PATH):
                raise FileNotFoundError(
                    f"Google credentials not found at: {CREDENTIALS_PATH}"
                )
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_PATH, SCOPES)
            creds = flow.run_local_server(port=0)
        os.makedirs(os.path.dirname(TOKEN_PATH), exist_ok=True)
        with open(TOKEN_PATH, "w") as f:
            f.write(creds.to_json())

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
    for h in headers:
        if h["name"].lower() == name.lower():
            return h["value"]
    return ""


def _fetch_group_via_gmail(
    service,
    group_name: str,
    since_dt: datetime,
    max_topics: int,
) -> List[Dict[str, Any]]:
    """
    Search Gmail (All Mail) for messages from a Google Group using the
    'list:' search operator which matches on the List-ID header.
    Works for private groups as long as the user receives the emails.
    """
    after_epoch = int(since_dt.timestamp())

    # Gmail 'list:' operator searches by the List-ID header
    # This finds group messages even if they skip the inbox
    query = f"list:{group_name}@googlegroups.com after:{after_epoch}"
    log.info(f"[{group_name}] Searching Gmail with: {query}")

    try:
        results = service.users().messages().list(
            userId="me",
            q=query,
            maxResults=max_topics,
        ).execute()
    except Exception as e:
        log.error(f"[{group_name}] Gmail search failed: {e}")
        return []

    messages = results.get("messages", [])
    log.info(f"[{group_name}] Found {len(messages)} messages via Gmail search.")

    posts = []
    for msg_meta in messages:
        try:
            msg = service.users().messages().get(
                userId="me",
                id=msg_meta["id"],
                format="full",
            ).execute()

            headers = msg.get("payload", {}).get("headers", [])
            subject = _get_header(headers, "Subject")
            author  = _get_header(headers, "From")
            date_str = _get_header(headers, "Date")

            # Strip [group-name] prefix that Google Groups adds to subjects
            import re
            subject = re.sub(r"^\[.*?\]\s*", "", subject).strip()

            body = _decode_body(msg.get("payload", {}))

            # Build a link to the message on groups.google.com if available
            msg_id_header = _get_header(headers, "Message-ID")
            url = f"https://groups.google.com/g/{group_name}"

            posts.append({
                "group": group_name,
                "title": subject or "(no subject)",
                "author": author,
                "date": date_str,
                "body": body[:2000],
                "url": url,
                "source": "gmail_list_search",
            })
        except Exception as e:
            log.warning(f"[{group_name}] Failed to fetch message {msg_meta['id']}: {e}")
            continue

    log.info(f"[{group_name}] Processed {len(posts)} group posts.")
    return posts


def fetch_group_posts(config: Dict) -> List[Dict[str, Any]]:
    """
    Main entry point: fetch posts from all configured Google Groups
    using Gmail API search (works for private groups).

    Returns a list of post dicts:
        {group, title, author, date, body, url, source}
    """
    groups_cfg = config.get("google_groups", {})
    group_names = groups_cfg.get("groups", [])
    max_topics = groups_cfg.get("max_topics_per_group", 20)
    time_window_hours = groups_cfg.get("time_window_hours", 4)

    if not group_names:
        log.info("No Google Groups configured. Skipping.")
        return []

    group_names = [g for g in group_names if g != "example-group-name"]
    if not group_names:
        log.info("No real Google Groups configured (only placeholder found). Skipping.")
        return []

    since_dt = datetime.now(timezone.utc) - timedelta(hours=time_window_hours)
    service = _get_gmail_service()

    all_posts = []
    for group_name in group_names:
        log.info(f"Processing group: {group_name}")
        posts = _fetch_group_via_gmail(service, group_name, since_dt, max_topics)
        all_posts.extend(posts)

    log.info(f"Total Google Groups posts fetched: {len(all_posts)}")
    return all_posts

