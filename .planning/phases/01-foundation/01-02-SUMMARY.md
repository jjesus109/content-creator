---
phase: 01-foundation
plan: "02"
subsystem: infra
tags: [python, supabase, circuit-breaker, telegram, python-telegram-bot, apscheduler, asyncio]

# Dependency graph
requires:
  - phase: 01-foundation/01-01
    provides: "Settings singleton (get_settings()), src/app/services/__init__.py package"
provides:
  - Supabase client singleton (get_supabase()) with lru_cache via service_role key
  - CircuitBreakerService with dual cost+count tracking persisted in Postgres singleton row
  - Midnight reset function clearing daily counters without touching rolling window state
  - Rolling 7-day escalation logic via last_trip_at timestamp comparison
  - Telegram bot singleton with updater(None) — Phase 1 outbound-only (SCRTY-02)
  - Creator filter (filters.User) as single source of truth for SCRTY-02
  - send_alert() async and send_alert_sync() for APScheduler thread pool compatibility
affects:
  - 01-03 (FastAPI lifespan imports get_supabase() and get_telegram_bot())
  - 01-03 (APScheduler jobs import CircuitBreakerService.midnight_reset and record_attempt)
  - All subsequent phases that need circuit breaker checks before API generation calls

# Tech tracking
tech-stack:
  added: []  # All dependencies already in pyproject.toml from Plan 01
  patterns:
    - Lazy circular import avoidance — send_alert_sync imported inside _send_escalation_alert method body
    - APScheduler thread safety — run_coroutine_threadsafe bridges sync scheduler thread to async FastAPI event loop
    - lru_cache singleton pattern applied to both Supabase client and Telegram bot for shared state

key-files:
  created:
    - src/app/services/database.py
    - src/app/services/circuit_breaker.py
    - src/app/services/telegram.py
  modified: []

key-decisions:
  - "Circular import avoided by importing send_alert_sync inside _send_escalation_alert body rather than at module level"
  - "send_alert_sync uses run_coroutine_threadsafe when event loop is running — required for APScheduler thread pool compatibility"
  - "Bot initialized with updater(None) — Phase 1 is outbound-only; polling added in Phase 4"
  - "Rolling 7-day escalation window uses last_trip_at timestamp comparison, not week_start counter — handles partial weeks correctly"

patterns-established:
  - "Pattern 4: All service singletons (Supabase client, Telegram bot) use lru_cache — never instantiate directly"
  - "Pattern 5: Circular imports resolved by local function-level import inside the calling method body"
  - "Pattern 6: APScheduler jobs calling async functions use run_coroutine_threadsafe on the existing loop"

requirements-completed: [INFRA-04, SCRTY-02]

# Metrics
duration: 3min
completed: 2026-02-20
---

# Phase 1 Plan 02: Service Layer Summary

**Supabase singleton, dual cost+count circuit breaker (Postgres-backed, rolling 7-day escalation), and outbound-only Telegram bot with SCRTY-02 creator filter — all independently importable with no FastAPI or APScheduler dependency**

## Performance

- **Duration:** ~3 min
- **Started:** 2026-02-20T03:48:10Z
- **Completed:** 2026-02-20T03:51:33Z
- **Tasks:** 2
- **Files modified:** 3 created

## Accomplishments

- `get_supabase()` Supabase client singleton using service_role key — shared across all services via lru_cache
- `CircuitBreakerService` with dual cost+count tracking: `record_attempt()` returns False and writes `tripped_at` when either daily cost or attempt limit is reached
- `midnight_reset()` zeroes `current_day_cost` and `current_day_attempts` without touching `weekly_trip_count` or `last_trip_at` (rolling 7-day window persists across resets)
- Escalation Telegram alert sent automatically when `weekly_trip_count` reaches 2+ within 7 days
- Telegram bot initialized with `updater(None)` — no polling, no event loop conflict with FastAPI
- `send_alert_sync()` bridges APScheduler thread pool to FastAPI's async event loop via `run_coroutine_threadsafe`
- `get_creator_filter()` returns `filters.User(user_id=CREATOR_ID)` as the SCRTY-02 enforcement point for Phase 4

## Task Commits

Each task was committed atomically:

1. **Task 1: Supabase client singleton and CircuitBreakerService** - `16ede8c` (feat)
2. **Task 2: Telegram outbound-only bot with creator filter** - `5cc5f44` (feat)

**Plan metadata:** (pending final commit)

## Files Created/Modified

- `src/app/services/database.py` - lru_cache singleton returning Supabase Client via service_role key
- `src/app/services/circuit_breaker.py` - CircuitBreakerService: get_state(), is_tripped(), record_attempt(), midnight_reset(), _trip(), _send_escalation_alert()
- `src/app/services/telegram.py` - get_telegram_bot(), get_creator_filter(), send_alert() (async), send_alert_sync() (sync)

## Decisions Made

- Circular import between `circuit_breaker.py` and `telegram.py` resolved by importing `send_alert_sync` inside the `_send_escalation_alert` method body (not at module level) — both modules remain independently importable
- `send_alert_sync()` uses `asyncio.run_coroutine_threadsafe()` when an event loop is running (APScheduler thread → FastAPI loop), falls back to `loop.run_until_complete()` or `asyncio.run()` for non-FastAPI contexts
- Rolling 7-day window implemented via `last_trip_at` timestamp delta comparison rather than a `week_start` counter — handles month/year boundaries and partial weeks without special casing

## Deviations from Plan

None — plan executed exactly as written. Both modules imported without errors on first attempt.

## Issues Encountered

- System `python` command not found (macOS ships without `python` alias) — used `.venv/bin/python` from the virtual environment created in Plan 01. No fix required; verification commands work correctly with venv Python.

## User Setup Required

None — no additional external service configuration required for this plan. Services import without connecting (connection occurs on first method call, which requires real credentials in `.env`).

## Next Phase Readiness

- All three service modules import without errors and are independently testable
- `CircuitBreakerService` and `get_telegram_bot()` are ready for APScheduler job registration in Plan 03
- `get_supabase()` ready for FastAPI lifespan health check in Plan 03
- Blocked on: User must have `.env` populated with real Supabase/Telegram credentials before Plan 03 runtime tests execute DB operations

---
*Phase: 01-foundation*
*Completed: 2026-02-20*

## Self-Check: PASSED

All 3 service files verified present on disk. Both task commits (16ede8c, 5cc5f44) verified in git history. SUMMARY.md created at .planning/phases/01-foundation/01-02-SUMMARY.md.
