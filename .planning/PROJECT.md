# Autonomous Content Machine

## What This Is

An automated AI-powered content pipeline for a single personal development creator. The system generates one short-form video per day — script, avatar video, and copy — delivers it to a Telegram bot for approval, then publishes to TikTok, IG Reels, FB Reels, and YT Shorts automatically. The entire operation runs on a philosophical framework (5 Pillars) that governs tone, aesthetics, and content direction.

## Core Value

A hyper-realistic AI avatar video lands in Telegram every day, ready to approve and publish — the creator's only job is to say yes or no.

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] Daily automated script generation (OpenAI) aligned to 5 Pillars and weekly mood profile
- [ ] Anti-repetition vector search ensures no topic >85% similar to prior content
- [ ] Script structure: Aggressive Hook (0-3s) + Philosophical Development + Reflective CTA (max 140 words)
- [ ] AI avatar video generation via HeyGen (hyper-realistic, dark aesthetic, 9:16 1080p, bokeh backgrounds)
- [ ] Background variety enforcement — no repeated environment in consecutive videos
- [ ] Audio post-processing (dark ambient style)
- [ ] Telegram bot delivery: video preview + post copy + [Approve] / [Reject with Cause] buttons
- [ ] Weekly mood profile input via Telegram (bot prompts creator once/week)
- [ ] Rejection feedback stored as negative context for next generation iteration
- [ ] Auto-publish to TikTok, IG Reels, FB Reels, YT Shorts via direct platform APIs (TikTok Content Publishing API, Meta Graph API, YouTube Data API v3)
- [ ] Optimal scheduling based on peak hours detected via platform API
- [ ] 48-hour performance metric harvest (views, shares, retention)
- [ ] Sunday weekly report + virality alert (500% above average triggers format clone)
- [ ] Tiered storage lifecycle: Hot (0-7d) → Warm (8-45d) → Cold/Delete (45d+, except viral)
- [ ] All API keys encrypted in environment variables; Telegram bot locked to single user ID

### Out of Scope

- Multi-user support — single creator only, no accounts or tenancy
- Manual content creation workflows — this system is fully automated
- Horizontal short-form formats — 9:16 only
- Long-form video content — 40-second shorts exclusively
- Analytics dashboards/UI — all interaction via Telegram only

## Context

- **Content language**: Neutral Spanish, masculine tone, short sentences optimized for AI voice rhythm
- **Philosophical framework**: 5 Pillars govern all content — Radical Responsibility (Amor Fati), Value in Solitude, Action over Words (Praxis), Temperance and Silence (Gravitas), Constant Evolution (Memento Mori)
- **Generation cadence**: 1 video/day, fully automated — creator approves or rejects via Telegram
- **Existing codebase**: Directory has existing code; architecture not yet mapped
- **Target platforms**: TikTok, Instagram Reels, Facebook Reels, YouTube Shorts

## Constraints

- **Tech — Language/Backend**: Python 3.11 + FastAPI
- **Tech — Script AI**: GPT-4o (primary) / Claude 3.5 (fallback)
- **Tech — Video generation**: HeyGen API (avatar rendering, lip-sync)
- **Tech — Voice**: ElevenLabs (TTS/voice cloning — verify if HeyGen native voice covers this)
- **Tech — Publishing**: Direct platform APIs: TikTok Content Publishing API, Meta Graph API (Instagram + Facebook Pages), YouTube Data API v3
- **Tech — Database**: Supabase (Postgres + pgvector for anti-repetition)
- **Tech — Storage**: Supabase Storage or S3 for video lifecycle management
- **Tech — Scheduler**: APScheduler 3.10.x with Postgres job store (survives deploys)
- **Tech — Telegram**: python-telegram-bot v21.x (async)
- **Tech — HTTP client**: httpx (async — never requests in async context)
- **Tech — Infrastructure**: Railway.app or Render (persistent worker, not serverless)
- **Tech — Interface**: Telegram bot only — no web UI, no mobile app
- **Performance**: Lip-sync must be 100% accurate; script auto-summarized if over 140 words
- **Privacy**: Bot restricted to creator's Telegram user ID; all secrets in encrypted env vars

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Telegram as sole UI | Zero-friction approval loop; no app to open | — Pending |
| HeyGen for avatar video | Hyper-realistic output, lip-sync quality | — Pending |
| Direct APIs vs Ayrshare aggregator | Direct API control: no third-party rate limits, no aggregator cost, full platform compliance | Direct posting chosen — TikTok Content Publishing API, Meta Graph API (Instagram/Facebook), YouTube Data API v3 |
| Vector DB for anti-repetition | Semantic similarity (not keyword) prevents topic recycling | — Pending |
| Single user architecture | Simpler, faster to build; no auth/tenancy overhead | — Pending |

---
*Last updated: 2026-02-19 after tech stack confirmed and research complete*
