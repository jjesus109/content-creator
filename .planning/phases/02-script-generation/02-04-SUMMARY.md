---
phase: 02-script-generation
plan: "04"
subsystem: api
tags: [anthropic, claude, script-generation, spanish, 6-pillar, nlp]

# Dependency graph
requires:
  - phase: 02-script-generation/02-02
    provides: EmbeddingService for similarity checking (generate_topic_summary feeds into it)
  - phase: 02-script-generation/02-03
    provides: MoodService with target_words, pool, tone fields consumed by generate_script()
  - phase: 01-foundation
    provides: get_settings() for API keys, get_supabase() for rejection_constraints queries
provides:
  - ScriptGenerationService with generate_topic_summary(), generate_script(), summarize_if_needed(), load_active_rejection_constraints()
  - 6-pillar Spanish philosophical script generation via synchronous Claude API
  - Auto-summarization guard — caller always receives within-limit script (SCRP-03)
  - Rejection constraint injection from rejection_constraints table
affects: [02-05-pipeline-orchestrator, 04-approval-flow]

# Tech tracking
tech-stack:
  added: [anthropic (sync Anthropic client)]
  patterns: [tuple return (text, cost_usd) for every Claude call, synchronous Anthropic client for APScheduler ThreadPoolExecutor compatibility]

key-files:
  created:
    - src/app/services/script_generation.py
  modified: []

key-decisions:
  - "generate_topic_summary() generates a 15-word phrase BEFORE full script — cheap similarity pre-check avoids paying for full generation on topics that will be rejected"
  - "attempt=1 vs attempt=2 give different retry instructions — same pool/different angle vs completely different topic within pool"
  - "summarize_if_needed() explicitly names which pillars to preserve (Philosophical Root, Emotional Anchor, Reflective CTA) — compression absorbs Insight Flip development section"
  - "Sentence-boundary truncation fallback when Claude overshoots summarization target — avoids mid-sentence cuts"
  - "target_words * 4 as max_tokens — enough room for Spanish word variance without wasting budget"
  - "Uses synchronous Anthropic client only — AsyncAnthropic incompatible with APScheduler ThreadPoolExecutor (no event loop)"
  - "load_active_rejection_constraints() fails open (returns []) on DB error — pipeline proceeds without constraints rather than halting"

patterns-established:
  - "Tuple return pattern: all public methods return (result, cost_usd) so daily pipeline can always call cb.record_attempt(cost)"
  - "Constraint injection: _format_constraints() builds RESTRICCIONES ACTIVAS block; empty string when no constraints — no conditional logic in caller"
  - "Sync-only Claude: All generation services use synchronous Anthropic client for APScheduler thread pool compatibility"

requirements-completed: [SCRP-01, SCRP-03]

# Metrics
duration: 1min
completed: 2026-02-20
---

# Phase 2 Plan 04: ScriptGenerationService Summary

**Synchronous Claude API service generating 6-pillar Spanish philosophical scripts with auto-summarization, retry-aware topic generation, and active rejection constraint injection**

## Performance

- **Duration:** 1 min
- **Started:** 2026-02-20T21:43:02Z
- **Completed:** 2026-02-20T21:44:00Z
- **Tasks:** 1
- **Files modified:** 1

## Accomplishments
- ScriptGenerationService with full 6-pillar system prompt in Spanish (RAIZ FILOSOFICA, TENSION UNIVERSAL, GIRO DE PERSPECTIVA, ANCLA EMOCIONAL, CTA REFLEXIVO, ARQUETIPO DEL CREADOR)
- generate_topic_summary() with attempt-aware retry instructions (same root/different angle vs completely different topic)
- summarize_if_needed() auto-compresses over-length scripts while preserving named pillars; sentence-boundary truncation fallback
- load_active_rejection_constraints() safely reads from rejection_constraints table (empty in Phase 2, written by Phase 4)
- All methods return (result, cost_usd) tuple for circuit breaker integration

## Task Commits

Each task was committed atomically:

1. **Task 1: ScriptGenerationService — 6-pillar generation, word count guard, summarization** - `f946cb7` (feat)

**Plan metadata:** (docs commit below)

## Files Created/Modified
- `src/app/services/script_generation.py` - ScriptGenerationService with generate_topic_summary(), generate_script(), summarize_if_needed(), load_active_rejection_constraints(), _call_claude(), _format_constraints()

## Decisions Made
- generate_topic_summary() pre-generates a 15-word topic phrase before full script generation — cheaper similarity check avoids paying for full Claude generation on topics that will be rejected by the similarity service
- attempt=1 gives "same philosophical root, different angle" instruction; attempt>=2 gives "completely different topic" — distinct retry strategies for different similarity failure modes
- summarize_if_needed() names the 3 pillars to preserve explicitly (Philosophical Root, Emotional Anchor, Reflective CTA) — Claude compresses the Insight Flip development section which is most flexible
- Sentence-boundary truncation fallback: if Claude still overshoots after summarization, truncate at last sentence-ending punctuation within target_words
- Synchronous Anthropic client chosen over AsyncAnthropic — APScheduler uses ThreadPoolExecutor, no event loop available

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required (ANTHROPIC_API_KEY already in settings.py, credential added to .env separately).

## Next Phase Readiness
- ScriptGenerationService ready for Plan 05 (daily pipeline orchestrator) which calls generate_topic_summary() → similarity check → generate_script() → summarize_if_needed()
- All Phase 2 services (EmbeddingService, SimilarityService, MoodService, ScriptGenerationService) import cleanly together
- rejection_constraints table exists and is safely queryable (returns empty list in Phase 2 state)

---
*Phase: 02-script-generation*
*Completed: 2026-02-20*
