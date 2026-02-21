# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-19)

**Core value:** A hyper-realistic AI avatar video lands in Telegram every day, ready to approve and publish — the creator's only job is to say yes or no.
**Current focus:** Phase 3 (Video Production) — Plan 2 of 6 complete

## Current Position

Phase: 3 of 7 (Video Production)
Plan: 2 of 6 in current phase — DONE
Status: 03-02 complete — HeyGenService (submit + background selector) and VideoStorageService (Supabase Storage upload with stable public URL) committed
Last activity: 2026-02-21 — 03-02 executed: heygen.py, video_storage.py

Progress: [██████░░░░] 38%

## Performance Metrics

**Velocity:**
- Total plans completed: 7
- Average duration: 2.6 min
- Total execution time: 0.3 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01-foundation | 3/3 | 9 min | 3 min |
| 02-script-generation | 5/5 (complete) | 13 min | 2.6 min |
| 03-video-production | 2/6 | 4 min | 2 min |

**Recent Trend:**
- Last 5 plans: 02-03 (4 min), 02-04 (1 min), 02-05 (3 min), 03-01 (2 min), 03-02 (2 min)
- Trend: stable

*Updated after each plan completion*

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [Roadmap]: 7 phases derived from dependency chain — scripts before video, video before approval, approval before publish, publish before analytics, all before hardening
- [Roadmap]: Phase 7 (Hardening) covers all 26 v1 requirements end-to-end verification; it holds no new functional requirements itself
- [Research]: HeyGen v2 API endpoint structure must be verified against live docs before starting Phase 3
- [Research]: Ayrshare TikTok support and plan tier limits must be confirmed before starting Phase 5
- [Research]: pgvector 0.85 threshold needs calibration with 20-30 seed Spanish scripts before Phase 2 goes live
- [Phase 01-foundation]: Use dependency-groups.dev (PEP 735) instead of deprecated tool.uv.dev-dependencies in pyproject.toml
- [Phase 01-foundation]: CircuitBreakerState includes last_trip_at column for rolling 7-day escalation window
- [Phase 01-foundation]: settings.database_url requires postgresql+psycopg2:// sync driver on port 5432 for APScheduler SQLAlchemyJobStore
- [Phase 01-foundation]: --workers 1 enforced in Dockerfile CMD and railway.toml startCommand — APScheduler must not be forked
- [Phase 01-02]: Circular import between circuit_breaker.py and telegram.py resolved by local import inside _send_escalation_alert method body
- [Phase 01-02]: send_alert_sync uses run_coroutine_threadsafe when event loop is running — required for APScheduler thread pool compatibility
- [Phase 01-02]: Telegram bot initialized with updater(None) — Phase 1 outbound-only; polling deferred to Phase 4
- [Phase 01-02]: Rolling 7-day escalation window uses last_trip_at timestamp comparison, not week_start counter
- [Phase 01-03]: BackgroundScheduler chosen over AsyncIOScheduler — runs in thread pool, no event loop contention with FastAPI
- [Phase 01-03]: Scheduler stored on app.state.scheduler — health endpoint inspects it via request.app.state without global variable
- [Phase 01-03]: Health endpoint returns 503 (not 500) on dependency failure — Railway ON_FAILURE policy requires non-200 to trigger restart
- [Phase 01-03]: register_jobs() centralizes all add_job() calls — single file for all scheduled job changes, replace_existing=True on every job
- [Phase 02-01]: PTB Application replaces updater(None) singleton — polling required for Phase 2 mood flow callback queries
- [Phase 02-01]: set_fastapi_app() pattern avoids circular imports between services/telegram.py and telegram/app.py
- [Phase 02-01]: check_script_similarity uses 1-(embedding<=>query) to convert pgvector cosine DISTANCE to similarity — correct inversion, common pgvector bug avoided
- [Phase 02-01]: rejection_constraints table created now (Phase 2 reads, Phase 4 writes) so queries return empty safely
- [Phase 02-02]: EmbeddingService returns (embedding, cost_usd) tuple so every caller can always report to CircuitBreakerService without recalculating
- [Phase 02-02]: SimilarityService fails open (returns False) on DB RPC errors — content repetition preferable to pipeline outage
- [Phase 02-02]: SimilarityService accepts optional supabase Client in __init__ for testability without live DB
- [Phase 02-03]: CallbackQueryHandler with prefix matching used instead of ConversationHandler — bot-initiated flows cannot use ConversationHandler entry_points
- [Phase 02-03]: await query.answer() called in all 3 handler steps — required to prevent Telegram loading spinner freezing on creator device
- [Phase 02-03]: DURATION_WORD_COUNTS (short=70, medium=140, long=200) baked into MoodService — pipeline reads target_words directly without mapping
- [Phase 02-04]: generate_topic_summary() pre-generates 15-word phrase BEFORE full script — cheaper similarity pre-check avoids paying for full Claude generation on topics that will be rejected
- [Phase 02-04]: attempt=1 gives "same root/different angle" instruction; attempt>=2 gives "completely different topic" — distinct retry strategies for different similarity failure modes
- [Phase 02-04]: summarize_if_needed() explicitly names 3 pillars to preserve (Philosophical Root, Emotional Anchor, Reflective CTA); Insight Flip section absorbs compression
- [Phase 02-04]: Synchronous Anthropic client only — AsyncAnthropic incompatible with APScheduler ThreadPoolExecutor (no event loop)
- [Phase 02-05]: MAX_RETRIES=2 (3 total attempts) — balances cost (~3 embed + ~3 topic gen calls max) vs freshness
- [Phase 02-05]: Circuit breaker checked after topic_cost and embed_cost separately — mid-run trip halts pipeline with distinct alert per stage
- [Phase 02-05]: summarize_if_needed CB call is non-fatal — script already generated; halting for word-count cost is disproportionate
- [Phase 02-05]: DB write failure is fail-soft — send Telegram alert, do not re-raise; script was generated
- [Phase 03-01]: pending_render_retry is the video_status sentinel for retry-once logic — avoids adding a retry_count column
- [Phase 03-01]: All 7 HeyGen fields required with no defaults — Pydantic raises at startup if any are missing
- [Phase 03-01]: ffmpeg installed in final Docker stage only (not builder) — it is a runtime, not build, dependency
- [Phase 03-01]: background_url stored in content_history to enable consecutive-background-repeat prevention
- [Phase 03-02]: Synchronous requests used for HeyGen HTTP call — httpx async incompatible with APScheduler ThreadPoolExecutor (no event loop)
- [Phase 03-02]: pick_background_url falls back to full pool if filtered pool is empty — defensive against single-URL edge case
- [Phase 03-02]: VideoStorageService accepts optional supabase client in __init__ for testability without live DB
- [Phase 03-02]: upsert='true' as string in file_options — Supabase Python client expects string, not bool
- [Phase 03-02]: cache-control=31536000 (1 year) on uploaded videos — content is permanent once approved
- [Phase 03-02]: File path convention videos/YYYY-MM-DD.mp4 is locked — changing requires migrating existing URLs

### Pending Todos

None yet.

### Blockers/Concerns

- [Deployment]: .env file not yet populated with real credentials — service cannot start until Supabase/Telegram/Anthropic/OpenAI credentials added
- [Phase 3]: HeyGen API v2 endpoint structure, webhook retry policy, and Spanish TTS behavior are MEDIUM confidence — verify against live docs before writing integration code
- [Phase 5]: Ayrshare TikTok content policy and plan tier limits are MEDIUM confidence — confirm before Phase 5 implementation
- [Phase 2]: pgvector 0.85 cosine similarity threshold is uncalibrated for Spanish philosophical content — seed DB with example scripts and run calibration before going live
- [Phase 2]: ANTHROPIC_API_KEY and OPENAI_API_KEY must be added to .env before service can start

## Session Continuity

Last session: 2026-02-21
Stopped at: Completed 03-02-PLAN.md — HeyGenService and VideoStorageService implemented
Resume file: None
