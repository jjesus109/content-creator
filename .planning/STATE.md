---
gsd_state_version: 1.0
milestone: v2.0
milestone_name: Mexican Cat Content Machine
status: unknown
stopped_at: Completed 09-04-PLAN.md
last_updated: "2026-03-19T14:27:40.700Z"
progress:
  total_phases: 3
  completed_phases: 1
  total_plans: 4
  completed_plans: 4
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-18)

**Core value:** A cute Mexican cat video lands in Telegram every day, ready to approve and publish — the creator's only job is to say yes or no.
**Current focus:** Phase 09 — mexican-animated-cat-video-format

## Current Position

Phase: 09 (mexican-animated-cat-video-format) — EXECUTING
Plan: 3 of 4

## Accumulated Context

### Decisions

- [v2.0]: Kling AI 3.0 via fal.ai async SDK selected (7-60x cheaper than alternatives; character consistency features shipped March 2026)
- [v2.0]: Character Bible locked at 40-50 words embedded in every prompt; reference image upgrade if consistency <90%
- [v2.0]: Anti-repetition threshold recalibrated to 75-80% (from v1.0's 85%) — requires empirical validation before automation
- [v2.0]: Universal Spanish caption (5-8 words, [observation]+[implied personality] formula) — per-platform variants deferred to v3.0
- [v2.0]: Music pool 200+ tracks pre-curated; license matrix per platform mandatory before first publish
- [v2.0]: Phase 4 (Telegram approval) and Phase 5-6 (publishing, analytics) reused unchanged from v1.0
- [09-01]: kling_circuit_breaker_state kept separate from circuit_breaker_state — different failure models (rate-based vs cost+count-based)
- [09-01]: fal_api_key added to Settings explicitly even though fal_client auto-reads env — forces startup validation if key missing
- [Phase 09]: CHARACTER_BIBLE set to 49 words — orange tabby Mochi in Mexican household; embedded as Python constant in kling.py for deployment consistency
- [Phase 09]: fal-client==0.13.1 added as runtime dependency (not dev-only) — required by KlingService and video_poller_job in APScheduler ThreadPoolExecutor
- [09-03]: KlingCircuitBreakerService uses kling_circuit_breaker_state singleton — separate table from HeyGen CB; different failure model (rate-based vs cost+count-based)
- [09-03]: check_balance() and is_open() are fail-open — return safe defaults on errors to avoid unnecessary pipeline halts
- [09-03]: _submit_with_backoff at module level (not instance method) for tenacity decorator compatibility; record_attempt called in video_poller not daily_pipeline
- [Phase 09-04]: AI label applied at publish time in platform_publish.py (not before Telegram approval); YouTube label in description only; exception fallback prevents silent omission

### v1.0 Quick Tasks Completed

| # | Description | Date |
|---|-------------|------|
| 001 | Improve script generation prompt | 2026-03-04 |
| 002 | Dry-run script generation CLI | 2026-03-04 |
| 003 | HeyGen v2 payload alignment + dry-run CLI | 2026-03-05 |
| 004 | Replace Ayrshare with direct API references | 2026-03-06 |
| 005 | Add POST /admin/trigger-pipeline endpoint | 2026-03-15 |
| 006 | Protect /admin/* with Bearer token auth | 2026-03-15 |
| 007 | Fix Telegram _sync event loop RuntimeError | 2026-03-16 |
| 008 | HeyGen dynamic title from topic_summary | 2026-03-16 |
| 009 | Supabase service_role JWT startup validation | 2026-03-16 |

### Pending Todos

None.

### Blockers/Concerns

- [Phase 9]: Kling exact rate limits unknown — Phase 9 plan should include 1-week API test to observe real failure patterns before circuit breaker threshold is finalized
- [Phase 10]: Anti-repetition 75-80% threshold is research estimate — empirical calibration with 20-30 test video pairs required before automation enabled
- [Deployment]: New env vars FAL_API_KEY and KLING_MODEL_VERSION declared in Settings and .env.example — must be added to Railway before Phase 9 plans 02-04 execute
- [Deployment]: Migration 0008_v2_schema.sql must be applied to Supabase DB before Phase 9 plans 02-04 execute

## Session Continuity

Last session: 2026-03-19T14:27:40.698Z
Stopped at: Completed 09-04-PLAN.md
Resume file: None
