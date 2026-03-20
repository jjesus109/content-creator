---
phase: quick
plan: 260320-fas
subsystem: kling-circuit-breaker
tags: [bugfix, kling, circuit-breaker, fal-ai, no-op]
dependency_graph:
  requires: []
  provides: [check_balance-no-op]
  affects: [daily_pipeline.py, video_poller_job]
tech_stack:
  added: []
  patterns: [fail-open, no-op-stub]
key_files:
  modified:
    - src/app/services/kling_circuit_breaker.py
    - tests/test_kling_balance.py
    - tests/test_kling_circuit_breaker.py
decisions:
  - "Removed requests import entirely — only used in check_balance(); no other method needed it"
  - "check_balance() replaced with logger.debug + return True — consistent with existing fail-open contract"
  - "BALANCE_ALERT_USD and BALANCE_HALT_USD constants kept — document design intent and referenced by test_kling_cb_constants"
metrics:
  duration: "61 minutes"
  completed_date: "2026-03-20"
  tasks_completed: 3
  files_modified: 3
---

# Quick 260320-fas: Fix KlingCB check_balance() 404 — No-op Stub Summary

**One-liner:** Replaced non-existent fal.ai billing REST call in check_balance() with logger.debug + return True, eliminating 404 errors during video polling.

## What Was Done

KlingCircuitBreakerService.check_balance() was calling `https://fal.ai/v1/billing/balance` which does not exist (fal.ai only exposes `/storage/*` and `/tokens/` paths via their SDK's rest.fal.ai base). This caused 404 errors in every 60-second polling cycle.

Fix: replaced the entire try/except REST block with a no-op that logs at DEBUG level and returns True unconditionally, preserving the fail-open contract documented in STATE.md decision [09-03].

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Replace HTTP balance call with no-op | b741be3 | src/app/services/kling_circuit_breaker.py |
| 2 | Update balance tests for no-op | e33be19 | tests/test_kling_balance.py |
| 3 | Full test suite smoke check + auto-fix stale mocks | 995b35c | tests/test_kling_circuit_breaker.py |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Stale requests.get patches in test_kling_circuit_breaker.py**
- **Found during:** Task 3 (full test suite run)
- **Issue:** `test_check_balance_proceeds_when_above_halt_threshold`, `test_check_balance_halts_when_below_one_dollar`, and `test_check_balance_alerts_but_proceeds_when_between_one_and_five` all patched `app.services.kling_circuit_breaker.requests.get` and `fal_client.auth.fetch_credentials`, both of which are no longer imported after Task 1's change. AttributeError raised at patch target resolution.
- **Fix:** Updated all 3 tests to call check_balance() directly as a no-op. Assertions updated to match the no-op contract (always True, no HTTP call, no alert).
- **Files modified:** tests/test_kling_circuit_breaker.py
- **Commit:** 995b35c

### Deferred Items

**Pre-existing test failure in test_kling_service.py:**
- `test_kling_fal_arguments_locked_spec` fails with `duration=20 vs 15`
- Root cause: `src/app/services/kling.py` has unstaged working-tree changes (DEFAULT_KLING_DURATION=15, committed version has duration=20 hardcoded)
- This was pre-existing before this task and is unrelated to circuit breaker balance changes
- Logged to deferred items — NOT in scope of this fix

## Self-Check

### Files Exist
- src/app/services/kling_circuit_breaker.py: present, no requests import, no HTTP call in check_balance()
- tests/test_kling_balance.py: present, 5 tests, no stale patches
- tests/test_kling_circuit_breaker.py: present, 9 tests, no stale patches

### Commits Exist
- b741be3: fix(260320-fas): replace check_balance() HTTP call with no-op
- e33be19: test(260320-fas): update balance tests for no-op check_balance()
- 995b35c: fix(260320-fas): update stale requests mocks in test_kling_circuit_breaker.py

## Self-Check: PASSED

All 5 tests in test_kling_balance.py pass. All 9 tests in test_kling_circuit_breaker.py pass. No requests import or fal.ai billing URL remains in kling_circuit_breaker.py. Module imports cleanly.
