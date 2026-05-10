"""
agents/notion_agent.py — Publishes AI summaries to your Notion database.

Creates a new page in your Notion database for each scheduled run,
with rich formatting: stats block, markdown summary, source metadata.
"""

import os
import re
from datetime import datetime
from typing import List, Dict, Any

from notion_client import Client
from dotenv import load_dotenv

from utils.logger import get_logger

load_dotenv()
log = get_logger("notion_agent")

NOTION_API_KEY = os.getenv("NOTION_API_KEY")
NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID")


def _get_client() -> Client:
    if not NOTION_API_KEY or NOTION_API_KEY.startswith("secret_XXXX"):
        raise ValueError(
            "NOTION_API_KEY is not set. "
            "Add it to the .env file. "
            "Get it at: https://www.notion.so/my-integrations"
        )
    if not NOTION_DATABASE_ID or len(NOTION_DATABASE_ID) < 10:
        raise ValueError(
            "NOTION_DATABASE_ID is not set or invalid. "
            "Copy the database ID from your Notion database URL."
        )
    return Client(auth=NOTION_API_KEY)


def _markdown_to_notion_blocks(markdown: str) -> List[Dict]:
    """
    Convert a markdown string into a list of Notion block objects.
    Supports: headings (##, ###), bullet points, bold, plain paragraphs.
    """
    blocks = []
    lines = markdown.split("\n")

    for line in lines:
        stripped = line.strip()

        if not stripped:
            # Empty line → spacer paragraph
            blocks.append({
                "object": "block",
                "type": "paragraph",
                "paragraph": {"rich_text": []},
            })
            continue

        # H2 heading
        if stripped.startswith("## "):
            text = stripped[3:]
            blocks.append({
                "object": "block",
                "type": "heading_2",
                "heading_2": {
                    "rich_text": [{"type": "text", "text": {"content": text}}]
                },
            })

        # H3 heading
        elif stripped.startswith("### "):
            text = stripped[4:]
            blocks.append({
                "object": "block",
                "type": "heading_3",
                "heading_3": {
                    "rich_text": [{"type": "text", "text": {"content": text}}]
                },
            })

        # Bullet points (-, *, •)
        elif re.match(r"^[-*•]\s+", stripped):
            text = re.sub(r"^[-*•]\s+", "", stripped)
            rich_text = _parse_inline_markdown(text)
            blocks.append({
                "object": "block",
                "type": "bulleted_list_item",
                "bulleted_list_item": {"rich_text": rich_text},
            })

        # Horizontal rule
        elif stripped in ("---", "***", "___"):
            blocks.append({"object": "block", "type": "divider", "divider": {}})

        # Plain paragraph
        else:
            rich_text = _parse_inline_markdown(stripped)
            blocks.append({
                "object": "block",
                "type": "paragraph",
                "paragraph": {"rich_text": rich_text},
            })

    return blocks


def _parse_inline_markdown(text: str) -> List[Dict]:
    """Parse inline **bold** and plain text into Notion rich_text elements."""
    rich_text = []
    pattern = re.compile(r"\*\*(.+?)\*\*|__(.+?)__")
    last_end = 0

    for match in pattern.finditer(text):
        # Plain text before bold
        if match.start() > last_end:
            plain = text[last_end:match.start()]
            if plain:
                rich_text.append({
                    "type": "text",
                    "text": {"content": plain},
                })
        # Bold text
        bold_text = match.group(1) or match.group(2)
        rich_text.append({
            "type": "text",
            "text": {"content": bold_text},
            "annotations": {"bold": True},
        })
        last_end = match.end()

    # Remaining plain text
    if last_end < len(text):
        remaining = text[last_end:]
        if remaining:
            rich_text.append({
                "type": "text",
                "text": {"content": remaining},
            })

    if not rich_text:
        rich_text = [{"type": "text", "text": {"content": text}}]

    return rich_text


def _build_stats_block(
    emails: List[Dict],
    group_posts: List[Dict],
    model: str,
    run_time: datetime,
) -> List[Dict]:
    """Build a callout block with run statistics."""
    email_count = len(emails)
    post_count = len(group_posts)

    stats_text = (
        f"📊 {email_count} emails · "
        f"💬 {post_count} group posts · "
        f"🤖 {model} · "
        f"🕐 {run_time.strftime('%H:%M IST')}"
    )

    return [
        {
            "object": "block",
            "type": "callout",
            "callout": {
                "rich_text": [{"type": "text", "text": {"content": stats_text}}],
                "icon": {"type": "emoji", "emoji": "📬"},
                "color": "blue_background",
            },
        },
        {"object": "block", "type": "divider", "divider": {}},
    ]


def publish_to_notion(
    summary: str,
    emails: List[Dict],
    group_posts: List[Dict],
    config: Dict,
) -> str:
    """
    Create a new Notion page with the summary and return its URL.

    Args:
        summary:     Markdown summary from the LLM
        emails:      List of email dicts (for stats)
        group_posts: List of group post dicts (for stats)
        config:      Full config dict

    Returns:
        URL of the created Notion page.
    """
    notion_cfg = config.get("notion", {})
    summary_cfg = config.get("summary", {})
    model = summary_cfg.get("model", "nvidia/llama-3.1-nemotron-70b-instruct")
    show_stats = notion_cfg.get("show_stats_block", True)

    run_time = datetime.now()
    title_fmt = notion_cfg.get("page_title_format", "📬 Summary · {date} {time}")
    page_title = title_fmt.format(
        date=run_time.strftime("%d %b %Y"),
        time=run_time.strftime("%H:%M"),
        email_count=len(emails),
        group_count=len(group_posts),
    )

    log.info(f"Publishing to Notion: '{page_title}'")
    client = _get_client()

    # Build page blocks
    blocks = []

    if show_stats:
        blocks.extend(_build_stats_block(emails, group_posts, model, run_time))

    # Convert markdown summary to Notion blocks (max 100 per API call)
    summary_blocks = _markdown_to_notion_blocks(summary)
    blocks.extend(summary_blocks[:95])  # Notion API limit per request

    try:
        response = client.pages.create(
            parent={"database_id": NOTION_DATABASE_ID},
            properties={
                "Name": {
                    "title": [{"type": "text", "text": {"content": page_title}}]
                },
            },
            children=blocks,
        )

        page_url = response.get("url", "")
        page_id = response.get("id", "")
        log.info(f"✅ Notion page created: {page_url}")

        # Append any remaining blocks if summary was long
        if len(summary_blocks) > 95:
            remaining = summary_blocks[95:]
            client.blocks.children.append(
                block_id=page_id,
                children=remaining[:100],
            )
            log.info(f"Appended {len(remaining)} additional blocks.")

        return page_url

    except Exception as e:
        log.error(f"Failed to create Notion page: {e}")
        raise
