# Autonomous Content Machine

## What This Is

An automated AI-powered dual-pipeline content machine for a single creator. Pipeline 1 generates one Mexican cat short-form video per day via Kling AI 3.0. Pipeline 2 generates one Deep History & Education narrated video (2–5 min 16:9 long-form + 60s 9:16 short cut) every two days via ElevenLabs voice, Shotstack stock-footage composition, and Whisper subtitles. Both pipelines deliver to Telegram for approval, then auto-publish to platform-appropriate targets with AI content labels.

## Core Value

Every piece of content lands in Telegram ready to approve — the creator's only job is to say yes or no.

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

<!-- v4.0 scope — Dual-Pipeline Content Machine -->

- [ ] `content_type` discriminator in `content_history` — separates cat and history rows across shared pipeline infrastructure
- [ ] GPT-4o script generation for Deep History & Education — 500–700 words, structured hook / body / CTA, topic anti-repetition via pgvector (30-day lookback)
- [ ] ElevenLabs voice narration — single consistent channel voice, MP3 stored in Supabase Storage `audio-files/` bucket
- [ ] Whisper subtitle generation — SRT from ElevenLabs audio, stored in Supabase Storage `subtitle-files/` bucket
- [ ] Shotstack video composition — Pexels stock footage + ElevenLabs audio + Whisper SRT, two JSON templates (long 16:9 / short 9:16)
- [ ] Dual-format render — 2–5 min 16:9 long-form and 60s 9:16 short cut produced per pipeline run
- [ ] History APScheduler job — runs every 2 days; cat job unchanged (daily); both share Postgres job store
- [ ] Telegram approval extended — shows content type (cat vs history) and format previews; single approval publishes all formats
- [ ] Format-aware publishing — YouTube + Facebook receive long-form; YouTube Shorts + TikTok + Instagram Reels receive short
- [ ] DB migration — `content_type` column on `content_history`, `history_topics` table, `audio_url` / `long_video_url` / `short_video_url` / `subtitle_url` columns, Supabase Storage buckets created

### Out of Scope

- Multi-user support — single creator only, no accounts or tenancy
- Analytics dashboards/UI — all interaction via Telegram only
- Per-platform post copy variants — universal caption validated in v2.0; same policy for history channel
- Weekly mood profile Telegram flow — replaced by seasonal calendar (cat) / topic rotation (history)
- 5 Pillars philosophical framework — not applicable
- Music for history videos — narrated voice content; no background music in v4.0
- Multiple history niches — single niche (Deep History & Education) only; multi-channel deferred
- AI avatar / on-camera presenter — stock footage + voice only; no avatar video
- Caption A/B testing — deferred
- Compliance audit log per publish — deferred
- Quarterly music pool refresh — deferred

## Current Milestone: v4.0 Dual-Pipeline Content Machine

**Goal:** Add Deep History & Education narrated video pipeline alongside the existing cat pipeline — shared infrastructure, separate jobs, unified Telegram approval.

**Target features:** script generation, ElevenLabs voice, Whisper subtitles, Shotstack composition, dual-format render (2–5 min + 60s), format-aware publishing, DB migration.

## Context

- **Pipeline 1 — Cat**: Fixed grey kitten character (CHARACTER_BIBLE, v3.0), Kling AI 3.0 via fal.ai, scene engine, music matching, Spanish captions, daily cadence, YT Shorts + TikTok + IG Reels + FB Reels
- **Pipeline 2 — History**: Deep History & Education niche, GPT-4o 500–700 word scripts, ElevenLabs voice, Shotstack + Pexels stock footage, Whisper SRT subtitles, every-2-days cadence, YouTube + Facebook (long-form) + YT Shorts + TikTok + IG Reels (short)
- **Shared infrastructure**: FastAPI, APScheduler (Postgres job store), Supabase (Postgres + pgvector + Storage), Telegram approval bot, direct platform publishers, Railway deployment
- **Anti-repetition**: Cat uses scene embedding (0.78 cosine, 7-day lookback); History uses topic+era embedding (0.78 cosine, 30-day lookback)
- **Storage**: Supabase Storage for all media — cat videos (existing), history audio / long video / short video / subtitles (new buckets)

## Constraints

- **Tech — Language/Backend**: Python 3.11 + FastAPI
- **Tech — Cat video generation**: Kling AI 3.0 via fal.ai async SDK (fal-client==0.13.1)
- **Tech — History script**: GPT-4o (same client as cat scene engine)
- **Tech — History voice**: ElevenLabs API — Flash v2.5, Creator Plan ($22/month, 100K chars)
- **Tech — History subtitles**: OpenAI Whisper-1 via `openai.audio.transcriptions`
- **Tech — History video composition**: Shotstack API — JSON templates, Pexels API for stock footage
- **Tech — Music**: Cat pipeline only; history pipeline has no background music in v4.0
- **Tech — Publishing**: Direct platform APIs: TikTok Content Publishing API, Meta Graph API (Instagram + Facebook Pages), YouTube Data API v3
- **Tech — Database**: Supabase (Postgres + pgvector for anti-repetition)
- **Tech — Storage**: Supabase Storage — no S3; all media (cat + history) stored in Supabase buckets
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

| Dual pipeline coexistence | Cat and history share infrastructure; `content_type` discriminator separates rows | — Pending |
| Supabase Storage (no S3) | All media in one managed service; no separate S3 billing or credentials | — Pending |
| ElevenLabs single voice | Consistent channel identity; voice chosen once, locked as Python constant | — Pending |
| Shotstack + Pexels | Royalty-free stock footage (Pexels free tier) + cloud rendering; cheaper than AI video for long-form | — Pending |
| Two Shotstack templates | One 16:9 long-form, one 9:16 short; generated from same audio in single pipeline run | — Pending |
| 30-day anti-repetition lookback for history | Topics repeat less frequently than cat scenes; 7-day cat lookback preserved unchanged | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd:transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd:complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-05-20 after v4.0 milestone start — Dual-Pipeline Content Machine*
