#!/usr/bin/env python3
"""
Dry-run script generation against the real Anthropic API.

Stops before HeyGen, Telegram, or any DB write.
Usage:
    python scripts/dry_run_script_generation.py
    python scripts/dry_run_script_generation.py --pool eastern --tone melancholico --duration short
"""
import sys, os, argparse
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from dotenv import load_dotenv
load_dotenv()

from unittest.mock import MagicMock
from app.services.script_generation import ScriptGenerationService, HARD_WORD_LIMIT, _word_count
from app.services.mood import DURATION_WORD_COUNTS, POOLS


def main() -> None:
    parser = argparse.ArgumentParser(description="Dry-run script generation (no HeyGen, no Telegram)")
    parser.add_argument("--pool", default="existential", choices=POOLS)
    parser.add_argument("--tone", default="contemplative")
    parser.add_argument("--duration", default="medium", choices=["short", "medium", "long"])
    args = parser.parse_args()

    mood = {"pool": args.pool, "tone": args.tone, "duration": args.duration}
    target_words = DURATION_WORD_COUNTS[args.duration]

    stub_supabase = MagicMock()
    svc = ScriptGenerationService(supabase=stub_supabase)
    svc.load_active_rejection_constraints = lambda: []

    sep = "=" * 60
    print(sep)
    print("DRY RUN: Script Generation")
    print(f"Mood: pool={args.pool} | tone={args.tone} | duration={args.duration} | target={target_words} words")
    print(sep)

    topic, topic_cost = svc.generate_topic_summary(mood, attempt=0, rejection_constraints=[])
    print(f"\n[TOPIC SUMMARY]")
    print(topic)
    print(f"Cost: ${topic_cost:.6f}")

    script, script_cost = svc.generate_script(topic, mood, target_words, rejection_constraints=[])
    raw_count = _word_count(script)
    print(f"\n[RAW SCRIPT]  ({raw_count} words)")
    print(script)
    print(f"Cost: ${script_cost:.6f}")

    final_script, summarize_cost = svc.summarize_if_needed(script, target_words)
    final_count = _word_count(final_script)

    if summarize_cost > 0.0:
        print(f"\n[FINAL SCRIPT]  ({final_count} words — summarized from {raw_count})")
        print(f"Cost: ${summarize_cost:.6f}")
    else:
        print(f"\n[FINAL SCRIPT]  ({final_count} words — no summarization needed)")
    print(final_script)

    total_cost = topic_cost + script_cost + summarize_cost
    print(f"\n{sep}")
    print(f"TOTAL COST: ${total_cost:.6f}")
    print(f"WORD COUNT: {final_count} / {HARD_WORD_LIMIT} limit")
    print(sep)


if __name__ == "__main__":
    main()
