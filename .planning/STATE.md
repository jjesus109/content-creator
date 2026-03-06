---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: unknown
last_updated: "2026-03-02T21:45:31.599Z"
progress:
  total_phases: 8
  completed_phases: 8
  total_plans: 36
  completed_plans: 36
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-19)

**Core value:** A hyper-realistic AI avatar video lands in Telegram every day, ready to approve and publish — the creator's only job is to say yes or no.
**Current focus:** Phase 8 (Milestone Closure) — Plans 01, 02, 03 complete; all audit gaps closed

## Current Position

Phase: 8 of 8 (Milestone Closure) — All plans complete
Plan: 3 of 3 in current phase — 08-01, 08-02, 08-03 all complete
Status: 08-03 complete — Orphaned src/app/scheduler/jobs/circuit_breaker.py deleted; audit gap INT-01 closed; file was untracked (never committed), confirmed zero imports reference it; all 21 smoke tests pass
Last activity: 2026-03-04 - Completed quick task 001: improve script generation prompt: enforce 120 word limit and add emotional hook to first phrase

Progress: [████████████████████████] 100% (All 8 phases complete, Phase 8 all plans done)

## Performance Metrics

**Velocity:**
- Total plans completed: 8
- Average duration: 2.4 min
- Total execution time: 0.3 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01-foundation | 3/3 | 9 min | 3 min |
| 02-script-generation | 5/5 (complete) | 13 min | 2.6 min |
| 03-video-production | 6/6 (complete) | 12 min | 2 min |

**Recent Trend:**
- Last 5 plans: 03-02 (2 min), 03-03 (1 min), 03-04 (2 min), 03-05 (2 min), 03-06 (5 min)
- Trend: stable

*Updated after each plan completion*
| Phase 04-telegram-approval-loop P01 | 1 | 1 tasks | 1 files |
| Phase 04-telegram-approval-loop P02 | 3 | 2 tasks | 2 files |
| Phase 04-telegram-approval-loop P03 | 2 | 2 tasks | 2 files |
| Phase 04-telegram-approval-loop P04 | 2 | 2 tasks | 3 files |
| Phase 04-telegram-approval-loop P05 | 5 | 1 tasks | 3 files |
| Phase 05-multi-platform-publishing P01 | 2 | 2 tasks | 3 files |
| Phase 05-multi-platform-publishing P02 | 2 | 2 tasks | 2 files |
| Phase 05 P03 | 2 | 2 tasks | 4 files |
| Phase 05 P04 | 1 | 2 tasks | 2 files |
| Phase 05 P05 | 4 | 1 tasks | 1 files |
| Phase 06 P01 | 2 | 2 tasks | 2 files |
| Phase 06 P02 | 3 | 2 tasks | 2 files |
| Phase 06 P03 | 2 | 2 tasks | 3 files |
| Phase 06 P04 | 4 | 2 tasks | 2 files |
| Phase 06-analytics-and-storage P05 | 1 | 2 tasks | 3 files |
| Phase 07-hardening P01 | 6 | 1 tasks | 2 files |
| Phase 07-hardening P02 | 2 | 2 tasks | 6 files |
| Phase 08-milestone-closure P01 | 3 | 2 tasks | 2 files |
| Phase 08-milestone-closure P03 | 1 | 1 tasks | 0 files |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [Roadmap]: 7 phases derived from dependency chain — scripts before video, video before approval, approval before publish, publish before analytics, all before hardening
- [Roadmap]: Phase 7 (Hardening) covers all 26 v1 requirements end-to-end verification; it holds no new functional requirements itself
- [Research]: HeyGen v2 API endpoint structure must be verified against live docs before starting Phase 3
- [Research]: Direct platform APIs chosen for Phase 5 — TikTok Content Publishing API, Meta Graph API (Instagram/Facebook), YouTube Data API v3; Ayrshare aggregator replaced
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
- [Phase 03-03]: Music written to temp file (not second pipe) because ffmpeg subprocess cannot read two stdin streams simultaneously
- [Phase 03-03]: music_volume default 0.25 (25%) — center of 20-30% research range; audible but subservient to voice
- [Phase 03-03]: frag_keyframe+empty_moov required for all piped MP4 output — fragmented header written progressively, no backward seek needed
- [Phase 03-03]: pick_music_track() raises ValueError on empty URL pool — fail-fast preferable to silent failure
- [Phase 03-02]: File path convention videos/YYYY-MM-DD.mp4 is locked — changing requires migrating existing URLs
- [Phase 03-video-production]: HMAC-SHA256 validated via compare_digest (timing-safe) in heygen webhook endpoint
- [Phase 03-video-production]: Predictable job ID 'video_poller_{video_id}' allows webhook to cancel poller by ID without shared state
- [Phase 03-video-production]: Lazy import of _process_completed_render inside handler body avoids circular import at module load time
- [Phase 03-05]: double-processing guard in_() filter covers pending_render, pending_render_retry, AND rendering — one conditional UPDATE atomically claims processing; zero rows updated means skip
- [Phase 03-05]: stable Supabase Storage URL written to video_url only — HeyGen signed URL is ephemeral and never persisted
- [Phase 03-05]: scheduler closure via lambda in registry.py — APScheduler threads have no FastAPI Request context, cannot use request.app.state
- [Phase 03-05]: HeyGen submission fail-soft in daily_pipeline_job — script saved without video fields, creator alerted, pipeline does not abort
- [Phase 03-video-production]: ffmpeg local unavailability is expected on macOS dev machine — Check 6 (Dockerfile) confirms ffmpeg in final Docker stage for Railway runtime
- [Phase 04-01]: cause_code CHECK constraint added on column (not just rejection_requires_cause) to restrict values to 4 defined codes even for direct DB inserts
- [Phase 04-01]: post_copy stored on content_history (not approval_events) — belongs to content record, Phase 5 reads it at publish time
- [Phase 04-01]: No mood_profile_id FK added to content_history — simpler query-by-week_start approach preferred; Phase 5 can add FK if needed
- [Phase 04-02]: PostCopyService uses synchronous Anthropic client only — APScheduler ThreadPoolExecutor has no event loop; AsyncAnthropic would raise RuntimeError
- [Phase 04-02]: extract_thumbnail() is module-level function (not class method) — thread-pool-only constraint visible at call site; docstring warns against async handler use
- [Phase 04-02]: ApprovalService.get_today_rejection_count() reads from DB on every call — no module-level counter — restart-safe after pod restart or re-deployment
- [Phase 04-02]: clear_constraints_for_approved_run() queries ALL today's rejections (not just approved content_history_id) — daily rejections share cause categories across session
- [Phase 04-03]: Original approval message preserved unchanged — no edit_message_reply_markup calls; only new messages via effective_chat.send_message()
- [Phase 04-03]: handle_cause imports trigger_immediate_rerun lazily — function defined in plan 04-04; lazy import avoids NameError at module load time
- [Phase 04-03]: Daily limit message uses get_settings().pipeline_hour dynamically — not hardcoded
- [Phase 04-03]: Cause keyboard each button on its own row (not side-by-side) for single-tap mobile UX
- [Phase 04-04]: send_approval_message_sync mirrors send_alert_sync pattern exactly — run_coroutine_threadsafe when event loop running, run_until_complete otherwise, asyncio.run() as RuntimeError fallback
- [Phase 04-04]: content_history_id retrieved via separate SELECT after READY DB update in _process_completed_render — same supabase client, heygen_job_id as key
- [Phase 04-04]: trigger_immediate_rerun uses DateTrigger 30s from now with replace_existing=True — prevents duplicate re-runs if rejection fires twice
- [Phase 04-04]: mood_profiles query uses order(created_at desc).limit(1) — no FK needed, latest row always wins; truncated to 40 chars for caption space
- [Phase 04-04]: Caption truncated to 1024 chars total — Telegram photo caption limit
- [Phase 04-05]: pytest added to dependency-groups.dev (PEP 735) — test runner is dev-only; no prod impact
- [Phase 04-05]: smoke tests use inspect/import only — no live DB or API calls; fast, side-effect-free
- [Phase 04-05]: tests/ directory created at project root — mirrors standard Python project layout
- [Phase 05-multi-platform-publishing]: publish_events is append-only — verification job inserts new verified/verify_failed rows; no UPDATE pattern; full audit trail preserved
- [Phase 05-multi-platform-publishing]: Platform API credentials have no defaults — Pydantic raises ValidationError at startup if TIKTOK_CLIENT_KEY, META_ACCESS_TOKEN, YOUTUBE_CLIENT_SECRET env vars are not set
- [Phase 05-multi-platform-publishing]: tenacity added to [project].dependencies (production) — used by PublishJob retry logic at runtime
- [Phase 05-multi-platform-publishing]: generate_platform_variants uses max_tokens=1500 — 4 variants need more output space than single generate() at 300 tokens
- [Phase 05-multi-platform-publishing]: JSON extraction uses re.search DOTALL pattern for Anthropic structured responses — handles markdown code fence wrapping
- [Phase 05-multi-platform-publishing]: has_all_variants guard avoids redundant Anthropic call if post_copy_tiktok/instagram/facebook/youtube already populated in content_history
- [Phase 05-multi-platform-publishing]: Caption 1024-char truncation applies to full combined caption including all 4 platform variant sections stacked
- [Phase 05-03]: tenacity @retry on _post() (internal method) with module-level _is_retryable predicate — retries 5xx+network, fails fast on 4xx
- [Phase 05-03]: publish_to_platform_job does not re-raise exceptions — APScheduler already logs; creator notified via Telegram fallback
- [Phase 05-03]: verify_publish_job is silent on success — only surfaces failures to creator; no retry on verify failure
- [Phase 05-03]: send_publish_confirmation sends new Telegram message (not edit) — preserves approval message immutability (CONTEXT.md locked)
- [Phase 05-04]: handle_approve fetches video_url from content_history via supabase inside handler body — same DB client pattern as other handlers
- [Phase 05-04]: scheduler accessed via _fastapi_app.state.scheduler inside handler body — no new global variable, consistent with existing _fastapi_app pattern in telegram.py
- [Phase 05-04]: set_publish_scheduler aliased from set_scheduler import in registry.py — avoids name collision with video_poller set_scheduler
- [Phase 05]: 12 smoke tests use inspect.getsource() to verify logic contracts without executing code
- [Phase 05]: Checkpoint task (migration + Railway env) requires human action — not automatable
- [Phase 06-01]: retention_rate float column in platform_metrics used by weekly report to rank top performer — not just views/likes
- [Phase 06-01]: No r2_key column and no R2/Cloudflare credentials — warm tier is DB label only; files stay in Supabase Storage; cold deletion uses supabase.storage.from_().remove()
- [Phase 06-01]: storage_status CHECK includes 'exempt' for viral/eternal videos that must never be deleted
- [Phase 06-01]: No UNIQUE constraint on (content_history_id, platform) in platform_metrics — one row per harvest cycle; idempotency at job level via job ID deduplication
- [Phase 06-01]: tiktok_access_token and tiktok_refresh_token use empty-string defaults — Settings loads cleanly without TikTok env vars; harvester degrades gracefully with logged warning
- [Phase 06-02]: Module-level settings = get_settings() removed from metrics.py — ValidationError at import time when env vars absent; settings accessed via self._settings inside __init__ only
- [Phase 06-02]: check_and_alert_virality uses 48h time-window de-duplication (virality_alerted_at > NOW()-48h) NOT IS NULL — fires on every harvest cycle while video stays viral
- [Phase 06-02]: Instagram Insights uses 'views' metric not 'video_views' — video_views deprecated in Meta Graph API v21 (January 2025)
- [Phase 06-02]: format_virality_alert is minimal: platform, video date, view count only — no baseline_avg, no pct_above
- [Phase 06-03]: Warm tier = DB label only; file stays in same Supabase Storage bucket; no copy, no R2, no boto3
- [Phase 06-03]: Cold deletion = supabase.storage.from_(bucket).remove([path]); content_history row kept for analytics history
- [Phase 06-03]: is_viral/is_eternal safety guard in handle_storage_confirm prevents accidental deletion of exempt videos
- [Phase 06-03]: handle_storage_warn_ok: no DB update needed; lifecycle job handles idempotency via storage_status='warm' AND deletion_requested_at IS NULL query
- [Phase 06-03]: reset_expired_deletion_requests() fetches IDs first then loops — Supabase Python client has no bulk update with compound WHERE clause
- [Phase Phase 06-04]: harvest_metrics_job fetches topic_summary AND created_at in single DB call — plan only showed topic_summary but analytics.py requires video_date arg; derived from created_at[:10]
- [Phase Phase 06-04]: harvest_run_at = now + 48h in publish success block only — harvest not scheduled on publish failure
- [Phase 06-analytics-and-storage]: asyncio.run() used in storage_lifecycle_job to bridge async StorageLifecycleService methods — APScheduler ThreadPoolExecutor has no event loop (different from send_alert_sync which uses run_coroutine_threadsafe when FastAPI loop exists)
- [Phase 06-analytics-and-storage]: storage_lifecycle_job never deletes files directly — actual deletion only on stor_confirm: Telegram handler tap (Plan 06-03)
- [Phase 06-analytics-and-storage]: is_viral=False and is_eternal=False guards in all three transition queries — exempt videos never transitioned
- [Phase 07-01]: Patch HeyGenService at app.services.heygen.HeyGenService (source module) — lazy import inside daily_pipeline_job() body requires source-path patching per Python mock "patch where looked up" rule
- [Phase 07-01]: pytest.mark.e2e registered in pyproject.toml [tool.pytest.ini_options] — prevents PytestUnknownMarkWarning and enables --strict-markers compatibility
- [Phase 07-01]: clear_lru_cache autouse fixture calls get_settings.cache_clear() after each test — prevents stale cached Settings from leaking between E2E test runs (Pitfall 7)
- [Phase 07-01]: All four externals mocked in mock_all_externals fixture: HeyGenService, register_video_poller, send_alert_sync, send_approval_message_sync — incomplete mocking causes APScheduler RuntimeError (Pitfall 6)
- [Phase 07-hardening]: APPROVAL_TIMEOUT enum value added before DB migration — daily_pipeline_job can reference status before Plan 03 adds DB CHECK constraint
- [Phase 07-hardening]: schedule_approval_timeout uses lazy import inside send_approval_message_sync body to break circular import through telegram.py
- [Phase 07-hardening]: handle_approve wraps remove_job in broad except — APScheduler JobLookupError must not stop the approval flow
- [Phase 07-03]: daily_trip_count incremented in _trip() after weekly escalation logic — separate DB UPDATE keeps atomic escalation update distinct from daily state update
- [Phase 07-03]: Halt alert fires only at new_daily_trip_count >= 3 AND already_halted is False — prevents duplicate halt alerts if circuit breaker fires more than 3 times in a day
- [Phase 07-03]: is_daily_halted() fails open (returns False) on DB exception — pipeline availability over halt enforcement when DB is unreachable
- [Phase 07-03]: No confirmation message sent to creator after /resume — CONTEXT.md locked decision
- [Phase 07-03]: midnight_reset includes daily_trip_count=0 + daily_halted_at=NULL — new calendar day always starts clean regardless of prior day halt state
- [Phase 07-hardening]: _expire_stale_approvals iterates ready IDs individually rather than JOIN — Supabase Python client has no JOIN query support
- [Phase 08-02]: mock_render_completion_externals patches AudioProcessingService, VideoStorageService, send_approval_message_sync at source modules — all are lazy imports inside _process_completed_render() body; patch-where-looked-up rule applies
- [Phase 08-02]: Render completion test skipif uses SUPABASE_URL+SUPABASE_KEY (not ANTHROPIC_API_KEY) — render path needs DB access only, not AI generation
- [Phase 08-02]: finally block deletes content_history row by id — guaranteed cleanup regardless of assertion outcome or mid-test exception
- [Phase 08-milestone-closure]: 05-VERIFICATION.md synthesizes existing evidence only — cites UAT test numbers, SUMMARY commits, and audit-confirmed source file references
- [Phase 08-milestone-closure]: INT-02 closed by design decision — MANUAL_PLATFORMS={tiktok} is intentional v1 architecture; documented in REQUIREMENTS.md v2 section
- [Phase 08-03]: scheduler/jobs/circuit_breaker.py was untracked (never committed) — git rm inapplicable; plain rm used; empty commit documents audit gap INT-01 closure
- [Phase 08-03]: Zero imports reference app.scheduler.jobs.circuit_breaker — deletion carries zero risk; production app.services.circuit_breaker is the single authoritative service

### Pending Todos

None yet.

### Blockers/Concerns

- [Deployment]: .env file not yet populated with real credentials — service cannot start until Supabase/Telegram/Anthropic/OpenAI credentials added
- [Phase 3]: HeyGen API v2 endpoint structure, webhook retry policy, and Spanish TTS behavior are MEDIUM confidence — verify against live docs before writing integration code
- [Phase 5]: Direct platform API credentials (TikTok Content Publishing API, Meta Graph API, YouTube Data API v3) must be provisioned before re-implementing Phase 5
- [Phase 2]: pgvector 0.85 cosine similarity threshold is uncalibrated for Spanish philosophical content — seed DB with example scripts and run calibration before going live
- [Phase 2]: ANTHROPIC_API_KEY and OPENAI_API_KEY must be added to .env before service can start

### Quick Tasks Completed

| # | Description | Date | Commit | Directory |
|---|-------------|------|--------|-----------|
| 001 | Improve script generation prompt: enforce 120 word limit and add emotional hook to first phrase | 2026-03-04 | 0890139 | [001-improve-script-prompt-word-limit-hook](.planning/quick/001-improve-script-prompt-word-limit-hook/) |
| 002 | Create dry-run script generation CLI that calls real Anthropic API and stops before HeyGen/Telegram | 2026-03-04 | 4822e18 | [002-test-script-generation-dry-run](.planning/quick/002-test-script-generation-dry-run/) |
| 003 | Align HeyGenService.submit() to verified v2 payload; add heygen_gesture_prompt to Settings; create dry-run HeyGen submit CLI | 2026-03-05 | 739f48d | [003-heygen-api-payload-update](.planning/quick/003-heygen-api-payload-update/) |

## Session Continuity

Last session: 2026-03-05
Stopped at: Completed quick task 003 — HeyGen v2 payload aligned to verified structure; heygen_gesture_prompt added to Settings; scripts/dry_run_heygen_submit.py created
Resume file: None
