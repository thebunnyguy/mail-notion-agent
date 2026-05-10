"""
utils/formatter.py — Converts raw email/group data into LLM-ready text.
"""

import re
from datetime import datetime
from typing import List, Dict, Any


def clean_text(text: str) -> str:
    """Strip excessive whitespace and control characters from text."""
    if not text:
        return ""
    # Remove HTML tags if any slipped through
    text = re.sub(r"<[^>]+>", " ", text)
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text


def truncate(text: str, max_chars: int = 800) -> str:
    """Truncate text to a safe length for the LLM context."""
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "… [truncated]"


def format_emails_for_llm(emails: List[Dict[str, Any]]) -> str:
    """Format a list of email dicts into structured text for the LLM."""
    if not emails:
        return "No emails to summarize."

    lines = ["=== GMAIL EMAILS ===\n"]
    for i, email in enumerate(emails, 1):
        lines.append(f"[Email {i}]")
        lines.append(f"From   : {email.get('sender', 'Unknown')}")
        lines.append(f"Subject: {email.get('subject', '(no subject)')}")
        lines.append(f"Date   : {email.get('date', '')}")
        body = truncate(clean_text(email.get("body", "")))
        lines.append(f"Body   : {body}")
        lines.append("")

    return "\n".join(lines)


def format_groups_for_llm(posts: List[Dict[str, Any]]) -> str:
    """Format a list of Google Groups post dicts into structured text."""
    if not posts:
        return "No Google Groups posts to summarize."

    lines = ["=== GOOGLE GROUPS POSTS ===\n"]
    for i, post in enumerate(posts, 1):
        lines.append(f"[Post {i}]")
        lines.append(f"Group  : {post.get('group', 'Unknown')}")
        lines.append(f"Author : {post.get('author', 'Unknown')}")
        lines.append(f"Title  : {post.get('title', '(no title)')}")
        lines.append(f"Date   : {post.get('date', '')}")
        body = truncate(clean_text(post.get("body", "")))
        lines.append(f"Content: {body}")
        if post.get("url"):
            lines.append(f"Link   : {post.get('url')}")
        lines.append("")

    return "\n".join(lines)


def build_llm_prompt(
    emails: List[Dict],
    group_posts: List[Dict],
    focus_topics: List[str],
    style: str = "bullet_points",
    language: str = "English",
) -> str:
    """Assemble the full prompt sent to the NVIDIA NIM LLM."""
    style_instructions = {
        "bullet_points": (
            "Format your response as grouped bullet points. "
            "Group related items by topic. Use emojis for section headers."
        ),
        "paragraph": (
            "Write concise paragraphs. One paragraph per topic cluster."
        ),
        "tldr": (
            "Produce a very short TL;DR — maximum 5 bullet points covering only "
            "the most critical updates."
        ),
    }.get(style, "Use bullet points grouped by topic.")

    topics_str = ", ".join(focus_topics) if focus_topics else "all topics"
    email_section = format_emails_for_llm(emails)
    groups_section = format_groups_for_llm(group_posts)

    prompt = f"""You are an intelligent personal assistant that summarizes emails and Google Groups posts.

INSTRUCTIONS:
- Language: {language}
- Focus on these topics: {topics_str}
- Ignore: newsletters, promotional content, automated notifications, spam
- {style_instructions}
- For each item, mention WHO said/sent it and WHAT the key point is
- Highlight any ACTION ITEMS or DEADLINES clearly with ⚠️
- If there is nothing relevant, say so briefly

---

{email_section}

{groups_section}

---

Now provide a clean, organized summary of the above content:"""

    return prompt
