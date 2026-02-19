# Phase 01: Foundation - Research

**Researched:** 2026-02-19
**Domain:** FastAPI + Railway deployment, Supabase/pgvector schema, APScheduler with Postgres job store, Telegram bot security, cost circuit breaker
**Confidence:** HIGH (core stack verified via official docs and Context7-equivalent sources)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

#### Project Structure
- Modular package layout: `src/app/` with subfolders (routes/, services/, models/, scheduler/, etc.)
- Pydantic `BaseSettings` for all configuration — reads from env vars automatically, typed, validatable
- Separate `models/` folder for Supabase table schemas and Pydantic models; services import from there
- `uv` + `pyproject.toml` for dependency management and Python version pinning

#### Schedule & Timezone
- Timezone: `America/Mexico_City`
- Daily pipeline trigger: **7:00 AM** (content ready when creator wakes up)
- APScheduler no-op test job: writes a `Scheduler heartbeat` log entry at scheduled time
- APScheduler job store: same Supabase DB (reuse existing connection, no separate Railway Postgres add-on)

#### Circuit Breaker
- Measures **both** dollar cost (Claude API spend) AND API call count — whichever fires first
- Limits are **configurable via env vars** (expose `DAILY_COST_LIMIT` and `MAX_DAILY_ATTEMPTS` in Railway); sensible defaults required
- On trip: auto-resets at midnight; sends escalation alert if the breaker fires **twice in any rolling 7-day window**
- State stored in a dedicated `circuit_breaker_state` table (columns: `current_day_cost`, `current_day_attempts`, `tripped_at`, `weekly_trip_count`)

#### Deployment
- Railway build: **Dockerfile** (explicit Python version, uv install steps, CMD — predictable over nixpacks)
- Env var documentation: `.env.example` committed to repo + inline comments in the Pydantic Settings class
- Single Railway service: FastAPI + APScheduler run in the same process (simpler, lower cost)
- Health endpoint (`GET /health`) probes deeper: verifies DB connection AND scheduler status, not just 200

#### Claude's Discretion
- Exact Dockerfile base image and layer ordering
- Pydantic Settings class field naming conventions
- APScheduler job ID naming scheme
- Health endpoint response schema (beyond passing DB + scheduler checks)

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within phase scope.
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| INFRA-01 | System runs as a persistent worker on Railway with FastAPI health endpoint and env-based config | Dockerfile pattern with uv, railway.toml healthcheckPath, Pydantic BaseSettings with SettingsConfigDict |
| INFRA-02 | Supabase schema initialized with pipeline_runs table, content history table, and pgvector column for embeddings | pgvector extension SQL, HNSW index syntax, vector(1536) for text-embedding-3-small, CREATE TABLE patterns |
| INFRA-03 | APScheduler with Postgres job store triggers daily content generation and survives deploys without missing jobs | SQLAlchemyJobStore on Supabase session pooler (port 5432), BackgroundScheduler with CronTrigger, misfire_grace_time and coalesce config |
| INFRA-04 | Cost circuit breaker enforces a hard daily generation limit to prevent runaway API spend | Custom circuit_breaker_state table, APScheduler midnight-reset job, Telegram alert on trip; no off-the-shelf library covers this use case |
| SCRTY-01 | All API keys stored as encrypted environment variables — never hardcoded | Pydantic BaseSettings reads from env, Railway encrypted env vars, .env.example pattern |
| SCRTY-02 | Telegram bot responds only to the creator's configured user ID, silently ignores all other senders | filters.User(user_id=CREATOR_ID) applied to all MessageHandlers; unmatched updates are silently dropped |
</phase_requirements>

---

## Summary

This phase establishes a production-ready FastAPI service on Railway with the full infrastructure stack needed for the content pipeline. The core technical challenge is running FastAPI and APScheduler together in a single process without duplicate job execution — this is achievable only with a single Uvicorn worker (`--workers 1`) and is a Railway-compatible constraint since the use case does not require horizontal scaling.

The Supabase connection strategy is critical: APScheduler's `SQLAlchemyJobStore` requires a synchronous SQLAlchemy engine, which means the job store must connect via `postgresql+psycopg2://` (not asyncpg). Supabase now defaults to IPv6 for direct connections (port 5432), but the **session pooler** (also port 5432, via `pooler.supabase.com`) provides IPv4 compatibility and is the correct connection type for persistent Railway workers — not transaction mode (port 6543), which breaks APScheduler's prepared statements.

The circuit breaker is custom (no off-the-shelf library covers dollar-cost + call-count dual tracking with timezone-aware midnight reset), stored in a dedicated Postgres table. Its midnight reset is itself an APScheduler CronTrigger job, which means both the reset job and the daily pipeline job survive service restarts because the job store is persistent.

**Primary recommendation:** Use `python:3.12-slim` as the Dockerfile base, connect APScheduler to Supabase session pooler via psycopg2, run with `--workers 1`, and implement the circuit breaker as a service class reading/writing `circuit_breaker_state` directly rather than using any third-party circuit breaker library.

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| fastapi | >=0.115 | Web framework + health endpoint | Official choice; async-native, Pydantic-integrated |
| uvicorn | >=0.32 | ASGI server | Standard FastAPI server; must run with `--workers 1` for APScheduler |
| pydantic-settings | >=2.7 | Env var config via BaseSettings | Official FastAPI recommendation; replaces pydantic v1 settings |
| APScheduler | ==3.11.2 | Background job scheduling with Postgres job store | 3.x branch is stable; 4.x is async-only and in alpha — stick with 3.x |
| sqlalchemy | >=2.0 | Required by APScheduler SQLAlchemyJobStore | APScheduler job store only works with sync SQLAlchemy engine |
| psycopg2-binary | >=2.9 | PostgreSQL driver for SQLAlchemy job store | Sync driver required for APScheduler 3.x job store |
| supabase | >=2.0 | Supabase Python client for data operations | Official client; handles REST API + storage |
| httpx | >=0.28 | Async HTTP client for external API calls | Project constraint; never use `requests` in async context |
| python-telegram-bot | ==21.x | Telegram bot for alerts and approval UI | Project constraint; v21 is async-native |
| pytz | >=2024.1 | Timezone support for APScheduler | Required by APScheduler 3.x for timezone-aware scheduling |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| python-dotenv | >=1.0 | Load .env file in local development | Pydantic Settings reads it automatically via SettingsConfigDict |
| uv | latest | Dependency management + Python version pinning | All local dev and Dockerfile installs |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| APScheduler 3.x | APScheduler 4.x | 4.x is async-native but still in pre-release; 3.x is stable and documented |
| psycopg2-binary | asyncpg | asyncpg breaks with APScheduler's sync SQLAlchemyJobStore; use psycopg2 for job store |
| supabase-py | raw psycopg2 | supabase-py provides a clean client API; raw psycopg2 only needed for job store |
| BackgroundScheduler | AsyncIOScheduler | AsyncIOScheduler shares the event loop with FastAPI — use only if all jobs are async; BackgroundScheduler uses a thread pool and is simpler for this use case |

**Installation:**
```bash
uv add fastapi uvicorn[standard] pydantic-settings APScheduler==3.11.2 sqlalchemy psycopg2-binary supabase httpx python-telegram-bot==21.* pytz python-dotenv
```

---

## Architecture Patterns

### Recommended Project Structure
```
src/
├── app/
│   ├── main.py              # FastAPI app factory, lifespan context manager
│   ├── settings.py          # Pydantic BaseSettings class (single source of truth)
│   ├── routes/
│   │   └── health.py        # GET /health — DB + scheduler probe
│   ├── models/
│   │   ├── pipeline.py      # pipeline_runs Pydantic + table schema
│   │   ├── content.py       # content_history Pydantic + table schema
│   │   ├── mood.py          # mood_profiles Pydantic + table schema
│   │   └── circuit_breaker.py  # circuit_breaker_state Pydantic + table schema
│   ├── services/
│   │   ├── database.py      # Supabase client singleton
│   │   ├── circuit_breaker.py  # CircuitBreakerService — read/write/trip/reset logic
│   │   └── telegram.py      # Telegram bot initialization and alert sender
│   └── scheduler/
│       ├── setup.py         # BackgroundScheduler factory with SQLAlchemyJobStore
│       ├── jobs/
│       │   ├── heartbeat.py     # No-op test job writing heartbeat log
│       │   └── cb_reset.py      # Midnight circuit breaker reset job
│       └── registry.py      # add_job() calls — single place to register all jobs
pyproject.toml
uv.lock
Dockerfile
railway.toml
.env.example
```

### Pattern 1: FastAPI Lifespan with Scheduler
**What:** Start APScheduler inside FastAPI's lifespan context manager so it starts before requests are served and shuts down cleanly.
**When to use:** Always — this is the only correct way to integrate a background scheduler with FastAPI.

```python
# Source: https://fastapi.tiangolo.com/advanced/events/
from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.scheduler.setup import create_scheduler

scheduler = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    global scheduler
    scheduler = create_scheduler()
    scheduler.start()
    yield
    # Shutdown
    scheduler.shutdown(wait=False)

app = FastAPI(lifespan=lifespan)
```

### Pattern 2: Pydantic BaseSettings with SettingsConfigDict
**What:** Single Settings class that reads all config from environment variables (Railway injects these) with type validation and defaults.
**When to use:** All configuration — never hardcode or read `os.environ` directly outside this class.

```python
# Source: https://fastapi.tiangolo.com/advanced/settings/
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Railway / App
    port: int = 8000
    debug: bool = False

    # Supabase
    supabase_url: str
    supabase_key: str
    database_url: str  # postgresql+psycopg2:// for APScheduler job store

    # Telegram
    telegram_bot_token: str
    telegram_creator_id: int  # SCRTY-02: only respond to this user

    # Circuit Breaker — configurable via Railway env vars (INFRA-04)
    daily_cost_limit: float = 2.0       # USD, default $2/day
    max_daily_attempts: int = 10        # max API calls/day

    # Schedule
    pipeline_hour: int = 7              # 7 AM Mexico City time

@lru_cache
def get_settings() -> Settings:
    return Settings()
```

### Pattern 3: APScheduler with SQLAlchemyJobStore on Supabase
**What:** Configure BackgroundScheduler with persistent Postgres job store so jobs survive service restarts and deploys.
**When to use:** Always for this project — the Postgres job store is the key that makes INFRA-03 possible.

```python
# Source: https://apscheduler.readthedocs.io/en/3.x/userguide.html
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.executors.pool import ThreadPoolExecutor

def create_scheduler(database_url: str, timezone: str = "America/Mexico_City") -> BackgroundScheduler:
    jobstores = {
        "default": SQLAlchemyJobStore(
            url=database_url,  # must be postgresql+psycopg2:// — NOT asyncpg
            tablename="apscheduler_jobs",
        )
    }
    executors = {
        "default": ThreadPoolExecutor(max_workers=4)
    }
    job_defaults = {
        "coalesce": True,          # if N missed fires, run once (not N times)
        "max_instances": 1,        # never run same job concurrently
        "misfire_grace_time": 3600 # 1 hour grace — job fires even if service was down
    }
    return BackgroundScheduler(
        jobstores=jobstores,
        executors=executors,
        job_defaults=job_defaults,
        timezone=timezone,
    )
```

### Pattern 4: Registering Jobs with Replace-Existing
**What:** Always use `replace_existing=True` when adding jobs so restarts don't create duplicate job entries in the job store.
**When to use:** Every `add_job()` call in this project.

```python
# Source: APScheduler 3.x docs
scheduler.add_job(
    heartbeat_job,
    trigger="cron",
    hour=7,
    minute=0,
    timezone="America/Mexico_City",
    id="daily_pipeline_trigger",  # stable ID — survives restarts
    replace_existing=True,         # CRITICAL — prevents duplicate jobs on redeploy
)

# Midnight circuit breaker reset
scheduler.add_job(
    reset_circuit_breaker,
    trigger="cron",
    hour=0,
    minute=0,
    timezone="America/Mexico_City",
    id="cb_midnight_reset",
    replace_existing=True,
)
```

### Pattern 5: Telegram Bot — Silent User Filter (SCRTY-02)
**What:** Apply `filters.User(user_id=CREATOR_ID)` to every handler. Messages from other users are silently dropped — no response sent.
**When to use:** All message handlers, callback query handlers.

```python
# Source: https://docs.python-telegram-bot.org/en/v21.7/telegram.ext.filters.html
from telegram.ext import ApplicationBuilder, MessageHandler, filters

CREATOR_ID = settings.telegram_creator_id

# Initialize bot without running its own event loop (FastAPI owns the loop)
bot_app = (
    ApplicationBuilder()
    .token(settings.telegram_bot_token)
    .updater(None)  # disable internal polling — we manage lifecycle
    .build()
)

creator_filter = filters.User(user_id=CREATOR_ID)

# All handlers must include creator_filter
bot_app.add_handler(
    MessageHandler(filters.TEXT & creator_filter, handle_text_message)
)
```

### Pattern 6: Health Endpoint with Deep Probing
**What:** The `/health` endpoint checks both DB connectivity AND scheduler running state, not just HTTP 200.
**When to use:** This is the Railway restart signal — must be thorough.

```python
# Source: Railway docs + research
from fastapi import HTTPException
from supabase import Client
from datetime import datetime, timezone

@router.get("/health")
async def health_check(
    supabase: Client = Depends(get_supabase),
    scheduler: BackgroundScheduler = Depends(get_scheduler),
):
    checks = {}

    # DB check
    try:
        supabase.table("pipeline_runs").select("id").limit(1).execute()
        checks["database"] = "ok"
    except Exception as e:
        checks["database"] = f"error: {str(e)}"

    # Scheduler check
    checks["scheduler"] = "running" if scheduler.running else "stopped"

    all_ok = checks["database"] == "ok" and checks["scheduler"] == "running"
    if not all_ok:
        raise HTTPException(status_code=503, detail=checks)

    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "checks": checks,
    }
```

### Anti-Patterns to Avoid
- **Multiple Uvicorn workers with APScheduler:** Running `--workers 2+` causes duplicate job execution since each worker starts its own scheduler. The job store serializes job state but does not synchronize execution across processes. Always use `--workers 1`.
- **Using asyncpg with APScheduler SQLAlchemyJobStore:** APScheduler 3.x's job store is synchronous; asyncpg with `postgresql+asyncpg://` will fail at runtime. Use `psycopg2-binary` for the job store connection only.
- **Using port 6543 (transaction pooler) for APScheduler:** PgBouncer transaction mode disables prepared statements, which breaks SQLAlchemy's psycopg2 adapter. Use the session pooler (port 5432 via `pooler.supabase.com`) or direct connection.
- **Using `@app.on_event("startup")`:** Deprecated in FastAPI. Use the `lifespan` asynccontextmanager pattern.
- **Calling `run_polling()` with FastAPI:** Blocks the event loop. Use `updater(None)` + manual `initialize()` / `start()` / `stop()` instead.
- **Hardcoding `add_job()` without `replace_existing=True`:** Every service restart creates a duplicate job record in the job store. After a few redeploys the scheduler table becomes inconsistent.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Env var validation | Custom parser + type casting | `pydantic-settings BaseSettings` | Type coercion, validation, error messages, .env support all included |
| Job persistence across restarts | File-based state / Redis | `APScheduler SQLAlchemyJobStore` | Built-in serialization, job locking, missed-job handling |
| Telegram update routing | Manual if/elif on message type | `python-telegram-bot Handlers + Filters` | Filter composition, async dispatch, type safety |
| Async HTTP calls | `requests` in async context | `httpx` async client | `requests` blocks the event loop in async context |
| Docker layer caching for Python | Manual pip workflows | `uv` with lock file + bind mounts | 10-100x faster, reproducible, proper layer separation |

**Key insight:** The circuit breaker IS hand-rolled by design — no library supports dual cost+count tracking with timezone-aware midnight reset and weekly escalation. Everything else should use the libraries above.

---

## Common Pitfalls

### Pitfall 1: APScheduler Duplicate Jobs on Restart
**What goes wrong:** Each service startup calls `add_job()`, which inserts a new row in `apscheduler_jobs`. After several restarts, the same job fires multiple times.
**Why it happens:** `add_job()` is additive by default — it does not overwrite existing jobs with the same ID.
**How to avoid:** Always pass `replace_existing=True` to `add_job()`. The `id` parameter becomes the primary key in the job store.
**Warning signs:** Heartbeat log writes more than once per scheduled interval.

### Pitfall 2: Supabase IPv6 Direct Connection Failure
**What goes wrong:** Railway cannot connect to Supabase direct connection (`db.[ref].supabase.co:5432`) because Railway's networking may not support IPv6 properly.
**Why it happens:** Supabase migrated direct connections to IPv6-only in 2024. Railway has mixed IPv4/IPv6 support.
**How to avoid:** Use the **session pooler** URL from the Supabase dashboard: `postgresql+psycopg2://postgres.[ref]:[password]@aws-0-[region].pooler.supabase.com:5432/postgres?sslmode=require`
**Warning signs:** Connection timeout errors during startup, health check returns 503 immediately.

### Pitfall 3: asyncpg + APScheduler Incompatibility
**What goes wrong:** Using `postgresql+asyncpg://` as the `DATABASE_URL` for the APScheduler job store causes a runtime error — APScheduler's job store creates a synchronous SQLAlchemy engine internally.
**Why it happens:** APScheduler 3.x's `SQLAlchemyJobStore` uses sync SQLAlchemy. Passing an async driver URL causes the engine creation to fail or behave unpredictably.
**How to avoid:** Use two separate connection strings: one `postgresql+psycopg2://` for APScheduler, one with the supabase-py client (which uses its own connection pooling internally). Name them distinctly in Settings.
**Warning signs:** `ImportError` or `sqlalchemy.exc.ArgumentError` on startup referencing asyncpg.

### Pitfall 4: Multiple Workers Breaking the Scheduler
**What goes wrong:** Deploying with `gunicorn -w 4` or `uvicorn --workers 4` starts 4 separate APScheduler instances. All 4 schedule the same job; the job store serializes job state but all 4 processes poll it and attempt execution.
**Why it happens:** APScheduler has no cross-process locking mechanism in 3.x.
**How to avoid:** Lock `CMD` to `uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1` in the Dockerfile. Never increase workers without moving the scheduler to a separate Railway service.
**Warning signs:** Heartbeat fires 2x, 4x more than expected in logs.

### Pitfall 5: America/Mexico_City DST Edge Cases
**What goes wrong:** Mexico City observes DST (clocks spring forward in April, fall back in October). A 7:00 AM `CronTrigger` may fire at 6:00 AM or 8:00 AM local time during the transition weekend.
**Why it happens:** APScheduler's cron trigger uses wall-clock time; the transition hour either skips or repeats.
**How to avoid:** Set `coalesce=True` in `job_defaults` so a skipped fire only runs once when it next catches up. For the DST-skip scenario (spring forward), the job simply fires 1 hour later — acceptable for this use case.
**Warning signs:** Job execution times in logs drift by 1 hour during April and October.

### Pitfall 6: Circuit Breaker State Race Condition
**What goes wrong:** Two concurrent API calls both read the circuit breaker state before either writes their increment, so the count is understated.
**Why it happens:** APScheduler runs jobs in a thread pool; if two jobs overlap (unlikely but possible), they race on the DB row.
**How to avoid:** Use a Postgres `UPDATE ... RETURNING` with a single atomic statement rather than separate SELECT + UPDATE. Use `SELECT FOR UPDATE` if using a raw SQL approach.
**Warning signs:** `current_day_attempts` count is lower than actual calls made.

### Pitfall 7: Health Endpoint Returns 200 When DB Is Down
**What goes wrong:** A health endpoint that just returns `{"status": "ok"}` without probing the DB passes Railway's health check even when Supabase is unreachable.
**Why it happens:** Naive health endpoint only checks if the FastAPI process is responding, not if dependencies are healthy.
**How to avoid:** Execute a lightweight query (`SELECT 1` or a `.limit(1)` on a small table) in the health handler. Return 503 on any exception.
**Warning signs:** Railway shows service as healthy but API calls fail; no restart triggered.

---

## Code Examples

### Supabase Schema Initialization SQL

```sql
-- Source: https://supabase.com/docs/guides/database/extensions/pgvector
-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA extensions;

-- Pipeline runs table (INFRA-02)
CREATE TABLE IF NOT EXISTS pipeline_runs (
    id          uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    created_at  timestamptz DEFAULT now() NOT NULL,
    status      text NOT NULL CHECK (status IN ('running', 'completed', 'failed', 'rejected')),
    mood_profile text,
    error_message text,
    cost_usd    numeric(10, 6) DEFAULT 0
);

-- Content history table with pgvector embedding column (INFRA-02)
CREATE TABLE IF NOT EXISTS content_history (
    id          uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    created_at  timestamptz DEFAULT now() NOT NULL,
    pipeline_run_id uuid REFERENCES pipeline_runs(id),
    script_text text NOT NULL,
    topic_summary text,
    embedding   extensions.vector(1536),  -- text-embedding-3-small dimensions
    rejection_reason text,
    published_at timestamptz
);

-- HNSW index — safe to create immediately (no data needed first)
-- Source: https://supabase.com/docs/guides/ai/vector-indexes/hnsw-indexes
CREATE INDEX IF NOT EXISTS content_history_embedding_hnsw
    ON content_history
    USING hnsw (embedding extensions.vector_cosine_ops);

-- Mood profiles table (SCRP-02 future, but schema here for Phase 1)
CREATE TABLE IF NOT EXISTS mood_profiles (
    id          uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    created_at  timestamptz DEFAULT now() NOT NULL,
    week_start  date NOT NULL UNIQUE,
    profile_text text NOT NULL
);

-- Circuit breaker state table (INFRA-04)
CREATE TABLE IF NOT EXISTS circuit_breaker_state (
    id                  int PRIMARY KEY DEFAULT 1,  -- singleton row
    current_day_cost    numeric(10, 6) DEFAULT 0,
    current_day_attempts int DEFAULT 0,
    tripped_at          timestamptz,
    weekly_trip_count   int DEFAULT 0,
    week_start          date DEFAULT CURRENT_DATE,
    updated_at          timestamptz DEFAULT now()
);

-- Insert the singleton row
INSERT INTO circuit_breaker_state (id) VALUES (1) ON CONFLICT DO NOTHING;
```

### Dockerfile with uv (Claude's Discretion — Recommended)

```dockerfile
# Source: https://docs.astral.sh/uv/guides/integration/docker/
# Multi-stage build for optimal layer caching

# ---- Build stage ----
FROM python:3.12-slim AS builder

# Copy uv from official image (pin version for reproducibility)
COPY --from=ghcr.io/astral-sh/uv:0.5.31 /uv /uvx /bin/

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_NO_DEV=1

# Install dependencies first (cached layer — only invalidated by pyproject.toml/uv.lock changes)
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project --no-dev

# Copy application code and install project
COPY . /app
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev

# ---- Runtime stage ----
FROM python:3.12-slim

# Non-root user for security
RUN useradd --create-home --uid 1001 appuser

WORKDIR /app

# Copy virtualenv from builder
COPY --from=builder --chown=appuser:appuser /app /app

USER appuser

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# CRITICAL: --workers 1 required — APScheduler must run in a single process
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
```

### railway.toml Configuration

```toml
# Source: https://docs.railway.com/reference/config-as-code

[build]
builder = "DOCKERFILE"
dockerfilePath = "Dockerfile"

[deploy]
startCommand = "uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1"
healthcheckPath = "/health"
healthcheckTimeout = 60
restartPolicyType = "ON_FAILURE"
```

### Circuit Breaker Service (Custom — No Library)

```python
# Custom implementation — no off-the-shelf library covers this
from datetime import datetime, timezone, timedelta
from app.settings import get_settings
from supabase import Client

class CircuitBreakerService:
    """Dual cost+count circuit breaker with timezone-aware midnight reset."""

    TABLE = "circuit_breaker_state"
    SINGLETON_ID = 1

    def __init__(self, supabase: Client, settings):
        self.db = supabase
        self.cost_limit = settings.daily_cost_limit
        self.attempt_limit = settings.max_daily_attempts

    def get_state(self) -> dict:
        result = (
            self.db.table(self.TABLE)
            .select("*")
            .eq("id", self.SINGLETON_ID)
            .single()
            .execute()
        )
        return result.data

    def record_attempt(self, cost_usd: float) -> bool:
        """Returns True if allowed, False if tripped."""
        state = self.get_state()
        new_cost = state["current_day_cost"] + cost_usd
        new_attempts = state["current_day_attempts"] + 1

        if new_cost >= self.cost_limit or new_attempts >= self.attempt_limit:
            self._trip(state)
            return False

        # Atomic increment — single UPDATE statement
        self.db.table(self.TABLE).update({
            "current_day_cost": new_cost,
            "current_day_attempts": new_attempts,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", self.SINGLETON_ID).execute()

        return True

    def _trip(self, state: dict):
        now = datetime.now(timezone.utc)
        week_count = state["weekly_trip_count"] + 1
        self.db.table(self.TABLE).update({
            "tripped_at": now.isoformat(),
            "weekly_trip_count": week_count,
            "updated_at": now.isoformat(),
        }).eq("id", self.SINGLETON_ID).execute()

        # Escalation: alert if second trip in rolling 7-day window
        if week_count >= 2:
            self._send_escalation_alert(week_count)

    def midnight_reset(self):
        """Called by APScheduler at midnight Mexico City time."""
        now = datetime.now(timezone.utc)
        self.db.table(self.TABLE).update({
            "current_day_cost": 0,
            "current_day_attempts": 0,
            "tripped_at": None,
            "updated_at": now.isoformat(),
        }).eq("id", self.SINGLETON_ID).execute()

    def is_tripped(self) -> bool:
        state = self.get_state()
        return state["tripped_at"] is not None
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `@app.on_event("startup")` | `lifespan` asynccontextmanager | FastAPI 0.93 (2023) | Startup/shutdown are co-located; on_event deprecated |
| `pydantic.BaseSettings` | `pydantic_settings.BaseSettings` | Pydantic v2 (2023) | Separate package: `pip install pydantic-settings` |
| IVFFlat index (pgvector) | HNSW index | pgvector 0.5 (2023) | HNSW is faster and doesn't need minimum row count before building |
| pip + requirements.txt | uv + pyproject.toml + uv.lock | 2024 onward | 10-100x faster install; reproducible builds via lockfile |
| Railway nixpacks | Dockerfile | Ongoing | Dockerfile is explicit and predictable; nixpacks may choose wrong Python version |

**Deprecated/outdated:**
- `from pydantic import BaseSettings`: Move to `from pydantic_settings import BaseSettings` — separate install required in Pydantic v2
- `python-telegram-bot < 20`: Sync API replaced by async in v20; v21 is the current stable async release
- IVFFlat pgvector index: HNSW is universally preferred — no warmup data needed, auto-maintains as rows are inserted
- `APScheduler 4.x`: Pre-release / alpha as of Feb 2026; documentation and API are unstable — use 3.11.2

---

## Open Questions

1. **Supabase connection string for Railway**
   - What we know: Session pooler (port 5432, `pooler.supabase.com`) is IPv4-compatible and works with psycopg2
   - What's unclear: Whether Railway's network supports the Supabase direct connection (port 5432, `db.[ref].supabase.co`) — this depends on whether Railway has purchased IPv4 add-ons; needs runtime verification
   - Recommendation: Default to session pooler URL; test direct connection as a fallback only if pooler has issues

2. **Telegram bot polling vs. webhook in same process as FastAPI**
   - What we know: `run_polling()` blocks the event loop; `updater(None)` disables polling; webhooks require a public HTTPS endpoint
   - What's unclear: For Phase 1, the bot only sends outbound alerts (circuit breaker trips) — it does not receive inbound commands from the creator yet. So polling infrastructure may not be needed until Phase 4 (Telegram Approval UI).
   - Recommendation: In Phase 1, initialize the bot in lifespan but only use it to send messages (no polling). Defer inbound handler setup to Phase 4.

3. **weekly_trip_count reset logic**
   - What we know: The circuit breaker should send escalation if fired twice in a rolling 7-day window; state table has `weekly_trip_count` and `week_start` columns
   - What's unclear: Whether `week_start` should reset weekly (every Monday) or whether "rolling 7 days" requires comparing timestamps
   - Recommendation: Store `last_trip_at` as a timestamp; escalate if `now() - last_trip_at < 7 days` AND a new trip occurs. Add `last_trip_at timestamptz` to the schema.

---

## Sources

### Primary (HIGH confidence)
- [FastAPI Lifespan Events](https://fastapi.tiangolo.com/advanced/events/) — lifespan asynccontextmanager pattern
- [FastAPI Settings and Environment Variables](https://fastapi.tiangolo.com/advanced/settings/) — Pydantic BaseSettings with lru_cache
- [APScheduler 3.x User Guide](https://apscheduler.readthedocs.io/en/3.x/userguide.html) — BackgroundScheduler, SQLAlchemyJobStore configuration, coalesce, misfire_grace_time
- [APScheduler SQLAlchemyJobStore API](https://apscheduler.readthedocs.io/en/3.x/modules/jobstores/sqlalchemy.html) — tablename, url, engine_options parameters
- [APScheduler CronTrigger](https://apscheduler.readthedocs.io/en/3.x/modules/triggers/cron.html) — CronTrigger fields, from_crontab(), timezone parameter
- [Supabase pgvector docs](https://supabase.com/docs/guides/database/extensions/pgvector) — extension enable SQL, vector column syntax
- [Supabase HNSW index docs](https://supabase.com/docs/guides/ai/vector-indexes/hnsw-indexes) — CREATE INDEX syntax, operator classes, timing
- [Supabase connecting to Postgres](https://supabase.com/docs/guides/database/connecting-to-postgres) — port 5432 vs 6543, session vs transaction pooler
- [Supabase SQLAlchemy troubleshooting](https://supabase.com/docs/guides/troubleshooting/using-sqlalchemy-with-supabase-FUqebT) — NullPool vs pool for persistent servers
- [Railway Config as Code](https://docs.railway.com/reference/config-as-code) — railway.toml healthcheckPath, restartPolicyType, healthcheckTimeout
- [uv Docker integration guide](https://docs.astral.sh/uv/guides/integration/docker/) — multi-stage build, UV_COMPILE_BYTECODE, UV_LINK_MODE
- [python-telegram-bot v21.7 filters](https://docs.python-telegram-bot.org/en/v21.7/telegram.ext.filters.html) — filters.User(user_id=...) silent filtering
- [python-telegram-bot ApplicationBuilder v21.9](https://docs.python-telegram-bot.org/en/v21.9/telegram.ext.applicationbuilder.html) — updater(None), manual initialize/start/stop
- [Optimal Dockerfile for Python uv — Depot](https://depot.dev/docs/container-builds/optimal-dockerfiles/python-uv-dockerfile) — complete multi-stage Dockerfile pattern

### Secondary (MEDIUM confidence)
- [Railway FastAPI Deployment Guide](https://docs.railway.com/guides/fastapi) — healthcheckPath behavior, Dockerfile detection
- [APScheduler GitHub Issue #315](https://github.com/agronholm/apscheduler/issues/315) — timezone behavior discussion
- [Supabase asyncpg pooling issue](https://medium.com/@patrickduch93/supabase-pooling-and-asyncpg-dont-mix-here-s-the-real-fix-44f700b05249) — transaction pooler incompatibility with prepared statements

### Tertiary (LOW confidence)
- General WebSearch results on single-worker constraint for APScheduler with FastAPI — consistent across multiple sources, not verified against a single authoritative reference

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all versions verified via official docs or PyPI
- Architecture: HIGH — FastAPI lifespan pattern verified; APScheduler job store config verified
- Pitfalls: HIGH (duplicates, IPv6, asyncpg) / MEDIUM (DST, race conditions) — IPv6 and duplicate pitfalls from official Supabase and APScheduler docs; DST from APScheduler GitHub issues
- Schema: HIGH — SQL verified against Supabase official docs
- Dockerfile: HIGH — pattern from official uv docs

**Research date:** 2026-02-19
**Valid until:** 2026-03-21 (30 days — stable ecosystem, APScheduler 3.x is not fast-moving)
