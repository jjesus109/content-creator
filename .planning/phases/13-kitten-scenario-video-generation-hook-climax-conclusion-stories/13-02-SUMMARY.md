---
phase: 13-kitten-scenario-video-generation-hook-climax-conclusion-stories
plan: 02
subsystem: api
tags: [similarity, anti-repetition, prompt-generation, gpt4o, kling-ai, pgvector]

# Dependency graph
requires:
  - phase: 12-grey-kitten-unified-prompt-generation
    provides: PromptGenerationService with _SYSTEM_PROMPT and grey kitten CHARACTER_BIBLE
  - phase: 10-scene-engine-and-music-pool
    provides: SimilarityService with is_too_similar_scene() pattern to mirror
  - phase: 13-02 (migration 0012)
    provides: check_prompt_similarity SQL function and prompt_embedding column
provides:
  - SimilarityService.is_too_similar_prompt() calling check_prompt_similarity RPC
  - PROMPT_SIMILARITY_THRESHOLD = 0.78 and PROMPT_LOOKBACK_DAYS = 7 constants
  - Updated PromptGenerationService _SYSTEM_PROMPT with hook->climax->conclusion arc preservation
affects:
  - 13-03 (pipeline wiring — will call is_too_similar_prompt and use arc-aware prompt)
  - 13-04 (tests — will test arc preservation end-to-end)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "is_too_similar_prompt() mirrors is_too_similar_scene() — same fail-open pattern, separate RPC"
    - "PromptGenerationService system prompt uses arc-aware instructions: hook->climax->conclusion must be preserved"
    - "Flowing prose required (no explicit time markers like 'In the first 3 seconds...')"

key-files:
  created: []
  modified:
    - src/app/services/similarity.py
    - src/app/services/prompt_generation.py

key-decisions:
  - "PROMPT_SIMILARITY_THRESHOLD = 0.78 — same as SCENE_SIMILARITY_THRESHOLD; visual/stylistic repetition operates at same fidelity"
  - "PROMPT_LOOKBACK_DAYS = 7 — matches scene similarity window; unified prompt embeddings have same freshness semantics"
  - "is_too_similar_prompt() is always-execute; enforcement by caller (pipeline) via feature flag — same separation-of-concerns as scene check"
  - "Arc preservation: GPT-4o instructed to preserve hook->climax->conclusion pacing, not flatten scene into single static shot"
  - "Flowing prose required — explicit time markers ('In the first 3 seconds') are prohibited to keep Kling AI generation natural"
  - "Output expanded from 2-4 to 3-5 sentences to accommodate arc depth with character integration across three beats"

patterns-established:
  - "Similarity methods follow fail-open pattern: always returns False on DB error, caller decides enforcement"
  - "Prompt system prompt structured as: CHARACTER block -> RAW SCENE ARC -> RULES list -> return instruction"

requirements-completed:
  - SCN-13-03
  - SCN-13-05

# Metrics
duration: 7min
completed: 2026-03-30
---

# Phase 13 Plan 02: Similarity Prompt Check + Arc-Preserving System Prompt Summary

**SimilarityService extended with is_too_similar_prompt() (check_prompt_similarity RPC, fail-open) and PromptGenerationService system prompt updated to preserve hook->climax->conclusion arc across all three narrative beats.**

## Performance

- **Duration:** 7 min
- **Started:** 2026-03-30T04:15:49Z
- **Completed:** 2026-03-30T04:22:37Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- Added is_too_similar_prompt() to SimilarityService — mirrors is_too_similar_scene() exactly but calls check_prompt_similarity RPC for visual/stylistic anti-repetition at the Kling-prompt level (D-09)
- Added PROMPT_SIMILARITY_THRESHOLD = 0.78 and PROMPT_LOOKBACK_DAYS = 7 constants matching scene similarity defaults
- Replaced PromptGenerationService _SYSTEM_PROMPT with arc-aware version: GPT-4o now instructed to preserve hook->climax->conclusion structure, weave kitten into each beat, and use flowing prose without explicit time markers
- All 24 affected tests pass (9 anti-repetition + 15 prompt generation)

## Task Commits

Each task was committed atomically:

1. **Task 1: Add is_too_similar_prompt() to SimilarityService** - `a2faee2` (feat)
2. **Task 2: Update PromptGenerationService system prompt for arc preservation** - `8a8677d` (feat)

## Files Created/Modified
- `src/app/services/similarity.py` - Added PROMPT_SIMILARITY_THRESHOLD, PROMPT_LOOKBACK_DAYS constants and is_too_similar_prompt() method
- `src/app/services/prompt_generation.py` - Replaced _SYSTEM_PROMPT with arc-preserving version (hook->climax->conclusion, flowing prose, kitten in each beat)

## Decisions Made
- PROMPT_SIMILARITY_THRESHOLD set to 0.78 (same as scene threshold) — prompt embeddings capture visual/stylistic content at similar fidelity
- is_too_similar_prompt() always executes the check; enforcement is external (caller uses feature flag) — same separation of concerns as is_too_similar_scene()
- Arc preservation added because plan RESEARCH.md identified pitfall 2: PromptGenerationService could flatten a 3-beat scene description into a single static shot
- Output length expanded from 2-4 to 3-5 sentences to allow GPT-4o to describe all three arc beats while maintaining character integration

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None - verification commands ran cleanly on first attempt.

## User Setup Required
None - no external service configuration required. Migration 0012 (check_prompt_similarity SQL function) is handled in plan 13-01.

## Next Phase Readiness
- SimilarityService ready for pipeline wiring in 13-03 (call is_too_similar_prompt() after prompt embedding generated)
- PromptGenerationService arc-aware system prompt active for all subsequent video generation
- 13-03 can wire is_too_similar_prompt() into daily_pipeline.py following same scene check pattern

---
*Phase: 13-kitten-scenario-video-generation-hook-climax-conclusion-stories*
*Completed: 2026-03-30*
