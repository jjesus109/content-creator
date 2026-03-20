---
phase: 10-scene-engine-and-music-pool
plan: "04"
subsystem: music
tags: [supabase, music-pool, bpm, licensing, random-selection, mocking]

# Dependency graph
requires:
  - phase: 10-01
    provides: music_pool table schema with artist column (migration 0009), conftest.py SAMPLE_MUSIC_POOL fixture
provides:
  - MusicMatcher class with pick_track(mood, target_platform) -> dict
  - MOOD_BPM_MAP constant: playful 110-125, sleepy 70-80, curious 90-100
  - 11 passing tests covering MUS-02 and MUS-03 requirements
affects:
  - 10-05 (daily_pipeline.py wires SceneEngine.mood output to MusicMatcher.pick_track)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "License expiry filtered in-Python after DB fetch — avoids Supabase .or_() complexity with NULLable timestamps"
    - "Supabase mock via MagicMock chained returns — .table().select().eq().gte().lte().eq().execute().data"

key-files:
  created:
    - src/app/services/music_matcher.py
  modified:
    - tests/test_music_matcher.py
    - tests/test_music_pool.py

key-decisions:
  - "License expiry handled in-Python (not in Supabase query) — simpler than .or_() filter, correct given NULL=permanent semantics"
  - "MOOD_BPM_MAP hardcoded as module-level constant — not from config, these are stable content-strategy values"

patterns-established:
  - "TDD pattern: failing import test committed as RED, then implementation as GREEN"

requirements-completed: [MUS-02, MUS-03]

# Metrics
duration: 5min
completed: "2026-03-20"
---

# Phase 10 Plan 04: MusicMatcher Service Summary

**MusicMatcher service selecting mood-matched BPM-ranged license-cleared tracks from music_pool, with in-Python expiry filtering and random candidate selection**

## Performance

- **Duration:** 5 min
- **Started:** 2026-03-20T04:01:39Z
- **Completed:** 2026-03-20T04:06:10Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- MusicMatcher class built with pick_track(mood, target_platform) matching MOOD_BPM_MAP BPM ranges against music_pool DB
- License expiry filtering applied in-Python post-fetch (tracks with past license_expires_at excluded, NULL treated as permanent)
- 11 test_music_matcher.py tests replace 4 stubs — full coverage of BPM constants, random selection, empty pool, invalid inputs, expiry filtering
- test_music_pool.py gains test_platform_flags_can_differ_per_platform; 5 fixture tests passing, 3 DB-dependent correctly skipped

## Task Commits

Each task was committed atomically:

1. **Task 1 RED: Failing tests** - `6d051f5` (test)
2. **Task 1 GREEN: MusicMatcher service** - `5fc7045` (feat)
3. **Task 2: Activate music pool tests** - `9e56c33` (feat)

_Note: TDD tasks have multiple commits (test RED → feat GREEN)_

## Files Created/Modified

- `src/app/services/music_matcher.py` - MusicMatcher class: pick_track(), MOOD_BPM_MAP, license expiry filter, random selection
- `tests/test_music_matcher.py` - 11 real tests replacing 4 skip stubs (MUS-02 + MUS-03)
- `tests/test_music_pool.py` - Added test_platform_flags_can_differ_per_platform; updated skip reasons

## Decisions Made

- License expiry handled in-Python after DB fetch rather than in Supabase query. The Supabase `.or_()` filter for `NULL OR > now()` is awkward with the client library; in-Python filtering is simpler, testable with plain dicts, and correct given that NULL means permanent (no expiry).
- MOOD_BPM_MAP is a module-level constant (not config-driven). These are stable content-strategy values locked at research time. Reading from config would add runtime complexity for values that should never change without deliberate code review.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- MusicMatcher ready for integration in Plan 05 (daily_pipeline.py)
- Plan 05 wires SceneEngine.pick_scene() mood output directly to MusicMatcher.pick_track(mood, platform)
- No blockers

---
*Phase: 10-scene-engine-and-music-pool*
*Completed: 2026-03-20*
