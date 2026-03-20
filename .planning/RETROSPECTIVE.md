# Project Retrospective

*A living document updated after each milestone. Lessons feed forward into future planning.*

---

## Milestone: v2.0 — Mexican Cat Content Machine

**Shipped:** 2026-03-20
**Phases:** 3 (9-11) | **Plans:** 12 | **Timeline:** 5 days (2026-03-15 → 2026-03-20)

### What Was Built

- Kling AI 3.0 video generation via fal.ai replacing HeyGen — CHARACTER_BIBLE constant (49 words, orange tabby Mochi) embedded in every generation prompt
- Scene engine: GPT-4o picks from 50 curated location/activity/mood combos; seasonal calendar auto-injects Mexican cultural day overlays
- Anti-repetition for scenes via pgvector (0.78 cosine, 7-day lookback) + rejection feedback injection — feature-flagged for empirical calibration
- MusicMatcher: mood-to-BPM selection (playful 110-125, sleepy 70-80, curious 90-100) from pre-tagged pool
- Music license gate: per-platform enforcement before any publish; `blocked` status in publish_events
- AI content labels applied on all 4 platforms before creator sees approval message

### What Worked

- Phase-by-phase TDD scaffold (Wave 0 failing tests → Wave 1 implementation) kept each plan self-contained and immediately testable
- Keeping CHARACTER_BIBLE as a Python constant (not DB config) eliminated a dependency and matched existing patterns in the codebase
- Fail-open defaults on circuit breakers and license gate (null music_track_id) protected backward compatibility without extra migration complexity
- Phase 11 gap closure as a dedicated plan (11-03) was clean — isolated schema gap, fixture sync, and targeted tests in one commit
- Using DB singleton table for Kling circuit breaker state (separate from HeyGen CB) kept failure models clean

### What Was Inefficient

- Scene anti-repetition threshold (0.78) was research-estimated, not empirically calibrated — feature had to ship in log-only mode with a flag; requires a dry-run script before automation can be enabled
- Kling rate limits unknown at development time — circuit breaker threshold (20%) is a reasonable default but needs 1-week production observation before trust
- music_pool schema lacked `platform_facebook` column until Phase 11 gap closure — caught by the gate implementation, not by upfront schema design

### Patterns Established

- Feature flags (Settings.scene_anti_repetition_enabled) for ML/threshold features that require empirical calibration before automation
- `_check_music_license_cleared()` as a pre-publish gate pattern — can be extended to other platform-specific compliance checks
- Seasonal calendar as a service class (not data in DB) — simple, deployment-consistent, no runtime cost
- Single GPT-4o call returning both scene_prompt and caption as JSON — avoids two round-trips for tightly coupled outputs

### Key Lessons

1. Schema gaps surface late when the feature consuming the schema is built last — schema review against all phases during Wave 0 would catch missing columns before implementation starts
2. Features with empirical calibration dependencies should ship with feature flags from day one — enables log-only validation without blocking the pipeline
3. CHARACTER_BIBLE as a Python constant (not DB config) is a strong pattern for stable content-strategy values: version-controlled, no startup validation needed, no migration to change

### Cost Observations

- Model mix: budget profile throughout (Haiku-class agents where applicable)
- Sessions: ~5 working sessions over 5 days
- Notable: 95 commits in 5 days; 12 plans across 3 phases — consistent daily throughput with no context resets required

---

## Cross-Milestone Trends

### Process Evolution

| Milestone | Phases | Plans | Timeline | Key Change |
|-----------|--------|-------|----------|------------|
| v1.0 | 8 | 36 | ~12 days | Initial pipeline — greenfield |
| v2.0 | 3 | 12 | 5 days | Content engine swap — v1.0 publishing infra reused unchanged |

### Cumulative Quality

| Milestone | Notes |
|-----------|-------|
| v1.0 | Full pipeline: scheduler, Telegram, multi-platform publish, analytics, storage lifecycle |
| v2.0 | Content engine replaced; scene engine, music matching, compliance gate added; 149+ tests passing at close |

### Top Lessons (Verified Across Milestones)

1. Reusing existing infrastructure (publish pipeline, approval loop, analytics) enables focused milestones — v2.0 delivered a full content engine swap in 5 days because phases 1-8 were untouched
2. DB singletons for circuit breaker state work well — simple, survives deploys, no ORM needed
3. Telegram as the sole UI remains the right call — zero friction for the creator, easy to extend

---
*Created: 2026-03-20 after v2.0 milestone*
