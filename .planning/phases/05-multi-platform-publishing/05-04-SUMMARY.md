---
phase: 05-multi-platform-publishing
plan: "04"
subsystem: publishing
tags: [apscheduler, telegram, approval-flow, platform-publish, registry]

# Dependency graph
requires:
  - phase: 05-02
    provides: platform copy variants (post_copy_tiktok/instagram/facebook/youtube) in content_history
  - phase: 05-03
    provides: schedule_platform_publishes(), send_publish_confirmation_sync(), platform_publish.set_scheduler()
provides:
  - handle_approve wired to trigger 4 platform publish jobs on creator approval
  - platform_publish._scheduler injected at startup via registry.py
  - Full publish loop closed: Approve tap -> schedule 4 jobs -> confirmation message
affects:
  - 05-05
  - future hardening phase

# Tech tracking
tech-stack:
  added: []
  patterns:
    - Local imports inside async handler body (prevents circular imports — consistent with existing style)
    - Module-level scheduler injection via set_scheduler() aliased as set_publish_scheduler in registry.py

key-files:
  created: []
  modified:
    - src/app/telegram/handlers/approval_flow.py
    - src/app/scheduler/registry.py

key-decisions:
  - "handle_approve fetches video_url from content_history via supabase before scheduling — same DB client pattern as other handlers"
  - "scheduler accessed via _fastapi_app.state.scheduler inside handler body — avoids global variable, consistent with existing pattern"
  - "set_publish_scheduler aliased from set_scheduler import in registry.py — avoids name collision with video_poller set_scheduler"

patterns-established:
  - "Registry pattern: every job module needing _scheduler gets injected via set_X_scheduler(scheduler) call in register_jobs()"
  - "Approval handler closes loop: record approval -> fetch data -> schedule jobs -> send confirmation (no direct message from handler)"

requirements-completed: [PUBL-01, PUBL-02]

# Metrics
duration: 1min
completed: 2026-02-25
---

# Phase 5 Plan 04: Wire Approval to Publishing Summary

**Approval handler now closes the publish loop: Approve tap fetches video_url, schedules 4 platform DateTrigger jobs, and sends per-platform confirmation — registry injects _scheduler into platform_publish at startup**

## Performance

- **Duration:** 1 min
- **Started:** 2026-02-25T18:25:39Z
- **Completed:** 2026-02-25T18:26:45Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- `handle_approve` now retrieves `video_url` from `content_history`, gets the scheduler from `_fastapi_app.state.scheduler`, calls `schedule_platform_publishes()` to register 4 DateTrigger jobs, and calls `send_publish_confirmation_sync()` with scheduled times
- `registry.py` imports `set_publish_scheduler` from `platform_publish` and calls it in `register_jobs()` — ensures `_scheduler` is not None when publish jobs need to schedule verify jobs 30 min later
- Original approval message with Approve/Reject buttons preserved unchanged (locked decision from Phase 4)
- `handle_reject` and `handle_cause` untouched

## Task Commits

Each task was committed atomically:

1. **Task 1: Wire handle_approve to schedule publishing + send confirmation** - `de350e5` (feat)
2. **Task 2: Inject platform_publish scheduler in registry.py at startup** - `99e8538` (feat)

**Plan metadata:** (docs commit — see below)

## Files Created/Modified
- `src/app/telegram/handlers/approval_flow.py` - Replaced static "Aprobado" message with publish job scheduling + confirmation send
- `src/app/scheduler/registry.py` - Added set_publish_scheduler import and call in register_jobs()

## Decisions Made
- `scheduler` retrieved from `_fastapi_app.state.scheduler` inside handler body — no new global variable needed, consistent with existing `_fastapi_app` usage in telegram.py
- Import aliased as `set_publish_scheduler` to avoid name collision with `set_scheduler` already imported from `video_poller`

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Publish loop is fully wired: Approve -> schedule 4 platform jobs -> confirmation message
- platform_publish._scheduler set at startup — verify jobs can schedule 30 min post-publish
- Ready for Phase 05-05 (final integration/smoke tests or remaining plans)

---
*Phase: 05-multi-platform-publishing*
*Completed: 2026-02-25*

## Self-Check: PASSED

- FOUND: src/app/telegram/handlers/approval_flow.py
- FOUND: src/app/scheduler/registry.py
- FOUND: .planning/phases/05-multi-platform-publishing/05-04-SUMMARY.md
- FOUND commit: de350e5 (Task 1)
- FOUND commit: 99e8538 (Task 2)
- FOUND commit: dd870b7 (metadata)
