---
phase: 09-mexican-animated-cat-video-format
plan: 01
subsystem: database
tags: [postgres, migrations, pydantic-settings, enums, kling, fal-ai, circuit-breaker]

# Dependency graph
requires: []
provides:
  - DB migration 0008 with kling_job_id column and updated video_status CHECK constraint
  - kling_circuit_breaker_state singleton table seeded with id=1
  - music_pool stub table for Phase 10
  - app_settings KV table seeded with character_bible_version=1
  - Settings.fal_api_key and Settings.kling_model_version fields
  - VideoStatus.KLING_PENDING, KLING_PENDING_RETRY, PUBLISHED enum values
affects:
  - 09-02 (KlingService uses fal_api_key + kling_model_version + KLING_PENDING status)
  - 09-03 (circuit breaker reads/writes kling_circuit_breaker_state)
  - 09-04 (poller uses KLING_PENDING_RETRY; publisher writes PUBLISHED)
  - 10-01 (music_pool table schema already in place)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "SQL migration style: IF NOT EXISTS + ON CONFLICT DO NOTHING for idempotency"
    - "Settings fields: explicit fal_api_key field even though fal_client auto-reads env — makes dependency visible at startup validation"

key-files:
  created:
    - migrations/0008_v2_schema.sql
  modified:
    - src/app/settings.py
    - src/app/models/video.py
    - .env.example

key-decisions:
  - "kling_circuit_breaker_state kept separate from circuit_breaker_state — different failure models (rate-based vs cost+count-based)"
  - "fal_api_key added to Settings even though fal_client reads FAL_API_KEY automatically — ensures startup validation failure if key missing"
  - "music_pool and app_settings created as Phase 10 stubs to keep all v2 schema in one migration"

patterns-established:
  - "Pattern: Singleton table with CHECK (id = 1) constraint for circuit breaker state"
  - "Pattern: Migration idempotency via IF NOT EXISTS and ON CONFLICT DO NOTHING on all DDL"

requirements-completed: [VID-01, VID-02, VID-03]

# Metrics
duration: 2min
completed: 2026-03-19
---

# Phase 9 Plan 01: DB Foundation + Settings Summary

**Postgres migration 0008 adding kling_job_id column, kling_circuit_breaker_state singleton table, music_pool and app_settings stubs, plus Settings.fal_api_key and VideoStatus Kling lifecycle values**

## Performance

- **Duration:** ~2 min
- **Started:** 2026-03-19T14:00:28Z
- **Completed:** 2026-03-19T14:02:29Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- Created migration 0008 with all Phase 9 schema changes in a single idempotent file
- Extended VideoStatus enum with KLING_PENDING, KLING_PENDING_RETRY, PUBLISHED (9 total values, all preserved from v1.0)
- Added fal_api_key and kling_model_version to Settings with startup-time validation
- Seeded kling_circuit_breaker_state singleton (id=1) and app_settings character_bible_version=1

## Task Commits

Each task was committed atomically:

1. **Task 1: DB migration 0008** - `6a0aee3` (feat)
2. **Task 2: Extend Settings + VideoStatus for Kling/fal.ai** - `4d00c51` (feat)

## Files Created/Modified

- `migrations/0008_v2_schema.sql` - Complete Phase 9 schema: kling_job_id column, updated video_status CHECK, kling_circuit_breaker_state table, music_pool stub, app_settings KV table
- `src/app/settings.py` - Added fal_api_key: str and kling_model_version: str fields in Kling block after heygen_gesture_prompt
- `src/app/models/video.py` - Added KLING_PENDING, KLING_PENDING_RETRY, PUBLISHED to VideoStatus enum; updated docstring
- `.env.example` - Added FAL_API_KEY and KLING_MODEL_VERSION entries

## Decisions Made

- Kept kling_circuit_breaker_state as a separate table from circuit_breaker_state because the two circuit breakers have different failure models (Kling is rate/failure-rate based; HeyGen is cost+count based).
- Added fal_api_key explicitly to Settings even though fal_client auto-reads FAL_API_KEY from the environment — forces startup validation so the app fails fast if the key is missing before any Kling requests.

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

Two new environment variables must be added before Phase 9 runs:

- `FAL_API_KEY` — fal.ai API key from fal.ai dashboard → API keys
- `KLING_MODEL_VERSION` — optional override (default: `fal-ai/kling-video/v3/standard/text-to-video`)

Migration `migrations/0008_v2_schema.sql` must be applied to the Supabase database via the Supabase SQL editor or migration tooling before Phase 9 plans 02-04 execute.

## Next Phase Readiness

- Plan 09-02 (KlingService) can proceed — FAL_API_KEY settings field present, KLING_PENDING status available, kling_job_id column ready in DB
- Plan 09-03 (circuit breaker) can proceed — kling_circuit_breaker_state table and singleton row in place
- Plan 09-04 (poller/publisher) can proceed — KLING_PENDING_RETRY and PUBLISHED status values available

---
*Phase: 09-mexican-animated-cat-video-format*
*Completed: 2026-03-19*
