---
phase: quick-009
plan: 01
subsystem: database
tags: [jwt, supabase, startup-validation, fail-fast, base64, stdlib]

# Dependency graph
requires:
  - phase: quick-007
    provides: event loop fixes in telegram sync wrappers
provides:
  - validate_supabase_key() function decoding JWT payload and asserting role == 'service_role'
  - lifespan call before run_migrations() so misconfiguration aborts startup with a clear message
affects: [lifespan startup, Railway deployment, database]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Fail-fast JWT role validation at startup using only stdlib (base64, json)"
    - "TDD: RED commit before GREEN implementation commit"

key-files:
  created:
    - tests/test_validate_supabase_key.py
  modified:
    - src/app/services/database.py
    - src/app/main.py

key-decisions:
  - "validate_supabase_key uses only base64 + json (stdlib) — no new runtime dependencies"
  - "No signature verification — only payload role claim is read; signing is irrelevant for role check"
  - "Placed before run_migrations() in lifespan so no DB work begins with wrong credentials"
  - "RuntimeError propagated unhandled from lifespan — FastAPI exits with non-zero code, Railway logs full message"

patterns-established:
  - "Startup guard pattern: validate env-derived secrets before any IO (DB, network) in lifespan"

requirements-completed: []

# Metrics
duration: 8min
completed: 2026-03-16
---

# Quick Task 009: Supabase Key Validation Summary

**Fail-fast startup guard decodes SUPABASE_KEY JWT payload and raises RuntimeError naming the wrong role before any DB work begins**

## Performance

- **Duration:** 8 min
- **Started:** 2026-03-16T00:00:00Z
- **Completed:** 2026-03-16T00:08:00Z
- **Tasks:** 2
- **Files modified:** 3 (database.py, main.py, tests/test_validate_supabase_key.py)

## Accomplishments

- `validate_supabase_key()` added to `src/app/services/database.py` using only stdlib (base64, json) — no new dependencies
- Six behavior cases covered by unit tests (TDD): service_role passes, anon raises, unexpected role raises, non-JWT string raises, one-dot malformed JWT raises, missing role key raises
- Lifespan now calls `validate_supabase_key(get_settings().supabase_key)` as the first statement after the startup log line, before `run_migrations()` — wrong key aborts the process before any DB work

## Task Commits

Each task was committed atomically:

1. **Task 1 RED: Failing tests** - `ef906aa` (test)
2. **Task 1 GREEN: validate_supabase_key() implementation** - `e68a947` (feat)
3. **Task 2: Wire into lifespan** - `1fb014a` (feat)

**Plan metadata:** (final docs commit)

_Note: TDD tasks have two commits — test (RED) then implementation (GREEN)._

## Files Created/Modified

- `src/app/services/database.py` - Added `validate_supabase_key()` + stdlib imports (base64, json, logging)
- `src/app/main.py` - Added import of `validate_supabase_key` and `get_settings`; inserted call before `run_migrations()`
- `tests/test_validate_supabase_key.py` - Six unit tests covering all specified behavior cases

## Decisions Made

- **Stdlib only:** base64 + json are sufficient; no PyJWT or cryptography needed since we skip signature verification — only the role claim matters.
- **No signature verification:** The key is a configuration secret already present in settings; we trust its content, just validate the role claim it encodes.
- **Placed before `run_migrations()`:** Ensures no DB work begins if credentials are wrong. This is the earliest practical validation point in the lifespan.
- **RuntimeError unhandled:** FastAPI propagates it as a startup exception; Railway catches the non-zero exit and logs the full message. No special exception handling needed.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None. Pre-existing unrelated failure: `test_hard_word_limit_constant` in `test_quick_001_script_generation.py` asserts `HARD_WORD_LIMIT == 120` but the constant was changed to 90 in a prior quick task. This is out-of-scope and pre-dates quick-009. All 6 new tests pass; all other previously-passing tests continue to pass.

## User Setup Required

None - no external service configuration required. The validation activates automatically on next Railway deployment using the existing `SUPABASE_KEY` env var.

## Next Phase Readiness

- Service will now fail fast at startup if `SUPABASE_KEY` is set to the anon key, preventing silent RLS 403s deep in the Storage upload pipeline.
- No blockers introduced.

---
*Phase: quick-009*
*Completed: 2026-03-16*
