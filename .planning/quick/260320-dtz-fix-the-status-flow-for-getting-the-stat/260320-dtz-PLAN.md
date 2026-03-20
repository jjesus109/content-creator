---
phase: quick
plan: 260320-dtz
type: execute
wave: 1
depends_on: []
files_modified:
  - src/app/scheduler/jobs/video_poller.py
  - tests/test_kling_poller.py
autonomous: true
requirements: [BUG-STATUS-01]

must_haves:
  truths:
    - "Kling job polling correctly detects completion using isinstance(status, fal_client.Completed)"
    - "Kling job polling correctly detects in-progress using isinstance(status, fal_client.InProgress)"
    - "Kling job polling correctly detects queued using isinstance(status, fal_client.Queued)"
    - "Video URL is retrieved via fal_client.result() on completion, not status.response"
    - "No failed status type exists — failures are surfaced as exceptions caught by the except block"
  artifacts:
    - path: "src/app/scheduler/jobs/video_poller.py"
      provides: "Correct fal_client type-based status checking"
    - path: "tests/test_kling_poller.py"
      provides: "Tests using fal_client.Completed/InProgress/Queued mock instances"
  key_links:
    - from: "video_poller_job"
      to: "fal_client.status()"
      via: "isinstance checks on returned Status subclass"
      pattern: "isinstance.*fal_client\\.Completed"
---

<objective>
Fix the video poller status detection logic in video_poller.py.

The current code checks `status.status == "completed"` / `status.status == "failed"` (string comparison), but
`fal_client.status()` returns typed class instances: `fal_client.Queued`, `fal_client.InProgress`, or
`fal_client.Completed`. There is no `.status` string attribute on these objects, and there is no
`"failed"` type — render failures surface as HTTP exceptions caught by the existing `except` block.

Additionally, when a job completes, the video URL must be retrieved via `fal_client.result(model, job_id)`,
NOT from `status.response["video"]["url"]` (the `Completed` type has no `.response` attribute).

Purpose: Prevent the poller from silently treating every Kling render as perpetually in-progress (never matching "completed") and crashing with AttributeError when trying to access status.response.
Output: Corrected video_poller.py + updated tests.
</objective>

<execution_context>
@/Users/jesusalbino/Projects/content-creation/.claude/get-shit-done/workflows/execute-plan.md
@/Users/jesusalbino/Projects/content-creation/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@/Users/jesusalbino/Projects/content-creation/.planning/STATE.md
@/Users/jesusalbino/Projects/content-creation/src/app/scheduler/jobs/video_poller.py
@/Users/jesusalbino/Projects/content-creation/tests/test_kling_poller.py
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Fix status detection in video_poller.py to use isinstance checks</name>
  <files>src/app/scheduler/jobs/video_poller.py, tests/test_kling_poller.py</files>
  <behavior>
    - COMPLETED state: `isinstance(status, fal_client.Completed)` is True — calls _process_completed_render + _cancel_self
    - IN_PROGRESS state: `isinstance(status, fal_client.InProgress)` is True — continue polling (no action)
    - QUEUED state: `isinstance(status, fal_client.Queued)` is True — continue polling (no action)
    - FAILED state: there is no Completed — but the existing `except Exception` block handles HTTP errors from fal.ai
    - Video URL: fetched via `fal_client.result(settings.kling_model_version, video_id)` when Completed, returns dict with `video["url"]`
    - Existing tests that mock `status.status = "completed"` / `status.status = "failed"` must be updated to use `fal_client.Completed()` / `fal_client.InProgress()` instances
  </behavior>
  <action>
In `src/app/scheduler/jobs/video_poller.py`, inside `video_poller_job()`, replace the string-based status checks:

BEFORE (broken):
```python
status = fal_client.status(
    settings.kling_model_version,
    video_id,
    with_logs=False,
)
...
if status.status == "completed":
    video_url = status.response["video"]["url"]
    ...
elif status.status == "failed":
    error_msg = str(status.response.get("error", "unknown"))
    ...
# "queued" or "in_progress" — continue polling
```

AFTER (correct):
```python
status = fal_client.status(
    settings.kling_model_version,
    video_id,
    with_logs=False,
)
...
if isinstance(status, fal_client.Completed):
    # Fetch the actual result payload to get the video URL
    result_data = fal_client.result(settings.kling_model_version, video_id)
    video_url = result_data["video"]["url"]
    logger.info(
        "Poller: Kling render complete for job_id=%s, triggering processing",
        video_id,
    )
    from app.services.kling import _process_completed_render
    _process_completed_render(video_id, video_url)
    kling_cb.record_attempt(success=True)
    _cancel_self(video_id)

elif isinstance(status, (fal_client.InProgress, fal_client.Queued)):
    # Still running — continue polling on next interval
    pass

# Any other case (unexpected type) — log and continue polling
```

Note: fal.ai does not return a typed "failed" status. HTTP-level errors (network, rate limit, server error)
raise exceptions caught by the existing `except Exception` block. That block must NOT be changed — it is the
correct error handling for transient failures.

In `tests/test_kling_poller.py`, update the helper `_make_fal_status` and all tests to create real
`fal_client.Completed` / `fal_client.InProgress` / `fal_client.Queued` instances instead of MagicMock with
a `.status` string. Example:

```python
import fal_client as fal_module

def _make_completed_status():
    return fal_module.Completed(logs=None, metrics={})

def _make_in_progress_status():
    return fal_module.InProgress(logs=None)

def _make_queued_status():
    return fal_module.Queued(position=0)
```

For the completed test, also patch `fal_client.result` to return `{"video": {"url": "https://fal.ai/video/test.mp4"}}`.

For the "failed" test (`test_video_poller_on_failed_calls_handle_render_failure`): rewrite to simulate an
exception raised by `fal_client.status()` (e.g., `side_effect=Exception("render error")`) and verify the
except block logs the error without cancelling the poller — transient errors should continue polling. If the
intent of that test was to verify the "failed" signal causes _handle_render_failure, note that _handle_render_failure
is only triggered from _retry_or_fail (timeout path), not from the status check. Keep that test deleted or
repurpose it to test exception handling.
  </action>
  <verify>
    <automated>cd /Users/jesusalbino/Projects/content-creation && python -m pytest tests/test_kling_poller.py -x -q 2>&1</automated>
  </verify>
  <done>
    - video_poller.py uses isinstance(status, fal_client.Completed) to detect completion
    - video_poller.py uses fal_client.result() to retrieve video URL
    - All tests in test_kling_poller.py pass
    - No AttributeError on status.status or status.response in production code
  </done>
</task>

<task type="auto">
  <name>Task 2: Run full test suite to confirm no regressions</name>
  <files></files>
  <action>
Run the full pytest suite to ensure the poller fix does not break anything else.
If any tests fail due to old mock patterns referencing status.status string checks in other test files, fix those
mocks the same way — replace with fal_client.Completed/InProgress/Queued instances.
  </action>
  <verify>
    <automated>cd /Users/jesusalbino/Projects/content-creation && python -m pytest tests/ -x -q 2>&1 | tail -20</automated>
  </verify>
  <done>Full test suite passes with no regressions related to status checking.</done>
</task>

</tasks>

<verification>
- `isinstance(status, fal_client.Completed)` pattern present in video_poller.py
- `fal_client.result()` called on completion to get video URL
- `status.status` string comparison removed from video_poller.py
- `status.response` attribute access removed from video_poller.py
- All pytest tests pass
</verification>

<success_criteria>
- video_poller_job correctly identifies completed Kling renders and triggers _process_completed_render
- video_poller_job correctly continues polling for InProgress and Queued states
- No AttributeError crash when fal_client returns a Completed/InProgress/Queued instance
- All existing poller tests pass with updated mock patterns
</success_criteria>

<output>
After completion, create `.planning/quick/260320-dtz-fix-the-status-flow-for-getting-the-stat/260320-dtz-SUMMARY.md`
</output>
