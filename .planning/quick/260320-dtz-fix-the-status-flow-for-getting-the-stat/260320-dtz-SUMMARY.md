---
phase: quick
plan: 260320-dtz
subsystem: video-poller
tags: [bug-fix, fal-client, kling, status-detection, tdd]
dependency_graph:
  requires: []
  provides: [correct-kling-status-detection, fal-result-fetch]
  affects: [video_poller.py, test_kling_poller.py, test_kling_backoff.py]
tech_stack:
  added: []
  patterns: [isinstance-type-dispatch, fal_client.result-for-url-retrieval]
key_files:
  created: []
  modified:
    - src/app/scheduler/jobs/video_poller.py
    - tests/test_kling_poller.py
    - tests/test_kling_backoff.py
decisions:
  - "fal_client returns typed instances (Completed/InProgress/Queued), not dicts with .status string — isinstance dispatch is the correct pattern"
  - "fal_client.result() must be called on Completed to get video URL — Completed has no .response attribute"
  - "No typed 'failed' status exists — HTTP errors surface as exceptions caught by existing except block, which continues polling"
  - "Tests in test_kling_backoff.py updated to match new semantics: exception path does not call record_attempt(success=False)"
metrics:
  duration: ~15min
  completed: 2026-03-20
  tasks_completed: 2
  tasks_total: 2
  files_changed: 3
---

# Quick Task 260320-dtz: Fix Kling Poller Status Detection Summary

**One-liner:** Replaced string-comparison status checks with fal_client isinstance dispatch and fal_client.result() URL retrieval, preventing silent never-complete and AttributeError crashes.

## What Was Done

Fixed `video_poller.py` to use the correct fal_client API. The code was checking `status.status == "completed"` but `fal_client.status()` returns typed class instances — `fal_client.Completed`, `fal_client.InProgress`, or `fal_client.Queued` — none of which have a `.status` string attribute. Additionally, the code accessed `status.response["video"]["url"]` but `Completed` has no `.response` attribute.

The result: every Kling render appeared perpetually in-progress (never matching "completed") and crashed with AttributeError when the Completed branch was somehow reached.

## Tasks Completed

| Task | Description | Commit |
|------|-------------|--------|
| 1 | Fix status detection + update test_kling_poller.py (TDD) | 8f8b0d1 |
| 2 | Fix test_kling_backoff.py old mock patterns + full suite pass | fabef7e |

## Changes Made

### src/app/scheduler/jobs/video_poller.py

- Replaced `if status.status == "completed":` with `if isinstance(status, fal_client.Completed):`
- Replaced `status.response["video"]["url"]` with `fal_client.result(model, video_id)["video"]["url"]`
- Replaced `elif status.status == "failed":` with `elif isinstance(status, (fal_client.InProgress, fal_client.Queued)): pass`
- Removed the entire "failed" status branch — failures are exceptions caught by the existing `except Exception` block
- Updated log message to use `type(status).__name__` instead of `status.status`

### tests/test_kling_poller.py

- Replaced `_make_fal_status(status_string)` helper with `_make_completed_status()`, `_make_in_progress_status()`, `_make_queued_status()` using real fal_client instances
- Added `mock_fal.result.return_value = mock_result` for completed tests
- Added explicit `mock_fal.Completed/InProgress/Queued = fal_module.*` on patched fal_client objects
- Rewrote "failed" test as `test_video_poller_on_exception_logs_and_continues_polling` — simulates exception from `fal_client.status()`, verifies poller is NOT cancelled
- Added `test_video_poller_on_in_progress_continues_polling` and `test_video_poller_on_queued_continues_polling`

### tests/test_kling_backoff.py

- Same helper replacement as above
- Rewrote `test_video_poller_records_failure_on_kling_failed` as `test_video_poller_does_not_record_attempt_on_transient_exception` — exception path does NOT call `record_attempt`
- Updated `test_video_poller_records_success_on_kling_completed` to use Completed instance + `mock_fal.result`

## Test Results

- `tests/test_kling_poller.py`: 10/10 pass
- `tests/test_kling_backoff.py`: 7/7 pass
- Full suite (excluding pre-existing failure): 154 pass, 5 skip

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] test_kling_backoff.py also used old string-based mock patterns**
- **Found during:** Task 2 full suite run
- **Issue:** `test_video_poller_records_failure_on_kling_failed` and `test_video_poller_records_success_on_kling_completed` both used the old `_make_fal_status("completed"/"failed")` helper which creates MagicMock objects with `.status` string — incompatible with the new isinstance-based production code
- **Fix:** Replaced both tests with real fal_client instances; rewrote "failed" test to verify exception path behavior (no record_attempt, no cancel)
- **Files modified:** tests/test_kling_backoff.py
- **Commit:** fabef7e

## Deferred Issues

**test_kling_service.py::test_kling_fal_arguments_locked_spec** — Pre-existing failure unrelated to this task. `kling.py` has `DEFAULT_KLING_DURATION = 15` in the working tree but the test expects `duration == 20`. This change was already present before this task started. Not caused by our changes.

## Self-Check: PASSED

- video_poller.py: FOUND
- test_kling_poller.py: FOUND
- test_kling_backoff.py: FOUND
- Commit 8f8b0d1: FOUND
- Commit fabef7e: FOUND
- isinstance check in video_poller.py: FOUND
- fal_client.result() call in video_poller.py: FOUND
- status.status string comparison: REMOVED (not present)
