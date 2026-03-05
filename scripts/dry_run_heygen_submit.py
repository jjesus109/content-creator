#!/usr/bin/env python3
"""
Dry-run HeyGen video submission against the real HeyGen v2 API.

Submits a render job and prints the video_id. Does NOT wait for completion.
Monitor progress at: https://app.heygen.com/videos

Usage:
    python scripts/dry_run_heygen_submit.py
    python scripts/dry_run_heygen_submit.py --script "Tu texto aquí."

Requirements:
    HEYGEN_API_KEY, HEYGEN_AVATAR_ID, HEYGEN_VOICE_ID, HEYGEN_WEBHOOK_URL,
    HEYGEN_GESTURE_PROMPT must be set in .env
"""
import sys, os, argparse
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from dotenv import load_dotenv
load_dotenv()

import requests
from app.services.heygen import HeyGenService

DEFAULT_SCRIPT = (
    "En cada momento de quietud, encontramos la claridad "
    "que el ruido del mundo nos roba."
)

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Submit a real HeyGen render job and print the video_id."
    )
    parser.add_argument(
        "--script",
        default=DEFAULT_SCRIPT,
        help="Spanish script text to render (default: short test phrase)",
    )
    args = parser.parse_args()

    sep = "=" * 60
    print(sep)
    print("DRY RUN: HeyGen Video Submit")
    print(f"Script ({len(args.script.split())} words): {args.script}")
    print(sep)

    svc = HeyGenService()
    try:
        video_id = svc.submit(script_text=args.script, background_url="")
        print(f"\n[SUCCESS]")
        print(f"video_id: {video_id}")
        print(f"\nJob is rendering. Monitor at: https://app.heygen.com/videos")
        print(f"The webhook will fire to HEYGEN_WEBHOOK_URL when complete.")
    except requests.HTTPError as exc:
        print(f"\n[FAILED] HTTP {exc.response.status_code}")
        print(exc.response.text)
        sys.exit(1)

    print(sep)

if __name__ == "__main__":
    main()
