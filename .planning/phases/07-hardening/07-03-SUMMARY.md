---
phase: 07-hardening
plan: "03"
subsystem: infra
tags: [circuit-breaker, telegram, apscheduler, daily-halt, resume-command, sql-migration]

# Dependency graph
requires:
  - phase: 01-foundation
    provides: CircuitBreakerService, midnight_reset, circuit_breaker_state table
  - phase: 04-telegram-approval-loop
    provides: build_telegram_app, get_creator_filter, CommandHandler pattern
  - phase: 07-hardening-02
    provides: approval_timeout VideoStatus value, daily_pipeline_job with _expire_stale_approvals
provides:
  - CircuitBreakerService.is_daily_halted() — returns True after 3 daily trips
  - CircuitBreakerService.clear_daily_halt() — called by /resume to unblock pipeline
  - CircuitBreakerService._send_daily_halt_alert() — halt Telegram alert with /resume instructions
  - circuit_breaker_state.daily_trip_count and daily_halted_at columns (migration 0007)
  - /resume CommandHandler restricted to creator ID — clears halt, triggers immediate rerun
  - daily_pipeline_job daily halt guard — returns early when cb.is_daily_halted() is True
  - midnight_reset clears daily halt state alongside daily cost/count reset
affects: [07-hardening, integration-tests, daily-pipeline]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - Lazy imports in handle_resume body to avoid circular import chain (mirrors approval_flow pattern)
    - Fail-open is_daily_halted() — returns False on DB exception so pipeline is not blocked by infrastructure failure
    - Daily halt fires only on 3rd trip AND only if not already halted (idempotent, no alert storm)

key-files:
  created:
    - migrations/0007_hardening.sql
    - src/app/telegram/handlers/resume_flow.py
  modified:
    - src/app/services/circuit_breaker.py
    - src/app/telegram/app.py
    - src/app/scheduler/jobs/daily_pipeline.py

key-decisions:
  - "daily_trip_count incremented in _trip() after the existing weekly escalation logic — separate DB UPDATE to keep separation of concerns"
  - "halt alert fires only at new_daily_trip_count >= 3 AND already_halted is False — prevents duplicate halt alerts if _trip() fires again"
  - "is_daily_halted() fails open (returns False) on DB exception — pipeline availability over halt enforcement when DB is unreachable"
  - "No confirmation message to creator after /resume — CONTEXT.md locked decision"
  - "register_resume_handler added to build_telegram_app() via lazy import at end of function — same pattern as storage_handlers"
  - "daily halt guard placed after is_tripped() check — tripped state is the primary circuit breaker; daily halt is the secondary accumulation guard"

patterns-established:
  - "Daily halt state uses daily_halted_at IS NOT NULL sentinel — single timestamp column tracks both 'is halted' and 'when halted'"
  - "midnight_reset includes daily_trip_count=0 + daily_halted_at=NULL — new calendar day always starts clean"

requirements-completed: [INFRA-04, SCRTY-02]

# Metrics
duration: 2min
completed: 2026-03-01
---

# Phase 7 Plan 03: Circuit Breaker Daily Halt + /resume Command Summary

**3-trips-per-day halt with /resume Telegram command: CircuitBreakerService extended with daily halt logic, migration 0007 adds DB columns, and creator-only /resume handler clears halt and triggers immediate pipeline rerun.**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-01T07:01:54Z
- **Completed:** 2026-03-01T07:03:54Z
- **Tasks:** 2
- **Files modified:** 5 (2 created, 3 modified)

## Accomplishments

- Migration 0007 adds daily_trip_count + daily_halted_at to circuit_breaker_state and extends video_status CHECK to include approval_timeout
- CircuitBreakerService._trip() now increments daily_trip_count and sends a halt alert with /resume instructions after 3 trips; midnight_reset clears daily halt state
- /resume CommandHandler created, wired into build_telegram_app(), restricted to creator ID only, triggers immediate pipeline rerun via trigger_immediate_rerun()
- daily_pipeline_job() returns early when cb.is_daily_halted() is True — pipeline does not loop on daily halt

## Task Commits

Each task was committed atomically:

1. **Task 1: Migration 0007 + CircuitBreakerService daily halt + midnight_reset** - `a72103d` (feat)
2. **Task 2: /resume handler + build_telegram_app wiring + daily halt guard** - `c409a17` (feat)

**Plan metadata:** (docs commit — see below)

## Files Created/Modified

- `migrations/0007_hardening.sql` - ALTER circuit_breaker_state (daily_trip_count, daily_halted_at), DROP+ADD content_history video_status CHECK with approval_timeout
- `src/app/services/circuit_breaker.py` - _trip() extended with daily_trip_count increment + halt logic; added is_daily_halted(), clear_daily_halt(), _send_daily_halt_alert(); midnight_reset() clears daily halt
- `src/app/telegram/handlers/resume_flow.py` - Creator-only /resume handler with lazy imports, calls clear_daily_halt() + trigger_immediate_rerun()
- `src/app/telegram/app.py` - build_telegram_app() registers register_resume_handler via lazy import
- `src/app/scheduler/jobs/daily_pipeline.py` - Added cb.is_daily_halted() guard after cb.is_tripped() check

## Decisions Made

- daily_trip_count incremented in _trip() after the existing weekly escalation logic — separate DB UPDATE keeps escalation state update atomic from daily state update
- Halt alert fires only when new_daily_trip_count >= 3 AND already_halted is False — prevents duplicate halt alerts if the circuit breaker fires more than 3 times
- is_daily_halted() fails open (returns False) on DB exception — pipeline availability is higher priority than halt enforcement when DB is unavailable
- No confirmation message to creator after /resume (CONTEXT.md locked decision)
- Daily halt guard placed after the existing is_tripped() check — primary breaker checked first; daily halt is the secondary accumulation guard

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

The `daily_pipeline.py` file had already been modified by plan 07-02 (added `_expire_stale_approvals()` step 0 and `VideoStatus.APPROVAL_TIMEOUT`). The edit was applied cleanly to the updated file state.

## User Setup Required

None - no external service configuration required. Migration 0007 must be applied to the production database before deploying.

## Next Phase Readiness

- Daily halt + /resume recovery path complete and wired
- Circuit breaker now has both a per-run trip signal (is_tripped) and a per-day accumulation halt (is_daily_halted)
- Ready for Phase 7 integration testing (07-04 or remaining hardening plans)

## Self-Check: PASSED

All created files confirmed present on disk. Both task commits (a72103d, c409a17) confirmed in git log.

---

*Phase: 07-hardening*
*Completed: 2026-03-01*
