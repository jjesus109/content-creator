---
phase: quick-005
plan: 01
subsystem: admin-api
tags: [fastapi, admin, pipeline, manual-trigger]
dependency_graph:
  requires: [src/app/scheduler/jobs/daily_pipeline.py]
  provides: [POST /admin/trigger-pipeline]
  affects: [src/app/main.py]
tech_stack:
  added: []
  patterns: [threading.Thread daemon=True for sync job from async handler, 202 Accepted for fire-and-forget]
key_files:
  created: [src/app/routes/admin.py]
  modified: [src/app/main.py]
decisions:
  - daemon=True on threading.Thread so thread dies with the process on Railway pod restart
  - status_code=202 correct HTTP semantic for fire-and-forget async job
  - No auth guard in v1 — quick task scope; add Bearer token or IP allowlist if service becomes public
  - No app.state access needed — daily_pipeline_job() acquires its own supabase client internally
metrics:
  duration: "~2 min"
  completed: "2026-03-15"
  tasks: 2
  files: 2
---

# Quick Task 005: Admin Trigger Pipeline Endpoint Summary

**One-liner:** POST /admin/trigger-pipeline fires daily_pipeline_job() in a daemon thread and returns 202 immediately, enabling manual end-to-end pipeline testing on Railway without waiting for the scheduler clock.

## What Was Built

A new FastAPI admin router (`src/app/routes/admin.py`) with a single endpoint:

- **POST /admin/trigger-pipeline** — status 202 Accepted
- Spawns `daily_pipeline_job()` in a `threading.Thread(daemon=True)` so the HTTP response returns immediately while the full pipeline (script generation, HeyGen submission, Telegram notification) runs in the background
- Registered on the FastAPI app via `app.include_router(admin_router)` in `main.py`

## Files Modified

| File | Change |
|------|--------|
| `src/app/routes/admin.py` | Created — admin router with POST /admin/trigger-pipeline |
| `src/app/main.py` | Added import and `app.include_router(admin_router)` |

## Verification Results

- `from app.routes.admin import router` imports cleanly
- `/admin/trigger-pipeline` present in `router.routes`
- `from app.main import app` imports cleanly; all 3 routes present: `/health`, `/webhooks/heygen`, `/admin/trigger-pipeline`
- 21 of 22 smoke tests pass (1 pre-existing failure in `test_quick_001_script_generation.py::test_hard_word_limit_constant` — `HARD_WORD_LIMIT` was changed to 90 in commit `31df53e` before this task; unrelated to admin endpoint)

## Decisions Made

1. **daemon=True** — thread dies with the process; prevents zombie threads on Railway pod restart
2. **status_code=202** — correct HTTP semantic for "accepted, running asynchronously"
3. **No auth guard in v1** — per quick-task scope; the plan explicitly notes this; add a Bearer token or IP allowlist before exposing the service publicly
4. **threading.Thread over asyncio.create_task** — `daily_pipeline_job()` is synchronous and blocking (designed for APScheduler's ThreadPoolExecutor); `threading.Thread` is the correct bridge from an async FastAPI handler to a blocking sync function

## Deviations from Plan

None — plan executed exactly as written.

## Deferred Items

**Pre-existing test failure** (not introduced by this task):
- `tests/test_quick_001_script_generation.py::test_hard_word_limit_constant` asserts `HARD_WORD_LIMIT == 120` but the constant is currently `90` (changed in commit `31df53e fix: Adjust script and video generation length`). This test needs to be updated to match the current value or the constant needs to be restored. Out of scope for quick task 005.

## Self-Check: PASSED

- `src/app/routes/admin.py` exists and contains `POST /admin/trigger-pipeline`
- `src/app/main.py` contains `admin_router` import and `app.include_router(admin_router)`
- Commit `6b8d14f` (Task 1) exists
- Commit `ab3daf8` (Task 2) exists
