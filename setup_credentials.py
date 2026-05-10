#!/usr/bin/env python3
"""
setup_credentials.py — Watches your Downloads folder and automatically moves
the Google credentials JSON to the right place once you download it.

Run this BEFORE you click "Download JSON" on Google Cloud Console:
    python3 setup_credentials.py
"""

import os
import time
import shutil
import glob
import sys

DOWNLOADS_DIR = os.path.expanduser("~/Downloads")
DEST_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "credentials", "google_credentials.json")
os.makedirs(os.path.dirname(DEST_PATH), exist_ok=True)

def find_credentials_file():
    """Find any recently downloaded Google OAuth credentials JSON."""
    patterns = [
        os.path.join(DOWNLOADS_DIR, "client_secret_*.json"),
        os.path.join(DOWNLOADS_DIR, "client_secret*.json"),
    ]
    matches = []
    for pattern in patterns:
        matches.extend(glob.glob(pattern))
    return matches

def main():
    print("\n" + "=" * 60)
    print("  Google Credentials Setup Helper")
    print("=" * 60)
    print(f"\n📁 Watching: {DOWNLOADS_DIR}")
    print(f"📂 Will save to: {DEST_PATH}")
    print("\n⏳ Waiting for you to download the credentials JSON from Google Cloud...")
    print("   (Run this, then download the file — it'll be moved automatically)\n")
    print("Press Ctrl+C to cancel.\n")

    # Remember existing files before waiting
    existing = set(find_credentials_file())

    try:
        while True:
            current = set(find_credentials_file())
            new_files = current - existing

            if new_files:
                src = sorted(new_files)[0]  # Take the first new file
                print(f"\n✅ Found credentials file: {os.path.basename(src)}")
                shutil.copy2(src, DEST_PATH)
                print(f"✅ Copied to: {DEST_PATH}")
                print("\n🎉 Done! You can now run:")
                print("   python3 main.py --test\n")
                break

            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\n❌ Cancelled.")
        sys.exit(0)

if __name__ == "__main__":
    main()
