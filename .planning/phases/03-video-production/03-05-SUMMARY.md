---
phase: 03-video-production
plan: "05"
subsystem: api
tags: [heygen, apscheduler, fastapi, webhook, ffmpeg, supabase, python]

# Dependency graph
requires:
  - phase: 03-02
    provides: HeyGenService.submit(), pick_background_url(), VideoStorageService.upload()
  - phase: 03-03
    provides: AudioProcessingService.process_video_audio()
  - phase: 03-04
    provides: webhooks router (routes/webhooks.py), video_poller.py, VideoStatus model

provides:
  - _process_completed_render(video_id, heygen_signed_url) in heygen.py — shared orchestrator for webhook and poller
  - _handle_render_failure(video_id, error_msg) in heygen.py — failure handler
  - daily_pipeline_job(scheduler) extended with HeyGen submission, background selection, poller registration
  - _save_to_content_history extended with heygen_job_id, video_status, background_url fields
  - POST /webhooks/heygen live in FastAPI app via include_router(webhooks_router)

affects: [04-approval-flow, phase-4, scheduler, webhook]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Shared orchestrator pattern: _process_completed_render called by both webhook handler and APScheduler poller; double-processing guard via conditional UPDATE"
    - "Closure injection: scheduler passed to daily_pipeline_job via lambda in registry.py, not global"
    - "Fail-soft HeyGen submission: pipeline saves script without video fields if HeyGen submit fails"
    - "Lazy local imports in _process_completed_render and _handle_render_failure to avoid circular imports"

key-files:
  created: []
  modified:
    - src/app/services/heygen.py
    - src/app/scheduler/jobs/daily_pipeline.py
    - src/app/scheduler/registry.py
    - src/app/main.py

key-decisions:
  - "double-processing guard covers pending_render, pending_render_retry, AND rendering — the in_() filter atomically claims processing; zero rows updated means another caller already owns it"
  - "stable Supabase Storage URL written to video_url, never the HeyGen signed URL (which expires)"
  - "scheduler closure in registry.py lambda — daily_pipeline_job cannot use request.app.state (no FastAPI Request in APScheduler thread)"
  - "HeyGen submission fail-soft: script saved to DB without video fields rather than aborting pipeline"

patterns-established:
  - "Shared orchestrator: single function handles post-render processing regardless of how completion was detected (webhook vs. poller)"
  - "Closure scheduler injection: all jobs needing scheduler access receive it at registration time via lambda, not via global"

requirements-completed: [VIDP-01, VIDP-02, VIDP-03, VIDP-04]

# Metrics
duration: 2min
completed: 2026-02-21
---

# Phase 3 Plan 05: Phase 3 Integration Summary

**Phase 3 wiring complete: _process_completed_render orchestrator + HeyGen submission in daily pipeline + /webhooks/heygen live — full video production flow operational end-to-end**

## Performance

- **Duration:** 2 min
- **Started:** 2026-02-21T06:47:42Z
- **Completed:** 2026-02-21T06:50:10Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- Added `_process_completed_render` to heygen.py with atomic double-processing guard covering all three pre-processing statuses (pending_render, pending_render_retry, rendering); orchestrates ffmpeg audio processing, Supabase upload, DB update, and Telegram alert
- Added `_handle_render_failure` to heygen.py for marking failed status and alerting creator
- Extended `daily_pipeline_job` to accept a `scheduler` parameter (passed via closure from registry.py), pick background URL, submit to HeyGen, save heygen_job_id+video_status+background_url to DB, and register the APScheduler poller — then exit immediately without blocking
- Registered `webhooks_router` in main.py so POST /webhooks/heygen is reachable in the live FastAPI app

## Task Commits

Each task was committed atomically:

1. **Task 1: Add _process_completed_render and _handle_render_failure to heygen.py** - `3297f85` (feat)
2. **Task 2: Extend daily_pipeline_job with HeyGen submission and wire webhook router** - `ae78e10` (feat)

**Plan metadata:** (docs commit follows)

## Files Created/Modified
- `src/app/services/heygen.py` - Added _process_completed_render and _handle_render_failure with module-level get_supabase/send_alert_sync imports; local AudioProcessingService/VideoStorageService/VideoStatus imports inside function bodies to prevent circular imports
- `src/app/scheduler/jobs/daily_pipeline.py` - daily_pipeline_job now accepts scheduler param; adds HeyGen submission block (background pick, submit, fail-soft fallback, poller registration); _save_to_content_history extended with optional heygen_job_id and background_url fields
- `src/app/scheduler/registry.py` - daily_pipeline_job registration wrapped in lambda to pass scheduler via closure
- `src/app/main.py` - Added webhooks_router import and app.include_router(webhooks_router)

## Decisions Made
- Double-processing guard's `in_()` filter includes `pending_render_retry` (in addition to `pending_render` and `rendering`) to cover videos that timed out once and were resubmitted via the retry path
- Stable Supabase Storage URL is the only value written to `content_history.video_url` — the HeyGen signed URL is ephemeral and never stored
- Scheduler passed via lambda closure in registry.py (not global variable) because APScheduler threads have no FastAPI Request context and cannot use `request.app.state.scheduler`
- HeyGen submission failure is fail-soft: script is saved without video fields and pipeline returns normally; creator is alerted via Telegram

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Phase 3 video production pipeline is fully operational end-to-end: script generation -> HeyGen submission -> webhook/poller completion detection -> ffmpeg processing -> Supabase upload -> ready status
- Phase 4 (Approval Flow) can now read `content_history` rows with `video_status='ready'` and `video_url` populated for creator approval and publishing
- All VIDP requirements (VIDP-01 through VIDP-04) are complete

---
*Phase: 03-video-production*
*Completed: 2026-02-21*
