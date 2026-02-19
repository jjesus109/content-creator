# Architecture Research

**Domain:** AI Automated Short-Form Video Content Pipeline
**Researched:** 2026-02-19
**Confidence:** MEDIUM (external API behaviors from training data; web fetch unavailable for live doc verification)

---

## Standard Architecture

### System Overview

```
┌──────────────────────────────────────────────────────────────────────┐
│                         TRIGGER LAYER                                │
│  ┌─────────────────────────────────────────────────────────────┐     │
│  │  APScheduler / Cron Job  (daily 06:00 local time)           │     │
│  └───────────────────────────────┬─────────────────────────────┘     │
└──────────────────────────────────│───────────────────────────────────┘
                                   │ kick off pipeline
                                   ▼
┌──────────────────────────────────────────────────────────────────────┐
│                      ORCHESTRATION LAYER                             │
│  ┌────────────────────────────────────────────────────────────┐      │
│  │             PipelineOrchestrator (FastAPI Background Task) │      │
│  │  Coordinates all steps, manages state in Supabase          │      │
│  └──────┬──────────┬──────────────┬──────────────┬────────────┘      │
└─────────│──────────│──────────────│──────────────│────────────────── ┘
          │          │              │              │
          ▼          ▼              ▼              ▼
┌──────────────────────────────────────────────────────────────────────┐
│                     CONTENT GENERATION LAYER                         │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────────────────┐  │
│  │ ScriptEngine │  │ AntiRepeat   │  │   MediaAssetBuilder       │  │
│  │  (OpenAI/   │  │  (pgvector   │  │  (HeyGen + ElevenLabs     │  │
│  │   Claude)   │  │   similarity)│  │   background selector)    │  │
│  └──────┬───────┘  └──────┬───────┘  └──────────────┬────────────┘  │
└─────────│─────────────────│─────────────────────────│───────────────┘
          │                 │                          │
          └────────┬────────┘           async poll     │
                   │                   (2-8 min wait)  │
                   ▼                                   ▼
┌──────────────────────────────────────────────────────────────────────┐
│                       APPROVAL LAYER                                 │
│  ┌────────────────────────────────────────────────────────────┐      │
│  │             Telegram Bot  (python-telegram-bot)            │      │
│  │  Sends: video preview + post copy + [Approve] [Reject]     │      │
│  │  Receives: button callbacks → approve_handler / reject_handler│   │
│  └────────────────────────┬───────────────────────────────────┘      │
└───────────────────────────│──────────────────────────────────────────┘
                            │ on approve
                            ▼
┌──────────────────────────────────────────────────────────────────────┐
│                     PUBLISHING LAYER                                 │
│  ┌────────────────────────────────────────────────────────────┐      │
│  │            PublishService  (Ayrshare API)                  │      │
│  │  TikTok  │  IG Reels  │  FB Reels  │  YT Shorts            │      │
│  └──────────────────────────────────────────────────────────┬─┘      │
└──────────────────────────────────────────────────────────────│───────┘
                                                              │ after 48h
                                                              ▼
┌──────────────────────────────────────────────────────────────────────┐
│                      ANALYTICS LAYER                                 │
│  ┌──────────────────────┐   ┌──────────────────────────────────────┐ │
│  │  MetricsPoller       │   │  ViralityDetector + ReportBuilder    │ │
│  │  (platform API poll) │   │  (Sunday report / 500% threshold)   │ │
│  └──────────────────────┘   └──────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────┘
          │ all layers read/write
          ▼
┌──────────────────────────────────────────────────────────────────────┐
│                       PERSISTENCE LAYER                              │
│  ┌──────────────────┐  ┌─────────────────────┐  ┌───────────────┐   │
│  │ Supabase Postgres│  │  pgvector embeddings│  │  S3 / Storage │   │
│  │ (pipeline state, │  │  (script similarity │  │  (video files │   │
│  │  content records,│  │   anti-repetition)  │  │   tiered LC)  │   │
│  │  metrics, mood)  │  └─────────────────────┘  └───────────────┘   │
│  └──────────────────┘                                                │
└──────────────────────────────────────────────────────────────────────┘
```

---

### Component Responsibilities

| Component | Responsibility | Typical Implementation |
|-----------|----------------|------------------------|
| **Scheduler** | Fires daily pipeline trigger at configured time | APScheduler inside FastAPI lifespan, or Railway cron |
| **PipelineOrchestrator** | Coordinates all steps; writes `pipeline_run` state to DB; retries on failure | FastAPI BackgroundTasks or Celery task |
| **ScriptEngine** | Calls OpenAI/Claude API, enforces 140-word cap, 5-Pillar alignment, weekly mood injection | Python service class, `openai` SDK |
| **AntiRepetitionGuard** | Embeds candidate script, queries pgvector for cosine similarity; rejects if > 0.85 | Supabase `vecs` or `pgvector` via `asyncpg` |
| **MediaAssetBuilder** | Submits to HeyGen API, selects unused background, polls for completion, downloads video | Async poller with exponential backoff (2-8 min window) |
| **AudioProcessor** | (Optional) ElevenLabs TTS if used standalone; applies dark ambient post-processing | If HeyGen provides own voice, this may be skipped |
| **ApprovalBot** | Telegram bot: sends preview video + copy; handles `approve`/`reject` callbacks | `python-telegram-bot` v20+ (async) |
| **PublishService** | Takes approved video + copy, calls Ayrshare API for all 4 platforms simultaneously | `httpx` async calls to Ayrshare REST |
| **MetricsPoller** | Scheduled 48h after publish; calls Ayrshare analytics or platform APIs; stores metrics | APScheduler delayed job keyed per video_id |
| **ViralityDetector** | Compares 48h metrics against rolling average; fires alert if > 500% | Pure Python logic on stored metrics |
| **ReportBuilder** | Sundays: aggregates week's metrics, sends summary to Telegram | Scheduled job, Telegram message |
| **StorageLifecycleManager** | Moves S3 objects: Hot→Warm (8d), Warm→Cold/Delete (45d), preserves viral | S3 lifecycle policies + DB flag for viral overrides |

---

## Recommended Project Structure

```
content-creation/
├── app/
│   ├── main.py                   # FastAPI app, lifespan, scheduler init
│   ├── config.py                 # Settings via pydantic-settings (env vars)
│   ├── pipeline/
│   │   ├── orchestrator.py       # PipelineOrchestrator: step sequencing + state
│   │   ├── script_engine.py      # ScriptEngine: OpenAI calls, pillar injection
│   │   ├── anti_repetition.py    # AntiRepetitionGuard: pgvector similarity check
│   │   ├── media_builder.py      # MediaAssetBuilder: HeyGen submit + async poll
│   │   └── audio_processor.py    # AudioProcessor: ElevenLabs (if standalone voice)
│   ├── approval/
│   │   ├── telegram_bot.py       # Bot setup, command handlers, callback handlers
│   │   ├── handlers.py           # approve_handler, reject_handler
│   │   └── mood_handler.py       # Weekly mood prompt + storage
│   ├── publishing/
│   │   ├── publish_service.py    # Ayrshare API calls, platform payload builder
│   │   └── scheduler_hints.py   # Peak hour detection logic
│   ├── analytics/
│   │   ├── metrics_poller.py     # 48h post-publish platform metrics fetch
│   │   ├── virality_detector.py  # 500% threshold logic
│   │   └── report_builder.py    # Sunday weekly report
│   ├── storage/
│   │   ├── s3_client.py          # S3 upload/download wrapper
│   │   └── lifecycle.py          # Hot/Warm/Cold tier management
│   └── db/
│       ├── client.py             # Supabase async client setup
│       ├── models.py             # SQLAlchemy / raw SQL table definitions
│       └── embeddings.py        # pgvector insert + similarity query
├── scripts/
│   └── seed_pillars.py           # One-time: embed 5-Pillar framework docs
├── tests/
│   ├── test_script_engine.py
│   ├── test_anti_repetition.py
│   ├── test_telegram_handlers.py
│   └── test_publish_service.py
├── .env                          # Secrets (never commit)
├── pyproject.toml                # Dependencies (uv or poetry)
├── Dockerfile
└── railway.toml                  # Railway deploy config
```

### Structure Rationale

- **`app/pipeline/`:** All generation logic isolated — testable without Telegram or S3 involvement.
- **`app/approval/`:** Telegram bot is a completely separate concern from pipeline; handlers just call back into orchestrator.
- **`app/publishing/`:** Publishing is decoupled from approval — approve triggers publish, but the publish logic is self-contained.
- **`app/analytics/`:** Async, delayed jobs that don't block any user-facing path.
- **`app/storage/`:** S3 abstraction layer so lifecycle rules can be changed without touching pipeline code.
- **`app/db/`:** Centralized DB access; prevents scattered Supabase client instantiation.

---

## Architectural Patterns

### Pattern 1: Async Step Sequencer with State Machine

**What:** The orchestrator runs each pipeline step sequentially, writing a status record to `pipeline_runs` table after each step. If any step fails, the run record captures the failure point and the step can be retried independently.

**When to use:** Any multi-step pipeline where steps can fail, take minutes (HeyGen), or need human checkpointing (approval).

**Trade-offs:** Adds DB writes per step; worth it for debugging and resumability.

**Example:**
```python
# app/pipeline/orchestrator.py

class PipelineOrchestrator:
    async def run(self) -> None:
        run_id = await self.db.create_run()

        # Step 1: Generate script
        await self.db.update_run(run_id, status="script_generating")
        script = await self.script_engine.generate()
        await self.db.update_run(run_id, status="script_done", data={"script": script})

        # Step 2: Anti-repetition check (may loop up to 3x)
        for attempt in range(3):
            approved, score = await self.anti_repeat.check(script)
            if approved:
                break
            script = await self.script_engine.regenerate(feedback="too_similar")
        await self.db.update_run(run_id, status="script_unique")

        # Step 3: Submit to HeyGen (async — returns video_id)
        await self.db.update_run(run_id, status="video_rendering")
        heygen_id = await self.media_builder.submit(script)

        # Step 4: Poll for completion (blocks up to ~10 min with backoff)
        video_url = await self.media_builder.wait_for_completion(heygen_id)
        await self.db.update_run(run_id, status="video_ready", data={"video_url": video_url})

        # Step 5: Deliver to Telegram for approval
        await self.approval_bot.send_for_approval(run_id, video_url, script)
        await self.db.update_run(run_id, status="awaiting_approval")
        # Approval is event-driven from here — Telegram callback continues the flow
```

### Pattern 2: Async Polling with Exponential Backoff (HeyGen Integration)

**What:** HeyGen video generation is asynchronous — the API returns a `video_id` immediately, and the video takes 2-10 minutes to render. The correct pattern is polling with backoff, not a tight loop.

**When to use:** Any external API that returns a job ID and requires status polling (HeyGen, Runway, Pika).

**Trade-offs:** Ties up an async task for the poll duration. Use `asyncio.sleep` not `time.sleep` to avoid blocking the event loop.

**Example:**
```python
# app/pipeline/media_builder.py

import asyncio
import httpx

async def wait_for_completion(self, video_id: str, max_wait: int = 600) -> str:
    """Poll HeyGen until video is complete. Returns download URL."""
    backoff = [10, 20, 30, 45, 60, 90, 120]  # seconds between polls
    elapsed = 0

    async with httpx.AsyncClient() as client:
        for delay in backoff + [120] * 10:  # after backoff list, poll every 2 min
            await asyncio.sleep(delay)
            elapsed += delay

            resp = await client.get(
                f"https://api.heygen.com/v1/video_status.get",
                params={"video_id": video_id},
                headers={"X-Api-Key": self.api_key}
            )
            data = resp.json()
            status = data["data"]["status"]

            if status == "completed":
                return data["data"]["video_url"]
            elif status == "failed":
                raise VideoRenderError(f"HeyGen render failed: {data}")

            if elapsed > max_wait:
                raise TimeoutError(f"HeyGen render exceeded {max_wait}s")
```

### Pattern 3: Event-Driven Approval via Telegram Callbacks

**What:** After the pipeline delivers content to Telegram, the orchestrator suspends. Approval resumes the pipeline only when the creator taps Approve or Reject — making the approval step event-driven rather than polling-based.

**When to use:** Any human-in-the-loop checkpoint in an otherwise automated pipeline.

**Trade-offs:** Run state must persist in DB (not in memory) so the callback handler can resume after bot restarts.

**Example:**
```python
# app/approval/handlers.py

async def approve_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    run_id = int(query.data.split(":")[1])
    run = await db.get_run(run_id)

    # Resume pipeline from "awaiting_approval" state
    await publish_service.publish(run)
    await db.update_run(run_id, status="published")
    await query.edit_message_text("Published to all platforms.")

async def reject_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    run_id = int(query.data.split(":")[1])
    # Ask for rejection reason
    await query.message.reply_text("Rejection reason? (reply to this message)")
    context.user_data["pending_rejection_run_id"] = run_id
```

### Pattern 4: Delayed Metrics Job Scheduling

**What:** After publishing, schedule a one-time job to fire exactly 48 hours later to collect metrics. Don't poll continuously — schedule precisely.

**When to use:** Any post-publish analytics that need to be collected after a fixed window.

**Trade-offs:** If the server restarts within 48h, the job is lost unless persisted. Use APScheduler with a persistent job store (Supabase/Postgres-backed) or schedule via Railway cron with DB lookup.

**Example:**
```python
# app/analytics/metrics_poller.py

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime, timedelta

def schedule_metrics_collection(scheduler: AsyncIOScheduler, video_id: str, publish_time: datetime):
    run_at = publish_time + timedelta(hours=48)
    scheduler.add_job(
        collect_metrics,
        "date",
        run_date=run_at,
        args=[video_id],
        id=f"metrics_{video_id}",
        replace_existing=True
    )
```

---

## Data Flow

### Primary Pipeline Flow (Daily Trigger → Published Video)

```
[APScheduler trigger — 06:00]
    │
    ▼
[PipelineOrchestrator.run()]
    │
    ├─── [ScriptEngine] ──────────────► [OpenAI API]
    │         │                              │
    │         │ script text (≤140 words)     │
    │         ◄──────────────────────────────┘
    │         │
    │    [AntiRepetitionGuard]
    │         │ embed script ──────────────► [Supabase pgvector]
    │         │                             cosine similarity query
    │         │ score < 0.85? continue       │
    │         ◄──────────────────────────────┘
    │         │ (if rejected: regenerate up to 3x)
    │         │
    │    [MediaAssetBuilder]
    │         │ submit script + avatar ID ──► [HeyGen API]
    │         │                              returns video_id
    │         │ poll every 30-120s (2-8min)
    │         │ status: completed ───────────► download video URL
    │         │ store video → [S3] (Hot tier)
    │         │
    │    [ApprovalBot.send_for_approval()]
    │         │ send video + copy ──────────► [Telegram API]
    │         │                              creator sees inline keyboard
    │         │
    ▼  [DB: status = "awaiting_approval"]  [EVENT BOUNDARY — async pause]

[Telegram callback: Approve button tapped]
    │
    ▼
[approve_callback()]
    │
    ├─── [PublishService]
    │         │ POST video URL + copy ──────► [Ayrshare API]
    │         │                              → TikTok
    │         │                              → IG Reels
    │         │                              → FB Reels
    │         │                              → YT Shorts
    │         │
    │    [schedule_metrics_collection(+48h)]
    │
    ▼
[DB: status = "published", published_at = now()]
```

### Rejection Flow

```
[Telegram callback: Reject button tapped]
    │
    ▼
[Bot prompts: "Rejection reason?"]
    │
[Creator replies with reason]
    │
    ▼
[reject_handler()]
    │ store rejection_feedback in pipeline_run row
    ├─── [Store as negative context in content_history table]
    │
    └─── [Re-trigger pipeline] OR [wait for next daily trigger]
         (configurable — immediate retry vs skip day)
```

### Metrics Flow (48h Post-Publish)

```
[APScheduler fires at publish_time + 48h]
    │
    ▼
[MetricsPoller.collect(video_id)]
    │ query Ayrshare analytics API ──────► [Platform APIs via Ayrshare]
    │ returns: views, shares, retention, likes
    │
    ▼
[Store metrics in video_metrics table]
    │
    ▼
[ViralityDetector.check(video_id)]
    │ compare to rolling_average (last 30 videos)
    │ if > 500%:
    │     ├─ set viral_flag = true (preserves from S3 deletion)
    │     └─ send Telegram alert to creator
    │
    ▼
[Sunday trigger: ReportBuilder.generate_weekly()]
    │ aggregate 7 videos' metrics
    └─ send formatted report to Telegram
```

### Weekly Mood Profile Flow

```
[Weekly trigger — Monday 07:00]
    │
    ▼
[Bot sends mood prompt to creator]
    │
[Creator responds (text or structured reply)]
    │
    ▼
[mood_handler stores MoodProfile in DB]
    │
    └─ ScriptEngine reads this week's MoodProfile on each generation
```

---

## Key Integration Points and Their Risks

### HeyGen API

| Aspect | Detail | Risk |
|--------|--------|------|
| Auth | `X-Api-Key` header | Key rotation breaks silently |
| Submit endpoint | `POST /v1/video.generate` | Payload schema can change |
| Status endpoint | `GET /v1/video_status.get?video_id=X` | No webhook available (LOW confidence — verify) |
| Render time | 2-10 minutes for 40s video at 1080p | Must use async polling, NOT sync wait |
| Rate limits | Unknown — LOW confidence | Assume 10 concurrent renders max |
| Video delivery | Signed URL (expires in ~24h) | Must download and re-store to S3 immediately |

**Critical:** HeyGen URLs are likely time-limited signed URLs. Download to S3 as soon as render completes — do not store the raw HeyGen URL in DB as a long-term reference.

### ElevenLabs API

| Aspect | Detail | Risk |
|--------|--------|------|
| TTS generation | Synchronous — returns audio bytes directly | Simple; no polling needed |
| Latency | 1-3 seconds for 40s script | Negligible |
| Use case | Only needed if HeyGen uses external audio track | HeyGen may handle voice internally |

**Decision point:** Verify whether HeyGen's avatar uses a pre-trained voice (internal) or accepts an audio file input. If HeyGen handles voice internally, ElevenLabs may not be needed.

### Supabase / pgvector

| Aspect | Detail | Risk |
|--------|--------|------|
| Vector similarity | `<=>` cosine distance operator | Requires `pgvector` extension enabled on Supabase project |
| Embedding model | `text-embedding-3-small` from OpenAI (1536 dimensions) | Model version lock — changing model invalidates all stored embeddings |
| Threshold | 0.85 cosine similarity = reject | Threshold needs calibration after ~20 videos |
| Async client | Use `asyncpg` or Supabase Python client with async support | Supabase Python SDK is synchronous — use `asyncpg` directly or run in threadpool |

### Ayrshare API

| Aspect | Detail | Risk |
|--------|--------|------|
| Auth | Bearer token | Single token for all platforms |
| Video posting | Accepts URL (must be publicly accessible) — video must be on S3 with public or signed URL | Private S3 = Ayrshare cannot download it |
| Platform support | TikTok, IG, FB, YT confirmed | Platform API changes can break specific channels without warning |
| Rate limits | Depends on Ayrshare plan tier | Check plan limits for 1 post/day across 4 platforms |
| Scheduling | Supports `scheduleDate` field | Can pre-schedule to optimal hours |

**Critical:** Video must be accessible via public URL for Ayrshare to download. Use S3 pre-signed URLs with sufficient expiry (24h minimum) OR make the S3 bucket public for the `hot/` prefix only.

### Telegram Bot

| Aspect | Detail | Risk |
|--------|--------|------|
| Library | `python-telegram-bot` v20+ (async) | v13 vs v20 are incompatible APIs |
| Deployment | Bot must have a running process (polling mode OR webhook) | Railway/Render keeps process alive |
| Security | Validate every update against creator's `user_id` | Reject all other user IDs immediately |
| Video delivery | Telegram has 50MB file size limit for bots | HeyGen 1080p 40s video likely exceeds 50MB — send URL link, not file upload |

**Critical:** Do NOT send video as a Telegram file upload. Send a download link or stream URL. A 40-second 1080p video is typically 80-200MB — well above Telegram's bot 50MB limit.

---

## Suggested Build Order (Dependency Graph)

The pipeline has hard dependencies that dictate build order:

```
Phase 1: Foundation
  DB schema + Supabase client + config/settings
    │
    ▼
Phase 2: Content Generation (no external dependencies except OpenAI)
  ScriptEngine + AntiRepetitionGuard (pgvector)
    │
    ▼
Phase 3: Media Production (depends on script being ready)
  MediaAssetBuilder (HeyGen integration + async poll)
    │
    ▼
Phase 4: Approval Loop (depends on media being ready)
  Telegram Bot + approve/reject handlers
    │
    ▼
Phase 5: Publishing (depends on approval flow)
  PublishService (Ayrshare) + S3 storage
    │
    ▼
Phase 6: Analytics (depends on publishing)
  MetricsPoller + ViralityDetector + ReportBuilder
    │
    ▼
Phase 7: Hardening
  Error handling, retries, storage lifecycle, weekly mood flow
```

**Rationale for this order:**
1. You cannot test HeyGen until you have scripts to render.
2. You cannot test Telegram approval until you have videos to preview.
3. You cannot test publishing until approval flow works.
4. Analytics requires real published content to measure.
5. Each phase can be tested independently with fixtures at its top boundary.

---

## Async vs Sync Considerations

| Component | Mode | Rationale |
|-----------|------|-----------|
| Scheduler trigger | Async (APScheduler AsyncIOScheduler) | Fires into FastAPI event loop |
| ScriptEngine (OpenAI) | Async (`openai.AsyncOpenAI`) | Non-blocking; 2-5s latency |
| AntiRepetitionGuard (pgvector) | Async (`asyncpg`) | Supabase Python SDK is sync — use asyncpg directly |
| HeyGen submit | Async (`httpx.AsyncClient`) | Fire-and-forget with returned video_id |
| HeyGen poll | Async with `asyncio.sleep` | Critical: use async sleep, never `time.sleep` |
| ElevenLabs TTS | Sync acceptable (fast) | Or wrap in `asyncio.to_thread` |
| Telegram bot | Async (`python-telegram-bot` v20) | Full async callback handlers required |
| Ayrshare publish | Async (`httpx.AsyncClient`) | Multi-platform fire; can fan out concurrently |
| Metrics poller | Async background task | Runs in same event loop 48h later |
| S3 operations | Async (`aioboto3`) | Video files are large; async prevents blocking |

**Key rule:** The HeyGen poll loop runs inside a FastAPI `BackgroundTask`. It must use `asyncio.sleep` exclusively — any `time.sleep` call will block the entire event loop and freeze the Telegram bot's webhook handling.

---

## Scalability Considerations

This is a single-user system. Scalability concerns are about reliability and cost, not traffic.

| Concern | At current scale (1 user, 1 video/day) | If expanded (10 videos/day) |
|---------|----------------------------------------|------------------------------|
| HeyGen concurrency | 1 render at a time — fine | Need queue; HeyGen rate limits unclear |
| OpenAI costs | ~$0.01/script — negligible | Still negligible |
| S3 storage | ~200MB/day in Hot → lifecycle manages it | Lifecycle rules handle it |
| Supabase DB | Trivial load | Trivial load |
| Telegram | 1 message/day — no concerns | No concerns |
| Ayrshare plan | Verify 1 post/day across 4 platforms is within free/base tier | May need higher tier |

**First real bottleneck:** HeyGen render queue. If videos pile up (retries + new daily), you may have 2-3 renders in flight. HeyGen's concurrent render limits are not publicly documented — verify during Phase 3.

---

## Anti-Patterns

### Anti-Pattern 1: Synchronous HeyGen Wait in Request Handler

**What people do:** Call HeyGen submit and then `time.sleep(300)` waiting for it in a synchronous function.
**Why it's wrong:** Blocks the entire process for 5+ minutes; kills Telegram bot responsiveness; Railway/Render may timeout the request.
**Do this instead:** Submit to HeyGen, store `video_id` in DB, return immediately. Poll in an async background task with `asyncio.sleep`.

### Anti-Pattern 2: Storing HeyGen Signed URLs as Permanent References

**What people do:** Store the `video_url` returned from HeyGen completion as the canonical video URL in the DB.
**Why it's wrong:** HeyGen signed URLs expire (typically within 24-48h). Links break when metrics collection or re-publishing tries to access them.
**Do this instead:** Download the video from HeyGen immediately after render completion. Upload to S3. Store the S3 key as the canonical reference.

### Anti-Pattern 3: In-Memory Pipeline State

**What people do:** Carry pipeline state in a Python dict or class instance across steps.
**Why it's wrong:** Server restart (Railway deploy, crash) loses state mid-pipeline. Approval callback arrives hours later in a fresh process with no memory of the run.
**Do this instead:** Write every state transition to `pipeline_runs` table. Callbacks look up run by ID from DB.

### Anti-Pattern 4: Sending Video File to Telegram Bot Upload

**What people do:** `bot.send_video(chat_id=..., video=open("file.mp4", "rb"))`.
**Why it's wrong:** Telegram bots have a 50MB upload limit. A 1080p 40-second video is 80-200MB — it will fail silently or throw an exception.
**Do this instead:** Upload video to S3, generate a presigned URL, send the URL in the Telegram message. The creator taps the link to preview in their browser or a video player.

### Anti-Pattern 5: Single Embedding Model Forever

**What people do:** Start with one OpenAI embedding model and never document which one was used.
**Why it's wrong:** If you switch models (e.g., `text-embedding-3-small` → `text-embedding-3-large`), cosine distances between old and new embeddings are not comparable. Anti-repetition queries become unreliable.
**Do this instead:** Store the `embedding_model` version alongside each embedding row. If you change models, re-embed all historical scripts. Flag in config.

### Anti-Pattern 6: Missing Rejection Feedback Loop

**What people do:** Reject content, restart pipeline from scratch with no memory of why the previous attempt failed.
**Why it's wrong:** The system will regenerate similar rejected content repeatedly, wasting HeyGen render credits ($$$).
**Do this instead:** Store rejection reason + rejected script embedding. Inject rejection context into the next ScriptEngine prompt. Store as negative examples in a `rejection_history` table.

---

## Integration Points Summary

### External Services

| Service | Integration Pattern | Key Gotcha |
|---------|---------------------|------------|
| OpenAI | REST via `openai` SDK, async | Token limits; enforce 140-word cap before API call |
| HeyGen | REST via `httpx`, job submission + polling | Signed URL expiry; concurrent render limits unknown |
| ElevenLabs | REST via `httpx`, synchronous response | Only needed if HeyGen doesn't handle voice |
| Supabase/pgvector | `asyncpg` directly or Supabase async client | Sync SDK requires thread pool; use asyncpg |
| S3 | `aioboto3` async | Public URL required for Ayrshare; plan access policy carefully |
| Telegram | `python-telegram-bot` v20 async | 50MB file limit; validate user_id on every update |
| Ayrshare | REST via `httpx`, single POST per publish | Video must be publicly accessible URL |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| Scheduler → Orchestrator | Direct async function call | APScheduler calls coroutine |
| Orchestrator → ScriptEngine | Synchronous method call (same process) | Pass mood profile as context |
| Orchestrator → AntiRepetitionGuard | Async method call | Returns (approved: bool, score: float) |
| Orchestrator → MediaBuilder | Async method call, fire-and-poll | Returns video URL after polling completes |
| MediaBuilder → ApprovalBot | Async method call | Passes run_id + video URL |
| Telegram callback → PublishService | Async callback handler calls service | State retrieved from DB by run_id |
| PublishService → MetricsScheduler | After publish: schedules delayed job | APScheduler date job, Postgres job store |
| MetricsPoller → ViralityDetector | Direct call after metrics collected | Same process |
| ViralityDetector → ApprovalBot | Send alert message if viral | Bot is running; just call bot.send_message |

---

## Sources

- HeyGen API patterns: Training data (MEDIUM confidence) — verify at https://docs.heygen.com/reference
- `python-telegram-bot` v20 async architecture: Training data (MEDIUM confidence) — verify at https://docs.python-telegram-bot.org/
- Ayrshare video posting patterns: Training data (MEDIUM confidence) — verify at https://docs.ayrshare.com/
- Supabase pgvector + asyncpg: Training data (MEDIUM confidence) — verify at https://supabase.com/docs/guides/database/extensions/pgvector
- APScheduler with Postgres job store: Training data (MEDIUM confidence) — verify at https://apscheduler.readthedocs.io/
- FastAPI BackgroundTasks + async patterns: Training data (HIGH confidence — widely documented) — https://fastapi.tiangolo.com/tutorial/background-tasks/
- S3 signed URL patterns: Training data (HIGH confidence) — https://docs.aws.amazon.com/AmazonS3/latest/userguide/ShareObjectPreSignedURL.html
- Telegram bot file size limits: Training data (MEDIUM confidence — 50MB is well-documented) — verify at https://core.telegram.org/bots/api#senddocument

---
*Architecture research for: AI Automated Short-Form Video Content Pipeline*
*Researched: 2026-02-19*
