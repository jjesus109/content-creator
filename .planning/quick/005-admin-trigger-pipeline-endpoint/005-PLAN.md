---
phase: quick-005
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - src/app/routes/admin.py
  - src/app/main.py
autonomous: true
requirements: [QUICK-005]

must_haves:
  truths:
    - "POST /admin/trigger-pipeline returns 202 and fires daily_pipeline_job in a background thread"
    - "The endpoint is reachable on Railway without breaking existing health or webhook routes"
  artifacts:
    - path: src/app/routes/admin.py
      provides: "Admin router with trigger-pipeline endpoint"
      exports: [router]
    - path: src/app/main.py
      provides: "Registers admin router on app startup"
      contains: "admin_router"
  key_links:
    - from: src/app/routes/admin.py
      to: src/app/scheduler/jobs/daily_pipeline.py
      via: "direct function call inside threading.Thread"
      pattern: "daily_pipeline_job"
    - from: src/app/main.py
      to: src/app/routes/admin.py
      via: "app.include_router(admin_router)"
      pattern: "include_router.*admin"
---

<objective>
Add POST /admin/trigger-pipeline to the FastAPI app so the daily pipeline job can be fired manually from Railway's HTTP console or curl for testing purposes.

Purpose: Remove the dependency on the scheduler clock when testing the end-to-end pipeline on Railway. The engineer sends one HTTP request instead of waiting for the scheduled cron window.
Output: src/app/routes/admin.py (new) + one-line addition in src/app/main.py to register it.
</objective>

<execution_context>
@./.claude/get-shit-done/workflows/execute-plan.md
@./.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@src/app/main.py
@src/app/routes/health.py
@src/app/scheduler/jobs/daily_pipeline.py
</context>

<tasks>

<task type="auto">
  <name>Task 1: Create src/app/routes/admin.py with POST /admin/trigger-pipeline</name>
  <files>src/app/routes/admin.py</files>
  <action>
Create a new FastAPI router file following the same structure as health.py.

```python
import logging
import threading

from fastapi import APIRouter

from app.scheduler.jobs.daily_pipeline import daily_pipeline_job

router = APIRouter(prefix="/admin", tags=["admin"])
logger = logging.getLogger(__name__)


@router.post("/trigger-pipeline", status_code=202)
async def trigger_pipeline():
    """
    Manually trigger the daily pipeline job for testing purposes.
    Fires daily_pipeline_job() in a daemon thread so the HTTP response
    returns immediately (202 Accepted) while the job runs in the background.

    daily_pipeline_job is synchronous and designed to run in APScheduler's
    ThreadPoolExecutor — a plain threading.Thread is the correct bridge from
    an async FastAPI handler to a blocking synchronous job (same pattern used
    by APScheduler internally).

    WARNING: This endpoint has no authentication. Do NOT expose it to the public
    internet in production — restrict via Railway's private networking or add a
    shared-secret header if the service is publicly reachable.
    """
    logger.info("Manual pipeline trigger requested via /admin/trigger-pipeline.")
    thread = threading.Thread(target=daily_pipeline_job, daemon=True, name="manual-pipeline-trigger")
    thread.start()
    return {"status": "accepted", "message": "Pipeline job triggered in background."}
```

Key decisions:
- `daemon=True` — thread dies with the process; no zombie threads on Railway pod restart.
- `status_code=202` — correct HTTP semantic for "accepted, running asynchronously".
- No request.app.state access needed — daily_pipeline_job() acquires the supabase client and scheduler references internally (same as when called by APScheduler).
- No auth guard in v1 — per the quick-task scope; add Bearer token or IP allowlist if the service is ever public-facing.
  </action>
  <verify>
    <automated>cd /Users/jesusalbino/Projects/content-creation && python -c "from app.routes.admin import router; print('import ok'); routes = [r.path for r in router.routes]; print(routes); assert '/admin/trigger-pipeline' in routes, 'route missing'"</automated>
  </verify>
  <done>src/app/routes/admin.py exists, imports cleanly, and exposes POST /admin/trigger-pipeline at status_code=202.</done>
</task>

<task type="auto">
  <name>Task 2: Register admin router in main.py</name>
  <files>src/app/main.py</files>
  <action>
Add two lines to src/app/main.py following the existing pattern for health_router and webhooks_router.

After the existing imports block, add:
```python
from app.routes.admin import router as admin_router
```

After the existing `app.include_router(webhooks_router)` line, add:
```python
app.include_router(admin_router)
```

The final router registration block should look like:
```python
app.include_router(health_router)
app.include_router(webhooks_router)
app.include_router(admin_router)
```

Do NOT modify the lifespan context manager or any other part of main.py.
  </action>
  <verify>
    <automated>cd /Users/jesusalbino/Projects/content-creation && python -c "from app.main import app; routes = [r.path for r in app.routes]; print(routes); assert '/admin/trigger-pipeline' in routes, 'route not registered on app'"</automated>
  </verify>
  <done>GET /health, POST /webhooks/heygen, and POST /admin/trigger-pipeline all appear in app.routes. App imports without error.</done>
</task>

</tasks>

<verification>
After both tasks complete, confirm:

1. App imports cleanly with no circular import or missing module errors:
   `python -c "from app.main import app; print('ok')"`

2. Route is registered at the correct path:
   `python -c "from app.main import app; assert any('/admin/trigger-pipeline' in str(r.path) for r in app.routes)"`

3. Existing smoke tests still pass:
   `python -m pytest tests/ -x -q 2>&1 | tail -20`
</verification>

<success_criteria>
- POST /admin/trigger-pipeline is reachable (returns 202) when the FastAPI app is running.
- daily_pipeline_job() executes in a background thread — the HTTP response does not block on job completion.
- Existing health and webhook routes are unaffected.
- All existing smoke tests pass.
</success_criteria>

<output>
After completion, create `.planning/quick/005-admin-trigger-pipeline-endpoint/005-SUMMARY.md` summarizing what was built, files modified, and any notable decisions made during execution.
</output>
