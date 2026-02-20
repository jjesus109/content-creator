---
phase: 01-foundation
plan: "01"
subsystem: infra
tags: [python, fastapi, pydantic, supabase, postgresql, pgvector, railway, docker, apscheduler, uv]

# Dependency graph
requires: []
provides:
  - Python 3.12 project with locked dependencies (uv.lock, 70 packages)
  - Multi-stage Dockerfile with uv, non-root appuser, --workers 1
  - Railway deployment manifest with healthcheckPath and restartPolicyType
  - Pydantic BaseSettings class as single source of truth for all env var config
  - Four Pydantic models: PipelineRun, ContentHistory, MoodProfile, CircuitBreakerState
  - Supabase schema SQL with pgvector HNSW index (user must execute in SQL Editor)
  - Package directory structure: src/app/{routes,models,services,scheduler,scheduler/jobs}
affects:
  - 01-02 (APScheduler service uses scheduler/ package and Settings)
  - 01-03 (FastAPI app uses models, settings, and routes/ package)
  - All subsequent phases (models and settings are shared across all services)

# Tech tracking
tech-stack:
  added:
    - fastapi>=0.115
    - uvicorn[standard]>=0.32
    - pydantic-settings>=2.7
    - APScheduler==3.11.2
    - sqlalchemy>=2.0
    - psycopg2-binary>=2.9
    - supabase>=2.0
    - httpx>=0.28
    - python-telegram-bot==21.*
    - pytz>=2024.1
    - python-dotenv>=1.0
    - uv (package manager, installed via Homebrew)
  patterns:
    - BaseSettings with lru_cache singleton for all configuration
    - Pydantic models mirror Supabase table columns exactly
    - src/ layout with src/app/ as importable package
    - Multi-stage Docker build: builder (uv) + runtime (non-root appuser)
    - Single process deployment (--workers 1) for APScheduler compatibility

key-files:
  created:
    - pyproject.toml
    - uv.lock
    - Dockerfile
    - railway.toml
    - .env.example
    - .gitignore
    - src/app/__init__.py
    - src/app/settings.py
    - src/app/models/pipeline.py
    - src/app/models/content.py
    - src/app/models/mood.py
    - src/app/models/circuit_breaker.py
    - src/app/routes/__init__.py
    - src/app/services/__init__.py
    - src/app/scheduler/__init__.py
    - src/app/scheduler/jobs/__init__.py
  modified: []

key-decisions:
  - "Use dependency-groups.dev (PEP 735) instead of deprecated tool.uv.dev-dependencies"
  - "circuit_breaker_state includes last_trip_at column for rolling 7-day escalation window"
  - "Settings.database_url requires postgresql+psycopg2:// (sync driver) not asyncpg — required for APScheduler SQLAlchemyJobStore"
  - "Single process (--workers 1) enforced in both Dockerfile CMD and railway.toml startCommand — APScheduler must not be forked"

patterns-established:
  - "Pattern 1: Always import settings via get_settings() — never os.environ directly"
  - "Pattern 2: Pydantic model field names match Supabase column names exactly (snake_case)"
  - "Pattern 3: Docker CMD and railway.toml startCommand both specify --workers 1 for APScheduler compatibility"

requirements-completed: [INFRA-01, INFRA-02, SCRTY-01]

# Metrics
duration: 3min
completed: 2026-02-20
---

# Phase 1 Plan 01: Project Scaffold Summary

**FastAPI+uv Python 3.12 project with locked deps, multi-stage Dockerfile, Railway config, Pydantic BaseSettings, and four Pydantic models mirroring Supabase tables (pgvector embedding on content_history)**

## Performance

- **Duration:** ~3 min
- **Started:** 2026-02-20T03:41:00Z
- **Completed:** 2026-02-20T03:44:33Z
- **Tasks:** 2 (code complete; Supabase SQL execution requires user action)
- **Files modified:** 16 created

## Accomplishments

- Python 3.12 project scaffolded with `uv sync --locked` resolving 70 packages cleanly
- `src/app/settings.py` as single source of truth: all env vars typed and validated via Pydantic BaseSettings with `lru_cache` singleton
- Four Pydantic models (`PipelineRun`, `ContentHistory`, `MoodProfile`, `CircuitBreakerState`) all importable with no errors
- Multi-stage Dockerfile with non-root `appuser` and `--workers 1` enforced for APScheduler
- railway.toml with `healthcheckPath = "/health"` and `restartPolicyType = "ON_FAILURE"`
- `.env.example` with placeholder-only values — no secrets in committed code

## Task Commits

Each task was committed atomically:

1. **Task 1: Project scaffold** - `80b02a9` (chore)
2. **Task 2: Pydantic settings + models** - `6acf131` (feat)
3. **Deviation fix: pyproject.toml deprecation** - `4058d69` (fix)

**Plan metadata:** (pending final commit)

## Files Created/Modified

- `pyproject.toml` - Python 3.12 project with all pinned dependencies
- `uv.lock` - Locked dependency graph (70 packages)
- `Dockerfile` - Multi-stage build: builder (uv) + runtime (non-root appuser, --workers 1)
- `railway.toml` - healthcheckPath=/health, restartPolicyType=ON_FAILURE
- `.env.example` - All env vars documented with placeholder values
- `.gitignore` - Covers .env, __pycache__, .venv, *.pyc, dist/, .eggs/
- `src/app/settings.py` - BaseSettings with lru_cache, all typed fields
- `src/app/models/pipeline.py` - PipelineRun model (status Literal, cost_usd Decimal)
- `src/app/models/content.py` - ContentHistory model (embedding: list[float] 1536 dims)
- `src/app/models/mood.py` - MoodProfile model (week_start date)
- `src/app/models/circuit_breaker.py` - CircuitBreakerState singleton (last_trip_at for 7-day window)
- `src/app/{routes,models,services,scheduler,scheduler/jobs}/__init__.py` - Package structure

## Decisions Made

- Used `dependency-groups.dev` (PEP 735) instead of deprecated `[tool.uv] dev-dependencies` to eliminate uv 0.10.4 deprecation warning
- `CircuitBreakerState` includes `last_trip_at` column for rolling 7-day escalation window (resolves open question from research)
- `database_url` must use `postgresql+psycopg2://` (sync driver) on port 5432 — APScheduler SQLAlchemyJobStore requires synchronous driver
- `--workers 1` enforced in both Dockerfile CMD and railway.toml to prevent APScheduler from being forked across multiple processes

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Replaced deprecated `[tool.uv] dev-dependencies` with `[dependency-groups] dev`**
- **Found during:** Task 1 verification (`uv sync --locked`)
- **Issue:** pyproject.toml used deprecated `tool.uv.dev-dependencies` field — uv 0.10.4 emits a deprecation warning that would appear on every `uv sync` command
- **Fix:** Replaced `[tool.uv]\ndev-dependencies = []` with `[dependency-groups]\ndev = []` per PEP 735
- **Files modified:** `pyproject.toml`
- **Verification:** `uv sync --locked` completes with no warnings
- **Committed in:** `4058d69` (standalone fix commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - deprecation warning in own code)
**Impact on plan:** Necessary for clean builds. No scope creep.

## Issues Encountered

- `uv` not installed on the machine — installed via `brew install uv` (Rule 3 - blocking issue, resolved automatically)
- `sudo` not available without terminal password prompt — worked around by using Homebrew instead of the official install script

## User Setup Required

**External services require manual configuration before the next plan can proceed.**

### Supabase Setup

1. Create a Supabase project at https://supabase.com if you haven't already

2. Get your credentials from the Supabase Dashboard:
   - `SUPABASE_URL`: Project Settings -> API -> Project URL
   - `SUPABASE_KEY`: Project Settings -> API -> service_role secret key (NOT the anon key)
   - `DATABASE_URL`: Project Settings -> Database -> Connection string -> Session mode (port 5432) — change prefix to `postgresql+psycopg2://` and append `?sslmode=require`

3. Run the schema SQL in the Supabase SQL Editor (Dashboard -> SQL Editor):

```sql
-- Enable pgvector extension in extensions schema
CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA extensions;

-- Pipeline runs (INFRA-02)
CREATE TABLE IF NOT EXISTS pipeline_runs (
    id            uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    created_at    timestamptz DEFAULT now() NOT NULL,
    status        text NOT NULL CHECK (status IN ('running','completed','failed','rejected')),
    mood_profile  text,
    error_message text,
    cost_usd      numeric(10,6) DEFAULT 0
);

-- Content history with pgvector embedding column (INFRA-02)
CREATE TABLE IF NOT EXISTS content_history (
    id               uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    created_at       timestamptz DEFAULT now() NOT NULL,
    pipeline_run_id  uuid REFERENCES pipeline_runs(id),
    script_text      text NOT NULL,
    topic_summary    text,
    embedding        extensions.vector(1536),
    rejection_reason text,
    published_at     timestamptz
);

-- HNSW index — create on empty table is safe and preferred over IVFFlat (INFRA-02)
CREATE INDEX IF NOT EXISTS content_history_embedding_hnsw
    ON content_history
    USING hnsw (embedding extensions.vector_cosine_ops);

-- Mood profiles (used starting Phase 2, schema created here)
CREATE TABLE IF NOT EXISTS mood_profiles (
    id           uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    created_at   timestamptz DEFAULT now() NOT NULL,
    week_start   date NOT NULL UNIQUE,
    profile_text text NOT NULL
);

-- Circuit breaker singleton (INFRA-04)
CREATE TABLE IF NOT EXISTS circuit_breaker_state (
    id                   int PRIMARY KEY DEFAULT 1,
    current_day_cost     numeric(10,6) DEFAULT 0,
    current_day_attempts int DEFAULT 0,
    tripped_at           timestamptz,
    last_trip_at         timestamptz,
    weekly_trip_count    int DEFAULT 0,
    week_start           date DEFAULT CURRENT_DATE,
    updated_at           timestamptz DEFAULT now()
);

-- Insert singleton row (idempotent)
INSERT INTO circuit_breaker_state (id) VALUES (1) ON CONFLICT DO NOTHING;
```

4. Verify in Supabase SQL Editor:
   ```sql
   SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' ORDER BY table_name;
   -- Should return: circuit_breaker_state, content_history, mood_profiles, pipeline_runs

   SELECT extname FROM pg_extension WHERE extname = 'vector';
   -- Should return 1 row

   SELECT * FROM pg_indexes WHERE tablename = 'content_history' AND indexname = 'content_history_embedding_hnsw';
   -- Should return 1 row

   SELECT id FROM circuit_breaker_state;
   -- Should return id=1
   ```

### Telegram Setup

1. Create a bot via BotFather: send `/newbot` to @BotFather on Telegram, copy the token
2. Get your user ID: send any message to @userinfobot to get your numeric Telegram user ID

### Create .env file

Copy `.env.example` to `.env` and fill in all real values:
```bash
cp .env.example .env
# Edit .env with your actual credentials
```

### Railway Setup

Add all variables from `.env.example` to Railway Dashboard -> Service -> Variables with real values.

## Next Phase Readiness

- All Python code artifacts are complete and tested
- Package installs cleanly with `uv sync --locked`
- All four Pydantic models importable with no errors
- Settings class ready for env var injection
- **Blocked on:** User must execute Supabase schema SQL before Plan 02 (APScheduler) can run its DB-dependent tests

---
*Phase: 01-foundation*
*Completed: 2026-02-20*

## Self-Check: PASSED

All 17 files verified present on disk. All 3 commits (80b02a9, 6acf131, 4058d69) verified in git history.
