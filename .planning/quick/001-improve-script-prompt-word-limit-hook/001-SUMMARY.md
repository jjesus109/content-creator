---
phase: quick-001
plan: 01
subsystem: api
tags: [script-generation, claude, prompt-engineering, word-limit]

# Dependency graph
requires:
  - phase: 02-script-generation
    provides: ScriptGenerationService with generate_script and summarize_if_needed methods
provides:
  - HARD_WORD_LIMIT = 120 constant enforced at generation time and post-generation guard
  - Mandatory emotional/curiosity hook as first phrase in every generated script
  - summarize_if_needed capped at HARD_WORD_LIMIT regardless of target_words input
affects: []

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "HARD_WORD_LIMIT constant defined at module level — single source of truth for word ceiling"
    - "effective_target = min(target_words, HARD_WORD_LIMIT) pattern caps long-duration scripts"

key-files:
  created:
    - tests/test_quick_001_script_generation.py
  modified:
    - src/app/services/script_generation.py

key-decisions:
  - "HARD_WORD_LIMIT = 120 replaces target_words * 1.15 as the ceiling — absolute limit, not a soft suggestion"
  - "Hook instruction added as item 0 before the 6 pillars — first mandatory structural requirement in generate_script"
  - "summarize_if_needed uses effective_target = min(target_words, HARD_WORD_LIMIT) everywhere including truncation guard"
  - "TDD approach used — failing tests committed first, then implementation to green"

patterns-established:
  - "Module-level HARD_WORD_LIMIT constant referenced by both generation and summarization paths — no magic numbers"

requirements-completed: []

# Metrics
duration: 3min
completed: 2026-03-04
---

# Quick Task 001: Improve Script Prompt — Word Limit + Hook

**120-word hard cap enforced at generation time and post-gen guard; mandatory emotional/curiosity hook added as first structural requirement in every script**

## Performance

- **Duration:** ~3 min
- **Started:** 2026-03-04T18:05:55Z
- **Completed:** 2026-03-04T18:08:31Z
- **Tasks:** 2 (+ TDD RED commit)
- **Files modified:** 2

## Accomplishments

- Added `HARD_WORD_LIMIT = 120` module-level constant — single source of truth for the absolute word ceiling
- Updated `generate_script` system prompt: item 0 is now a mandatory emotional/curiosity hook instruction; guardrail replaced with `min(target_words, HARD_WORD_LIMIT)` and explicit "LIMITE ABSOLUTO: 120" language
- Updated `summarize_if_needed` to use `effective_target = min(target_words, HARD_WORD_LIMIT)` throughout — early-exit check, log messages, user prompt, max_tokens, and overshoot truncation guard all use `effective_target`
- Added hook first-phrase requirement to `summarize_if_needed` guardrails
- 7 new tests (TDD) — all pass; full suite: 28 passed, 2 skipped

## Task Commits

Each task was committed atomically:

1. **RED: Failing tests** - `4c9627c` (test — quick-001-01)
2. **Task 1: HARD_WORD_LIMIT constant + generate_script prompt** - `bcb21bd` (feat — quick-001-01)
3. **Task 2: summarize_if_needed effective_target + guardrails** - `10f92f7` (feat — quick-001-02)

## Files Created/Modified

- `src/app/services/script_generation.py` — Added HARD_WORD_LIMIT = 120 constant; updated generate_script guardrails and added hook as item 0; rewrote summarize_if_needed to use effective_target throughout
- `tests/test_quick_001_script_generation.py` — 7 new smoke/inspect tests covering HARD_WORD_LIMIT importability, _word_count correctness, prompt content assertions for both methods

## Decisions Made

- `HARD_WORD_LIMIT` defined after cost-rate constants (existing module-level constant pattern) rather than as a class attribute — available to module-level functions like `_word_count` if needed and consistent with COST_INPUT_PER_MTOK / COST_OUTPUT_PER_MTOK placement
- Hook instruction placed as item 0 before the numbered 6-pillar list (no renumbering of pillars 1-6) — preserves existing structure while adding pre-requirement
- `effective_target * 5` used for max_tokens in summarize (same multiplier as before, now based on capped target) — no change to token budget logic

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Script generation pipeline now enforces 120-word ceiling end-to-end at both generation and summarization stages
- All scripts will lead with an emotional/curiosity hook from the first word
- No callers need to change — the cap is internal to the service

---
*Phase: quick-001*
*Completed: 2026-03-04*

## Self-Check: PASSED

- FOUND: src/app/services/script_generation.py
- FOUND: tests/test_quick_001_script_generation.py
- FOUND: .planning/quick/001-improve-script-prompt-word-limit-hook/001-SUMMARY.md
- FOUND commit: 4c9627c (RED tests)
- FOUND commit: bcb21bd (Task 1 GREEN)
- FOUND commit: 10f92f7 (Task 2 GREEN)
