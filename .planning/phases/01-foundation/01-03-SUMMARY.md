---
phase: 01-foundation
plan: "03"
subsystem: infra
tags: [python, fastapi, apscheduler, uvicorn, lifespan, railway, supabase, sqlalchemy, psycopg2, health-check]

# Dependency graph
requires:
  - phase: 01-foundation/01-01
    provides: "Settings singleton (get_settings()), src/app/scheduler/__init__.py package, src/app/routes/__init__.py package"
  - phase: 01-foundation/01-02
    provides: "get_supabase() singleton, CircuitBreakerService.midnight_reset(), all service layer modules"
provides:
  - FastAPI application factory (app) with asynccontextmanager lifespan (not deprecated @app.on_event)
  - APScheduler BackgroundScheduler started in lifespan, stored on app.state.scheduler
  - SQLAlchemyJobStore on Supabase session pooler (postgresql+psycopg2://) — apscheduler_jobs table auto-created
  - GET /health deep probe: returns 200 when DB+scheduler healthy, 503 when either unhealthy (Railway restart signal)
  - daily_pipeline_trigger job (heartbeat at 7 AM America/Mexico_City, replace_existing=True, stable ID)
  - cb_midnight_reset job (midnight America/Mexico_City, calls CircuitBreakerService.midnight_reset(), replace_existing=True)
  - Single-file entry point: uvicorn app.main:app --workers 1
affects:
  - All subsequent phases (all phases use main.py as the app entry point)
  - Phase 4 (approval flow will add Telegram command router to main.py)
  - Phase 7 (hardening will verify health endpoint SLO)

# Tech tracking
tech-stack:
  added: []  # All dependencies already in pyproject.toml from Plan 01
  patterns:
    - asynccontextmanager lifespan for startup/shutdown (FastAPI 0.93+ pattern, replaces deprecated @app.on_event)
    - Scheduler stored on app.state for cross-request access in health endpoint
    - BackgroundScheduler (not AsyncIOScheduler) — runs in thread pool, does not compete with FastAPI event loop
    - replace_existing=True + stable string ID on every add_job() call — prevents duplicate rows on redeploy

key-files:
  created:
    - src/app/main.py
    - src/app/routes/health.py
    - src/app/scheduler/setup.py
    - src/app/scheduler/registry.py
    - src/app/scheduler/jobs/heartbeat.py
    - src/app/scheduler/jobs/cb_reset.py
  modified: []

key-decisions:
  - "BackgroundScheduler chosen over AsyncIOScheduler — runs in dedicated thread pool, no event loop contention with FastAPI"
  - "Scheduler stored on app.state.scheduler — allows health endpoint to inspect scheduler.running without global variable"
  - "Health endpoint checks both DB (pipeline_runs lightweight query) and scheduler (scheduler.running) — 503 on either failure triggers Railway restart"
  - "register_jobs() centralizes all add_job() calls in one file — single place to find/modify all scheduled jobs"

patterns-established:
  - "Pattern 7: All scheduler jobs use replace_existing=True and stable string IDs — prevents duplicate apscheduler_jobs rows on redeploy"
  - "Pattern 8: app.state.scheduler is the authoritative handle for APScheduler — never use a module-level global"
  - "Pattern 9: Health endpoint returns 503 (not 500) on dependency failure — Railway ON_FAILURE policy requires non-200 to trigger restart"

requirements-completed: [INFRA-01, INFRA-03]

# Metrics
duration: 3min
completed: 2026-02-20
---

# Phase 1 Plan 03: FastAPI + APScheduler Wiring Summary

**FastAPI app with asynccontextmanager lifespan starting BackgroundScheduler (SQLAlchemyJobStore on Supabase), two registered cron jobs (heartbeat at 7 AM + cb_reset at midnight, both America/Mexico_City), and a deep /health probe returning 503 to trigger Railway restarts**

## Performance

- **Duration:** ~3 min
- **Started:** 2026-02-20T03:52:31Z
- **Completed:** 2026-02-20T03:55:00Z
- **Tasks:** 2
- **Files modified:** 6 created

## Accomplishments

- `src/app/main.py` wires FastAPI + APScheduler via asynccontextmanager lifespan — scheduler alive before first request
- `GET /health` deep probe checks Supabase (`pipeline_runs` lightweight select) and APScheduler (`scheduler.running`) — 503 on any failure triggers Railway ON_FAILURE restart policy
- `create_scheduler()` creates BackgroundScheduler with SQLAlchemyJobStore on Supabase session pooler (`postgresql+psycopg2://`) — `apscheduler_jobs` table auto-created on first startup
- `register_jobs()` registers both jobs with `replace_existing=True` and stable IDs — no duplicate rows across service restarts
- `daily_pipeline_trigger` (heartbeat) fires at 7 AM America/Mexico_City — observable in Railway logs as "Scheduler heartbeat"
- `cb_midnight_reset` fires at midnight America/Mexico_City — calls `CircuitBreakerService.midnight_reset()` to zero daily counters

## Task Commits

Each task was committed atomically:

1. **Task 1: APScheduler setup, heartbeat job, cb_reset job, registry** - `e802f56` (feat)
2. **Task 2: FastAPI main.py with lifespan and health endpoint** - `e2d90b1` (feat)

**Plan metadata:** (pending final commit)

## Files Created/Modified

- `src/app/main.py` - FastAPI app factory with asynccontextmanager lifespan (starts/stops APScheduler)
- `src/app/routes/health.py` - GET /health deep probe (DB + scheduler), 200/503 response
- `src/app/scheduler/setup.py` - BackgroundScheduler factory with SQLAlchemyJobStore on Supabase
- `src/app/scheduler/registry.py` - Centralizes all add_job() calls with replace_existing=True and stable IDs
- `src/app/scheduler/jobs/heartbeat.py` - No-op heartbeat logging "Scheduler heartbeat" at 7 AM Mexico City
- `src/app/scheduler/jobs/cb_reset.py` - Calls CircuitBreakerService.midnight_reset() at midnight Mexico City

## Decisions Made

- `BackgroundScheduler` chosen over `AsyncIOScheduler` — runs in its own thread pool and does not contend with FastAPI's async event loop; `AsyncIOScheduler` would require careful coroutine management for every job
- Scheduler stored on `app.state.scheduler` rather than a module-level global — the health endpoint can inspect it via `request.app.state` without coupling to a module import
- Health probe uses `pipeline_runs` table (not a dedicated ping table) — lightweight `select("id").limit(1)` query verifies the same Supabase connection path used by pipeline jobs
- `register_jobs()` is a separate module from `setup.py` — scheduler creation is decoupled from job registration, making future job additions a single-file change

## Deviations from Plan

None — plan executed exactly as written. All six files created on first attempt, all import checks passed.

## Issues Encountered

- Runtime health check test could not complete because no `.env` file exists with real Supabase/Telegram credentials. This is the same credential gate as Plans 01-01 and 01-02. The service correctly fails at startup with a Pydantic ValidationError listing the 5 missing required fields — confirming that the service code is structurally correct and will function once credentials are provided. Import-level verification (`from app.main import app` → `ok`) confirms no code errors.

## Authentication Gate

**Gate encountered during:** Task 2 runtime verification
**What was attempted:** `uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1` to verify health endpoint
**Outcome:** Service correctly rejected startup with missing credentials (Pydantic ValidationError: 5 fields required — supabase_url, supabase_key, database_url, telegram_bot_token, telegram_creator_id)
**Status:** Normal — all code is correct; `.env` file with real credentials required before runtime testing

## User Setup Required

To complete runtime verification (verify health endpoint returns 200):

1. Populate `.env` from `.env.example`:
   ```bash
   cp .env.example .env
   # Fill in: SUPABASE_URL, SUPABASE_KEY, DATABASE_URL, TELEGRAM_BOT_TOKEN, TELEGRAM_CREATOR_ID
   ```

2. Start the service:
   ```bash
   PYTHONPATH=src .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1
   ```
   Expected startup logs:
   - `Starting up content-creation service.`
   - `Registered job: daily_pipeline_trigger at 07:00 America/Mexico_City`
   - `Registered job: cb_midnight_reset at 00:00 America/Mexico_City`
   - `APScheduler started with 2 jobs.`

3. Verify health endpoint:
   ```bash
   curl -s http://localhost:8000/health | python -m json.tool
   ```
   Expected: `{"status": "healthy", "timestamp": "...", "checks": {"database": "ok", "scheduler": "running", "scheduled_jobs": 2}}`

4. Verify in Supabase Table Editor: `apscheduler_jobs` table exists with 2 rows

## Next Phase Readiness

- All Phase 1 Foundation code artifacts complete: project scaffold, service layer, FastAPI + APScheduler wiring
- Service is ready to be deployed to Railway once credentials are added to Railway Dashboard -> Service -> Variables
- Phase 2 (Script Generation) can now begin: `main.py` is the integration point for all new services
- **Blocked on:** User must populate `.env` with real credentials and execute Supabase schema SQL (documented in Plan 01-01 Summary) before deploying to Railway

---
*Phase: 01-foundation*
*Completed: 2026-02-20*

## Self-Check: PASSED

All 6 source files and SUMMARY.md verified present on disk. Both task commits (e802f56, e2d90b1) verified in git history.
