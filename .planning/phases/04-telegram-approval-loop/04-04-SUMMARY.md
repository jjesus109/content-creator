---
phase: 04-telegram-approval-loop
plan: "04"
subsystem: telegram
tags: [telegram, python-telegram-bot, apscheduler, heygen, post-copy, thumbnail]

# Dependency graph
requires:
  - phase: 04-03
    provides: approval_flow handlers (handle_approve, handle_reject, handle_cause) wired into build_telegram_app()
  - phase: 04-02
    provides: PostCopyService.generate(), extract_thumbnail(), ApprovalService
  - phase: 04-01
    provides: approval_events table, post_copy column on content_history
  - phase: 03-video-production
    provides: _process_completed_render() in heygen.py, VideoStatus.READY, Supabase stable video URL
provides:
  - send_approval_message() async coroutine in services/telegram.py
  - send_approval_message_sync() thread bridge in services/telegram.py
  - _process_completed_render() triggers send_approval_message_sync instead of generic send_alert_sync
  - trigger_immediate_rerun() in daily_pipeline.py for rejection-triggered pipeline re-runs
affects: [05-publish-pipeline, 04-05]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - send_approval_message_sync mirrors send_alert_sync thread bridge (asyncio.get_event_loop + run_coroutine_threadsafe + RuntimeError fallback)
    - lazy local import of send_approval_message_sync inside _process_completed_render body avoids circular imports
    - trigger_immediate_rerun imports _scheduler lazily from video_poller at call time (not at module load)
    - DateTrigger one-shot job with replace_existing=True ensures only one rejection re-run queued

key-files:
  created: []
  modified:
    - src/app/services/telegram.py
    - src/app/services/heygen.py
    - src/app/scheduler/jobs/daily_pipeline.py

key-decisions:
  - "send_approval_message_sync mirrors send_alert_sync pattern exactly — run_coroutine_threadsafe when event loop running, run_until_complete otherwise, asyncio.run() as RuntimeError fallback"
  - "content_history_id retrieved via separate SELECT after READY DB update in _process_completed_render — same supabase client, heygen_job_id as key"
  - "trigger_immediate_rerun uses DateTrigger 30s from now with replace_existing=True — prevents duplicate re-runs if rejection fires twice"
  - "mood_profiles query uses order(created_at desc).limit(1) — no FK needed, latest row always wins; truncated to 40 chars for caption space"
  - "Caption truncated to 1024 chars total — Telegram photo caption limit"

patterns-established:
  - "Approval message delivery: photo with post_copy caption + 4 metadata fields + Approve/Reject inline keyboard"
  - "Thread bridge pattern for async Telegram calls from APScheduler context: established in Phase 1, extended in Phase 4"

requirements-completed: [TGAP-01, TGAP-02, TGAP-04]

# Metrics
duration: 2min
completed: 2026-02-23
---

# Phase 4 Plan 04: Wiring Video Delivery and Rejection Re-run Summary

**Telegram approval photo message sent automatically when video reaches READY via send_approval_message_sync wired into _process_completed_render(), plus trigger_immediate_rerun() for rejection-triggered one-shot pipeline re-runs**

## Performance

- **Duration:** 2 min
- **Started:** 2026-02-23T23:59:59Z
- **Completed:** 2026-02-24T00:01:35Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- `send_approval_message()` coroutine in telegram.py: loads content_history, queries mood_profiles (latest row, 40-char truncated), generates post_copy if missing (persists to DB), extracts thumbnail with fallback, sends photo or text message with Approve/Reject inline keyboard
- `send_approval_message_sync()` thread bridge in telegram.py mirrors existing `send_alert_sync` pattern exactly — compatible with APScheduler ThreadPoolExecutor context
- `_process_completed_render()` in heygen.py now retrieves content_history_id and calls `send_approval_message_sync` instead of generic `send_alert_sync` — closes the video READY -> creator notification loop
- `trigger_immediate_rerun()` in daily_pipeline.py schedules a one-shot pipeline job 30 seconds in the future via APScheduler DateTrigger, using the already-injected `_scheduler` from video_poller

## Task Commits

Each task was committed atomically:

1. **Task 1: Add send_approval_message and sync wrapper to services/telegram.py** - `04eacef` (feat)
2. **Task 2: Wire delivery into heygen.py and add trigger_immediate_rerun to daily_pipeline.py** - `aa70332` (feat)

**Plan metadata:** (see final docs commit)

## Files Created/Modified
- `src/app/services/telegram.py` - Added `send_approval_message()` async coroutine and `send_approval_message_sync()` thread bridge after existing `send_alert_sync`
- `src/app/services/heygen.py` - In `_process_completed_render()`: retrieve `content_history_id` via SELECT, call `send_approval_message_sync` replacing generic `send_alert_sync("Video listo...")`
- `src/app/scheduler/jobs/daily_pipeline.py` - Added `trigger_immediate_rerun()` at bottom of file using APScheduler DateTrigger

## Decisions Made
- `send_approval_message_sync` mirrors `send_alert_sync` pattern exactly — same runtime context (APScheduler ThreadPoolExecutor), same bridge approach
- `content_history_id` retrieved via a dedicated SELECT after the READY DB update (same supabase client, keyed on `heygen_job_id`) — avoids threading the row ID through the entire call stack
- `trigger_immediate_rerun()` imports `_scheduler` lazily from `video_poller` at call time, not at module load — avoids circular import at module load time consistent with Phase 04-03 pattern
- Caption truncated to 1024 chars — Telegram photo caption limit
- `mood_profiles` query uses `order("created_at", desc=True).limit(1)` — no FK needed, latest row always wins; profile_text truncated to 40 chars

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Video delivery loop is complete: HeyGen render READY -> creator Telegram photo message -> Approve/Reject buttons
- Rejection re-run wired: `handle_cause()` (04-03) calls `trigger_immediate_rerun()` (04-04) -> new pipeline job in 30 seconds
- Plan 04-05 (final phase integration/verification) can now proceed

---
*Phase: 04-telegram-approval-loop*
*Completed: 2026-02-23*
