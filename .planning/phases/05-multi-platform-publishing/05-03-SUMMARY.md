---
phase: 05-multi-platform-publishing
plan: "03"
subsystem: publishing
tags: [ayrshare, tenacity, apscheduler, telegram, python, retry]

requires:
  - phase: 05-01
    provides: publish_events table, ayrshare_api_key setting, peak_hour_* settings
  - phase: 05-02
    provides: post_copy_tiktok/instagram/facebook/youtube columns on content_history
  - phase: 04-telegram-approval-loop
    provides: send_alert_sync pattern, approval flow, content_history table

provides:
  - PublishingService wrapping Ayrshare POST /post with tenacity retry (3 attempts, exponential 2-30s)
  - schedule_platform_publishes() helper registering 4 DateTrigger jobs with stable IDs
  - publish_to_platform_job APScheduler job (success+failure paths, DB persist + Telegram notify)
  - verify_publish_job APScheduler job (30 min post-publish check, alert only on failure)
  - 6 Telegram publish helpers (send_publish_confirmation, send_platform_success, send_platform_failure + sync wrappers)

affects:
  - 05-04 (approval_flow.py integration — calls schedule_platform_publishes + send_publish_confirmation_sync)
  - 05-05 (smoke tests will verify imports and behavior)

tech-stack:
  added: []
  patterns:
    - "set_scheduler() injector pattern on platform_publish module — same as video_poller; avoids pickle/closure issues"
    - "All APScheduler job args are str-only — picklable for SQLAlchemyJobStore serialization"
    - "Stable job IDs: publish_{content_history_id}_{platform} and verify_{content_history_id}_{platform}"
    - "Inclusive lower bound: approval_at_or_before_peak -> today's window; approval_after_peak -> tomorrow"
    - "verify_publish_job is silent on success — only surfaces failures to creator via Telegram alert"
    - "Failure fallback uses Supabase Storage URL (link-based, not file upload) — CONTEXT.md locked decision"

key-files:
  created:
    - src/app/services/publishing.py
    - src/app/scheduler/jobs/platform_publish.py
    - src/app/scheduler/jobs/publish_verify.py
  modified:
    - src/app/services/telegram.py

key-decisions:
  - "tenacity @retry on _post() method (not publish()) — decorator must be on the method that does the actual HTTP call; module-level _is_retryable predicate avoids tenacity decorator lambda limitations"
  - "verify_publish_job does not retry — verification failure is informational; creator alerted, no automated recovery"
  - "publish_to_platform_job does not re-raise on exception — APScheduler already logs; creator already notified via Telegram fallback"
  - "send_publish_confirmation sends new message (not edit) — CONTEXT.md locked decision: original approval message preserved unchanged"
  - "6 Telegram helpers follow send_alert_sync pattern exactly: run_coroutine_threadsafe when event loop running"

patterns-established:
  - "Platform job success path: DB insert published row -> Telegram success notify -> schedule verify job"
  - "Platform job failure path: DB insert failed row -> Telegram fallback with video URL + copy text"
  - "Verify job success: DB update to verified -> silent log only"
  - "Verify job failure: DB update to verify_failed -> Telegram alert to creator"

requirements-completed: [PUBL-01, PUBL-02, PUBL-03, PUBL-04]

duration: 2min
completed: 2026-02-25
---

# Phase 5 Plan 03: Publishing Engine Summary

**Ayrshare HTTP wrapper (tenacity 3-attempt retry) + peak-hour APScheduler jobs (publish + verify) + 6 Telegram publish notification helpers**

## Performance

- **Duration:** 2 min
- **Started:** 2026-02-25T18:20:12Z
- **Completed:** 2026-02-25T18:22:00Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- Created `publishing.py` with PublishingService wrapping Ayrshare POST /post with tenacity retry (3 attempts, exponential backoff 2-30s); fail-fast on 4xx, retry on 5xx + network errors; get_post_status() for verification
- Created `platform_publish.py` APScheduler job that fires at peak hour: publishes via Ayrshare, persists publish_events row (success or failure), sends Telegram notification, schedules verify job 30 min later; Telegram fallback on failure sends Supabase Storage URL + platform copy (link-based, not file upload)
- Created `publish_verify.py` APScheduler job that fires 30 min post-publish: queries Ayrshare status, updates DB to verified silently on success, updates to verify_failed + alerts creator via Telegram on failure
- Added 6 Telegram helpers to `telegram.py`: send_publish_confirmation/sync (schedule summary message), send_platform_success/sync (per-platform success), send_platform_failure/sync (fallback with video URL + copy)
- schedule_platform_publishes() helper registers 4 DateTrigger jobs with stable IDs using inclusive peak hour logic

## Task Commits

Each task was committed atomically:

1. **Task 1: PublishingService + schedule_platform_publishes helper** - `43f2694` (feat)
2. **Task 2: platform_publish job + publish_verify job + Telegram publish helpers** - `8b1e258` (feat)

**Plan metadata:** (docs commit below)

## Files Created/Modified
- `src/app/services/publishing.py` - PublishingService (Ayrshare wrapper + tenacity retry) + schedule_platform_publishes() helper registering 4 DateTrigger jobs
- `src/app/scheduler/jobs/platform_publish.py` - publish_to_platform_job: fires at peak hour, handles success+failure with DB persist and Telegram notify; set_scheduler() injector
- `src/app/scheduler/jobs/publish_verify.py` - verify_publish_job: 30-min post-publish Ayrshare status check; alerts only on failure
- `src/app/services/telegram.py` - 6 new helpers appended: send_publish_confirmation/sync, send_platform_success/sync, send_platform_failure/sync

## Decisions Made
- tenacity @retry on `_post()` (internal method) rather than `publish()` — the decorator targets the method that does the actual HTTP call; module-level `_is_retryable` predicate (not lambda) required by tenacity's `retry_if_exception`
- `publish_to_platform_job` does not re-raise exceptions — APScheduler already logs; creator is already notified via Telegram fallback message; silent exception swallowing is intentional for this job
- `verify_publish_job` has no retry — verification failure is informational; creator alerted once, no automated recovery attempt
- `send_publish_confirmation` sends new Telegram message (not editing original approval message) — preserves CONTEXT.md locked decision on approval message immutability
- 6 Telegram helpers follow `send_alert_sync` pattern exactly: `run_coroutine_threadsafe` when event loop is running, `run_until_complete` otherwise, `asyncio.run()` as RuntimeError fallback

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None — all 8 verification checks passed on first attempt. Import chain resolved cleanly without circular dependency issues.

## User Setup Required
None - no external service configuration required beyond what was established in Phase 5 Plan 01 (AYRSHARE_API_KEY).

## Next Phase Readiness
- Publishing engine is complete — PublishingService, publish job, verify job, and Telegram helpers all importable
- 05-04 (approval_flow integration) can call schedule_platform_publishes() and send_publish_confirmation_sync() directly
- Both job modules have set_scheduler() injectors ready for registry.py wiring
- Stable job IDs (publish_/verify_) ensure idempotent behavior on double-approval or pod restart

---
*Phase: 05-multi-platform-publishing*
*Completed: 2026-02-25*

## Self-Check: PASSED

- FOUND: src/app/services/publishing.py
- FOUND: src/app/scheduler/jobs/platform_publish.py
- FOUND: src/app/scheduler/jobs/publish_verify.py
- FOUND: .planning/phases/05-multi-platform-publishing/05-03-SUMMARY.md
- FOUND commit: 43f2694
- FOUND commit: 8b1e258
