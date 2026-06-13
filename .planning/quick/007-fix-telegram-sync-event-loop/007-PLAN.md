---
phase: quick-007
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - src/app/services/telegram.py
  - src/app/main.py
autonomous: true
requirements: []
must_haves:
  truths:
    - "APScheduler thread pool jobs can send Telegram messages without RuntimeError: Event loop is closed"
    - "All five _sync wrappers use the captured uvicorn event loop via run_coroutine_threadsafe"
    - "main.py lifespan captures the running asyncio loop and passes it to telegram.py on startup"
  artifacts:
    - path: "src/app/services/telegram.py"
      provides: "_event_loop module variable, set_event_loop() function, all five _sync wrappers updated"
      contains: "_event_loop = None"
    - path: "src/app/main.py"
      provides: "lifespan calls set_event_loop(asyncio.get_event_loop()) after set_fastapi_app"
      contains: "set_event_loop"
  key_links:
    - from: "src/app/main.py lifespan"
      to: "src/app/services/telegram._event_loop"
      via: "set_event_loop(asyncio.get_event_loop())"
      pattern: "set_event_loop\\(asyncio\\.get_event_loop\\(\\)\\)"
    - from: "_sync wrappers"
      to: "_event_loop"
      via: "asyncio.run_coroutine_threadsafe(coro, _event_loop)"
      pattern: "run_coroutine_threadsafe.*_event_loop"
---

<objective>
Fix "RuntimeError: Event loop is closed" in all five Telegram _sync wrappers caused by
APScheduler ThreadPoolExecutor threads calling asyncio.get_event_loop() on Python 3.10+.

Purpose: On Python 3.10+, asyncio.get_event_loop() from a thread NOT in the main thread
returns a closed or newly-created loop — not the live uvicorn event loop. The httpx client
inside the PTB Bot is tied to the original loop and raises RuntimeError when invoked on
the wrong one. Capturing the loop at lifespan startup and passing it via a module-level
variable makes run_coroutine_threadsafe use the correct loop every time.

Output: telegram.py with module-level _event_loop + set_event_loop(), all five _sync
wrappers replaced with the run_coroutine_threadsafe pattern; main.py lifespan updated
to call set_event_loop() immediately after set_fastapi_app().
</objective>

<execution_context>
@./.claude/get-shit-done/workflows/execute-plan.md
@./.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
</context>

<tasks>

<task type="auto">
  <name>Task 1: Add _event_loop module variable and set_event_loop() to telegram.py</name>
  <files>src/app/services/telegram.py</files>
  <action>
    After the existing `_fastapi_app = None` declaration (line 11), add:

    ```python
    # Captured uvicorn event loop — set during lifespan startup so APScheduler threads
    # can use run_coroutine_threadsafe instead of asyncio.get_event_loop() (broken on Python 3.10+).
    _event_loop = None


    def set_event_loop(loop) -> None:
        """Called from main.py lifespan to capture the running uvicorn asyncio event loop."""
        global _event_loop
        _event_loop = loop
    ```

    Then replace the body of ALL FIVE _sync wrappers with the correct pattern.
    The pattern for each is identical in structure — only the coroutine call differs:

    send_alert_sync (lines 60-69):
    ```python
    def send_alert_sync(message: str) -> None:
        """Sync wrapper for APScheduler thread pool jobs — same pattern as Phase 1."""
        coro = send_alert(message)
        if _event_loop is not None and _event_loop.is_running():
            future = asyncio.run_coroutine_threadsafe(coro, _event_loop)
            future.result(timeout=30)
        else:
            asyncio.run(coro)
    ```

    send_approval_message_sync (lines 191-211): keep the schedule_approval_timeout call
    and logger.info AFTER the new pattern body:
    ```python
    def send_approval_message_sync(content_history_id: str, video_url: str) -> None:
        """
        Sync wrapper for APScheduler thread pool / executor context.
        Same pattern as send_alert_sync(). Called from _process_completed_render().
        After sending the approval message, schedules a 24h timeout job.
        """
        coro = send_approval_message(content_history_id, video_url)
        if _event_loop is not None and _event_loop.is_running():
            future = asyncio.run_coroutine_threadsafe(coro, _event_loop)
            future.result(timeout=30)
        else:
            asyncio.run(coro)

        # Schedule 24h approval timeout job — lazy import avoids circular import
        from app.scheduler.jobs.approval_timeout import schedule_approval_timeout
        schedule_approval_timeout(content_history_id)
        logger.info("Approval timeout job scheduled for content_history_id=%s", content_history_id[:8])
    ```

    send_publish_confirmation_sync (lines 265-281):
    ```python
    def send_publish_confirmation_sync(
        content_history_id: str,
        scheduled_times: dict,
        video_url: str = "",
        tiktok_copy: str = "",
    ) -> None:
        """Sync wrapper for APScheduler/async approval handler context."""
        coro = send_publish_confirmation(content_history_id, scheduled_times, video_url, tiktok_copy)
        if _event_loop is not None and _event_loop.is_running():
            future = asyncio.run_coroutine_threadsafe(coro, _event_loop)
            future.result(timeout=30)
        else:
            asyncio.run(coro)
    ```

    send_platform_success_sync (lines 298-307):
    ```python
    def send_platform_success_sync(platform: str, content_history_id: str) -> None:
        """Sync wrapper for APScheduler thread context."""
        coro = send_platform_success(platform, content_history_id)
        if _event_loop is not None and _event_loop.is_running():
            future = asyncio.run_coroutine_threadsafe(coro, _event_loop)
            future.result(timeout=30)
        else:
            asyncio.run(coro)
    ```

    send_platform_failure_sync (lines 333-349):
    ```python
    def send_platform_failure_sync(
        platform: str,
        video_url: str,
        post_copy: str,
        error_message: str,
    ) -> None:
        """Sync wrapper for APScheduler thread context."""
        coro = send_platform_failure(platform, video_url, post_copy, error_message)
        if _event_loop is not None and _event_loop.is_running():
            future = asyncio.run_coroutine_threadsafe(coro, _event_loop)
            future.result(timeout=30)
        else:
            asyncio.run(coro)
    ```

    Do NOT change any async function signatures, the `_fastapi_app` variable, or any imports.
    `asyncio` is already imported at line 1.
  </action>
  <verify>
    grep -n "_event_loop" /Users/jesusalbino/Projects/content-creation/src/app/services/telegram.py
    # Must show: module-level _event_loop = None, set_event_loop def, and 5 usages in _sync wrappers.
    # Must NOT show asyncio.get_event_loop() anywhere in a _sync wrapper body.
    grep -n "get_event_loop" /Users/jesusalbino/Projects/content-creation/src/app/services/telegram.py
    # Must return zero results from _sync wrapper bodies (only acceptable in send_approval_message async body line ~111)
  </verify>
  <done>
    - _event_loop = None declared at module level
    - set_event_loop(loop) function defined and exported
    - All five _sync wrapper bodies use: coro = ..., run_coroutine_threadsafe(coro, _event_loop) with future.result(timeout=30), else asyncio.run(coro)
    - No _sync wrapper calls asyncio.get_event_loop()
    - All existing docstrings, async function bodies, and imports unchanged
  </done>
</task>

<task type="auto">
  <name>Task 2: Capture running event loop in main.py lifespan</name>
  <files>src/app/main.py</files>
  <action>
    Add `import asyncio` at the top of main.py if not already present (check current imports
    — it is not in the current file, lines 1-18).

    Add the import after the existing imports block:
    ```python
    import asyncio
    ```

    Also add `set_event_loop` to the import line that already imports `set_fastapi_app`:
    ```python
    from app.services.telegram import set_fastapi_app, set_event_loop
    ```

    Then in the lifespan function, add one line immediately after `set_fastapi_app(app)` (line 40):
    ```python
    set_fastapi_app(app)  # allows APScheduler threads to reach app.state.telegram_app
    set_event_loop(asyncio.get_event_loop())  # capture running uvicorn loop for _sync wrappers
    ```

    Do NOT change any other startup logic, order of operations, or existing comments.
  </action>
  <verify>
    grep -n "set_event_loop\|import asyncio" /Users/jesusalbino/Projects/content-creation/src/app/main.py
    # Must show: import asyncio near top, set_event_loop in import from app.services.telegram,
    # and set_event_loop(asyncio.get_event_loop()) call in lifespan body.
  </verify>
  <done>
    - `import asyncio` present in main.py imports
    - `set_event_loop` imported from app.services.telegram alongside set_fastapi_app
    - `set_event_loop(asyncio.get_event_loop())` called in lifespan immediately after `set_fastapi_app(app)`
    - No other changes to main.py
  </done>
</task>

</tasks>

<verification>
After both tasks complete, verify the full fix is coherent:

1. Confirm no _sync wrapper calls asyncio.get_event_loop():
   `grep -n "get_event_loop" src/app/services/telegram.py`
   Expected: only appears inside the async `send_approval_message` body (loop.run_in_executor call, line ~111) — not in any _sync wrapper.

2. Confirm five _sync wrappers all use _event_loop:
   `grep -c "run_coroutine_threadsafe.*_event_loop" src/app/services/telegram.py`
   Expected: 5

3. Confirm lifespan wires the loop:
   `grep -n "set_event_loop" src/app/main.py`
   Expected: one import line + one call line in lifespan.

4. Run smoke tests:
   `cd /Users/jesusalbino/Projects/content-creation && python -m pytest tests/ -x -q`
   Expected: all tests pass (zero failures).
</verification>

<success_criteria>
- All five _sync wrappers in telegram.py use run_coroutine_threadsafe with _event_loop (not asyncio.get_event_loop())
- _event_loop is populated at startup via set_event_loop() called from main.py lifespan
- APScheduler thread pool jobs calling _sync wrappers no longer raise "RuntimeError: Event loop is closed"
- All existing smoke tests pass
- No async function signatures or behavior changed
</success_criteria>

<output>
After completion, create `.planning/quick/007-fix-telegram-sync-event-loop/007-SUMMARY.md`
with what was changed, files modified, and commit hash.
</output>
