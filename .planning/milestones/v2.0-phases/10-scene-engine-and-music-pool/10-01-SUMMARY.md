---
phase: 10-scene-engine-and-music-pool
plan: 01
subsystem: database
tags: [postgresql, pgvector, migrations, pytest, csv, scene-engine, music-pool]

# Dependency graph
requires:
  - phase: 09-kling-video-generation
    provides: music_pool stub table (created in 0008), content_history with kling_job_id
provides:
  - migrations/0009_phase10_schema.sql — Phase 10 DB schema with scene_embedding, check_scene_similarity, scene_combo, artist columns
  - tests/conftest.py — shared Phase 10 fixtures (mock_scene_library, mock_music_pool, mock_supabase, mock_openai_client)
  - 7 Wave 0 test stub files covering SCN-01 through SCN-05, MUS-01 through MUS-03
  - src/app/data/music_seed.csv — 10-row representative music pool seed template
affects:
  - 10-02 (SceneEngine implementation uses scene_embedding column and check_scene_similarity function)
  - 10-03 (anti-repetition uses check_scene_similarity and scene_combo on rejection_constraints)
  - 10-04 (MusicMatcher uses music_pool with artist column)
  - 10-05 (pipeline wiring uses all columns from 0009)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - check_scene_similarity mirrors check_script_similarity pattern from 0002 (same pgvector <=> operator, same parameter names)
    - Wave 0 scaffold pattern: importable stub files with pytest.mark.skip for DB-dependent tests, fixture-based tests for data validation

key-files:
  created:
    - migrations/0009_phase10_schema.sql
    - tests/conftest.py
    - tests/test_music_pool.py
    - tests/test_scene_engine.py
    - tests/test_seasonal_calendar.py
    - tests/test_anti_repetition.py
    - tests/test_music_matcher.py
    - tests/test_caption_generator.py
    - tests/test_pipeline_wiring.py
    - src/app/data/music_seed.csv
  modified: []

key-decisions:
  - "scene_embedding stored on content_history (not separate table) — atomic updates, no join complexity; existing embedding column (script) preserved unchanged"
  - "check_scene_similarity defaults: threshold=0.78 (mid-range of 75-80% research), lookback=7 days (vs 90 days for script similarity)"
  - "artist column added to music_pool via ALTER TABLE in 0009 (was missing from Phase 9 stub in 0008)"

patterns-established:
  - "Wave 0 scaffold: test stub files are importable, fixture-validation tests are non-skipped, DB-dependent tests use pytest.mark.skip"
  - "SQL function pattern: check_scene_similarity mirrors check_script_similarity exactly in structure, different parameters reflect scene-specific calibration"

requirements-completed: [MUS-01, MUS-03]

# Metrics
duration: 3min
completed: 2026-03-20
---

# Phase 10 Plan 01: DB Schema Migration and Wave 0 Test Scaffold Summary

**Migration 0009 with scene_embedding vector(1536), check_scene_similarity pgvector function, and 7 Wave 0 test stub files unblocking parallel Wave 2 execution**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-20T03:48:44Z
- **Completed:** 2026-03-20T03:51:50Z
- **Tasks:** 2
- **Files modified:** 10 created

## Accomplishments
- Migration 0009 adds scene_embedding, scene_prompt, caption, music_track_id to content_history; artist to music_pool; scene_combo + updated CHECK constraint to rejection_constraints; check_scene_similarity SQL function
- 7 Wave 0 test stub files importable and passing (7 passed, 21 skipped); full test suite 110 passed, 23 skipped
- tests/conftest.py with 4 shared fixtures (mock_scene_library, mock_music_pool, mock_supabase, mock_openai_client)
- music_seed.csv with 10 representative rows covering all 4 moods and mixed platform license flags

## Task Commits

Each task was committed atomically:

1. **Task 1: Migration 0009 — Phase 10 schema additions** - `78bb447` (feat)
2. **Task 2: Wave 0 test scaffold + music seed CSV** - `ecb8ba2` (feat)

## Files Created/Modified
- `migrations/0009_phase10_schema.sql` - Phase 10 DB schema: scene_embedding, scene_prompt, caption, music_track_id, artist, scene_combo, check_scene_similarity function
- `tests/conftest.py` - Shared Phase 10 fixtures: SAMPLE_SCENE_LIBRARY, SAMPLE_MUSIC_POOL, mock_supabase, mock_openai_client
- `tests/test_music_pool.py` - MUS-01 and MUS-03 test stubs; 4 non-skipped fixture validation tests passing
- `tests/test_scene_engine.py` - SCN-01 test stubs; 2 non-skipped structure tests passing
- `tests/test_seasonal_calendar.py` - SCN-02 stubs (all skipped, implement in plan 02)
- `tests/test_anti_repetition.py` - SCN-03 and SCN-04 stubs (all skipped, implement in plan 03)
- `tests/test_music_matcher.py` - MUS-02 stubs (all skipped, implement in plan 04)
- `tests/test_caption_generator.py` - SCN-05 stubs; 1 non-skipped word count validation passing
- `tests/test_pipeline_wiring.py` - End-to-end integration stubs (all skipped, implement in plan 05)
- `src/app/data/music_seed.csv` - 10-row music pool seed template (file_url placeholders require replacement with actual CDN URLs before production)

## Decisions Made
- scene_embedding stored directly on content_history (not a separate table) — follows CONTEXT.md recommendation for atomic updates and reduced join complexity
- check_scene_similarity threshold defaults: 0.78 (mid-range of 75-80% research estimate) and 7-day lookback (vs 90-day for script similarity)
- artist column added to music_pool via ADD COLUMN IF NOT EXISTS in 0009 (was missing from Phase 9 stub in 0008_v2_schema.sql)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

**Migration 0009 must be applied to Supabase DB before Phase 10 plans 02-05 execute.**

The pgvector extension must be enabled in the Supabase project (it was required by Phase 2 for check_script_similarity — it should already be enabled). If not: `CREATE EXTENSION IF NOT EXISTS vector SCHEMA extensions;`

Apply: run migration file `migrations/0009_phase10_schema.sql` in Supabase SQL editor.

## Next Phase Readiness

- Migration 0009 is the foundation for all Wave 2 plans (10-02 through 10-05)
- Test stubs are in place; non-skipped fixture validation confirms data contracts are correct
- Wave 2 plans can now run: 10-02 (SceneEngine), 10-03 (anti-repetition), 10-04 (MusicMatcher) are independent of each other and can execute in parallel
- music_seed.csv file_url values are placeholder examples — must be replaced with actual Supabase Storage or licensed CDN URLs before production

## Self-Check: PASSED

- migrations/0009_phase10_schema.sql: FOUND
- tests/conftest.py: FOUND
- tests/test_music_pool.py: FOUND
- tests/test_scene_engine.py: FOUND
- tests/test_seasonal_calendar.py: FOUND
- tests/test_anti_repetition.py: FOUND
- tests/test_music_matcher.py: FOUND
- tests/test_caption_generator.py: FOUND
- tests/test_pipeline_wiring.py: FOUND
- src/app/data/music_seed.csv: FOUND
- 10-01-SUMMARY.md: FOUND
- commit 78bb447: FOUND
- commit ecb8ba2: FOUND

---
*Phase: 10-scene-engine-and-music-pool*
*Completed: 2026-03-20*
