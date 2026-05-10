"""
main.py — Entry point for the Mail + Google Groups → Notion Summarization Agent.

Usage:
    python main.py             # Start the scheduler (runs at configured times)
    python main.py --run-now   # Run immediately once (for testing)
    python main.py --test      # Dry run: fetch only, no Notion publish
"""

import argparse
import sys
import os
import yaml
import pytz

from datetime import datetime
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agents.gmail_agent import fetch_emails
from agents.groups_agent import fetch_group_posts
from agents.summarizer import summarize
from agents.notion_agent import publish_to_notion
from utils.logger import get_logger

load_dotenv()
log = get_logger("main")

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.yaml")


def load_config() -> dict:
    """Load and return the YAML configuration file."""
    with open(CONFIG_PATH, "r") as f:
        return yaml.safe_load(f)


def run_agent(config: dict, dry_run: bool = False) -> None:
    """
    Core agent pipeline:
      1. Fetch Gmail emails
      2. Fetch Google Groups posts
      3. Summarize via NVIDIA NIM
      4. Publish to Notion (unless dry_run)
    """
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log.info("=" * 60)
    log.info(f"🚀 Agent run started at {now}")
    log.info("=" * 60)

    emails = []
    group_posts = []
    summary = ""
    notion_url = ""

    # ── Step 1: Fetch Gmail ───────────────────────────────────
    try:
        log.info("📥 Step 1/4 — Fetching Gmail...")
        emails = fetch_emails(config)
        log.info(f"   ✅ {len(emails)} emails fetched.")
    except Exception as e:
        log.error(f"   ❌ Gmail fetch failed: {e}")

    # ── Step 2: Fetch Google Groups ───────────────────────────
    try:
        log.info("💬 Step 2/4 — Fetching Google Groups posts...")
        group_posts = fetch_group_posts(config)
        log.info(f"   ✅ {len(group_posts)} group posts fetched.")
    except Exception as e:
        log.error(f"   ❌ Google Groups fetch failed: {e}")

    # ── Step 3: Summarize ─────────────────────────────────────
    try:
        log.info("🤖 Step 3/4 — Summarizing via NVIDIA NIM...")
        summary = summarize(emails, group_posts, config)
        log.info("   ✅ Summary generated.")
        if dry_run:
            log.info("\n" + "─" * 50)
            log.info("DRY RUN — Summary Preview:")
            log.info("─" * 50)
            print(summary)
            log.info("─" * 50)
    except Exception as e:
        log.error(f"   ❌ Summarization failed: {e}")
        return

    # ── Step 4: Publish to Notion ─────────────────────────────
    if dry_run:
        log.info("⏭️  Step 4/4 — Skipping Notion publish (dry run mode).")
        log.info("✅ Dry run complete.")
        return

    try:
        log.info("📝 Step 4/4 — Publishing to Notion...")
        notion_url = publish_to_notion(summary, emails, group_posts, config)
        log.info(f"   ✅ Published: {notion_url}")
    except Exception as e:
        log.error(f"   ❌ Notion publish failed: {e}")

    log.info("=" * 60)
    log.info(f"✅ Run complete — {len(emails)} emails, {len(group_posts)} posts → Notion")
    log.info("=" * 60)


def start_scheduler(config: dict) -> None:
    """
    Start the APScheduler with the configured daily times.
    Blocks indefinitely until Ctrl+C.
    """
    schedule_cfg = config.get("schedule", {})
    times = schedule_cfg.get("times", ["09:00", "12:30", "15:00", "18:00", "21:00"])
    tz_name = schedule_cfg.get("timezone", "Asia/Kolkata")
    tz = pytz.timezone(tz_name)

    scheduler = BlockingScheduler(timezone=tz)

    for time_str in times:
        try:
            hour, minute = map(int, time_str.split(":"))
            scheduler.add_job(
                run_agent,
                trigger=CronTrigger(hour=hour, minute=minute, timezone=tz),
                args=[config],
                id=f"agent_{time_str.replace(':', '')}",
                name=f"Mail Summary @ {time_str}",
                misfire_grace_time=300,  # 5-min grace window
                replace_existing=True,
            )
            log.info(f"  ⏰ Scheduled: {time_str} {tz_name}")
        except ValueError:
            log.warning(f"  ⚠️  Invalid time format: '{time_str}' — skipping.")

    log.info("\n" + "=" * 60)
    log.info("📬 Mail-Notion Agent is running!")
    log.info(f"   Timezone: {tz_name}")
    log.info(f"   Schedule: {', '.join(times)}")
    log.info("   Press Ctrl+C to stop.")
    log.info("=" * 60 + "\n")

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        log.info("🛑 Scheduler stopped by user.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Mail + Google Groups → Notion Summarization Agent"
    )
    parser.add_argument(
        "--run-now",
        action="store_true",
        help="Run the agent immediately once and exit.",
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Dry run: fetch + summarize only, skip Notion publish.",
    )
    args = parser.parse_args()

    config = load_config()

    if args.test:
        log.info("🧪 Running in DRY RUN / TEST mode...")
        run_agent(config, dry_run=True)
    elif args.run_now:
        log.info("▶️  Running agent immediately (--run-now)...")
        run_agent(config, dry_run=False)
    else:
        # Default: start the scheduler
        start_scheduler(config)


if __name__ == "__main__":
    main()
