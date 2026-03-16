---
phase: quick-007
plan: 01
subsystem: telegram-sync-wrappers
tags: [bugfix, asyncio, apscheduler, telegram, event-loop]
dependency_graph:
  requires: []
  provides: [thread-safe telegram messaging from APScheduler thread pool jobs]
  affects: [src/app/services/telegram.py, src/app/main.py]
tech_stack:
  added: []
  patterns: [run_coroutine_threadsafe with captured event loop instead of asyncio.get_event_loop()]
key_files:
  created: []
  modified:
    - src/app/services/telegram.py
    - src/app/main.py
decisions:
  - "Capture uvicorn event loop at lifespan startup via asyncio.get_event_loop() and store in module-level _event_loop — the only reliable way to reach the live loop from APScheduler threads on Python 3.10+"
  - "Use future.result(timeout=30) to block the calling APScheduler thread until the coroutine completes — ensures caller sees errors and avoids fire-and-forget silencing"
  - "Keep asyncio.run(coro) as the fallback branch — handles test contexts and edge cases where no live uvicorn loop exists"
metrics:
  duration: "~5 min"
  completed: "2026-03-16"
  tasks: 2
  files: 2
---

# Quick Task 007: Fix Telegram Sync Event Loop Summary

**One-liner:** Replaced all five `_sync` wrapper bodies in `telegram.py` with `run_coroutine_threadsafe(_event_loop)` pattern; `main.py` lifespan now captures and wires the uvicorn event loop at startup.

## What Was Fixed

APScheduler `ThreadPoolExecutor` jobs calling `_sync` Telegram wrappers raised `RuntimeError: Event loop is closed` on Python 3.10+. The root cause: `asyncio.get_event_loop()` from a non-main thread returns a closed or newly-created loop — not the live uvicorn loop. The PTB `Bot` httpx client is bound to the original loop and raises when invoked on the wrong one.

## Changes Made

### src/app/services/telegram.py (commit 91f702d)

- Added `_event_loop = None` module-level variable with explanatory comment
- Added `set_event_loop(loop)` function that stores the captured loop globally
- Replaced `send_alert_sync` body: removed `try/except asyncio.get_event_loop()` pattern, replaced with `coro = ...; run_coroutine_threadsafe(coro, _event_loop); future.result(timeout=30)` with `asyncio.run(coro)` fallback
- Replaced `send_approval_message_sync` body: same pattern; preserved post-send `schedule_approval_timeout` call and logger statement
- Replaced `send_publish_confirmation_sync` body: same pattern
- Replaced `send_platform_success_sync` body: same pattern
- Replaced `send_platform_failure_sync` body: same pattern
- The `asyncio.get_event_loop()` inside the **async** `send_approval_message` body (line 119, `loop.run_in_executor` call) was left unchanged — it runs in the uvicorn loop, not a thread

### src/app/main.py (commit 3ae6459)

- Added `import asyncio` at top of file
- Added `set_event_loop` to existing import from `app.services.telegram`
- Added `set_event_loop(asyncio.get_event_loop())` call immediately after `set_fastapi_app(app)` in lifespan startup

## Verification

```
grep -c "run_coroutine_threadsafe.*_event_loop" src/app/services/telegram.py  → 5 code lines (+ 1 comment line = 6 total)
grep -n "set_event_loop" src/app/main.py  → line 15 (import), line 42 (call)
grep -n "get_event_loop" src/app/services/telegram.py  → line 119 only (async body, expected)
```

## Test Results

21 passed, 2 skipped. 1 pre-existing failure (`test_hard_word_limit_constant`) unrelated to this task — `HARD_WORD_LIMIT` was changed from 120 to 90 by a prior quick task; the test was already failing before this fix.

## Deviations from Plan

None. Plan executed exactly as written.

## Deferred Items

- `tests/test_quick_001_script_generation.py::test_hard_word_limit_constant` asserts `HARD_WORD_LIMIT == 120` but value is `90` (changed by quick task 031). Pre-existing failure, out of scope for this task.

## Self-Check: PASSED

- `src/app/services/telegram.py` — exists and contains `_event_loop = None`, `set_event_loop`, and 5 `run_coroutine_threadsafe` calls
- `src/app/main.py` — exists and contains `import asyncio`, `set_event_loop` import, and `set_event_loop(asyncio.get_event_loop())` call in lifespan
- Commits `91f702d` and `3ae6459` verified in git log
