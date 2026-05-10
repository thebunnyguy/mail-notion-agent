"""
agents/summarizer.py — Calls NVIDIA NIM API to summarize emails + group posts.

Uses the OpenAI-compatible endpoint at integrate.api.nvidia.com.
Model: nvidia/llama-3.1-nemotron-70b-instruct (free tier).
"""

import os
from typing import List, Dict, Any

from openai import OpenAI
from dotenv import load_dotenv

from utils.logger import get_logger
from utils.formatter import build_llm_prompt

load_dotenv()
log = get_logger("summarizer")

NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY")
NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"


def _get_client() -> OpenAI:
    if not NVIDIA_API_KEY or NVIDIA_API_KEY.startswith("nvapi-XXXX"):
        raise ValueError(
            "NVIDIA_API_KEY is not set. "
            "Please add your key to the .env file. "
            "Get a free key at: https://build.nvidia.com"
        )
    return OpenAI(base_url=NVIDIA_BASE_URL, api_key=NVIDIA_API_KEY)


def summarize(
    emails: List[Dict[str, Any]],
    group_posts: List[Dict[str, Any]],
    config: Dict,
) -> str:
    """
    Send emails + group posts to NVIDIA NIM and return a markdown summary.

    Args:
        emails:      List of email dicts from gmail_agent
        group_posts: List of post dicts from groups_agent
        config:      Full config dict from config.yaml

    Returns:
        A markdown-formatted summary string.
    """
    summary_cfg = config.get("summary", {})
    model = summary_cfg.get("model", "meta/llama-3.3-70b-instruct")
    focus_topics = summary_cfg.get("focus_topics", [])
    style = summary_cfg.get("style", "bullet_points")
    language = summary_cfg.get("language", "English")
    max_tokens = summary_cfg.get("max_tokens", 1500)
    temperature = summary_cfg.get("temperature", 0.3)

    if not emails and not group_posts:
        log.info("Nothing to summarize — no emails or posts fetched.")
        return "✅ No new emails or Google Groups posts in this time window."

    log.info(
        f"Sending to NVIDIA NIM [{model}]: "
        f"{len(emails)} emails + {len(group_posts)} group posts"
    )

    prompt = build_llm_prompt(
        emails=emails,
        group_posts=group_posts,
        focus_topics=focus_topics,
        style=style,
        language=language,
    )

    try:
        client = _get_client()
        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a concise, intelligent personal assistant. "
                        "You summarize emails and group posts clearly and helpfully. "
                        "Always respond in well-formatted markdown."
                    ),
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
            max_tokens=max_tokens,
            temperature=temperature,
            stream=False,
        )

        summary = response.choices[0].message.content.strip()
        usage = response.usage
        log.info(
            f"Summary generated. Tokens used — "
            f"prompt: {usage.prompt_tokens}, "
            f"completion: {usage.completion_tokens}, "
            f"total: {usage.total_tokens}"
        )
        return summary

    except Exception as e:
        log.error(f"NVIDIA NIM API call failed: {e}")
        raise
