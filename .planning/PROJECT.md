# Autonomous Content Machine

## What This Is

An automated AI-powered content pipeline for a single creator. The system generates one cute Mexican cat short-form video per day — AI-generated via Kling AI 3.0 with a fixed character bible, dynamically matched licensed music, and a scene engine that varies location, activity, and mood daily with seasonal Mexican cultural overlays — delivers it to a Telegram bot for approval, then publishes to TikTok, IG Reels, FB Reels, and YT Shorts automatically with AI content labels and music license enforcement at the publish gate.

## Core Value

A cute Mexican cat video lands in Telegram every day, ready to approve and publish — the creator's only job is to say yes or no.

## Current State

**Shipped:** v2.0 Mexican Cat Content Machine — 2026-03-20
**Codebase:** ~7,040 LOC Python
**Tech stack:** Python 3.11, FastAPI, APScheduler, Supabase (Postgres + pgvector), fal.ai (Kling AI 3.0), GPT-4o, Railway

The full pipeline is operational: Kling AI generates a cat video daily from a GPT-4o scene prompt, MusicMatcher picks a licensed track, the creator approves or rejects via Telegram, and the video publishes to all 4 platforms with AI compliance labels and per-platform music license enforcement.

**Remaining before live deployment:**
- Empirical anti-repetition threshold calibration (scene_anti_repetition_enabled is False; log-only mode)
- Kling API rate limit observation (1-week test recommended before circuit breaker threshold finalized)
- Railway env vars: FAL_API_KEY, KLING_MODEL_VERSION must be added
- Supabase migration 0008-0011 must be applied to production DB

## Requirements

### Validated

<!-- Shipped in v1.0 — confirmed working -->

- ✓ Daily automated pipeline job (APScheduler + FastAPI) — v1.0/Phase 1
- ✓ Anti-repetition vector search via pgvector — v1.0/Phase 2 (recalibrated to 0.78 threshold, 7-day lookback in v2.0)
- ✓ Telegram bot delivery: video preview + caption + [Approve] / [Reject with Cause] buttons — v1.0/Phase 4
- ✓ Rejection feedback stored and injected into next generation — v1.0/Phase 4 + v2.0/Phase 10
- ✓ Auto-publish to TikTok, IG Reels, FB Reels, YT Shorts via direct platform APIs — v1.0/Phase 5
- ✓ 48-hour performance metric harvest (views, shares, retention) — v1.0/Phase 6
- ✓ Sunday weekly report + virality alert (500% above average) — v1.0/Phase 6
- ✓ Tiered storage lifecycle: Hot (0-7d) → Warm (8-45d) → Cold/Delete (45d+, except viral) — v1.0/Phase 6
- ✓ Circuit breaker with daily halt + weekly escalation — v1.0/Phase 7
- ✓ Approval timeout handling — v1.0/Phase 7
- ✓ All API keys encrypted in environment variables; Telegram bot locked to single user ID — v1.0/Phase 1
- ✓ AI cat video generation (20-30s, 9:16 1080p) via Kling AI 3.0 + fal.ai — v2.0/Phase 9
- ✓ Fixed Mexican cat character (CHARACTER_BIBLE constant, 49 words, orange tabby Mochi) — v2.0/Phase 9
- ✓ Kling circuit breaker: 20% failure threshold, exponential backoff, midnight reset — v2.0/Phase 9
- ✓ AI content labels applied on all platforms before publish — v2.0/Phase 9
- ✓ Scene engine: GPT-4o selects from 50 curated location/activity/mood combos — v2.0/Phase 10
- ✓ Seasonal calendar: themed scene overlays for Sep 16, Nov 1-2, Nov 20, Aug 8 — v2.0/Phase 10
- ✓ Scene anti-repetition (0.78 cosine, 7-day lookback) — v2.0/Phase 10 (feature-flagged, log-only until calibrated)
- ✓ Universal Spanish caption (5-8 words, [observation] + [implied personality]) — v2.0/Phase 10
- ✓ MusicMatcher: mood-to-BPM selection from pre-tagged pool — v2.0/Phase 10
- ✓ Per-platform music license matrix enforced at publish gate — v2.0/Phase 11

### Active

<!-- Next milestone scope -->

(None — awaiting v3.0 planning)

### Out of Scope

- Multi-user support — single creator only, no accounts or tenancy
- Horizontal short-form formats — 9:16 only
- Analytics dashboards/UI — all interaction via Telegram only
- AI avatar / spoken content — cat videos are visual-only, no voice
- Per-platform post copy variants — universal caption validated in v2.0
- Weekly mood profile Telegram flow — replaced by seasonal calendar
- 5 Pillars philosophical framework — not applicable to cat content
- Music fallback pool (50-track backup) — deferred to v3.0
- Compliance audit log per publish — deferred to v3.0
- Quarterly music pool refresh workflow — deferred to v3.0
- MEDIUM/HIGH complexity scenes (pounce, zoom) — expand after LOW complexity validates
- Caption A/B testing — deferred to v3.0

## Context

- **Content identity**: Fixed recurring Mexican cat character "Mochi" (orange tabby, 49-word character bible), shown in varied Mexican and everyday environments
- **Scene variety**: 50 curated combos; location + activity + mood rotate daily via GPT-4o selection; seasonal themes overlay automatically
- **Content language**: Captions in Spanish, casual and cute tone; universal (no per-platform variants)
- **Generation cadence**: 1 video/day, fully automated — creator approves or rejects via Telegram
- **Target platforms**: TikTok, Instagram Reels, Facebook Reels, YouTube Shorts
- **Music pool**: Pre-curated, tagged by mood + BPM + per-platform license flags; per-platform license gate at publish

## Constraints

- **Tech — Language/Backend**: Python 3.11 + FastAPI
- **Tech — Scene AI**: GPT-4o generates scene prompts within curated categories
- **Tech — Video generation**: Kling AI 3.0 via fal.ai async SDK (fal-client==0.13.1)
- **Tech — Music**: Pre-curated music pool, mood-matched per video; no voice/TTS
- **Tech — Publishing**: Direct platform APIs: TikTok Content Publishing API, Meta Graph API (Instagram + Facebook Pages), YouTube Data API v3
- **Tech — Database**: Supabase (Postgres + pgvector for anti-repetition)
- **Tech — Storage**: Supabase Storage for video lifecycle management
- **Tech — Scheduler**: APScheduler 3.10.x with Postgres job store (survives deploys)
- **Tech — Telegram**: python-telegram-bot v21.x (async)
- **Tech — HTTP client**: httpx (async — never requests in async context)
- **Tech — Infrastructure**: Railway.app (persistent worker, not serverless)
- **Tech — Interface**: Telegram bot only — no web UI, no mobile app
- **Privacy**: Bot restricted to creator's Telegram user ID; all secrets in encrypted env vars

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Telegram as sole UI | Zero-friction approval loop; no app to open | ✓ Good — validated in v1.0 |
| Direct APIs vs Ayrshare aggregator | Direct API control: no third-party rate limits, no aggregator cost, full platform compliance | ✓ Good — TikTok, Meta, YouTube APIs in place |
| Vector DB for anti-repetition | Semantic similarity (not keyword) prevents topic/scene recycling | ✓ Good — validated in v1.0 and v2.0 |
| Single user architecture | Simpler, faster to build; no auth/tenancy overhead | ✓ Good — validated in v1.0 |
| Kling AI 3.0 via fal.ai | 7-60x cheaper than alternatives; character consistency features shipped March 2026 | ✓ Good — selected after v2.0 research |
| CHARACTER_BIBLE as Python constant | Deployment-consistent; no DB lookup on every generation; embedded in kling.py | ✓ Good — 49 words, orange tabby Mochi |
| Universal caption vs per-platform | Simpler pipeline; cat content performs without platform-specific copy | ✓ Good — validated in v2.0 |
| Hybrid scene engine | AI creativity within curated guardrails (50 combos) ensures quality + variety | ✓ Good — validated in v2.0 |
| Scene anti-repetition feature-flagged | Threshold requires empirical calibration; log-only mode until 20-30 test video pairs validated | ⚠️ Revisit — enable when calibration complete |
| Music license gate fail-open on null track_id | Backward compatibility for legacy content_history rows without a track | ✓ Good — safe default |
| Kling CB separate from HeyGen CB | Different failure models: rate-based vs cost+count-based | ✓ Good — clean separation |

---
*Last updated: 2026-03-20 after v2.0 milestone — Mexican Cat Content Machine*
