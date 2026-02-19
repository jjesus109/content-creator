# Phase 1: Foundation - Context

**Gathered:** 2026-02-19
**Status:** Ready for planning

<domain>
## Phase Boundary

Deploy a persistent, secure FastAPI service on Railway with all infrastructure in place — Supabase schema, APScheduler with Postgres job store, cost circuit breaker, and Telegram security baseline. All subsequent pipeline phases build on top of this foundation.

</domain>

<decisions>
## Implementation Decisions

### Project Structure
- Modular package layout: `src/app/` with subfolders (routes/, services/, models/, scheduler/, etc.)
- Pydantic `BaseSettings` for all configuration — reads from env vars automatically, typed, validatable
- Separate `models/` folder for Supabase table schemas and Pydantic models; services import from there
- `uv` + `pyproject.toml` for dependency management and Python version pinning

### Schedule & Timezone
- Timezone: `America/Mexico_City`
- Daily pipeline trigger: **7:00 AM** (content ready when creator wakes up)
- APScheduler no-op test job: writes a `Scheduler heartbeat` log entry at scheduled time
- APScheduler job store: same Supabase DB (reuse existing connection, no separate Railway Postgres add-on)

### Circuit Breaker
- Measures **both** dollar cost (Claude API spend) AND API call count — whichever fires first
- Limits are **configurable via env vars** (expose `DAILY_COST_LIMIT` and `MAX_DAILY_ATTEMPTS` in Railway); sensible defaults required
- On trip: auto-resets at midnight; sends escalation alert if the breaker fires **twice in any rolling 7-day window**
- State stored in a dedicated `circuit_breaker_state` table (columns: `current_day_cost`, `current_day_attempts`, `tripped_at`, `weekly_trip_count`)

### Deployment
- Railway build: **Dockerfile** (explicit Python version, uv install steps, CMD — predictable over nixpacks)
- Env var documentation: `.env.example` committed to repo + inline comments in the Pydantic Settings class
- Single Railway service: FastAPI + APScheduler run in the same process (simpler, lower cost)
- Health endpoint (`GET /health`) probes deeper: verifies DB connection AND scheduler status, not just 200

### Claude's Discretion
- Exact Dockerfile base image and layer ordering
- Pydantic Settings class field naming conventions
- APScheduler job ID naming scheme
- Health endpoint response schema (beyond passing DB + scheduler checks)

</decisions>

<specifics>
## Specific Ideas

- The `circuit_breaker_state` table should reset `current_day_cost` and `current_day_attempts` at midnight Mexico City time — this aligns the counter window with the daily pipeline schedule
- The health endpoint should be the Railway restart-recovery signal: if it returns non-200, Railway should restart the service

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 01-foundation*
*Context gathered: 2026-02-19*
