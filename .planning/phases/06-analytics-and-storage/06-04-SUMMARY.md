---
phase: 06-analytics-and-storage
plan: 04
subsystem: scheduler
tags: [apscheduler, metrics, analytics, platform-metrics, virality, datetrigger]

# Dependency graph
requires:
  - phase: 06-02
    provides: MetricsService.fetch_and_store() and AnalyticsService.check_and_alert_virality()
provides:
  - harvest_metrics_job APScheduler function (fetches metrics + runs virality check)
  - DateTrigger harvest job scheduled 48h after successful publish in platform_publish_job
affects:
  - 06-05 (weekly_report_job references platform_metrics populated by this job)
  - 07-hardening (smoke tests should cover harvest job import and scheduling)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Lazy import of child job inside parent function body to avoid circular imports at module load (same as verify_publish_job)"
    - "All APScheduler job args are str for SQLAlchemyJobStore pickling"
    - "Job wrapped in top-level try/except to prevent APScheduler from logging exception after job already ran"
    - "Deterministic job ID pattern: harvest_{content_history_id}_{platform}"

key-files:
  created:
    - src/app/scheduler/jobs/harvest_metrics.py
  modified:
    - src/app/scheduler/jobs/platform_publish.py

key-decisions:
  - "harvest_metrics_job fetches topic_summary AND created_at in single DB call — plan only showed topic_summary but analytics.py requires video_date arg"
  - "video_date derived from created_at[:10] (YYYY-MM-DD slice) — no separate query needed"
  - "harvest_run_at = now + 48h inside publish success block, not in except block — metrics only harvested for successful publishes"
  - "replace_existing=True on harvest job — idempotent if approval message re-triggers publish"

patterns-established:
  - "Child job lazy import: from app.scheduler.jobs.X import Y inside parent function body, not at top of module"
  - "Fail-soft APScheduler job: entire body wrapped in try/except Exception, logger.error with exc_info=True"
  - "DateTrigger +48h pattern mirrors +30m verify pattern from Phase 5"

requirements-completed: [ANLX-01, ANLX-03]

# Metrics
duration: 4min
completed: 2026-02-28
---

# Phase 6 Plan 04: Harvest Metrics Job Summary

**harvest_metrics_job APScheduler function that fetches platform metrics via MetricsService, runs AnalyticsService virality check, and is automatically scheduled 48h after each successful publish via DateTrigger in platform_publish_job**

## Performance

- **Duration:** 4 min
- **Started:** 2026-02-28T20:27:10Z
- **Completed:** 2026-02-28T20:31:00Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Created `harvest_metrics_job` that fetches metrics via `MetricsService().fetch_and_store()` and runs virality detection via `AnalyticsService().check_and_alert_virality()`, wrapped in fail-soft try/except
- Wired DateTrigger harvest scheduling into `publish_to_platform_job` success block — harvest fires 48h after publish with deterministic job ID `harvest_{content_history_id}_{platform}`
- Auto-fixed missing `video_date` argument required by `AnalyticsService.check_and_alert_virality()` — fetched `created_at` alongside `topic_summary` in single DB call

## Task Commits

Each task was committed atomically:

1. **Task 1: Create harvest_metrics_job** - `156f986` (feat)
2. **Task 2: Wire harvest DateTrigger into platform_publish_job** - `9136fad` (feat)

**Plan metadata:** TBD (docs: complete plan)

## Files Created/Modified

- `src/app/scheduler/jobs/harvest_metrics.py` - APScheduler job that harvests platform metrics 48h after publish and runs virality check
- `src/app/scheduler/jobs/platform_publish.py` - Added harvest DateTrigger scheduling in success block (lines 102-118)

## Decisions Made

- `harvest_metrics_job` fetches `topic_summary` AND `created_at` in a single content_history DB call — plan only specified `topic_summary` but `AnalyticsService.check_and_alert_virality()` requires `video_date` as 5th argument; `video_date` derived from `created_at[:10]`
- `video_date` derived from `created_at[:10]` (ISO date slice) — no separate query needed, same DB call as `topic_summary`
- Harvest scheduling placed after verify scheduling block inside try block — only scheduled on successful publish, not on failure
- `replace_existing=True` ensures idempotency if the same publish job were to fire more than once

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Added missing `video_date` argument to `check_and_alert_virality()` call**
- **Found during:** Task 1 (Create harvest_metrics_job)
- **Issue:** The plan specified calling `AnalyticsService().check_and_alert_virality(content_history_id, platform, current_views, topic_summary)` with 4 args. The actual function signature in `analytics.py` requires 5 args: `(content_history_id, platform, current_views, topic_summary, video_date)`. Calling with 4 args would raise `TypeError` at runtime.
- **Fix:** Extended the content_history DB select to also fetch `created_at`; derived `video_date = created_at[:10]`; passed it as the 5th argument.
- **Files modified:** `src/app/scheduler/jobs/harvest_metrics.py`
- **Verification:** Import and function call verified with project venv; `AnalyticsService.check_and_alert_virality` signature inspected to confirm match.
- **Committed in:** `156f986` (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 bug — missing required argument)
**Impact on plan:** Essential fix for correctness — without it the job would TypeError on every execution. No scope creep.

## Issues Encountered

None — both tasks executed cleanly after the auto-fix.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- `harvest_metrics_job` is importable and correctly wired via DateTrigger in `platform_publish_job`
- Phase 6 plan 05 (weekly_report_job + storage_lifecycle_job) depends on `platform_metrics` rows populated by this job
- Metrics harvest will run correctly for all 4 platforms (YouTube, Instagram, TikTok, Facebook) once env vars are populated

---
*Phase: 06-analytics-and-storage*
*Completed: 2026-02-28*
