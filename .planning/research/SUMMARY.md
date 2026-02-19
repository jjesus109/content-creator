# Project Research Summary

**Project:** AI-Automated Short-Form Video Content Pipeline
**Domain:** Solo creator autonomous content pipeline — avatar video, multi-platform social publishing
**Researched:** 2026-02-19
**Confidence:** MEDIUM overall (Python ecosystem HIGH; external API behaviors MEDIUM; some API-specific details need live verification before implementation)

## Executive Summary

This project is a fully autonomous daily content pipeline for a solo personal development creator. It generates short-form avatar video (via HeyGen), delivers it to the creator for single-tap approval via Telegram, and publishes simultaneously to TikTok, Instagram Reels, Facebook Reels, and YouTube Shorts via Ayrshare. The system's differentiation lies in three compounding mechanisms: a 5-Pillar philosophical framework that ensures voice consistency across hundreds of videos, semantic anti-repetition using pgvector cosine similarity to prevent topic recycling, and a rejection feedback loop that makes the system progressively smarter over time. No existing tool combines all of these in a single pipeline.

The recommended approach is a layered async Python pipeline: APScheduler triggers a daily FastAPI BackgroundTask that sequences through ScriptEngine (OpenAI/Claude), AntiRepetitionGuard (pgvector), MediaAssetBuilder (HeyGen polling), and Telegram approval delivery. The Telegram callback then resumes the pipeline to publish via Ayrshare. All pipeline state is persisted in Supabase so the system survives server restarts and Telegram callbacks arriving in a fresh process. This is not a complex architecture — it is a straightforward step sequencer with async I/O at every external boundary.

The top three risks are: (1) HeyGen webhook unreliability requiring a polling fallback to prevent silent video loss, (2) cost runaway from looping rejection bugs or scheduler misfires requiring a hard daily generation cap, and (3) the HeyGen video URL expiry pattern — signed S3 URLs must be downloaded to self-hosted storage immediately upon render completion, before sending to Telegram or Ayrshare. These pitfalls are preventable with explicit patterns documented in the research.

---

## Key Findings

### Recommended Stack

The Python ecosystem is the clear choice for this pipeline. FastAPI provides the async web layer and webhook receiver. `python-telegram-bot` v21 (async-native) handles the Telegram approval interface. APScheduler runs the daily cron in-process, eliminating the infrastructure overhead of Celery + Redis for a single daily job. All external API calls use `httpx` (async), since the synchronous `requests` library blocks the event loop and is incompatible with this architecture.

Storage and data are handled entirely by Supabase (Postgres + pgvector) plus S3 for video files. The pgvector anti-repetition pattern is well-documented and handles years of daily content at negligible cost — no external vector database (Pinecone, Weaviate) is needed. HeyGen and Ayrshare have no official Python SDKs; both are integrated directly via `httpx`. The full dependency list is concrete and narrow.

**Core technologies:**
- **Python 3.11**: Runtime — stable, strong ML/AI ecosystem, significant perf gains over 3.10
- **FastAPI 0.111+**: HTTP layer + webhook receiver — async-native, minimal boilerplate
- **python-telegram-bot 21.x**: Telegram bot — de-facto standard, full async, InlineKeyboard support
- **APScheduler 3.10+**: Daily cron + 48h metrics jobs — in-process scheduler, avoids Celery overhead
- **httpx 0.27+**: Async HTTP client — all external API calls (HeyGen, Ayrshare, ElevenLabs)
- **openai 1.x + anthropic 0.25+**: Script generation — dual LLM support
- **supabase-py 2.x + pgvector**: Database + vector similarity — single service for CRUD and anti-repetition
- **boto3 1.34+**: S3 video storage — lifecycle tiering, stable URLs for publishing
- **tenacity 8.x**: Retry logic — exponential backoff for all external API calls
- **Railway.app**: Deployment — persistent service, native env vars, built-in logging

See `/Users/jesusalbino/Projects/content-creation/.planning/research/STACK.md` for full stack details, version compatibility matrix, and what NOT to use.

### Expected Features

The pipeline divides cleanly into v1 (launch-blocking) and v1.x (post-launch, first 2 weeks). Anything requiring baseline data (analytics, virality detection) cannot meaningfully function until real content has been published, which is the right deferral criterion.

**Must have (v1 — table stakes):**
- Script generation with 5-Pillar framework + weekly mood profile injection — without this, nothing else runs
- Anti-repetition via pgvector cosine similarity (>85% threshold) — content degrades within weeks without it
- HeyGen avatar video generation (9:16, 1080p, dark aesthetic, background variety enforcement)
- Word count enforcement at 140 words — HeyGen lip-sync degrades above this; must run before API call
- Telegram bot delivery with Approve/Reject inline keyboard — sole creator interaction point
- Rejection cause capture + negative context storage and injection — closes the feedback loop at v1
- Multi-platform publish via Ayrshare (TikTok, IG Reels, FB Reels, YT Shorts) — without publishing, it is a toy
- Secrets management via env vars + single-user Telegram lock — non-negotiable security baseline

**Should have (v1.x — add after first week of live content):**
- 48-hour performance metric harvest via Ayrshare analytics
- Sunday weekly Telegram report
- Virality alert at 500% above rolling average (requires ~2 weeks of baseline data)
- Tiered storage lifecycle (Hot 0-7d, Warm 8-45d, Cold/delete 45d+, viral = permanent exempt)
- Dark ambient audio post-processing (only if creator requests after seeing v1 videos)
- Optimal publish scheduling based on platform peak hours

**Defer (v2+):**
- Format clone on virality — requires video analysis; manual analysis is more accurate for first viral events
- Mood profile question refinement — calibrate after 8 weeks of creator feedback
- Background catalog expansion — start with 5-10 approved backgrounds; expand as aesthetic evolves
- Multi-user/multi-creator support — architectural rework; defer until product-market fit is proven

**Anti-features to avoid:** web dashboard, multi-creator support, auto-approval without human review, horizontal video formats, per-platform caption variants, A/B testing per post.

See `/Users/jesusalbino/Projects/content-creation/.planning/research/FEATURES.md` for full feature dependency graph and prioritization matrix.

### Architecture Approach

The system is organized into six functional layers: Trigger (APScheduler), Orchestration (PipelineOrchestrator as a FastAPI BackgroundTask), Content Generation (ScriptEngine + AntiRepetitionGuard + MediaAssetBuilder), Approval (Telegram Bot), Publishing (Ayrshare), and Analytics (MetricsPoller + ViralityDetector + ReportBuilder). All layers share a single Persistence layer: Supabase Postgres for relational data and pgvector, plus S3 for video binaries.

The key architectural insight is the event boundary at the Telegram approval step. The orchestrator writes state to the database and suspends. The Telegram callback handler resumes the pipeline hours later by looking up the run by ID. This means all pipeline state must live in the database, never in memory. Any in-memory state assumption causes approval callbacks to silently fail after server restarts.

**Major components:**
1. **PipelineOrchestrator** — step sequencer; writes status to `pipeline_runs` table after each step; enables retry and resumability
2. **ScriptEngine** — OpenAI/Claude API calls with 5-Pillar prompt, mood profile injection, word count enforcement
3. **AntiRepetitionGuard** — embeds candidate script via OpenAI `text-embedding-3-small`; queries pgvector cosine similarity; rejects if > 0.85
4. **MediaAssetBuilder** — submits to HeyGen API; polls for completion with exponential backoff; downloads video to S3 immediately upon completion
5. **ApprovalBot** — sends video URL + post copy + InlineKeyboard to creator; handles `approve`/`reject` callbacks; resumes or terminates pipeline
6. **PublishService** — calls Ayrshare single-POST endpoint for all 4 platforms; stores platform post IDs for metrics collection
7. **MetricsPoller + ViralityDetector** — APScheduler date job fires +48h post-publish; compares to rolling 30-video average; sends alert if viral
8. **StorageLifecycleManager** — S3 lifecycle rules + viral flag exemption

See `/Users/jesusalbino/Projects/content-creation/.planning/research/ARCHITECTURE.md` for full component diagram, data flow maps, and all async vs sync considerations.

### Critical Pitfalls

Research identified 10 pitfalls; these 5 are the ones that cause the most damage if missed:

1. **HeyGen signed URLs expire (24-48h)** — Never store the HeyGen completion URL as the canonical reference. Download immediately to S3 upon render completion and use the S3 URL everywhere (Telegram delivery, Ayrshare publish). Failure causes silent publish failures hours or days later.

2. **HeyGen webhook is fire-and-forget, not guaranteed** — Implement polling fallback alongside any webhook registration. After triggering generation, store `video_id` with status `pending`. A background poller checks all `pending` videos every 90 seconds. If webhook fails (cold start, network drop), polling catches the completion.

3. **Cost runaway from scheduler bugs or rejection loops** — Implement a hard daily generation counter before any paid API call. Default max: 2 generations/day. On the third attempt, alert the creator via Telegram and halt. Also set budget alerts in HeyGen and OpenAI dashboards. Without this, a scheduler bug can generate $10-50 in API costs in a single day.

4. **In-memory pipeline state breaks approval callbacks** — All state transitions must be written to `pipeline_runs` table. Telegram approval callbacks arrive minutes to hours later, potentially in a fresh server process. Any pipeline state held in memory is lost on restart. This is non-negotiable.

5. **Telegram bot 50MB file upload limit** — A 1080p 40-second avatar video is typically 80-200MB. Sending via `bot.send_video(video=file_bytes)` will fail. Always send as a public URL (Supabase Storage or pre-signed S3 URL). Telegram fetches from the URL without the size restriction.

Secondary pitfalls (material but recoverable): pgvector threshold miscalibration (start at 0.80, tune after 30 days), Telegram webhook/polling race condition when running dev and prod simultaneously (always use separate bot tokens), rejection context pollution after 30+ days (cap injected context at top 5-10 recent entries), and Ayrshare async publish status (HTTP 200 from Ayrshare != published on platform — verify status 15-30 min later).

See `/Users/jesusalbino/Projects/content-creation/.planning/research/PITFALLS.md` for full detail, prevention code patterns, and recovery strategies for all 10 pitfalls.

---

## Implications for Roadmap

Based on the combined research, the build order is fully determined by hard dependencies: you cannot test HeyGen without scripts; you cannot test approval without videos; you cannot test publishing without an approval flow; analytics requires published content to measure. The architecture research makes this dependency chain explicit. Suggested phase structure follows these constraints.

### Phase 1: Foundation
**Rationale:** Everything else fails without this. Database schema, environment config, and deployment setup must exist before any code touches an external API. This phase also addresses Pitfall 3 (Railway sleeping) by deploying the FastAPI service with APScheduler from day one.
**Delivers:** Running service on Railway with health endpoint, Supabase schema (pipeline_runs, scripts, content_history, video_metrics, mood_profiles tables), pgvector extension enabled and indexed, S3 bucket configured, all secrets in env vars, single-user Telegram lock in place.
**Addresses:** secrets management, single-user lock (table stakes from FEATURES.md)
**Avoids:** Pitfall 3 (infrastructure sleep), Pitfall 5 (no schema = no cost circuit breaker), security pitfalls

### Phase 2: Script Generation + Anti-Repetition
**Rationale:** Script generation is the first step of the pipeline and has no upstream dependencies. Anti-repetition must be built alongside it, not after — embedding every approved script is a habit established here. The 5-Pillar prompt kernel and word count enforcement are both implemented in this phase.
**Delivers:** ScriptEngine generating 140-word Spanish scripts with 5-Pillar constraints; AntiRepetitionGuard with pgvector cosine similarity; rejection negative context storage and injection; weekly mood profile Telegram prompt.
**Uses:** openai 1.x, anthropic 0.25+, supabase-py with pgvector, python-telegram-bot 21.x (mood prompt only)
**Implements:** ScriptEngine, AntiRepetitionGuard components
**Avoids:** Pitfall 6 (threshold miscalibration — seed DB with sample scripts before launch), Pitfall 10 (rejection context pollution — implement rolling window cap from day one)
**Research flag:** Needs validation of Spanish character encoding through OpenAI embeddings and HeyGen TTS before going live.

### Phase 3: Video Production (HeyGen Integration)
**Rationale:** Depends on Phase 2 producing scripts. HeyGen integration is the highest-complexity single step in the pipeline — async job submission, polling, download-to-S3 pattern, and format validation all live here. The polling fallback (Pitfall 1) and immediate S3 re-hosting (Pitfall 4) must be implemented in this phase, not retrofitted later.
**Delivers:** MediaAssetBuilder submitting scripts to HeyGen, polling for completion with exponential backoff, downloading video to S3 immediately upon completion, ffprobe format validation, background variety enforcement.
**Uses:** httpx 0.27+, tenacity 8.x, boto3 1.34+, ffmpeg-python (if HeyGen audio injection insufficient)
**Implements:** MediaAssetBuilder, StorageLifecycleManager (upload side), webhook receiver FastAPI endpoint
**Avoids:** Pitfall 1 (webhook-only), Pitfall 4 (expired HeyGen URL in Ayrshare), Pitfall 2 (script encoding failures)
**Research flag:** Verify HeyGen v2 API endpoint structure, webhook availability, concurrent render limits, and Spanish character TTS behavior against live docs before starting this phase.

### Phase 4: Telegram Approval Loop
**Rationale:** Depends on Phase 3 delivering a video to Telegram. This phase wires the approval callback back to the PipelineOrchestrator state machine. The event boundary (state written to DB, callback resumes by ID lookup) is the architectural centerpiece and must be validated here.
**Delivers:** Complete approve/reject flow — Telegram inline keyboard, approve triggers publish (Phase 5 hook), reject captures cause, stores negative context, provides creator UX (progress indicator, script preview in approval message).
**Uses:** python-telegram-bot 21.x, supabase-py (state persistence)
**Implements:** ApprovalBot, approve_callback, reject_callback, mood_handler
**Avoids:** Pitfall 7 (dev/prod webhook conflict — separate bot tokens required), Pitfall 8 (file size — send as URL), Telegram UX pitfalls (progress message, script excerpt in approval message)

### Phase 5: Multi-Platform Publishing
**Rationale:** Depends on Phase 4 — the Approve callback triggers publish. This phase implements the PublishService and the post-publish verification step (Pitfall 9). Cost circuit breaker from Pitfall 5 must be in place before this phase goes live.
**Delivers:** Ayrshare single-POST publishing to all 4 platforms, optimal scheduling via Ayrshare `scheduleDate`, post-status verification 15-30 min after submission, platform post ID storage for metrics.
**Uses:** httpx 0.27+ (Ayrshare REST), APScheduler (post-verification delay job)
**Implements:** PublishService, scheduler_hints (peak hour logic)
**Avoids:** Pitfall 9 (Ayrshare async publish status), Pitfall 4 (video must be at stable URL before this phase)

### Phase 6: Analytics + Intelligence
**Rationale:** Requires real published content to measure. Cannot be meaningfully implemented before Phase 5 is producing live videos. This phase adds the learning loop that makes the system compound in value over time — metrics harvest, virality detection, weekly reports, and storage lifecycle management.
**Delivers:** 48h metrics harvest job, virality alert at 500% above rolling average, Sunday weekly Telegram report, S3 lifecycle rules (Hot/Warm/Cold), viral flag exemption from deletion.
**Uses:** APScheduler (date jobs), Ayrshare analytics API (httpx), aioboto3 (S3 lifecycle)
**Implements:** MetricsPoller, ViralityDetector, ReportBuilder, StorageLifecycleManager (cleanup side)
**Avoids:** Pitfall 5 (48h job must check published status before harvesting, not assume publish succeeded)

### Phase 7: Hardening + Production Readiness
**Rationale:** Each prior phase introduces patterns that need systematic verification before the system runs autonomously for months. This phase closes the "Looks Done But Isn't" checklist from PITFALLS.md — timeout handling, 24h approval expiry, budget guardrails, health endpoint verification, Spanish character validation, and rejection context pruning.
**Delivers:** Full system integration tests, 24h unanswered approval timeout with auto-skip, daily generation circuit breaker (verified at 3 triggers), health endpoint checking DB + scheduler state, structlog JSON logging in Railway, all pitfall prevention code verified against test scenarios.
**Uses:** pytest 8.x, pytest-asyncio 0.23+, structlog

### Phase Ordering Rationale

- Foundation before all integration work because the DB schema, env config, and health endpoint affect every other phase.
- Script generation before video production because HeyGen API calls need ready scripts; testing is impossible without them.
- Video production before Telegram approval because you cannot deliver a video that does not exist.
- Approval before publishing because the Approve callback fires the publish — they are causally linked.
- Analytics strictly after publishing because the 500% virality threshold requires a rolling baseline (minimum ~14 days of data) and the metrics harvest requires platform post IDs returned at publish time.
- Hardening last because it validates the system as a whole; individual phase testing happens during each phase, but system-level edge cases (rejection loops, scheduler misfires, cold start behavior) require all layers to be in place.

### Research Flags

**Phases requiring deeper research or live API verification before implementation:**
- **Phase 3 (HeyGen integration):** HeyGen API v2 endpoint structure, webhook retry policy, concurrent render limits, and Spanish TTS character behavior must be verified against live HeyGen docs (https://docs.heygen.com/reference) before writing integration code. MEDIUM confidence in training data.
- **Phase 5 (Ayrshare publishing):** Current TikTok content policy constraints, Ayrshare plan tier limits for 4-platform posting, and exact `scheduleDate` format must be confirmed against live Ayrshare docs (https://docs.ayrshare.com). MEDIUM confidence.
- **Phase 2 (pgvector threshold):** The 0.85 cosine similarity threshold is untested against Spanish philosophical niche content. Seed DB with 20-30 example scripts and run calibration test before setting threshold in production.

**Phases with well-established patterns (no additional research needed):**
- **Phase 1 (Foundation):** FastAPI + Railway + Supabase setup is well-documented with HIGH confidence patterns. Pydantic-settings for env var management is stable.
- **Phase 4 (Telegram approval):** python-telegram-bot v21 InlineKeyboard + callback_query pattern is HIGH confidence and extensively documented.
- **Phase 7 (Hardening):** pytest + pytest-asyncio testing patterns are standard and HIGH confidence.

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH (Python ecosystem) / MEDIUM (external APIs) | Core Python libs (FastAPI, PTB, APScheduler, httpx, openai, pydantic) are HIGH confidence. HeyGen, Ayrshare, ElevenLabs integration details are MEDIUM — verify endpoint structure against live docs before implementation. |
| Features | HIGH | Feature requirements are grounded in PROJECT.md constraints plus well-understood social platform patterns. Dependency map is clear. |
| Architecture | MEDIUM | Overall pattern (async step sequencer + DB state machine + event-driven approval) is well-established and HIGH confidence. Specific component behaviors tied to HeyGen and Ayrshare API behavior are MEDIUM. |
| Pitfalls | HIGH (patterns) / MEDIUM (API-specific) | Structural pitfalls (in-memory state, signed URL expiry, polling vs webhook fallback) are HIGH confidence. API-specific behaviors (HeyGen rate limits, Ayrshare TikTok support) need live verification. |

**Overall confidence:** MEDIUM-HIGH — sufficient to start building. The architecture and stack decisions are solid. The unknowns are externally imposed (third-party API behaviors) and are explicitly flagged for verification before those specific phases begin.

### Gaps to Address

- **HeyGen v2 API structure:** Endpoint paths in training data may not match current v2 API. Verify before Phase 3. Check: video generation endpoint, status polling endpoint, webhook support and retry policy, concurrent render limits, Spanish TTS character handling.
- **Ayrshare TikTok support and plan limits:** Confirm current platform support, rate limits, and whether the base Social API plan supports all 4 target platforms at 1 post/day. Verify `scheduleDate` behavior.
- **pgvector threshold calibration:** The 0.85 threshold is a business assumption, not an empirically calibrated value for Spanish philosophical niche content. Plan a calibration exercise using 20-30 seed scripts before Phase 2 goes to production.
- **ElevenLabs necessity:** Research is ambiguous on whether HeyGen handles voice via its own cloning or requires external audio. Confirm during Phase 3: if HeyGen voice cloning is sufficient, ElevenLabs becomes an optional dependency.
- **APScheduler 4.x stability:** APScheduler 4.x (async-first rewrite) may have matured since August 2025. Verify whether 3.10.x or 4.x is the correct choice at implementation time.

---

## Sources

### Primary (HIGH confidence)
- PROJECT.md (project constraints and requirements, 2026-02-19) — feature scope, creator constraints
- Python standard library and official SDKs (FastAPI, openai 1.x, pydantic 2.x, python-telegram-bot 21.x) — stack decisions
- Supabase pgvector official documentation — cosine similarity pattern and HNSW index requirement
- python-telegram-bot v21 documentation — InlineKeyboard, callback_query, file size limits
- FastAPI BackgroundTasks documentation — async pattern for pipeline execution
- S3 presigned URL documentation — URL expiry behavior and lifecycle rules

### Secondary (MEDIUM confidence)
- HeyGen API training data (August 2025 cutoff) — endpoint structure, async rendering pattern; verify at https://docs.heygen.com/reference
- Ayrshare API training data (August 2025 cutoff) — single-POST multi-platform publishing; verify at https://docs.ayrshare.com
- ElevenLabs Python SDK (training data) — optional dependency; verify at https://github.com/elevenlabs/elevenlabs-python
- Railway.app behavior — persistent service, sleep behavior on free vs paid tiers; verify at time of infrastructure selection
- APScheduler 3.10.x with Postgres job store — verify at https://apscheduler.readthedocs.io

### Tertiary (LOW confidence — needs validation)
- TikTok current video upload requirements (codec, duration, file size) — TikTok API terms change frequently; verify at https://developers.tiktok.com at build time
- HeyGen concurrent render limits — not publicly documented; test empirically during Phase 3
- Competitor feature analysis (Opus Clip, Munch, n8n flows) — training data cutoff; current feature state may differ

---
*Research completed: 2026-02-19*
*Ready for roadmap: yes*
