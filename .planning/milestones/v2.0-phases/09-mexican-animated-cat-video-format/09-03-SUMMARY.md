---
phase: 09-mexican-animated-cat-video-format
plan: "03"
subsystem: kling-circuit-breaker
tags: [circuit-breaker, kling, fal-ai, resilience, tenacity, backoff]
dependency_graph:
  requires: [09-01, 09-02]
  provides: [KlingCircuitBreakerService, kling-cb-wiring, tenacity-backoff]
  affects: [video_poller.py, daily_pipeline.py, kling.py]
tech_stack:
  added: [tenacity (already present >=8.0)]
  patterns: [failure-rate-based circuit breaker, exponential backoff, fail-open pattern, DB singleton state]
key_files:
  created:
    - src/app/services/kling_circuit_breaker.py
    - tests/test_kling_circuit_breaker.py
    - tests/test_kling_balance.py
    - tests/test_kling_backoff.py
  modified:
    - src/app/services/kling.py
    - src/app/scheduler/jobs/video_poller.py
    - src/app/scheduler/jobs/daily_pipeline.py
decisions:
  - "KlingCircuitBreakerService uses kling_circuit_breaker_state table (migration 0008 singleton) — separate from HeyGen circuit_breaker_state"
  - "check_balance() is fail-open — returns True on fal_client exception to avoid unnecessary pipeline halts"
  - "is_open() is fail-open — returns False on DB error (pipeline can continue if DB is unavailable)"
  - "_submit_with_backoff wraps fal_client.submit at module level (not instance method) for tenacity decorator compatibility"
  - "record_attempt called in video_poller after status branch (not daily_pipeline) — keeps submission and tracking decoupled"
metrics:
  duration_seconds: 372
  completed_date: "2026-03-19"
  tasks_completed: 2
  files_created: 4
  files_modified: 3
  tests_added: 20
---

# Phase 09 Plan 03: Kling Circuit Breaker Summary

**One-liner:** Failure-rate-based circuit breaker for Kling AI — 20% threshold, $1/$5 balance guards, 2s/8s/32s tenacity backoff, DB-persisted state.

## What Was Built

### Task 1: KlingCircuitBreakerService (877d87a)

Created `src/app/services/kling_circuit_breaker.py` — a failure-rate-based circuit breaker for Kling AI API calls, separate from the existing HeyGen cost+count CB.

Key design:
- **State persists in Postgres** via `kling_circuit_breaker_state` singleton (migration 0008) — survives service restarts
- **Failure threshold:** >20% failure rate over a 24h rolling window opens the CB
- **Balance thresholds:** <$1.00 halts pipeline; <$5.00 sends warning alert but proceeds
- **Fail-open:** Both `is_open()` and `check_balance()` return safe defaults on errors
- **Recovery:** `reset()` called by `/resume` Telegram command and APScheduler midnight reset

Public API:
- `get_state()` — reads singleton row from DB
- `is_open()` — fail-open check (returns False on DB error)
- `record_attempt(success: bool)` — updates counts, trips CB if threshold exceeded
- `check_balance()` — queries fal.ai balance, no DB writes
- `reset()` — zeroes all counters, clears is_open (midnight + /resume)
- `_trip()` — opens CB, persists state, sends Telegram alert with failure rate + /resume

### Task 2: CB wiring + tenacity backoff (ed8e97f)

**video_poller.py:**
- Balance check at start of every 60s poll (not per submission)
- Cancels poller and returns if `check_balance()` returns False
- Records `success=True` after completed render, `success=False` after failed render

**daily_pipeline.py:**
- `kling_cb.is_open()` check before `KlingService.submit()`
- Sends Telegram alert and returns early if CB is open

**kling.py:**
- Added `_submit_with_backoff` module-level function decorated with tenacity
- `wait_exponential(multiplier=1, min=2, max=32)` — 2s → 8s → 32s on retries
- `stop_after_attempt(3)` — 3 total attempts, then reraise
- `KlingService.submit()` now calls `_submit_with_backoff` instead of `fal_client.submit` directly

## Tests

20 tests across 3 files — all pass:
- `tests/test_kling_circuit_breaker.py` — 9 tests covering all CB methods
- `tests/test_kling_balance.py` — 4 tests covering balance edge cases + constants
- `tests/test_kling_backoff.py` — 7 tests covering poller wiring, pipeline wiring, backoff

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check: PASSED
