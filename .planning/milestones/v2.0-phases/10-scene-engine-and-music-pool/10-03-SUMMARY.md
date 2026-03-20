---
phase: 10-scene-engine-and-music-pool
plan: "03"
subsystem: api
tags: [similarity, anti-repetition, feature-flag, scene-engine, pgvector]

# Dependency graph
requires:
  - phase: 10-01
    provides: check_scene_similarity SQL function, SCENE_SIMILARITY_THRESHOLD=0.78 decision
  - phase: 10-02
    provides: store_scene_rejection() and load_active_scene_rejections() in SceneEngine
provides:
  - SimilarityService.is_too_similar_scene() method using check_scene_similarity RPC
  - SCENE_SIMILARITY_THRESHOLD=0.78 and SCENE_LOOKBACK_DAYS=7 constants
  - scene_anti_repetition_enabled: bool = False feature flag in Settings
  - 9 passing tests for SCN-03 (anti-repetition check) and SCN-04 (rejection feedback)
affects: [10-05, daily_pipeline]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Fail-open similarity check: DB errors return False (allow generation) not True (block)"
    - "Feature flag in Settings defaults to False (log-only) until empirical calibration complete"
    - "Mirror pattern: is_too_similar_scene() mirrors is_too_similar() with different RPC/defaults"

key-files:
  created: []
  modified:
    - src/app/services/similarity.py
    - src/app/settings.py
    - tests/test_anti_repetition.py

key-decisions:
  - "is_too_similar_scene() always executes check; caller (pipeline) decides whether to enforce based on feature flag — separation of concerns"
  - "scene_anti_repetition_enabled defaults to False (log-only mode) — enforcement deferred until empirical threshold calibration with dry-run script"

patterns-established:
  - "Feature flag naming: {feature}_enabled: bool = False in Settings (log-only until calibrated)"
  - "Scene similarity constants prefixed SCENE_ to distinguish from script similarity constants"

requirements-completed: [SCN-03, SCN-04]

# Metrics
duration: 8min
completed: 2026-03-19
---

# Phase 10 Plan 03: Anti-Repetition Scene Check Summary

**is_too_similar_scene() method with check_scene_similarity RPC, 0.78 threshold, 7-day lookback, and scene_anti_repetition_enabled feature flag in log-only mode**

## Performance

- **Duration:** 8 min
- **Started:** 2026-03-19T22:01:41Z
- **Completed:** 2026-03-19T22:09:25Z
- **Tasks:** 2 completed
- **Files modified:** 3

## Accomplishments
- Added `is_too_similar_scene()` to SimilarityService — mirrors `is_too_similar()` but calls `check_scene_similarity` RPC with 0.78 threshold and 7-day lookback
- Added `scene_anti_repetition_enabled: bool = False` to Settings — keeps enforcement in log-only mode until empirical calibration
- Replaced 4 skipped test stubs with 9 real tests covering both SCN-03 (similarity check) and SCN-04 (rejection feedback storage/load)

## Task Commits

Each task was committed atomically:

1. **Task 1: Add is_too_similar_scene() to SimilarityService + feature flag to Settings** - `4d26e1c` (feat)
2. **Task 2: Activate anti-repetition tests (SCN-03 + SCN-04)** - `0e30970` (test)

**Plan metadata:** (docs commit — see below)

## Files Created/Modified
- `src/app/services/similarity.py` - Added SCENE_SIMILARITY_THRESHOLD=0.78, SCENE_LOOKBACK_DAYS=7, and is_too_similar_scene() method
- `src/app/settings.py` - Added scene_anti_repetition_enabled: bool = False feature flag
- `tests/test_anti_repetition.py` - Replaced 4 skipped stubs with 9 real passing tests (SCN-03: 6 tests, SCN-04: 3 tests)

## Decisions Made
- `is_too_similar_scene()` always executes the check and returns the result — enforcement logic lives in daily_pipeline.py (Plan 05). This separates the similarity check from the enforcement decision, making the method easier to test and reuse.
- `scene_anti_repetition_enabled` defaults to False (log-only mode) — enforcement deferred until empirical threshold calibration with dry-run script validates 0.78 threshold on real video pairs.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

Pre-existing failure in `tests/test_music_matcher.py` (ModuleNotFoundError: app.services.music_matcher) — this module is implemented in Plan 04 and was already broken before this plan. Not a regression, not in scope. Full test suite excluding that file: 131 passed, 8 skipped.

## User Setup Required

None - no external service configuration required. Feature flag `SCENE_ANTI_REPETITION_ENABLED` can be set to `true` in Railway env vars when threshold calibration is complete.

## Next Phase Readiness

- Plan 05 executor can confirm: `uv run pytest tests/test_anti_repetition.py -v --tb=short` exits 0 with 9 passed, 0 skips
- Both SCN-03 (similarity check) and SCN-04 (rejection storage/load) are verified passing
- is_too_similar_scene() is ready for wiring into daily_pipeline.py in Plan 05
- store_scene_rejection() and load_active_scene_rejections() (from Plan 02) are verified by tests in this plan

---
*Phase: 10-scene-engine-and-music-pool*
*Completed: 2026-03-19*
