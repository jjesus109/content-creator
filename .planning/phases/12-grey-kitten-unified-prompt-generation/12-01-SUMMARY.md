---
phase: 12-grey-kitten-unified-prompt-generation
plan: 01
subsystem: api
tags: [openai, gpt-4o, tenacity, character-bible, prompt-generation, kling]

# Dependency graph
requires:
  - phase: 09-mexican-animated-cat-video-format
    provides: CHARACTER_BIBLE constant and KlingService in kling.py
  - phase: 10-scene-engine-and-music-pool
    provides: SceneEngine.pick_scene() returning raw scene_prompt string
provides:
  - CHARACTER_BIBLE updated to grey kitten (blue eyes, pink tongue, light grey fur, 49 words)
  - PromptGenerationService.generate_unified_prompt(scene_prompt) — GPT-4o unified prompt with fallback
  - _call_gpt4o_with_backoff — module-level tenacity-wrapped GPT-4o call function
affects:
  - 12-02-pipeline-wiring (will import PromptGenerationService into daily_pipeline)
  - 12-03-test-updates (will rewrite old orange-tabby assertions in test_character_bible.py)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - module-level tenacity retry function (not instance method) for APScheduler ThreadPoolExecutor compatibility
    - never-raise service pattern: try/except wraps tenacity call, fallback always returns string
    - self._last_cost_usd attribute on service for cost tracking by circuit breaker caller
    - TDD tests mock get_settings to avoid pydantic ValidationError on missing env vars

key-files:
  created:
    - src/app/services/prompt_generation.py
    - tests/test_prompt_generation.py
    - tests/test_character_bible_grey_kitten.py
  modified:
    - src/app/services/kling.py

key-decisions:
  - "CHARACTER_BIBLE updated from orange tabby Mochi to grey kitten: blue eyes, pink tongue, soft light grey fur (49 words, v3.0)"
  - "PromptGenerationService uses plain-text GPT-4o output (not JSON response_format) — output is prose for Kling, not structured data"
  - "Temperature 0.9 for PromptGenerationService (vs 0.85 in SceneEngine) — more creative character integration needed"
  - "Old orange-tabby assertions in test_character_bible.py intentionally left failing — will be rewritten in Plan 03"
  - "TDD tests patch get_settings to avoid pydantic ValidationError — pattern to reuse in future service tests"

patterns-established:
  - "Never-raise service: generate_unified_prompt always returns a string, never propagates exceptions"
  - "Module-level tenacity: _call_gpt4o_with_backoff at module level (not instance method) for APScheduler compatibility"
  - "Cost tracking: _last_cost_usd attribute set on every call (0.0 on fallback) for circuit breaker use"

requirements-completed: [GREY-01]

# Metrics
duration: 5min
completed: 2026-03-21
---

# Phase 12 Plan 01: Grey Kitten Character + PromptGenerationService Summary

**Grey kitten CHARACTER_BIBLE (49 words, blue eyes/pink tongue) replaces orange tabby Mochi; new PromptGenerationService wraps GPT-4o with tenacity retry and concatenation fallback for animated Kling prompt generation**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-03-21T17:48:06Z
- **Completed:** 2026-03-21T17:52:35Z
- **Tasks:** 2
- **Files modified:** 4 (1 modified, 3 created)

## Accomplishments
- Updated CHARACTER_BIBLE in kling.py from orange tabby Mochi to light grey kitten with huge blue eyes, open-mouthed smile, and pink tongue (49 words, within 40-50 target)
- Created PromptGenerationService with GPT-4o unified prompt generation, tenacity retry (3 attempts, 2s–16s backoff), and concatenation fallback
- Created 16 TDD tests across 2 test files covering all character and service behavior assertions

## Task Commits

Each task was committed atomically:

1. **Task 1: Update CHARACTER_BIBLE to grey kitten** - `dcee516` (feat)
2. **Task 2: Create PromptGenerationService** - `9dfc7b1` (feat)

## Files Created/Modified
- `src/app/services/kling.py` - CHARACTER_BIBLE updated to grey kitten; comment updated to v3.0
- `src/app/services/prompt_generation.py` - New: PromptGenerationService + _call_gpt4o_with_backoff
- `tests/test_character_bible_grey_kitten.py` - New: 7 TDD tests asserting grey kitten identity
- `tests/test_prompt_generation.py` - New: 9 TDD tests for PromptGenerationService behavior

## Decisions Made
- CHARACTER_BIBLE updated to grey kitten with blue eyes, pink tongue, soft light grey fur (49 words) — replaces orange tabby Mochi v1.0 constant
- PromptGenerationService uses plain-text GPT-4o output (no JSON response_format) — output is prose for Kling AI, not structured data
- Temperature 0.9 for PromptGenerationService (vs 0.85 in SceneEngine) — more creative character integration needed
- Old orange-tabby assertions in test_character_bible.py intentionally left failing — will be rewritten in Plan 03
- TDD tests patch get_settings (not env vars) — clean isolation without real credentials required

## Deviations from Plan

None - plan executed exactly as written.

The plan noted that existing test_character_bible.py assertions (orange/tabby, mexican) would intentionally fail after CHARACTER_BIBLE update — this is expected and documented: Plan 03 will rewrite those tests.

## Issues Encountered
- Tests required patching `get_settings` to avoid pydantic ValidationError from missing env vars — standard pattern not documented in the plan but applied consistently across all 7 service-instantiation tests.

## User Setup Required
None - no external service configuration required. PromptGenerationService uses existing `OPENAI_API_KEY` env var already in production settings.

## Next Phase Readiness
- PromptGenerationService ready for pipeline wiring in Plan 02
- CHARACTER_BIBLE grey kitten identity live in kling.py
- 2 tests in test_character_bible.py will remain failing until Plan 03 rewrites them

---
*Phase: 12-grey-kitten-unified-prompt-generation*
*Completed: 2026-03-21*
