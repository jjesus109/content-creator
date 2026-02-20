---
phase: 02-script-generation
plan: "05"
subsystem: scheduler
tags: [apscheduler, pipeline, orchestration, circuit-breaker, embeddings, similarity, script-generation]

# Dependency graph
requires:
  - phase: 02-script-generation plan 04
    provides: ScriptGenerationService with generate_topic_summary, generate_script, summarize_if_needed
  - phase: 02-script-generation plan 02
    provides: EmbeddingService and SimilarityService
  - phase: 02-script-generation plan 03
    provides: MoodService with get_current_week_mood
  - phase: 01-foundation
    provides: CircuitBreakerService, APScheduler registry, get_supabase, send_alert_sync
provides:
  - daily_pipeline_job() orchestrating the full Phase 2 generation loop at 7 AM Mexico City
  - _save_to_content_history() persisting script + embedding for future similarity checks
  - 4 registered scheduler jobs (was 2 in Phase 1, added weekly_mood in 02-03, now daily_pipeline replaces heartbeat)
affects: [03-video-generation, 07-hardening]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Retry loop with attempt counter — attempt=0 (fresh), attempt=1 (same root/different angle), attempt>=2 (completely different topic)"
    - "Circuit breaker checked after every external API call with early return on trip"
    - "Fail-soft on DB write — script loss preferable to false failure alert"

key-files:
  created:
    - src/app/scheduler/jobs/daily_pipeline.py
  modified:
    - src/app/scheduler/registry.py
    - src/app/scheduler/jobs/heartbeat.py

key-decisions:
  - "MAX_RETRIES=2 (3 total attempts): balances cost (~3 embed + ~3 topic gen calls max) vs freshness — same planner decision from 02-04"
  - "Circuit breaker checked after topic_cost and embed_cost separately — mid-run trip halts pipeline immediately with distinct alert per stage"
  - "summarize_if_needed CB report is non-fatal: cb.record_attempt() called but return value not checked — script already generated, losing word-count guard is preferable to halting"
  - "DB write failure is fail-soft: do not re-raise, send Telegram alert instead — script was generated, losing DB write is preferable to alerting as pipeline failure"
  - "heartbeat_job deprecated in Phase 2 but kept for reference — daily_pipeline_trigger now points to daily_pipeline_job"

patterns-established:
  - "Pipeline pattern: CB check first → load config → initialize services → load constraints → retry loop → save"
  - "Retry continuation: `continue` inside loop on similarity hit, early `return` on CB trip or exhausted retries"

requirements-completed: [SCRP-01, SCRP-02, SCRP-03, SCRP-04]

# Metrics
duration: 3min
completed: 2026-02-20
---

# Phase 2 Plan 05: Daily Pipeline Orchestrator Summary

**APScheduler daily_pipeline_job wires all Phase 2 services: CB check, mood load, topic gen, embed, similarity retry loop (3 attempts), script gen, auto-summarize, save to content_history with embedding**

## Performance

- **Duration:** 3 min
- **Started:** 2026-02-20T21:47:04Z
- **Completed:** 2026-02-20T21:50:00Z
- **Tasks:** 1 of 1 auto tasks complete (checkpoint pending human review)
- **Files modified:** 3

## Accomplishments

- Created `daily_pipeline_job()` with complete orchestration: CB check, mood load, topic gen, embed, similarity check, script gen, auto-summarize, save to content_history
- Wired `daily_pipeline_trigger` in `registry.py` to call `daily_pipeline_job` (replacing `heartbeat_job`)
- Full import chain verified: `main.py` -> `registry.py` -> `daily_pipeline.py` -> all Phase 2 services
- 4 registered scheduler jobs confirmed: `daily_pipeline_trigger`, `cb_midnight_reset`, `weekly_mood_prompt`, `weekly_mood_reminder`
- Deprecated `heartbeat.py` with Phase 2 comment (kept for reference)

## Task Commits

Each task was committed atomically:

1. **Task 1: daily_pipeline_job — full orchestration loop, update registry** - `28c234e` (feat)

**Plan metadata:** (pending — will be added in final commit)

## Files Created/Modified

- `src/app/scheduler/jobs/daily_pipeline.py` - Full pipeline orchestrator with MAX_RETRIES=2, CB checks, retry loop, save helper
- `src/app/scheduler/registry.py` - daily_pipeline_trigger now calls daily_pipeline_job; heartbeat_job removed
- `src/app/scheduler/jobs/heartbeat.py` - Deprecation comment added at top of file

## Decisions Made

- MAX_RETRIES=2 (3 total attempts): balances cost vs freshness — consistent with planner's 02-04 decision
- Circuit breaker checked after topic generation cost and embedding cost separately — distinct early-return paths with separate Telegram alerts per stage
- `summarize_if_needed` CB call is non-fatal — script already generated; halting for word-count summarization cost is disproportionate
- DB write failure is fail-soft: send Telegram alert and continue — script was already generated

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

None — all imports resolved cleanly, verification passed on first attempt.

## User Setup Required

None — no external service configuration required for this plan.

## Next Phase Readiness

- Phase 2 (Script Generation) is functionally complete: all services wired, pipeline runs daily at 7 AM Mexico City
- Checkpoint pending: human must verify full import chain and 4 registered jobs (see checkpoint task in plan)
- Phase 3 (Video Generation) can begin after checkpoint approval and .env credential population
- Blockers remain: .env credentials not populated; pgvector 0.85 threshold uncalibrated for Spanish philosophical content

---
*Phase: 02-script-generation*
*Completed: 2026-02-20*
