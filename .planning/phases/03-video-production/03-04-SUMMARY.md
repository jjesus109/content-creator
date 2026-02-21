---
phase: 03-video-production
plan: "04"
subsystem: api
tags: [heygen, webhook, hmac, apscheduler, polling, fastapi, pydantic]

# Dependency graph
requires:
  - phase: 03-video-production/03-01
    provides: Settings class with heygen_webhook_secret and heygen_api_key; pending_render_retry sentinel established; video_status CHECK constraint in migration 0003

provides:
  - VideoStatus enum (6 values including pending_render_retry sentinel) and HeyGenWebhookPayload Pydantic models in src/app/models/video.py
  - POST /webhooks/heygen FastAPI endpoint with HMAC-SHA256 validation, poller cancel-by-ID, thread executor offload
  - video_poller_job() 60s interval APScheduler job with retry-once logic and self-cancel
  - register_video_poller() callable for daily_pipeline_job to register pollers after HeyGen submission
  - _retry_or_fail() implements retry-once at 20 min timeout: resubmits on first, marks failed + alerts on second

affects:
  - 03-05-processing (_process_completed_render and _handle_render_failure must be implemented in app.services.heygen — called lazily from both webhook and poller)
  - 03-06-orchestration (register_video_poller must be called from daily_pipeline_job after HeyGen submission; router must be included in main.py)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - POLLER_JOB_ID_PREFIX pattern: predictable job ID "video_poller_{video_id}" enables webhook to cancel poller by ID without direct reference
    - Lazy import pattern: _process_completed_render imported inside handler body to avoid circular import at module level
    - video_status as retry sentinel: pending_render_retry distinguishes first from second timeout without extra column
    - Timeout guard runs before HTTP poll: elapsed check happens before every requests.get call

key-files:
  created:
    - src/app/models/video.py
    - src/app/routes/webhooks.py
    - src/app/scheduler/jobs/video_poller.py
  modified: []

key-decisions:
  - "HMAC-SHA256 validated via hmac.compare_digest (timing-safe) — prevents timing oracle attacks on signature verification"
  - "Webhook returns 200 immediately and offloads to thread executor — HeyGen does not retry non-200 responses"
  - "Predictable job ID 'video_poller_{video_id}' allows webhook to cancel by ID via remove_job without shared state"
  - "Lazy import of _process_completed_render inside handler body avoids circular import at module load time"
  - "video_status sentinel (pending_render_retry) used to distinguish first vs second timeout — locked decision from plan 03-01"

patterns-established:
  - "Poller job ID prefix 'video_poller_' is shared constant between webhooks.py and video_poller.py — both files define POLLER_JOB_ID_PREFIX for independence"
  - "Lazy service imports inside handler bodies: app.services.heygen imported at call site, not module top"

requirements-completed: [VIDP-01]

# Metrics
duration: 2min
completed: 2026-02-21
---

# Phase 3 Plan 04: Video Production Completion Detection Summary

**HMAC-verified webhook endpoint and 60s APScheduler poller with retry-once timeout logic using pending_render_retry sentinel to detect HeyGen render completion via dual paths**

## Performance

- **Duration:** 2 min
- **Started:** 2026-02-21T06:42:46Z
- **Completed:** 2026-02-21T06:45:03Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- Created `src/app/models/video.py` with VideoStatus enum (6 values including pending_render_retry sentinel) and HeyGenWebhookPayload Pydantic models — shared imports for both webhook and poller without circular dependencies
- Created `src/app/routes/webhooks.py` with POST /webhooks/heygen endpoint: timing-safe HMAC-SHA256 validation, synchronous-200-return with thread executor offload, and poller cancel via remove_job(video_poller_{video_id})
- Created `src/app/scheduler/jobs/video_poller.py` with 60s interval job, _retry_or_fail() retry-once at 20-minute timeout (first timeout: resubmit via HeyGenService.submit() + update heygen_job_id + set pending_render_retry; second timeout: mark failed + Telegram alert), and register_video_poller() for pipeline integration

## Task Commits

Each task was committed atomically:

1. **Task 1: VideoStatus enum and HeyGenWebhookPayload Pydantic models** - `b70064f` (feat)
2. **Task 2: FastAPI webhook endpoint + APScheduler video poller with retry-once logic** - `066aea9` (feat)

## Files Created/Modified

- `src/app/models/video.py` - VideoStatus enum (pending_render, pending_render_retry, rendering, processing, ready, failed) and HeyGenWebhookEventData/HeyGenWebhookPayload Pydantic models; no service imports to avoid circular dependency
- `src/app/routes/webhooks.py` - POST /webhooks/heygen with HMAC-SHA256 validation (compare_digest), poller cancel via remove_job(video_poller_{video_id}), processing offloaded to thread executor via run_in_executor
- `src/app/scheduler/jobs/video_poller.py` - video_poller_job() polls HeyGen status API every 60s; _retry_or_fail() implements retry-once with video_status sentinel; register_video_poller() registers predictable-ID job; _cancel_self() graceful removal

## Decisions Made

- HMAC-SHA256 verified using `hmac.compare_digest` for timing-safe comparison — prevents timing oracle attacks on signature validation
- Webhook handler returns 200 immediately and offloads all I/O to thread executor — HeyGen treats any non-200 as failure and does not retry; blocking the async handler would risk timeout
- `POLLER_JOB_ID_PREFIX = "video_poller_"` defined as constant in both webhooks.py and video_poller.py — webhook can cancel by predictable ID without shared state or direct reference to poller
- All service imports from `app.services.heygen` are lazy (inside handler bodies) to avoid circular imports at module load time — consistent with Phase 1-02 decision pattern
- `pending_render_retry` video_status sentinel distinguishes first timeout (retry eligible) from second (fail and alert) — avoids a retry_count column; locked decision carried from plan 03-01

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

Python binary is `python3` not `python` in this environment — discovered during Task 1 verification. Used `.venv/bin/python` to verify against the venv-installed pydantic. Not a code issue.

## User Setup Required

None - no external service configuration required beyond what was established in plan 03-01.

## Next Phase Readiness

- Detection infrastructure complete: both webhook path and poller fallback are in place
- Plan 03-05 must implement `_process_completed_render(video_id, signed_url)` and `_handle_render_failure(video_id, error_msg)` in `src/app/services/heygen.py` — these are called lazily by both webhook and poller; they do not yet exist and imports will fail at runtime until plan 03-05 is complete
- Plan 03-06 (orchestration) must: (1) call `register_video_poller(scheduler, heygen_job_id)` from daily_pipeline_job after HeyGen submission; (2) include the webhooks router in main.py via `app.include_router(router)` from `app.routes.webhooks`
- double-processing guard (`_process_completed_render` checks video_status before proceeding) is implemented in plan 03-05 per the plan spec

## Self-Check: PASSED

- FOUND: src/app/models/video.py
- FOUND: src/app/routes/webhooks.py
- FOUND: src/app/scheduler/jobs/video_poller.py
- FOUND commit b70064f: feat(03-04): add VideoStatus enum and HeyGenWebhookPayload models
- FOUND commit 066aea9: feat(03-04): add webhook endpoint and APScheduler video poller

---
*Phase: 03-video-production*
*Completed: 2026-02-21*
