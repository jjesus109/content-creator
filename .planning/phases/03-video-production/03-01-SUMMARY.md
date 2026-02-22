---
phase: 03-video-production
plan: "01"
subsystem: infra
tags: [heygen, ffmpeg, supabase, postgresql, pydantic-settings, migration]

# Dependency graph
requires:
  - phase: 02-script-generation
    provides: content_history table base schema and Settings class structure this plan extends

provides:
  - SQL migration adding heygen_job_id, video_url, video_status, background_url columns to content_history
  - Settings class with all 7 HeyGen/audio fields required by downstream services
  - ffmpeg binary available in runtime Docker image

affects:
  - 03-02-heygen-service (needs heygen_* Settings and video columns)
  - 03-03-audio-processing (needs ffmpeg and heygen_ambient_music_urls)
  - 03-04-video-storage (needs video_url column and supabase settings)
  - 03-05-webhook (needs heygen_webhook_url, heygen_webhook_secret)
  - 03-06-orchestration (needs all video columns and full Settings)

# Tech tracking
tech-stack:
  added: [ffmpeg (system binary via apt-get)]
  patterns:
    - All Phase 3 secrets required (no defaults) — fail-fast at startup via Pydantic
    - pending_render_retry sentinel encodes retry-once logic in video_status without extra column
    - IF NOT EXISTS idempotency guard on SQL migration columns

key-files:
  created:
    - migrations/0003_video_columns.sql
  modified:
    - src/app/settings.py
    - Dockerfile

key-decisions:
  - "pending_render_retry is the video_status sentinel for retry-once logic — avoids adding a retry_count column"
  - "heygen_webhook_secret defaults to empty string to support HeyGen free plan (no signing secret provided); webhook handler skips HMAC validation when empty — intentional post-execution change"
  - "ffmpeg installed in final Docker stage only (not builder) — it is a runtime, not build, dependency"
  - "background_url stored in content_history to enable consecutive-background-repeat prevention"

patterns-established:
  - "Phase 3 settings follow Phase 2 pattern: all secrets required, no defaults, injected via Railway env vars"
  - "SQL migrations use IF NOT EXISTS for idempotency — safe to re-run on service restart"

requirements-completed: [VIDP-01, VIDP-02, VIDP-03, VIDP-04]

# Metrics
duration: 2min
completed: 2026-02-21
---

# Phase 3 Plan 01: Video Production Infrastructure Foundation Summary

**SQL migration with 4 video tracking columns (including retry sentinel), 7 HeyGen/audio Settings fields with fail-fast validation, and ffmpeg installed in the Docker runtime stage**

## Performance

- **Duration:** 2 min
- **Started:** 2026-02-21T06:31:21Z
- **Completed:** 2026-02-21T06:32:43Z
- **Tasks:** 3
- **Files modified:** 3

## Accomplishments

- Created `migrations/0003_video_columns.sql` adding heygen_job_id, video_url, video_status (with 6-value CHECK constraint), and background_url to content_history
- Extended `Settings` class with all 7 HeyGen fields (heygen_api_key, heygen_avatar_id, heygen_voice_id, heygen_webhook_url, heygen_webhook_secret, heygen_dark_backgrounds, heygen_ambient_music_urls) — all required, no defaults
- Added ffmpeg installation layer in the Dockerfile final runtime stage with --no-install-recommends and apt-list cleanup

## Task Commits

Each task was committed atomically:

1. **Task 1: Migration 0003 — add video columns to content_history** - `1ca6d8b` (feat)
2. **Task 2: Extend Settings with HeyGen and audio fields** - `6ca013f` (feat)
3. **Task 3: Install ffmpeg in Dockerfile final stage** - `ccbcf40` (feat)

## Files Created/Modified

- `migrations/0003_video_columns.sql` - Adds 4 columns to content_history for Phase 3 video render tracking; video_status constrained to 6 valid values including pending_render_retry sentinel
- `src/app/settings.py` - Extended with 7 HeyGen/audio required fields; all fail-fast on missing env vars
- `Dockerfile` - Final runtime stage installs ffmpeg for AudioProcessingService; builder stage unchanged

## Decisions Made

- `pending_render_retry` chosen as video_status sentinel value for retry-once logic — avoids adding a separate retry_count column while still enabling the poller to distinguish first timeout from second
- All 7 HeyGen fields are required with no defaults — Pydantic raises ValidationError at startup if any are absent, which is the intended fail-fast behavior
- ffmpeg placed in final stage only: it is a runtime dependency for audio mixing, not needed at build time

## Deviations from Plan

- **heygen_webhook_secret** — plan specified all 7 HeyGen fields required with no defaults. Post-execution, `heygen_webhook_secret` was given a default of `""` to support HeyGen free plan users who are not provided a signing secret. The webhook handler skips HMAC validation when the secret is empty and enforces it when set. This is intentional and preserves security for paid-plan users.

## Issues Encountered

None — migration file was partially pre-created from prior planning work; content matched the plan spec exactly and was committed as-is.

## User Setup Required

Before Phase 3 services can start, the following environment variables must be added to the Railway project (or local .env):

- `HEYGEN_API_KEY` — from HeyGen dashboard → Settings → API
- `HEYGEN_AVATAR_ID` — portrait-trained avatar ID (verify in HeyGen dashboard)
- `HEYGEN_VOICE_ID` — fixed voice ID for consistent brand voice
- `HEYGEN_WEBHOOK_URL` — public URL of /webhooks/heygen route on Railway
- `HEYGEN_WEBHOOK_SECRET` — HMAC-SHA256 signing secret from HeyGen webhook config
- `HEYGEN_DARK_BACKGROUNDS` — comma-separated Supabase Storage public URLs for dark cinematic backgrounds (min 2)
- `HEYGEN_AMBIENT_MUSIC_URLS` — comma-separated Supabase Storage public URLs for ambient music tracks (2-4 tracks)

## Next Phase Readiness

- Foundation complete: schema, settings, and ffmpeg all in place
- Plans 03-02 through 03-06 can proceed in their defined waves
- Blocker reminder: HeyGen API v2 endpoint structure is MEDIUM confidence — verify against live docs before implementing 03-02 HeyGenService

## Self-Check: PASSED

- FOUND: migrations/0003_video_columns.sql
- FOUND: src/app/settings.py
- FOUND: Dockerfile
- FOUND: .planning/phases/03-video-production/03-01-SUMMARY.md
- FOUND commit 1ca6d8b: feat(03-01): add video columns migration to content_history
- FOUND commit 6ca013f: feat(03-01): extend Settings with HeyGen and audio fields
- FOUND commit ccbcf40: feat(03-01): install ffmpeg in Dockerfile final stage

---
*Phase: 03-video-production*
*Completed: 2026-02-21*
