---
phase: quick-002
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - scripts/dry_run_script_generation.py
autonomous: true
requirements: []

must_haves:
  truths:
    - "Running the script calls the real Anthropic API and prints the generated script to stdout"
    - "The script stops before any HeyGen or Telegram call — no video submission, no message sent"
    - "Word count and cost are printed so quality of the prompt changes can be evaluated locally"
    - "The script works with just ANTHROPIC_API_KEY in .env — no Supabase or other credentials required"
  artifacts:
    - path: "scripts/dry_run_script_generation.py"
      provides: "CLI entry point for dry-running script generation with a hardcoded or CLI-supplied mood"
      exports: ["main"]
  key_links:
    - from: "scripts/dry_run_script_generation.py"
      to: "src/app/services/script_generation.ScriptGenerationService"
      via: "direct import and instantiation with supabase=None stub"
      pattern: "ScriptGenerationService"
    - from: "dry_run_script_generation.py"
      to: "Anthropic API"
      via: "_call_claude inside ScriptGenerationService"
      pattern: "anthropic_api_key"
---

<objective>
Create a single CLI script (`scripts/dry_run_script_generation.py`) that calls the real Anthropic
API through the existing `ScriptGenerationService` and prints the result — stopping before HeyGen,
Telegram, or any DB write.

Purpose: Validate prompt quality changes locally without deploying or running the full pipeline.
After quick task 001 (hook + 120-word cap), the developer needs a fast feedback loop: run the
script, read the output, tweak the prompt, repeat.

Output: `scripts/dry_run_script_generation.py` — runnable with `python scripts/dry_run_script_generation.py`
</objective>

<execution_context>
@./.claude/get-shit-done/workflows/execute-plan.md
@./.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@src/app/services/script_generation.py
@src/app/services/mood.py
@src/app/settings.py

<interfaces>
<!-- Key types and contracts the executor needs. Extracted from codebase. -->

From src/app/services/script_generation.py:
```python
HARD_WORD_LIMIT = 120   # module-level constant

class ScriptGenerationService:
    def __init__(self, supabase: Client | None = None) -> None: ...
    # supabase=None triggers get_supabase() — pass a stub to avoid real DB connection

    def generate_topic_summary(
        self,
        mood: dict,
        attempt: int = 0,
        rejection_constraints: list[dict] | None = None,
    ) -> tuple[str, float]: ...
    # Returns (topic_summary_text, cost_usd)

    def generate_script(
        self,
        topic_summary: str,
        mood: dict,
        target_words: int,
        rejection_constraints: list[dict] | None = None,
    ) -> tuple[str, float]: ...
    # Returns (script_text, cost_usd)

    def summarize_if_needed(
        self,
        script: str,
        target_words: int,
    ) -> tuple[str, float]: ...
    # Returns (final_script, cost_usd); cost_usd=0.0 if no summarization needed
```

From src/app/services/mood.py:
```python
DURATION_WORD_COUNTS = {
    "short": 70,    # 30s
    "medium": 140,  # 60s (default)
    "long": 200,    # 90s
}

POOLS = ["existential", "practical_wisdom", "human_nature",
         "modern_paradoxes", "eastern", "creative_life"]

DEFAULT_TONE = "contemplative"
DEFAULT_DURATION = "medium"
```

From src/app/settings.py:
```python
@lru_cache
def get_settings() -> Settings:
    return Settings()
# Settings reads from .env file. Only ANTHROPIC_API_KEY is required for this script.
```
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Create scripts/dry_run_script_generation.py</name>
  <files>scripts/dry_run_script_generation.py</files>
  <action>
Create `scripts/dry_run_script_generation.py` at the project root (sibling to `src/`, `tests/`).

The script must:

1. **Accept optional CLI arguments** using `argparse`:
   - `--pool` (default: `"existential"`) — one of the 6 pool names from `mood.py`
   - `--tone` (default: `"contemplative"`) — free string (e.g. "melancholico", "esperanzador")
   - `--duration` (default: `"medium"`) — one of `short | medium | long`

2. **Stub out the Supabase client** so the script works with only `ANTHROPIC_API_KEY` in `.env`.
   Pass a `MagicMock()` (from `unittest.mock`) as `supabase` to `ScriptGenerationService`.
   Also patch `load_active_rejection_constraints` to return `[]` so no DB call fires:
   ```python
   from unittest.mock import MagicMock
   stub_supabase = MagicMock()
   svc = ScriptGenerationService(supabase=stub_supabase)
   svc.load_active_rejection_constraints = lambda: []
   ```

3. **Run the three generation steps** in order:
   a. `generate_topic_summary(mood, attempt=0, rejection_constraints=[])` — prints topic
   b. `generate_script(topic_summary, mood, target_words)` — prints raw script + word count
   c. `summarize_if_needed(script, target_words)` — prints final script + word count

4. **Print a clear, readable report** to stdout:
   ```
   ============================================================
   DRY RUN: Script Generation
   Mood: pool=existential | tone=contemplative | duration=medium | target=140 words
   ============================================================

   [TOPIC SUMMARY]
   <topic text>
   Cost: $0.000012

   [RAW SCRIPT]  (87 words)
   <script text>
   Cost: $0.000234

   [FINAL SCRIPT]  (87 words — no summarization needed)
   <script text>

   ============================================================
   TOTAL COST: $0.000246
   WORD COUNT: 87 / 120 limit
   ============================================================
   ```
   If summarization WAS needed, show both raw and final word counts and note the reduction.

5. **Load `.env` automatically** via `python-dotenv` before importing settings:
   ```python
   from dotenv import load_dotenv
   load_dotenv()
   ```
   This ensures `ANTHROPIC_API_KEY` is available even if the shell does not export it.

6. **sys.path injection** at the top so `src/app` imports resolve without installing the package:
   ```python
   import sys, os
   sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
   ```

Full file structure:
```python
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
```
  </action>
  <verify>
    <automated>cd /Users/jesusalbino/Projects/content-creation && python -c "
import ast, sys
with open('scripts/dry_run_script_generation.py') as f:
    src = f.read()
# Syntax check
ast.parse(src)
# Structure checks
assert 'load_dotenv' in src, 'missing dotenv load'
assert 'MagicMock' in src, 'missing supabase stub'
assert 'generate_topic_summary' in src, 'missing topic summary call'
assert 'generate_script' in src, 'missing script generation call'
assert 'summarize_if_needed' in src, 'missing summarize call'
assert 'HARD_WORD_LIMIT' in src, 'missing word limit display'
assert '--pool' in src, 'missing --pool arg'
assert '--duration' in src, 'missing --duration arg'
print('PASS: dry_run_script_generation.py is valid and contains required elements')
"
    </automated>
  </verify>
  <done>
`scripts/dry_run_script_generation.py` exists, parses cleanly, stubs Supabase with MagicMock,
calls all three generation methods, and prints topic + raw script + final script with word counts
and cost. Running `python scripts/dry_run_script_generation.py --help` shows usage without error.
  </done>
</task>

</tasks>

<verification>
After task completes:

1. Syntax + structure: `python -c "import ast; ast.parse(open('scripts/dry_run_script_generation.py').read()); print('OK')"` — no SyntaxError.
2. Help flag works without credentials: `python scripts/dry_run_script_generation.py --help` — prints argparse help and exits 0.
3. Smoke import: `python -c "import sys; sys.path.insert(0,'src'); from app.services.script_generation import ScriptGenerationService"` — no ImportError.
4. Live run (requires ANTHROPIC_API_KEY in .env): `python scripts/dry_run_script_generation.py --pool eastern --tone melancholico --duration short` — prints topic, raw script, final script, total cost. No HeyGen or Telegram calls fire.
5. Existing tests unaffected: `python -m pytest tests/ -x -q -m "not e2e"` — all pass.
</verification>

<success_criteria>
- `scripts/dry_run_script_generation.py` exists and is syntactically valid
- Script stubs Supabase so only `ANTHROPIC_API_KEY` in `.env` is needed
- All three generation steps (topic, script, summarize) are called and their output printed
- Word count and cost are displayed clearly for each step and as a total
- `--pool`, `--tone`, `--duration` CLI args allow varying the mood without editing the file
- No HeyGen, Telegram, or DB writes occur — safe to run in any environment
</success_criteria>

<output>
After completion, create `.planning/quick/002-test-script-generation-dry-run/002-SUMMARY.md`
</output>
