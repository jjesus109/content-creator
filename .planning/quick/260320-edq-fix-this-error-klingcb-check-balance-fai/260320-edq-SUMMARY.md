---
phase: quick
plan: 260320-edq
subsystem: kling-circuit-breaker
tags: [bug-fix, fal-api, balance-check, tests]
dependency_graph:
  requires: []
  provides: [working-check_balance-via-rest]
  affects: [kling_circuit_breaker.py, test_kling_circuit_breaker.py, test_kling_balance.py]
tech_stack:
  added: []
  patterns: [requests.get for fal.ai billing REST API]
key_files:
  created: []
  modified:
    - src/app/services/kling_circuit_breaker.py
    - tests/test_kling_circuit_breaker.py
    - tests/test_kling_balance.py
decisions:
  - "Use requests.get to https://fal.ai/v1/billing/balance — fal-client 0.13.1 has no get_balance() method"
  - "Use fal_client.auth.fetch_credentials() for Authorization header (returns raw key string)"
  - "Add requests import to kling_circuit_breaker.py (was missing, not pre-existing)"
metrics:
  duration: ~5 minutes
  completed_date: "2026-03-20"
  tasks_completed: 2
  files_modified: 3
---

# Quick Task 260320-edq: Fix KlingCB check_balance() fal_client.get_balance AttributeError

**One-liner:** Fixed check_balance() by replacing non-existent fal_client.get_balance() with direct REST call to https://fal.ai/v1/billing/balance using requests.get + fal_client.auth.fetch_credentials() for auth.

## What Was Done

The `KlingCircuitBreakerService.check_balance()` method was calling `fal_client.get_balance()` which does not exist in fal-client 0.13.1. This caused an `AttributeError` every 60 seconds during video polling, breaking the balance guard entirely.

### Task 1: Fix check_balance() implementation

Replaced the broken `fal_client.get_balance()` call with a REST call to the fal.ai billing API:

- Added `import requests` at module level in `kling_circuit_breaker.py`
- New implementation uses `import fal_client.auth as _fal_auth` inside try block to get credentials
- Calls `requests.get("https://fal.ai/v1/billing/balance", headers={"Authorization": f"Key {credentials}"}, timeout=10)`
- All threshold logic, alerts, logging, and fail-open behavior unchanged

**Commit:** `3f0a961`

### Task 2: Update balance tests

Updated 5 tests across 2 files to mock `requests.get` instead of the non-existent `fal_client.get_balance`:

- `tests/test_kling_circuit_breaker.py`: 3 balance tests updated
- `tests/test_kling_balance.py`: 2 balance tests updated
- Removed `patch.dict("sys.modules", {"fal_client": mock_fal})` pattern from these tests
- Added `patch("app.services.kling_circuit_breaker.requests.get", return_value=mock_resp)` pattern
- Added `patch("fal_client.auth.fetch_credentials", return_value="test_key_123")` to all balance tests

**Commit:** `dd578c9`

## Verification Results

- All 13 tests in `test_kling_circuit_breaker.py` + `test_kling_balance.py` pass
- Full test suite (154 passed, 5 skipped) with no regressions introduced by this task
- Manual verification: `check_balance()` returns True with mocked $10 balance, no AttributeError

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Import] Added `import requests` to kling_circuit_breaker.py**
- **Found during:** Task 1
- **Issue:** The plan stated "The code already imports `requests` at the top of the file (line 16)" but the file had no `requests` import — only `logging`, `datetime`, `supabase`, and `telegram` imports
- **Fix:** Added `import requests` after the `from datetime import datetime, timezone` line
- **Files modified:** `src/app/services/kling_circuit_breaker.py`
- **Commit:** `3f0a961`

## Deferred Items

**Pre-existing test failure (out of scope):** `tests/test_kling_service.py::test_kling_fal_arguments_locked_spec` fails because `kling.py` has `DEFAULT_KLING_DURATION = 15` but the test expects `duration == 20`. This mismatch existed before this task (kling.py shown as modified in git status at task start). Logged to deferred-items.md.

## Self-Check: PASSED

- `src/app/services/kling_circuit_breaker.py` — FOUND
- `tests/test_kling_circuit_breaker.py` — FOUND
- `tests/test_kling_balance.py` — FOUND
- Commit `3f0a961` — FOUND
- Commit `dd578c9` — FOUND
