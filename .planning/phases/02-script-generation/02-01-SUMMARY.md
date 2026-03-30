---
phase: 02-script-generation
plan: "01"
subsystem: infra
tags: [anthropic, openai, pgvector, telegram, python-telegram-bot, fastapi, apscheduler]

# Dependency graph
requires:
  - phase: 01-foundation
    provides: FastAPI app with APScheduler lifespan, Telegram bot (outbound-only), DB migrations runner, Settings class
provides:
  - anthropic and openai packages installed and importable
  - settings.py extended with anthropic_api_key, openai_api_key, claude_generation_model
  - migrations/0002_script_generation.sql with check_script_similarity SQL function and rejection_constraints table
  - src/app/telegram/app.py with build_telegram_app(), start_telegram_polling(), stop_telegram_polling()
  - FastAPI lifespan starts and stops PTB Application alongside APScheduler
  - app.state.telegram_app available for downstream handlers
affects: [02-02, 02-03, 02-04, 02-05, 03-video-generation, 04-approval-flow]

# Tech tracking
tech-stack:
  added: [anthropic==0.83.0, openai==2.21.0, jiter, sniffio, distro, docstring-parser, tqdm]
  patterns:
    - PTB Application stored on app.state.telegram_app — downstream modules register handlers without owning lifecycle
    - set_fastapi_app() stores FastAPI app reference in services/telegram.py — APScheduler threads access app.state via this without importing main.py
    - Telegram bot lifecycle managed by FastAPI lifespan (start with APScheduler, stop before APScheduler shutdown)

key-files:
  created:
    - src/app/telegram/__init__.py
    - src/app/telegram/app.py
    - migrations/0002_script_generation.sql
  modified:
    - pyproject.toml
    - uv.lock
    - src/app/settings.py
    - src/app/services/telegram.py
    - src/app/main.py

key-decisions:
  - "PTB Application replaces updater(None) singleton — polling required for Phase 2 mood flow callback queries"
  - "set_fastapi_app() pattern avoids circular imports between services/telegram.py and telegram/app.py"
  - "check_script_similarity uses 1-(embedding<=>query) to convert pgvector cosine DISTANCE to similarity — common pgvector bug avoided"
  - "rejection_constraints table created now (Phase 2 reads, Phase 4 writes) so queries return empty safely"

patterns-established:
  - "Telegram handlers registered by feature modules, not by telegram/app.py — app.py owns lifecycle only"
  - "APScheduler jobs use send_alert_sync() via run_coroutine_threadsafe — no direct loop.run_until_complete from thread"

requirements-completed: [SCRP-02, SCRP-04]

# Metrics
duration: 2min
completed: 2026-02-20
---

# Phase 2 Plan 01: Script Generation Infrastructure Summary

**PTB Application with full polling lifecycle, pgvector similarity function for Spanish script deduplication, and anthropic+openai packages wired into FastAPI lifespan**

## Performance

- **Duration:** ~2 min
- **Started:** 2026-02-20T21:29:38Z
- **Completed:** 2026-02-20T21:31:29Z
- **Tasks:** 2
- **Files modified:** 7 (5 modified, 3 created)

## Accomplishments
- anthropic 0.83.0 and openai 2.21.0 installed; both importable from .venv
- Settings extended with anthropic_api_key, openai_api_key, and claude_generation_model (defaults to claude-haiku-3-5-20241022)
- Migration 0002 creates check_script_similarity function (cosine distance→similarity inversion) and rejection_constraints table
- Telegram bot upgraded from outbound-only updater(None) singleton to full PTB Application with polling
- FastAPI lifespan now starts/stops Telegram Application alongside APScheduler

## Task Commits

Each task was committed atomically:

1. **Task 1: Install dependencies, extend settings, create migration 0002** - `876b84b` (feat)
2. **Task 2: Upgrade Telegram to polling Application, update lifespan** - `3517e5d` (feat)

**Plan metadata:** TBD (docs: complete plan)

## Files Created/Modified
- `pyproject.toml` - added anthropic>=0.83.0 and openai>=2.21.0 dependencies
- `uv.lock` - updated lockfile with new packages and transitive deps
- `src/app/settings.py` - added anthropic_api_key, openai_api_key, claude_generation_model fields
- `migrations/0002_script_generation.sql` - check_script_similarity SQL function + rejection_constraints table
- `src/app/telegram/__init__.py` - package marker (empty)
- `src/app/telegram/app.py` - build_telegram_app(), start_telegram_polling(), stop_telegram_polling()
- `src/app/services/telegram.py` - removed updater(None) lru_cache singleton; get_telegram_bot() reads from app.state.telegram_app.bot; added set_fastapi_app()
- `src/app/main.py` - lifespan updated to start/stop PTB Application, store on app.state.telegram_app, call set_fastapi_app()

## Decisions Made
- PTB Application replaces updater(None) singleton — polling required for Phase 2 mood flow callback queries
- set_fastapi_app() pattern avoids circular imports between services/telegram.py and telegram/app.py by storing the FastAPI app reference at module level rather than importing telegram/app.py from services
- check_script_similarity filters WHERE (1 - embedding<=>query) > threshold, NOT where distance > threshold — correct pgvector cosine distance-to-similarity inversion
- rejection_constraints table created now (Phase 2 reads, Phase 4 writes) so pipeline queries return empty result safely

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required

The following environment variables must be added to `.env` before the service will start:

| Variable | Source |
|----------|--------|
| ANTHROPIC_API_KEY | https://console.anthropic.com/ -> API Keys -> Create Key |
| OPENAI_API_KEY | https://platform.openai.com/api-keys -> Create new secret key |

CLAUDE_GENERATION_MODEL defaults to `claude-haiku-3-5-20241022` — override in .env to upgrade without redeploy.

## Next Phase Readiness
- Plan 02-02 (Topic generation service) can now import anthropic/openai and call the similarity SQL function
- Plan 02-03 (Mood flow handlers) can register callback query handlers on app.state.telegram_app
- Migration 0002 must be applied to Supabase before the pipeline runs similarity checks
- .env file needs ANTHROPIC_API_KEY and OPENAI_API_KEY populated

## Self-Check: PASSED

- FOUND: src/app/telegram/__init__.py
- FOUND: src/app/telegram/app.py
- FOUND: migrations/0002_script_generation.sql
- FOUND: 02-01-SUMMARY.md
- FOUND: commit 876b84b (Task 1)
- FOUND: commit 3517e5d (Task 2)
- FOUND: commit bad6c25 (metadata)

---
*Phase: 02-script-generation*
*Completed: 2026-02-20*
