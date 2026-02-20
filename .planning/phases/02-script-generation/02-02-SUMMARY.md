---
phase: 02-script-generation
plan: "02"
subsystem: api
tags: [openai, pgvector, supabase, embeddings, similarity]

# Dependency graph
requires:
  - phase: 02-01
    provides: check_script_similarity SQL function (migration 0002), supabase client (database.py), openai_api_key in settings

provides:
  - EmbeddingService.generate(text) -> (list[float], float) — 1536-dim embedding + cost_usd
  - SimilarityService.is_too_similar(embedding) -> bool — pgvector cosine similarity check via RPC
  - SimilarityService.get_similar_scripts(embedding) -> list[dict] — debug/logging helper
affects: [02-03, 02-04, 02-05]  # daily pipeline job uses both services

# Tech tracking
tech-stack:
  added: []  # openai already added in 02-01
  patterns:
    - "Synchronous OpenAI client in APScheduler thread pool — never AsyncOpenAI"
    - "Fail-open similarity check — DB errors return False to prevent pipeline outage"
    - "RPC-only pgvector queries — .rpc() not .table().select() for vector operators"
    - "Cost-returning API wrappers — every external call returns cost_usd for circuit breaker"

key-files:
  created:
    - src/app/services/embeddings.py
    - src/app/services/similarity.py
  modified: []

key-decisions:
  - "EmbeddingService returns (embedding, cost_usd) tuple so caller can always call cb.record_attempt(cost)"
  - "SimilarityService fails open (returns False) on DB errors — content repetition preferable to pipeline outage"
  - "LOOKBACK_DAYS=90 and SIMILARITY_THRESHOLD=0.85 as module constants — configurable without code change if needed"
  - "SimilarityService accepts optional supabase Client in __init__ for testability without live DB"

patterns-established:
  - "Cost-returning wrapper: every OpenAI call returns cost so caller handles circuit breaker reporting"
  - "Fail-open DB checks: similarity/history queries default to safe permissive state on DB error"
  - "Injectable dependencies: services accept optional client args for unit testing without live credentials"

requirements-completed: [SCRP-02]

# Metrics
duration: 3min
completed: 2026-02-20
---

# Phase 2 Plan 02: Embedding and Similarity Services Summary

**OpenAI text-embedding-3-small wrapper and pgvector cosine similarity check via Supabase RPC, ready for daily pipeline anti-repetition gate**

## Performance

- **Duration:** 3 min
- **Started:** 2026-02-20T21:34:17Z
- **Completed:** 2026-02-20T21:37:00Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- EmbeddingService wrapping synchronous OpenAI text-embedding-3-small, returning (embedding, cost_usd) for circuit breaker reporting
- SimilarityService calling check_script_similarity via Supabase RPC, with fail-open design and 0.85/90-day defaults
- Both services are injectable (accept optional client args) for future unit testing without live credentials

## Task Commits

Each task was committed atomically:

1. **Task 1: EmbeddingService — synchronous OpenAI text-embedding-3-small wrapper** - `387abdc` (feat)
2. **Task 2: SimilarityService — pgvector check via Supabase RPC** - `29a6a7a` (feat)

**Plan metadata:** (docs commit — see below)

## Files Created/Modified
- `src/app/services/embeddings.py` - EmbeddingService with generate(text) -> (list[float], float); sync OpenAI client safe for APScheduler thread pool
- `src/app/services/similarity.py` - SimilarityService with is_too_similar() and get_similar_scripts(); uses .rpc() only, fails open on DB error

## Decisions Made
- EmbeddingService returns cost_usd alongside embedding so every caller can always report to CircuitBreakerService without needing to recalculate
- SimilarityService fails open (returns False) when the DB RPC raises — a single missed anti-repetition check is less harmful than a pipeline outage
- Injectable Supabase client in SimilarityService.__init__ enables unit tests without a live DB connection

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required beyond OPENAI_API_KEY already documented in Phase 2-01 blockers.

## Next Phase Readiness
- EmbeddingService and SimilarityService are ready for use in the Phase 2 daily pipeline job (02-03+)
- Both services import cleanly and have verified interfaces
- Blocker: OPENAI_API_KEY must be present in .env for actual API calls (documented in STATE.md)

---
*Phase: 02-script-generation*
*Completed: 2026-02-20*
