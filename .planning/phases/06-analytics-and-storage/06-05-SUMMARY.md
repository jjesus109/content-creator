---
phase: 06-analytics-and-storage
plan: 05
subsystem: infra
tags: [apscheduler, cronjob, analytics, storage-lifecycle, telegram, supabase]

# Dependency graph
requires:
  - phase: 06-02
    provides: AnalyticsService.build_weekly_report() with weekly report query + formatting logic
  - phase: 06-03
    provides: StorageLifecycleService with transition_to_warm(), send_7day_warning(), request_deletion_confirmation(), reset_expired_deletion_requests()
provides:
  - weekly_analytics_report_job APScheduler job (Sunday 9 AM Mexico City, ANLX-02)
  - storage_lifecycle_job APScheduler job (daily 2 AM Mexico City, ANLX-04)
  - Both jobs registered in registry.py with stable IDs and replace_existing=True
affects: [07-hardening]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - asyncio.run() as async bridge in APScheduler ThreadPoolExecutor threads (no existing event loop)
    - CronTrigger jobs registered in registry.py with stable IDs and replace_existing=True

key-files:
  created:
    - src/app/scheduler/jobs/weekly_report.py
    - src/app/scheduler/jobs/storage_lifecycle.py
  modified:
    - src/app/scheduler/registry.py

key-decisions:
  - "asyncio.run() used in storage_lifecycle_job to bridge async StorageLifecycleService methods — APScheduler ThreadPoolExecutor thread has no event loop (different from send_alert_sync which uses run_coroutine_threadsafe when FastAPI loop exists)"
  - "storage_lifecycle_job never deletes files directly — actual deletion only on stor_confirm: Telegram handler tap"
  - "is_viral=False and is_eternal=False guards in all three transition queries — exempt videos never transitioned"
  - "reset_expired_deletion_requests() called first in each lifecycle run — safe default: do NOT delete without confirmation"

patterns-established:
  - "asyncio.run() bridge pattern for async service calls from APScheduler thread pool (no event loop context)"
  - "CronTrigger jobs: stable ID + replace_existing=True + TIMEZONE constant — required for SQLAlchemyJobStore restart safety"

requirements-completed: [ANLX-02, ANLX-04]

# Metrics
duration: 1min
completed: 2026-02-28
---

# Phase 6 Plan 05: Scheduled Jobs (Weekly Report + Storage Lifecycle) Summary

**Weekly analytics report cron (Sun 9 AM) and storage lifecycle cron (daily 2 AM) registered in APScheduler via registry.py — completing Phase 6's observable scheduler behaviors**

## Performance

- **Duration:** 1 min
- **Started:** 2026-02-28T20:27:12Z
- **Completed:** 2026-02-28T20:28:52Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- Created `weekly_report.py` job: calls `AnalyticsService().build_weekly_report()` then `send_alert_sync()` — fires Sunday 9 AM Mexico City
- Created `storage_lifecycle.py` job: 4-step daily cron (reset expired, hot→warm DB label, 7-day pre-warning, 45-day deletion confirmation) — fires daily 2 AM Mexico City
- Registered both jobs in `registry.py` with stable IDs (`weekly_analytics_report`, `storage_lifecycle_cron`), `replace_existing=True`, and `TIMEZONE` constant

## Task Commits

Each task was committed atomically:

1. **Task 1: Create weekly_report_job and storage_lifecycle_job** - `daf3fbf` (feat)
2. **Task 2: Register both jobs in registry.py** - `793f070` (feat)

## Files Created/Modified
- `src/app/scheduler/jobs/weekly_report.py` - APScheduler job wrapping AnalyticsService.build_weekly_report() + send_alert_sync()
- `src/app/scheduler/jobs/storage_lifecycle.py` - Daily cron: reset expired deletions, hot→warm, 7-day pre-warning, 45-day confirmation; no R2/boto3
- `src/app/scheduler/registry.py` - Added imports and CronTrigger registrations for both new jobs

## Decisions Made
- `asyncio.run()` used as the async bridge in `storage_lifecycle_job`: APScheduler ThreadPoolExecutor threads have no existing event loop, unlike FastAPI's main thread where `send_alert_sync` uses `run_coroutine_threadsafe`. These are different async contexts requiring different bridges.
- Storage lifecycle job never deletes files — it only transitions labels and sends Telegram alerts. Actual deletion requires creator confirmation via `stor_confirm:` handler (Plan 06-03).
- `is_viral=False` and `is_eternal=False` guards applied at the Supabase query level for all three transition steps — ensures exempt videos are never transitioned even if service-level guards fail.
- `reset_expired_deletion_requests()` called first in each run — safe default ensures no files are deleted without explicit creator confirmation within 24h.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Phase 6 APScheduler job layer is complete: daily pipeline, cb_reset, weekly mood (prompt + reminder), metrics harvest, weekly analytics report, storage lifecycle
- Phase 7 (Hardening) can verify all 6 scheduled jobs are registered and firing correctly
- No blockers

---
*Phase: 06-analytics-and-storage*
*Completed: 2026-02-28*
