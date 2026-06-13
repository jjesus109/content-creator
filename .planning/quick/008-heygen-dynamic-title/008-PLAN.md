---
phase: quick-008
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - src/app/services/heygen.py
  - src/app/scheduler/jobs/daily_pipeline.py
autonomous: true
requirements: [QUICK-008]
must_haves:
  truths:
    - "HeyGen video title reflects the topic_summary provided by the pipeline"
    - "When no title is passed, the title falls back to 'Video YYYY-MM-DD' (today's date)"
    - "Titles longer than 100 characters are truncated before submission"
    - "Existing callers that omit the title parameter continue to work unchanged"
  artifacts:
    - path: src/app/services/heygen.py
      provides: "HeyGenService.submit() with optional title param"
      contains: "title: str | None = None"
    - path: src/app/scheduler/jobs/daily_pipeline.py
      provides: "Pipeline passes topic_summary as title to heygen_svc.submit()"
      contains: "title=topic_summary"
  key_links:
    - from: src/app/scheduler/jobs/daily_pipeline.py
      to: src/app/services/heygen.py
      via: "heygen_svc.submit(script_text=script, background_url=background_url, title=topic_summary)"
      pattern: "submit.*title=topic_summary"
---

<objective>
Replace the hardcoded `"Daily video"` title in HeyGen API payload with the `topic_summary`
generated during the pipeline run, falling back to a date-based title when none is supplied.

Purpose: Each HeyGen render is identifiable in the HeyGen dashboard by its topic rather than
a generic label, making debugging and content review easier.
Output: `HeyGenService.submit()` accepts an optional `title` param; `daily_pipeline.py` passes
`topic_summary` at the call site.
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
  <name>Task 1: Add optional title param to HeyGenService.submit() and build title in payload</name>
  <files>src/app/services/heygen.py</files>
  <action>
    Modify `HeyGenService.submit()` at line 79:

    1. Change the signature from:
       ```python
       def submit(self, script_text: str, background_url: str) -> str:
       ```
       to:
       ```python
       def submit(self, script_text: str, background_url: str, title: str | None = None) -> str:
       ```

    2. Inside the method body, before building `payload`, add title resolution logic:
       ```python
       from datetime import date
       resolved_title = (title or f"Video {date.today().isoformat()}")[:100]
       ```

    3. Replace the hardcoded `"title": "Daily video"` line in `payload` (line 105) with:
       ```python
       "title": resolved_title,
       ```

    4. Update the existing docstring Args section to document the new parameter:
       ```
       title: Optional human-readable label for the HeyGen dashboard. Falls back to
              'Video YYYY-MM-DD' (today's date) if not provided. Truncated to 100 chars.
       ```

    The `from datetime import date` import should be placed inline just before `resolved_title`
    assignment (not at module top) to keep the diff minimal and follow the lazy-import convention
    already used elsewhere in this file.
  </action>
  <verify>
    <automated>cd /Users/jesusalbino/Projects/content-creation && python -c "
import inspect
from app.services.heygen import HeyGenService
sig = inspect.signature(HeyGenService.submit)
assert 'title' in sig.parameters, 'title param missing'
assert sig.parameters['title'].default is None, 'title default must be None'
src = inspect.getsource(HeyGenService.submit)
assert 'resolved_title' in src, 'resolved_title not found'
assert 'Daily video' not in src, 'hardcoded title still present'
assert '[:100]' in src, 'truncation missing'
print('OK: submit() signature and payload title verified')
"
    </automated>
  </verify>
  <done>
    `HeyGenService.submit()` accepts `title: str | None = None`. The payload uses a resolved title
    built from the supplied value (or date fallback), truncated to 100 chars. The string
    `"Daily video"` no longer appears in the method body.
  </done>
</task>

<task type="auto">
  <name>Task 2: Pass topic_summary as title at heygen_svc.submit() call site in daily_pipeline.py</name>
  <files>src/app/scheduler/jobs/daily_pipeline.py</files>
  <action>
    In `daily_pipeline_job()`, locate the `heygen_svc.submit()` call at line 145:
    ```python
    heygen_job_id = heygen_svc.submit(script_text=script, background_url=background_url)
    ```
    Change it to:
    ```python
    heygen_job_id = heygen_svc.submit(script_text=script, background_url=background_url, title=topic_summary)
    ```

    `topic_summary` is already in scope at this point (assigned at line 75 in the attempt loop).
    No other changes needed — the fail-soft path that calls `_save_to_content_history` without
    submitting to HeyGen does NOT call `heygen_svc.submit()`, so no change is required there.
  </action>
  <verify>
    <automated>cd /Users/jesusalbino/Projects/content-creation && python -c "
import inspect
from app.scheduler.jobs import daily_pipeline
src = inspect.getsource(daily_pipeline.daily_pipeline_job)
assert 'title=topic_summary' in src, 'title=topic_summary not found in daily_pipeline_job'
print('OK: daily_pipeline_job passes title=topic_summary to heygen_svc.submit()')
" && python -m pytest tests/ -x -q 2>&1 | tail -10
    </automated>
  </verify>
  <done>
    `heygen_svc.submit()` is called with `title=topic_summary`. All existing smoke tests pass.
  </done>
</task>

</tasks>

<verification>
Full check after both tasks:

```bash
cd /Users/jesusalbino/Projects/content-creation && python -m pytest tests/ -x -q
```

Expected: all smoke tests pass (no regressions from signature change).

Also confirm no remaining hardcoded title string:
```bash
grep -n '"Daily video"' src/app/services/heygen.py
```
Expected: no output.
</verification>

<success_criteria>
- `HeyGenService.submit()` signature includes `title: str | None = None` with no breaking change
- Payload `"title"` field uses `topic_summary` truncated to 100 chars when supplied, or `"Video YYYY-MM-DD"` as fallback
- `daily_pipeline_job()` passes `title=topic_summary` to `heygen_svc.submit()`
- All smoke tests pass
- String `"Daily video"` does not appear anywhere in `heygen.py`
</success_criteria>

<output>
After completion, create `.planning/quick/008-heygen-dynamic-title/008-SUMMARY.md`
</output>
