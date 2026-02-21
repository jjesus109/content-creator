---
phase: 03-video-production
plan: "02"
subsystem: api
tags: [heygen, supabase-storage, requests, video, avatar, background-rotation]

# Dependency graph
requires:
  - phase: 03-video-production
    plan: "01"
    provides: HeyGen Settings fields (heygen_api_key, heygen_avatar_id, heygen_voice_id, heygen_webhook_url, heygen_dark_backgrounds) and video_status/background_url columns in content_history

provides:
  - HeyGenService.submit() building HeyGen v2 payload with portrait dimensions (1080x1920) and callback_url, returning video_id
  - pick_background_url() enforcing no-consecutive-repeat from HEYGEN_DARK_BACKGROUNDS pool
  - VideoStorageService.upload() uploading processed MP4 bytes to Supabase Storage 'videos' bucket with upsert, returning stable public URL

affects:
  - 03-03-audio-processing (needs VideoStorageService.upload() to persist final audio-mixed video)
  - 03-05-webhook (calls HeyGenService indirectly; uses video_id from submit())
  - 03-06-orchestration (calls HeyGenService.submit() and pick_background_url(); persists video_id and background_url)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - Synchronous requests library (not httpx async) — APScheduler ThreadPoolExecutor has no event loop
    - Optional supabase client injection in __init__ for testability (mirrors SimilarityService pattern from Phase 2)
    - upsert='true' as string, not bool — Supabase Python client requirement for file_options

key-files:
  created:
    - src/app/services/heygen.py
    - src/app/services/video_storage.py
  modified: []

key-decisions:
  - "Synchronous requests used for HeyGen HTTP call — httpx async incompatible with APScheduler ThreadPoolExecutor (no event loop)"
  - "pick_background_url falls back to full pool if filtered pool is empty — defensive against single-URL edge case"
  - "VideoStorageService accepts optional supabase client in __init__ for testability without live DB"
  - "upsert='true' as string in file_options — Supabase Python client expects string, not bool"
  - "cache-control=31536000 (1 year) on uploaded videos — content is permanent once approved"
  - "File path convention videos/YYYY-MM-DD.mp4 is locked — changing requires migrating existing URLs"

patterns-established:
  - "Service classes are stateless and dependency-injectable — no orchestration logic, no DB writes (callers handle persistence)"
  - "Module-level constants (HEYGEN_GENERATE_URL, VIDEO_BUCKET) for URL/bucket name references"

requirements-completed: [VIDP-01, VIDP-02, VIDP-04]

# Metrics
duration: 2min
completed: 2026-02-21
---

# Phase 3 Plan 02: HeyGen Service and Video Storage Summary

**HeyGenService submitting portrait-format avatar renders to HeyGen v2 API with no-consecutive-repeat background rotation, and VideoStorageService uploading processed MP4 bytes to Supabase Storage with stable public URL via upsert**

## Performance

- **Duration:** 2 min
- **Started:** 2026-02-21T06:35:12Z
- **Completed:** 2026-02-21T06:36:48Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Created `src/app/services/heygen.py` with `HeyGenService.submit()` building the correct HeyGen v2 payload (portrait 1080x1920 dimensions, avatar, voice, image background, callback_url) using synchronous `requests` for APScheduler thread pool compatibility
- Created `pick_background_url()` helper that reads the comma-separated `HEYGEN_DARK_BACKGROUNDS` pool, excludes the last-used URL for no-consecutive-repeat enforcement, and falls back to the full pool on single-URL edge case
- Created `src/app/services/video_storage.py` with `VideoStorageService.upload()` uploading bytes to Supabase Storage 'videos' bucket as `videos/YYYY-MM-DD.mp4` with upsert (string "true"), returning the stable public URL

## Task Commits

Each task was committed atomically:

1. **Task 1: HeyGenService — submit and background selector** - `225370a` (feat)
2. **Task 2: VideoStorageService — Supabase Storage upload with stable public URL** - `cbc666e` (feat)

## Files Created/Modified

- `src/app/services/heygen.py` - HeyGenService and pick_background_url(); HEYGEN_GENERATE_URL constant; synchronous requests; no module-level network calls
- `src/app/services/video_storage.py` - VideoStorageService with upload(); VIDEO_BUCKET constant; optional supabase injection; upsert as string

## Decisions Made

- Synchronous `requests` used instead of `httpx` async — APScheduler ThreadPoolExecutor runs outside any event loop; async HTTP would require event loop management
- `pick_background_url()` returns from full pool as fallback if filtered pool becomes empty — defensive against misconfiguration edge cases while preserving no-repeat intent
- `upsert="true"` as string in `file_options` — Supabase Python client requires string value, not Python bool
- `cache-control: 31536000` (1 year) on uploaded videos — once a video is approved and published, the URL is permanent; long cache improves CDN performance
- File path `videos/YYYY-MM-DD.mp4` locked as naming convention — documented in docstring to prevent silent breakage if convention drifts

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no new external service configuration required beyond what was documented in 03-01.

Pre-flight reminder (from 03-01): The `videos` Supabase Storage bucket MUST be set to PUBLIC before `VideoStorageService.upload()` can return accessible public URLs. This is noted in the `video_storage.py` module docstring.

## Next Phase Readiness

- Both service classes importable without live credentials; no module-level network calls
- 03-03 (audio processing) can now call `VideoStorageService.upload()` to persist the audio-mixed output
- 03-06 (orchestration) can call `HeyGenService.submit()` and `pick_background_url()` to kick off renders
- Blocker reminder: HeyGen API v2 endpoint structure is MEDIUM confidence — test with real API key before first live render

## Self-Check: PASSED

- FOUND: src/app/services/heygen.py
- FOUND: src/app/services/video_storage.py
- FOUND: .planning/phases/03-video-production/03-02-SUMMARY.md
- FOUND commit 225370a: feat(03-02): implement HeyGenService and pick_background_url
- FOUND commit cbc666e: feat(03-02): implement VideoStorageService with Supabase Storage upload

---
*Phase: 03-video-production*
*Completed: 2026-02-21*
