---
phase: quick-002
plan: 01
subsystem: script-generation
tags: [anthropic, cli, dry-run, debugging, script-generation]

# Dependency graph
requires:
  - phase: quick-001
    provides: improved script generation prompt with 120-word cap and emotional hook
provides:
  - CLI dry-run entry point for iterating on script generation prompts without deploying
affects: [script-generation, prompt-iteration, local-dev]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "MagicMock supabase stub pattern: pass MagicMock() to ScriptGenerationService to bypass DB entirely"
    - "Method-level monkey-patch: svc.load_active_rejection_constraints = lambda: [] avoids DB call inside service"
    - "sys.path injection at top of scripts/ files so src/app imports resolve without package install"

key-files:
  created:
    - scripts/dry_run_script_generation.py
  modified: []

key-decisions:
  - "MagicMock() as supabase stub allows ScriptGenerationService to run with only ANTHROPIC_API_KEY — no Supabase, no DB"
  - "Method monkey-patch (not unittest.mock.patch) used for load_active_rejection_constraints — simpler and sufficient for a one-shot CLI script"
  - "Script placed in scripts/ directory (new, peer to src/) — keeps one-off dev tools separate from application code"
  - "dotenv loaded before any app imports so ANTHROPIC_API_KEY is in os.environ when Settings is constructed"

patterns-established:
  - "Quick task scripts use sys.path.insert(0, '../src') to import app modules without editable install"

requirements-completed: []

# Metrics
duration: 5min
completed: 2026-03-04
---

# Quick Task 002: Test Script Generation Dry Run Summary

**CLI dry-run script calling real Anthropic API through ScriptGenerationService with MagicMock Supabase stub, printing topic + raw script + final script with per-step word counts and costs**

## Performance

- **Duration:** 5 min
- **Started:** 2026-03-04T00:00:00Z
- **Completed:** 2026-03-04T00:05:00Z
- **Tasks:** 1
- **Files modified:** 1 (created)

## Accomplishments

- Created `scripts/dry_run_script_generation.py` as a standalone CLI entry point for prompt iteration
- Stubs Supabase entirely with MagicMock — only `ANTHROPIC_API_KEY` in `.env` required
- Runs all three generation steps (topic summary, raw script, summarize_if_needed) and prints readable report with costs
- `--pool`, `--tone`, `--duration` CLI args allow iterating over mood variations without editing files
- All 28 existing smoke tests pass unaffected

## Task Commits

1. **Task 1: Create scripts/dry_run_script_generation.py** - `4822e18` (feat)

## Files Created/Modified

- `/Users/jesusalbino/Projects/content-creation/scripts/dry_run_script_generation.py` - CLI dry-run tool for script generation with argparse, MagicMock supabase stub, full 3-step generation pipeline, and formatted report output

## Decisions Made

- MagicMock() passed as supabase to ScriptGenerationService — avoids DB import chains entirely
- `svc.load_active_rejection_constraints = lambda: []` used as instance-level monkey-patch — simpler than unittest.mock.patch context manager for a one-shot script
- `load_dotenv()` called before any `app.*` imports so Settings reads ANTHROPIC_API_KEY from .env file at construction time
- Script placed in a new `scripts/` directory at project root, parallel to `src/` and `tests/`

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- System `python` command not available (macOS); used `.venv/bin/python3` for all verification steps. The script itself uses `#!/usr/bin/env python3` shebang and runs correctly with `.venv/bin/python3 scripts/dry_run_script_generation.py`.

## User Setup Required

None — only `ANTHROPIC_API_KEY` must be present in `.env` (already required by the app). Run with:

```bash
.venv/bin/python3 scripts/dry_run_script_generation.py
.venv/bin/python3 scripts/dry_run_script_generation.py --pool eastern --tone melancholico --duration short
```

## Next Phase Readiness

- Prompt iteration loop is now available locally: edit `src/app/services/script_generation.py`, run the dry-run script, evaluate output, repeat
- No blockers

---
*Phase: quick-002*
*Completed: 2026-03-04*
