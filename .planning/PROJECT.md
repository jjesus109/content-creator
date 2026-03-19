# Autonomous Content Machine

## What This Is

An automated AI-powered content pipeline for a single creator. The system generates one cute Mexican cat short-form video per day — AI-generated video with dynamically matched music — delivers it to a Telegram bot for approval, then publishes to TikTok, IG Reels, FB Reels, and YT Shorts automatically. Content is driven by a scene engine that varies location, activity, and mood daily, with seasonal themes tied to Mexican national days and cultural events.

## Core Value

A cute Mexican cat video lands in Telegram every day, ready to approve and publish — the creator's only job is to say yes or no.

## Current Milestone: v2.0 Mexican Cat Content Machine

**Goal:** Replace the avatar video pipeline with an AI-generated cat video engine — same publishing infrastructure, completely new content strategy.

**Target features:**
- AI-generated 20-30s cute cat video from daily scene prompt
- Hybrid scene engine: AI generates within curated categories (location, activity, mood)
- Seasonal calendar: Mexican national days + International Cat Day
- Dynamically matched background music per video mood
- Universal caption (single caption, all platforms)

## Requirements

### Validated

<!-- Shipped in v1.0 — confirmed working -->

- ✓ Daily automated pipeline job (APScheduler + FastAPI) — v1.0/Phase 1
- ✓ Anti-repetition vector search via pgvector (85% cosine similarity threshold) — v1.0/Phase 2
- ✓ Telegram bot delivery: video preview + caption + [Approve] / [Reject with Cause] buttons — v1.0/Phase 4
- ✓ Rejection feedback stored as negative context for next generation — v1.0/Phase 4
- ✓ Auto-publish to TikTok, IG Reels, FB Reels, YT Shorts via direct platform APIs — v1.0/Phase 5
- ✓ 48-hour performance metric harvest (views, shares, retention) — v1.0/Phase 6
- ✓ Sunday weekly report + virality alert (500% above average) — v1.0/Phase 6
- ✓ Tiered storage lifecycle: Hot (0-7d) → Warm (8-45d) → Cold/Delete (45d+, except viral) — v1.0/Phase 6
- ✓ Circuit breaker with daily halt + weekly escalation — v1.0/Phase 7
- ✓ Approval timeout handling — v1.0/Phase 7
- ✓ All API keys encrypted in environment variables; Telegram bot locked to single user ID — v1.0/Phase 1

### Active

<!-- v2.0 scope — building toward these -->

- [ ] Daily scene prompt generation: AI picks location + activity + mood within curated category library
- [ ] Seasonal calendar service: injects themed scene context for Mexican national days (Sep 16, Nov 1-2, Nov 20) and International Cat Day (Aug 8)
- [ ] Anti-repetition for scenes: vector search prevents >85% similar scene within recent history
- [ ] AI cat video generation (20-30s, 9:16 1080p) — tool TBD via research
- [ ] Fixed Mexican cat character identity maintained across all videos
- [ ] Background music dynamically selected to match video mood/action
- [ ] Universal single caption per video (replaces per-platform variants)
- [ ] Same Telegram approval flow: video + caption → approve/reject

### Out of Scope

- Multi-user support — single creator only, no accounts or tenancy
- Horizontal short-form formats — 9:16 only
- Analytics dashboards/UI — all interaction via Telegram only
- AI avatar / spoken content — cat videos are visual-only, no voice
- Per-platform post copy variants — universal caption only for v2.0
- Weekly mood profile Telegram flow — replaced by seasonal calendar
- 5 Pillars philosophical framework — not applicable to cat content

## Context

- **Content identity**: Fixed recurring Mexican cat character, shown in varied Mexican and everyday environments
- **Scene variety**: Location + activity + mood rotate daily via AI within curated categories; seasonal themes overlay when applicable
- **Content language**: Captions in Spanish (same audience), casual and cute tone
- **Generation cadence**: 1 video/day, fully automated — creator approves or rejects via Telegram
- **Target platforms**: TikTok, Instagram Reels, Facebook Reels, YouTube Shorts
- **v1.0 codebase**: Full pipeline implemented — phases 1-8 complete; v2.0 replaces content engine only

## Constraints

- **Tech — Language/Backend**: Python 3.11 + FastAPI
- **Tech — Scene AI**: GPT-4o generates scene prompts within curated categories
- **Tech — Video generation**: TBD via v2.0 research (Runway Gen-3, Kling, Pika — replacing HeyGen)
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
| Vector DB for anti-repetition | Semantic similarity (not keyword) prevents topic/scene recycling | ✓ Good — validated in v1.0 |
| Single user architecture | Simpler, faster to build; no auth/tenancy overhead | ✓ Good — validated in v1.0 |
| HeyGen replaced | Avatar + voice not needed for cat content; different AI video tool required | — Pending (v2.0 research) |
| Universal caption vs per-platform | Simpler pipeline; cat content performs without platform-specific copy | — Pending |
| Hybrid scene engine | AI creativity within curated guardrails ensures quality + variety | — Pending |

---
*Last updated: 2026-03-18 after v2.0 milestone started — Mexican Cat Content Machine*
