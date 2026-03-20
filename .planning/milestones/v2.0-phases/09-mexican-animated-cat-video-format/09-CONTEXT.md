# Phase 9: Character Bible and Video Generation - Context

**Gathered:** 2026-03-19
**Status:** Ready for planning

<domain>
## Phase Boundary

Replace HeyGen with Kling AI 3.0 via fal.ai async SDK for video generation. Deliver four capabilities: (1) DB schema migration for v2.0 tables/columns, (2) Character Bible definition + Kling integration + video storage, (3) Kling-specific circuit breaker, (4) AI content label automation on all platforms before any content reaches the creator. Scene generation (GPT-4o scene prompts) and music are Phase 10.

</domain>

<decisions>
## Implementation Decisions

### Character Bible content
- **Cat appearance**: Orange tabby with white markings — bright, distinct, easy for Kling to maintain across generations
- **Mexican cultural identity**: Conveyed through environment (serape, pottery, plants, Mexican architecture) — the cat itself has no accessories or cultural markers on its body
- **Personality**: Curious and mischievous — always getting into things; this shapes scene prompt framing
- **Name**: A Mexican name (e.g., Mochi) — used internally in prompts to anchor character identity, not necessarily surfaced in captions
- **Bible format**: 40-50 words, embedded unchanged as the first part of every Kling generation prompt

### Kling/fal.ai integration architecture
- **Polling pattern**: Keep APScheduler polling — adapt `video_poller.py` for Kling/fal.ai status checks (60s interval, same architecture as HeyGen)
- **Service file**: Create `src/app/services/kling.py` — new service with `submit()` and `_process_completed_render()`. Keep `heygen.py` untouched for audit trail
- **Prompt construction**: Character Bible (40-50 words) + scene prompt concatenated into a single Kling text prompt. No separate system/user field split
- **Video spec**: 20-30s, 9:16 aspect ratio, 1080p — submitted via fal.ai async SDK
- **Timeout/retry**: Same as v1.0 HeyGen pattern — 20-min timeout, retry once (`pending_render_retry` sentinel), then alert creator and skip the day
- **daily_pipeline.py**: Updated to call `KlingService.submit()` instead of `HeyGenService.submit()`

### Kling circuit breaker
- **Separate CB**: New Kling-specific circuit breaker — does not share state with the existing HeyGen CB in `circuit_breaker.py`
- **Failure threshold**: >20% failures over a rolling 24-hour window (resets at midnight, consistent with daily pipeline cadence)
- **Backoff**: Exponential backoff on retry — 2s, 8s, 32s (matches REQUIREMENTS.md VID-03 spec)
- **Credit balance check**: fal.ai balance queried before each Kling call. If balance < $5: alert creator via Telegram but proceed. If balance critically low (< $5), pipeline is blocked for that day
- **CB open behavior**: Pipeline halts, Telegram alert sent to creator
- **Recovery**: `/resume` Telegram command re-opens CB and retries immediately — same UX as v1.0 hardening phase

### AI content labels
- **Timing**: Labels applied during the publish API call (in `platform_publish.py`), not before Telegram approval
- **TikTok**: Caption prefix `🤖 Creado con IA` prepended to the universal caption. Skip the TikTok `ai_generated` API flag
- **YouTube**: `🤖 Creado con IA` prepended to video description
- **Instagram**: `🤖 Creado con IA` prepended to caption
- **Failure fallback**: If the platform API label application fails, fall back to caption prefix — publish proceeds with the text prefix as the label. No silent failures
- **Label string**: Uniform across all platforms: `🤖 Creado con IA`

### Claude's Discretion
- Exact 40-50 word Character Bible text (Claude drafts, then embeds as a constant in kling.py)
- Specific Mexican cat name to use (Mochi recommended)
- fal.ai SDK method signatures for submit + status polling
- DB column names for v2.0 schema migration (pipeline_runs v2 columns, character_bible setting storage)
- Internal structure of the Kling CB class

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements and state
- `.planning/REQUIREMENTS.md` — VID-01 through VID-04 acceptance criteria and constraints
- `.planning/STATE.md` — Accumulated v2.0 decisions, including Kling selection rationale and known blockers

### Existing codebase (MUST READ before modifying)
- `src/app/services/heygen.py` — Pattern to replicate in kling.py (submit, process_completed_render, _handle_render_failure)
- `src/app/services/circuit_breaker.py` — Existing CB implementation to use as reference for Kling CB
- `src/app/scheduler/jobs/video_poller.py` — Polling job to adapt for fal.ai status checks (register_video_poller, _retry_or_fail, _cancel_self)
- `src/app/scheduler/jobs/daily_pipeline.py` — Entry point to update: swap HeyGen call for Kling call
- `src/app/services/video_storage.py` — Unchanged: VideoStorageService.upload() receives final MP4 bytes and returns Supabase public URL
- `src/app/scheduler/jobs/platform_publish.py` — Where AI label logic must be added (per-platform publish calls)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `VideoStorageService` (`src/app/services/video_storage.py`): Uploads MP4 bytes to Supabase Storage, returns public URL. Unchanged — kling.py calls this after download
- `CircuitBreakerService` (`src/app/services/circuit_breaker.py`): Reference implementation for the new Kling CB
- `video_poller_job` + `register_video_poller` (`src/app/scheduler/jobs/video_poller.py`): Adapt these for fal.ai — replace HeyGen status URL with fal.ai job status check
- `send_alert_sync` (`src/app/services/telegram.py`): Used for CB alert and low-balance Telegram notification

### Established Patterns
- APScheduler polling: 60s interval, predictable job ID (`video_poller_{job_id}`), picklable args only (no closures)
- `pending_render` / `pending_render_retry` / `failed` VideoStatus sentinel pattern for timeout tracking
- `get_settings()` + env var injection: new vars needed — `FAL_API_KEY`, `KLING_MODEL_VERSION`
- Synchronous services in APScheduler ThreadPoolExecutor context (use `requests` or fal sync SDK, not async)
- `send_alert_sync` for all Telegram notifications from scheduler jobs

### Integration Points
- `daily_pipeline.py` → `KlingService.submit()` replaces `HeyGenService.submit()` — same call site, different service
- `video_poller.py` → fal.ai status check replaces HeyGen `video_status.get` HTTP call
- `platform_publish.py` → AI label added per-platform before the actual publish API call
- `migrations/` → New migration file for v2.0 schema (pipeline_runs columns, music_pool table, character_bible setting)

</code_context>

<specifics>
## Specific Ideas

- The Character Bible should be a Python constant (e.g., `CHARACTER_BIBLE = "..."`) in `kling.py` or a dedicated `character_bible.py` — not in a config or DB — so it's always in sync with code deploys
- STATE.md blocker: Kling exact rate limits unknown — Phase 9 plan should include a 1-week API test step to observe real failure patterns before the 20% CB threshold is finalized in production
- New env vars confirmed needed before Phase 9 executes: `FAL_API_KEY`, `KLING_MODEL_VERSION`
- The fal.ai SDK uses async patterns — since APScheduler runs in ThreadPoolExecutor, use `fal_client.submit()` (sync) or run async in a dedicated thread with `asyncio.run()`

</specifics>

<deferred>
## Deferred Ideas

- Reference image upload to Kling for enhanced character consistency (upgrade path if visual consistency < 90% after empirical testing) — Phase 9 ships text-only prompts first
- TikTok native `ai_generated` API flag — skipped per user decision; caption prefix used instead. Can be added later if TikTok changes compliance requirements

</deferred>

---

*Phase: 09-mexican-animated-cat-video-format*
*Context gathered: 2026-03-19*
