---
phase: 07-hardening
plan: 01
subsystem: testing
tags: [pytest, unittest.mock, e2e, integration-test, daily-pipeline, anthropic]

# Dependency graph
requires:
  - phase: 06-analytics-and-storage
    provides: complete pipeline chain including analytics jobs and storage lifecycle
  - phase: 03-video-production
    provides: daily_pipeline_job() with HeyGen submit and content_history writes
  - phase: 04-telegram-approval-loop
    provides: send_approval_message_sync and approval flow
provides:
  - E2E integration test (test_daily_pipeline_writes_content_history) verifying full pipeline chain
  - pytest e2e mark registered in pyproject.toml
  - clear_lru_cache autouse fixture preventing settings cache pollution between tests
  - Regression safety net for Phase 7 hardening changes
affects: [07-02, 07-03, 07-04]

# Tech tracking
tech-stack:
  added: [pytest.mark.e2e (registered marker)]
  patterns: [TDD test-first, patch-where-looked-up for lazy imports, skipif-on-missing-credential]

key-files:
  created:
    - tests/test_phase07_e2e.py
  modified:
    - pyproject.toml

key-decisions:
  - "Patch HeyGenService at app.services.heygen.HeyGenService (source module) not at importer — lazy import inside daily_pipeline_job() body requires source-path patching per Python mock rules"
  - "Register pytest.mark.e2e in [tool.pytest.ini_options] to suppress PytestUnknownMarkWarning"
  - "clear_lru_cache autouse fixture teardown prevents stale Settings cached instance across test calls (Pitfall 7)"
  - "Mock all four externals: HeyGenService, register_video_poller, send_alert_sync, send_approval_message_sync — incomplete mocking causes APScheduler RuntimeError (Pitfall 6)"

patterns-established:
  - "E2E test: import daily_pipeline_job inside test function body to avoid import-time ValidationError"
  - "skipif(not os.getenv('ANTHROPIC_API_KEY')): skip-not-fail on missing credential"
  - "mock_all_externals fixture yields dict keyed by short name for readable assertion access"

requirements-completed:
  - INFRA-01
  - INFRA-02
  - INFRA-03
  - INFRA-04
  - SCRTY-01
  - SCRTY-02
  - SCRP-01
  - SCRP-02
  - SCRP-03
  - SCRP-04
  - VIDP-01
  - VIDP-02
  - VIDP-03
  - VIDP-04
  - TGAP-01
  - TGAP-02
  - TGAP-03
  - TGAP-04
  - PUBL-01
  - PUBL-02
  - PUBL-03
  - PUBL-04
  - ANLX-01
  - ANLX-02
  - ANLX-03
  - ANLX-04

# Metrics
duration: 6min
completed: 2026-03-01
---

# Phase 7 Plan 01: E2E Integration Test Summary

**Pytest E2E test calling daily_pipeline_job() directly with real Anthropic and mocked HeyGen/Telegram, asserting content_history DB row creation and mock invocation counts**

## Performance

- **Duration:** 6 min
- **Started:** 2026-03-01T07:01:38Z
- **Completed:** 2026-03-01T07:07:38Z
- **Tasks:** 1
- **Files modified:** 2

## Accomplishments
- Created tests/test_phase07_e2e.py with full pipeline E2E test covering all 26 v1 requirements
- Test collects cleanly under pytest with no warnings; skips gracefully when ANTHROPIC_API_KEY absent
- All 21 existing smoke tests (phases 4 and 5) remain green after changes
- Registered pytest.mark.e2e in pyproject.toml to eliminate PytestUnknownMarkWarning

## Task Commits

Each task was committed atomically:

1. **Task 1: Write E2E integration test with mocked externals** - `d183bb0` (feat)

**Plan metadata:** (docs commit below)

_Note: TDD task — test and implementation are in a single file; GREEN confirmed by collection + skip behavior_

## Files Created/Modified
- `tests/test_phase07_e2e.py` - E2E integration test calling daily_pipeline_job() with mocked HeyGen/Telegram and real Anthropic
- `pyproject.toml` - Added [tool.pytest.ini_options] with e2e marker registration

## Decisions Made
- Registered `pytest.mark.e2e` in pyproject.toml `[tool.pytest.ini_options]` to avoid PytestUnknownMarkWarning — clean test runs are important for CI readability
- Used `@pytest.mark.skipif(not os.getenv("ANTHROPIC_API_KEY"), ...)` over `pytest.importorskip` — simpler for env-var-based skip condition
- `mock_all_externals` yields a dict (not multiple fixture args) — single fixture argument in test signature, readable assertion access via `mock_all_externals["heygen"]`

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Registered pytest.mark.e2e marker in pyproject.toml**
- **Found during:** Task 1 (test collection verification)
- **Issue:** pytest emitted PytestUnknownMarkWarning for `pytest.mark.e2e` — unregistered marks produce warnings that clutter CI output and may fail with `--strict-markers`
- **Fix:** Added `[tool.pytest.ini_options]` section to pyproject.toml with `markers = ["e2e: ..."]`
- **Files modified:** pyproject.toml
- **Verification:** Re-ran `--collect-only` — no warnings, 1 test collected
- **Committed in:** d183bb0 (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (Rule 2 - missing marker registration)
**Impact on plan:** Necessary for clean test output. No scope creep.

## Issues Encountered
None — plan executed without blocking issues. The patch-at-source-module approach for lazy imports worked correctly on first attempt.

## User Setup Required
None - no external service configuration required for test file creation.

## Next Phase Readiness
- E2E test provides regression safety net for all subsequent Phase 7 hardening changes
- Test is ready to run with real ANTHROPIC_API_KEY when available (skips cleanly otherwise)
- Plans 07-02 (approval timeout), 07-03 (manual resume), 07-04 (JSON logging) can all be validated against this test
- Note: test also requires real Supabase credentials (SUPABASE_URL, SUPABASE_KEY) to write and read content_history row

---
*Phase: 07-hardening*
*Completed: 2026-03-01*
