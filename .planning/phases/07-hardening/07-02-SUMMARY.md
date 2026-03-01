---
phase: 07-hardening
plan: 02
subsystem: scheduler
tags: [apscheduler, telegram, approval-timeout, pipeline, datetrigger]

# Dependency graph
requires:
  - phase: 04-telegram-approval-loop
    provides: approval_events table, send_approval_message_sync, handle_approve, ApprovalService
  - phase: 07-01
    provides: VideoStatus enum context, circuit_breaker hardening patterns

provides:
  - VideoStatus.APPROVAL_TIMEOUT enum value for use everywhere video_status is compared or written
  - approval_timeout.py job: schedule_approval_timeout + check_approval_timeout_job + set_scheduler
  - 24h last-chance message flow: fires if approval_events row missing at job time
  - Pipeline startup stale-row cleanup: _expire_stale_approvals() marks ready rows with no approval_events as approval_timeout
  - handle_approve cancels the timeout job by ID before recording approval

affects: [07-03-migration, daily_pipeline_job, send_approval_message_sync, handle_approve]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Lazy import inside function body to break circular import (telegram.py <-> approval_timeout.py)"
    - "Module-level _scheduler + set_scheduler() pattern (same as video_poller.py)"
    - "DateTrigger one-shot job with stable ID for cancellability"

key-files:
  created:
    - src/app/scheduler/jobs/approval_timeout.py
  modified:
    - src/app/models/video.py
    - src/app/scheduler/jobs/daily_pipeline.py
    - src/app/services/telegram.py
    - src/app/telegram/handlers/approval_flow.py
    - src/app/scheduler/registry.py

key-decisions:
  - "APPROVAL_TIMEOUT enum value added now so daily_pipeline_job can reference it; DB CHECK constraint update deferred to Plan 03 migration"
  - "Lazy import of schedule_approval_timeout inside send_approval_message_sync body avoids circular import through telegram.py"
  - "schedule_approval_timeout guards on _scheduler is None and returns silently (no raise) — safe in dev/test environments without a live scheduler"
  - "handle_approve wraps remove_job in broad except — APScheduler raises JobLookupError for missing jobs; must not stop the approval flow"
  - "_expire_stale_approvals iterates ready IDs individually (no JOIN) — Supabase Python client has no JOIN query support"

patterns-established:
  - "Approval timeout job ID pattern: approval_timeout_{content_history_id} — stable, predictable, cancellable"
  - "Pipeline startup cleanup: _expire_stale_approvals runs before circuit breaker check — ensures stale state cleared on every pipeline start"

requirements-completed: [TGAP-02, TGAP-03, TGAP-04, INFRA-03]

# Metrics
duration: 2min
completed: 2026-03-01
---

# Phase 7 Plan 02: Approval Timeout Flow Summary

**24h approval timeout: DateTrigger job, last-chance Telegram re-send, pipeline stale-row cleanup, and handle_approve cancellation wired end-to-end**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-01T07:01:37Z
- **Completed:** 2026-03-01T07:03:41Z
- **Tasks:** 2
- **Files modified:** 5 (+ 1 created)

## Accomplishments

- Created `approval_timeout.py` with `schedule_approval_timeout()` (DateTrigger 24h, stable ID) and `check_approval_timeout_job()` (exits silently if already actioned, sends last-chance alert + re-sends approval message if not)
- Extended `VideoStatus` enum with `APPROVAL_TIMEOUT = "approval_timeout"` so the status is usable everywhere before the DB migration in Plan 03
- Wired `schedule_approval_timeout()` call into `send_approval_message_sync()` after delivery (lazy import avoids circular import)
- Added `_expire_stale_approvals()` to `daily_pipeline_job` startup — marks any `ready` row with no `approval_events` row as `approval_timeout`
- `handle_approve` cancels the timeout job by ID before processing approval — no spurious last-chance messages
- `registry.py` injects scheduler into `approval_timeout` module at startup via `set_approval_timeout_scheduler(scheduler)`

## Task Commits

Each task was committed atomically:

1. **Task 1: Extend VideoStatus enum + create approval_timeout.py job** - `1509ecb` (feat)
2. **Task 2: Wire timeout scheduling into send_approval_message_sync, stale-row cleanup into daily_pipeline_job, cancellation into handle_approve, registry update** - `27d5aba` (feat)

**Plan metadata:** _(committed in final docs commit)_

## Files Created/Modified

- `src/app/scheduler/jobs/approval_timeout.py` - New job file: set_scheduler, schedule_approval_timeout (DateTrigger 24h), check_approval_timeout_job (checks approval_events, sends last-chance message)
- `src/app/models/video.py` - Added APPROVAL_TIMEOUT = "approval_timeout" to VideoStatus enum
- `src/app/scheduler/jobs/daily_pipeline.py` - Added _expire_stale_approvals() called at startup; marks stale ready rows as approval_timeout
- `src/app/services/telegram.py` - send_approval_message_sync now calls schedule_approval_timeout after sending
- `src/app/telegram/handlers/approval_flow.py` - handle_approve cancels timeout job by ID before processing
- `src/app/scheduler/registry.py` - Imports and calls set_approval_timeout_scheduler(scheduler) at startup

## Decisions Made

- APPROVAL_TIMEOUT enum value added now; DB CHECK constraint update deferred to Plan 03 (migration 0007) — pipeline can reference the value before the DB is updated
- Lazy import of approval_timeout inside send_approval_message_sync function body breaks potential circular import (telegram.py -> approval_timeout.py -> telegram.py)
- schedule_approval_timeout returns None silently when _scheduler is None — no raise, safe in test/dev contexts
- handle_approve wraps remove_job in broad except — APScheduler raises JobLookupError for missing jobs; this must not stop the approval flow
- _expire_stale_approvals uses individual per-ID queries rather than JOIN — Supabase Python client does not support JOIN queries

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Approval timeout flow fully implemented at application level
- Plan 03 (migration) must add 'approval_timeout' to the DB CHECK constraint on content_history.video_status before the daily_pipeline_job can write this status to the DB
- All 21 existing smoke tests pass (test_phase04_smoke.py + test_phase05_smoke.py)

---
*Phase: 07-hardening*
*Completed: 2026-03-01*
