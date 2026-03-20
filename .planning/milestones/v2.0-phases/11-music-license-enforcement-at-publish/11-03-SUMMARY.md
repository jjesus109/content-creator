---
phase: 11-music-license-enforcement-at-publish
plan: "03"
subsystem: database
tags: [supabase, music-pool, platform-facebook, license-gate, migration, pytest]

# Dependency graph
requires:
  - phase: 11-01
    provides: _check_music_license_cleared() gate function with platform_facebook reference
  - phase: 11-02
    provides: integration tests validating publish_to_platform_job() gate wiring
provides:
  - migration 0011 adding platform_facebook BOOLEAN NOT NULL DEFAULT FALSE to music_pool
  - VALID_PLATFORMS updated to include "facebook" in music_matcher.py
  - conftest.py fixtures updated to 4-platform schema (SAMPLE_MUSIC_POOL x3, SAMPLE_EXPIRED_TRACK)
  - 2 new targeted tests (test_license_gate_facebook_cleared, test_license_gate_facebook_blocked)
affects: [publish pipeline, music_matcher.py callers, future platform additions]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - ADD COLUMN IF NOT EXISTS pattern for idempotent Supabase migrations
    - VALID_PLATFORMS set as single source of truth for platform guard in MusicMatcher

key-files:
  created:
    - migrations/0011_add_platform_facebook.sql
  modified:
    - tests/conftest.py
    - src/app/services/music_matcher.py
    - tests/test_music_license_gate.py
    - tests/test_music_matcher.py

key-decisions:
  - "[11-03]: VALID_PLATFORMS updated to include facebook — keeps MusicMatcher aligned with 4-platform publish pipeline"
  - "[11-03]: migration 0011 uses ADD COLUMN IF NOT EXISTS — idempotent, safe to apply to Supabase multiple times"
  - "[11-03]: test_pick_track_raises_on_invalid_platform updated to use snapchat as invalid platform (facebook now valid)"

patterns-established:
  - "Platform addition pattern: add to VALID_PLATFORMS + add migration column + add fixture field + add gate tests"

requirements-completed: [PUB-01]

# Metrics
duration: 3min
completed: 2026-03-20
---

# Phase 11 Plan 03: Gap Closure — platform_facebook Schema Summary

**ALTER TABLE adds missing platform_facebook column, VALID_PLATFORMS updated, 10 license gate tests pass — facebook publishes no longer incorrectly blocked**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-20T14:52:19Z
- **Completed:** 2026-03-20T14:55:00Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments

- Created `migrations/0011_add_platform_facebook.sql` with idempotent `ALTER TABLE music_pool ADD COLUMN IF NOT EXISTS platform_facebook BOOLEAN NOT NULL DEFAULT FALSE`
- Updated `VALID_PLATFORMS` in `music_matcher.py` to include `"facebook"`, aligning the matcher with the 4-platform publish pipeline
- Updated all shared test fixtures in `conftest.py` to include `platform_facebook: True` in all 4 track dicts (3 in SAMPLE_MUSIC_POOL, 1 in SAMPLE_EXPIRED_TRACK)
- Added `test_license_gate_facebook_cleared` and `test_license_gate_facebook_blocked` to `test_music_license_gate.py` — 10 tests total, all pass
- Full test suite: 159 passed, 5 skipped — no regressions

## Task Commits

Each task was committed atomically:

1. **Task 1: Migration 0011 — add platform_facebook column to music_pool** - `92dd5fe` (feat)
2. **Task 2: Update fixtures and VALID_PLATFORMS; add facebook gate tests** - `b536304` (feat)

**Plan metadata:** (docs commit — see final_commit step)

## Files Created/Modified

- `migrations/0011_add_platform_facebook.sql` - ALTER TABLE migration adding platform_facebook BOOLEAN NOT NULL DEFAULT FALSE to music_pool
- `tests/conftest.py` - SAMPLE_MUSIC_POOL (3 dicts) and SAMPLE_EXPIRED_TRACK now include platform_facebook: True
- `src/app/services/music_matcher.py` - VALID_PLATFORMS = {"tiktok", "youtube", "instagram", "facebook"}
- `tests/test_music_license_gate.py` - Added test_license_gate_facebook_cleared and test_license_gate_facebook_blocked (10 tests total)
- `tests/test_music_matcher.py` - Updated invalid platform test to use "snapchat" instead of "facebook" (auto-fix)

## Decisions Made

- `VALID_PLATFORMS` updated to include `facebook` — single source of truth for platform guard in MusicMatcher; keeping it in sync with the 4-platform publish pipeline prevents future "no tracks found" errors for facebook publishes.
- Migration uses `ADD COLUMN IF NOT EXISTS` — idempotent pattern, safe to re-apply to Supabase without errors.
- `test_pick_track_raises_on_invalid_platform` updated to use `"snapchat"` — `"facebook"` was the test's example of an invalid platform, but it is now valid. Using a genuinely invalid platform name keeps the test semantically correct.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Updated test_pick_track_raises_on_invalid_platform to use "snapchat" as invalid platform**
- **Found during:** Task 2 (update fixtures and VALID_PLATFORMS; add facebook gate tests)
- **Issue:** The test used `"facebook"` as an example of an invalid platform. After adding `"facebook"` to `VALID_PLATFORMS`, the test was no longer exercising the invalid-platform guard — it raised a "no cleared tracks" error instead of "invalid platform".
- **Fix:** Changed `target_platform="facebook"` to `target_platform="snapchat"` in the test — snapchat is genuinely not in VALID_PLATFORMS and keeps the test semantically correct.
- **Files modified:** `tests/test_music_matcher.py`
- **Verification:** `pytest tests/ -q` → 159 passed, 5 skipped (no regressions)
- **Committed in:** `b536304` (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - bug in test expectation made stale by intentional code change)
**Impact on plan:** Auto-fix was necessary for test suite correctness. No scope creep.

## Issues Encountered

None — plan executed with one auto-fix for a test that became stale due to VALID_PLATFORMS update.

## User Setup Required

**One manual step required before next facebook publish fires in production:**

Apply migration 0011 to the live Supabase database via the Supabase SQL editor:

```sql
ALTER TABLE music_pool
    ADD COLUMN IF NOT EXISTS platform_facebook BOOLEAN NOT NULL DEFAULT FALSE;
```

After applying, existing tracks will have `platform_facebook = FALSE` (not cleared). Update specific track rows to `platform_facebook = TRUE` for tracks with valid facebook licenses before facebook publishes are enabled.

## Next Phase Readiness

- Phase 11 gap is closed: `_check_music_license_cleared()` will correctly allow or block facebook publishes once migration 0011 is applied to Supabase
- ROADMAP Phase 11 success criterion #2 is now achievable: "A video with a fully licensed track publishes to all four platforms without manual intervention"
- No further code work needed for Phase 11

---
*Phase: 11-music-license-enforcement-at-publish*
*Completed: 2026-03-20*
