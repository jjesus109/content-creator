# Phase 4: Telegram Approval Loop - Research

**Researched:** 2026-02-22
**Domain:** python-telegram-bot 21.x, Supabase/PostgreSQL, ffmpeg thumbnail extraction, Anthropic Haiku, APScheduler thread bridge
**Confidence:** HIGH (core PTB patterns verified via official docs; codebase analysis is direct evidence)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

#### Message design
- Video presented as URL + thumbnail image inline — creator sees a frame before tapping
- Message contains: video URL, generated post copy, and metadata (generation date, mood profile used, script word count, background used)
- Two inline keyboard buttons side by side: ✅ Approve | ❌ Reject with Cause

#### Post copy generation
- Language: Spanish (same as the script — no translation)
- Format: Hook line + 2–3 body lines + hashtags
- Generated just before Telegram delivery (Phase 4 responsibility, not Phase 2 pipeline)
- Model: Claude Haiku (same model used for script generation)
- Stored to content_history alongside the video record

#### Rejection flow behavior
- Rejection triggers immediate retry (same day) — new script + new video with the constraint injected, new approval message sent
- Daily retry limit: 2 rejections per day (3 total attempts before the run is abandoned)
- Rejection cause categories: Script Error / Visual Error / Technical Error / Off-topic
- Constraint persistence: rejection cause remains active until a run in that category is approved — it does not clear after a single injection

#### Approval state & feedback
- After tapping Approve or Reject: a new follow-up message is sent (original message stays unchanged)
- Approval confirmation: "✅ Approved — queued for publish" (Phase 5 will enhance with actual platform schedule times)
- Rejection confirmation: "⚠️ Rejected ([cause]) — new video incoming in ~X minutes"
- Daily retry limit reached notification: "Daily limit reached, next run tomorrow at [time]"
- Approval state stored in a separate `approval_events` table (not extending content_history directly)
- Restart-safe: inline keyboard buttons remain functional after server restart — approval state always read from DB, never in-memory

### Claude's Discretion
- Exact thumbnail generation approach (whether to extract a frame from video or use a cover image)
- Precise retry timing estimate shown in rejection confirmation message
- Schema details for approval_events table beyond the decisions above
- How rejection constraints are surfaced to the script generation prompt (format/injection logic)

### Deferred Ideas (OUT OF SCOPE)
- Platform-specific scheduled post times in approval confirmation — Phase 5 (requires Ayrshare scheduling to be built first)
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| TGAP-01 | Bot delivers daily video to creator via presigned S3/Supabase URL (not file upload) with generated post copy | `bot.send_photo(photo=url, caption=..., reply_markup=...)` supports HTTPS URL natively; Telegram downloads it server-side. Photo = extracted thumbnail frame, caption = post copy + metadata + video link. |
| TGAP-02 | Bot presents inline [Approve] and [Reject with Cause] buttons; approval triggers publish pipeline, rejection suspends the run | `InlineKeyboardMarkup([[approve_btn, reject_btn]])` side-by-side pattern; handler reads from DB not memory; publish pipeline call dispatched via run_coroutine_threadsafe from callback handler. |
| TGAP-03 | Rejection opens a structured cause menu: Script Error / Visual Error / Technical Error | Second-step CallbackQueryHandler with prefix `appr_cause:` edits the original message to show a 4-button cause menu; same await query.answer() + edit_message_text pattern already used in mood_flow.py. |
| TGAP-04 | Rejection cause is stored as negative context and injected into the next generation iteration as a constraint | Write to rejection_constraints table (already exists from migration 0002, already read by script_generation.py); constraint persists until an approved run is recorded in the same cause category. |
</phase_requirements>

---

## Summary

Phase 4 closes the production loop by adding interactive approval over Telegram. The creator receives a photo message (extracted thumbnail frame from the video) with the video URL in the caption, generated post copy in Spanish, and two side-by-side inline buttons. Tapping Approve or Reject with Cause triggers a two-step callback handler that reads all state from the database — making the flow restart-safe. Rejection opens a structured four-button cause menu; the chosen cause is written to the existing `rejection_constraints` table and triggers an immediate pipeline re-run.

The entire Phase 4 flow builds on patterns already proven in Phase 2 (mood_flow.py). The CallbackQueryHandler + prefix matching approach is the correct one — ConversationHandler cannot be used for bot-initiated flows. Three new modules are needed: `telegram/handlers/approval_flow.py` (the callback handlers), `services/post_copy.py` (Claude Haiku generation), and `services/approval.py` (DB reads/writes for the approval_events table). One new migration creates the `approval_events` table and adds a `post_copy` column to `content_history`. The video delivery is triggered from within `_process_completed_render()` in `services/heygen.py` after video_status transitions to READY.

The most important architectural insight: all approval state lives in the database, not in `context.bot_data`. This is already the pattern for mood_flow Phase 2 state at step 3 (DB write), and must be used from step 1 for approval since the creator may tap buttons hours after the bot restarts.

**Primary recommendation:** Extend the existing Phase 2 CallbackQueryHandler + prefix pattern directly. Add three new handler functions behind `appr_approve:`, `appr_reject:`, and `appr_cause:` prefixes. Deliver the message from inside `_process_completed_render()` using `send_alert_sync`'s `asyncio.run_coroutine_threadsafe` pattern already in `services/telegram.py`.

---

## Standard Stack

### Core (already in pyproject.toml — no new dependencies needed)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| python-telegram-bot | 21.* | CallbackQueryHandler, InlineKeyboardMarkup, Bot.send_photo | Already installed, proven in Phase 2 |
| anthropic | >=0.83.0 | Synchronous Anthropic client for post copy generation | Already used in ScriptGenerationService |
| supabase | >=2.0 | approval_events reads/writes, content_history post_copy update | Already the DB client |
| APScheduler | 3.11.2 | Immediate pipeline re-run job after rejection | Already used; pattern already in video_poller.py |

### Supporting (already in pyproject.toml)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| ffmpeg (system binary) | any recent | Extract first frame as JPEG bytes for thumbnail | Thumbnail generation from Supabase video URL |
| subprocess (stdlib) | Python 3.12 | Call ffmpeg with pipe:1 output | Frame extraction in-memory without temp files |
| io.BytesIO (stdlib) | Python 3.12 | Wrap JPEG bytes for bot.send_photo() | PTB accepts BytesIO as photo input |
| requests | already transitive | Download video bytes for thumbnail extraction | Already used in audio_processing.py, video_poller.py |

### No New Dependencies Required

The entire Phase 4 can be built with what is already installed. ffmpeg is already present in the Docker image (used by AudioProcessingService). The only new system interaction is `bot.send_photo()` which PTB already provides.

**Installation:** None needed.

---

## Architecture Patterns

### Recommended New File Structure

```
src/app/
├── telegram/
│   ├── app.py                          # MODIFY: register_approval_handlers(app) call added
│   └── handlers/
│       ├── mood_flow.py                # UNCHANGED
│       └── approval_flow.py            # NEW: approve/reject/cause callback handlers
├── services/
│   ├── approval.py                     # NEW: ApprovalService (DB reads/writes for approval_events)
│   ├── post_copy.py                    # NEW: PostCopyService (Claude Haiku, Spanish copy generation)
│   ├── heygen.py                       # MODIFY: call send_approval_message() at end of _process_completed_render()
│   └── telegram.py                     # MODIFY: add send_approval_message() coroutine
├── scheduler/
│   └── jobs/
│       └── daily_pipeline.py           # MODIFY: trigger_immediate_rerun() helper for rejection retry
migrations/
└── 0004_approval_events.sql            # NEW: approval_events table + post_copy column on content_history
```

### Pattern 1: Delivery Trigger — Call from _process_completed_render()

**What:** When video_status transitions to READY, call `send_approval_message()` from within `_process_completed_render()`. This is the only natural trigger point: it runs in a thread pool executor, has the stable `video_url`, and already calls `send_alert_sync()` as the last step.

**When to use:** Every time a video reaches READY status (whether via webhook or poller).

**Example:**
```python
# In services/heygen.py — _process_completed_render(), after DB update to READY
# Replace the existing send_alert_sync("Video listo...") call with:
from app.services.telegram import send_approval_message_sync

send_approval_message_sync(content_history_id=row_id, video_url=stable_url)
```

The sync wrapper follows the identical pattern used by `send_alert_sync()` in `services/telegram.py`:
```python
# Source: services/telegram.py — send_alert_sync() pattern
def send_approval_message_sync(content_history_id: str, video_url: str) -> None:
    """Sync wrapper for APScheduler/executor thread. Same pattern as send_alert_sync."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.run_coroutine_threadsafe(
                send_approval_message(content_history_id, video_url), loop
            )
        else:
            loop.run_until_complete(send_approval_message(content_history_id, video_url))
    except RuntimeError:
        asyncio.run(send_approval_message(content_history_id, video_url))
```

### Pattern 2: Approval/Rejection Handlers — Prefix CallbackQueryHandler

**What:** Three new `CallbackQueryHandler` instances with unique prefixes, registered in `telegram/app.py` via `register_approval_handlers()`. Mirrors the mood_flow pattern exactly.

**When to use:** Whenever the creator taps any approval-related inline button.

**Prefixes:**
- `appr_approve:` + content_history_id — Approve button
- `appr_reject:` + content_history_id — "Reject with Cause" button (opens cause menu)
- `appr_cause:` + content_history_id + ":" + cause_code — Cause selection button

**Example:**
```python
# Source: telegram/handlers/approval_flow.py — follows mood_flow.py pattern exactly
PREFIX_APPROVE = "appr_approve:"
PREFIX_REJECT  = "appr_reject:"
PREFIX_CAUSE   = "appr_cause:"

async def handle_approve(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()  # REQUIRED — prevents Telegram loading spinner freezing

    content_history_id = query.data[len(PREFIX_APPROVE):]

    # Read state from DB — restart-safe (never from context.bot_data)
    approval_svc = ApprovalService()
    if approval_svc.is_already_actioned(content_history_id):
        await update.effective_chat.send_message("Ya procesado.")
        return

    approval_svc.record_approve(content_history_id)
    await update.effective_chat.send_message("✅ Approved — queued for publish")

async def handle_reject(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()  # REQUIRED

    content_history_id = query.data[len(PREFIX_REJECT):]

    # Show cause menu by editing the original message text only (not the buttons area)
    # Keep original approval message intact — send new message for cause selection
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("Script Error",     callback_data=f"{PREFIX_CAUSE}{content_history_id}:script_error")],
        [InlineKeyboardButton("Visual Error",     callback_data=f"{PREFIX_CAUSE}{content_history_id}:visual_error")],
        [InlineKeyboardButton("Technical Error",  callback_data=f"{PREFIX_CAUSE}{content_history_id}:technical_error")],
        [InlineKeyboardButton("Off-topic",        callback_data=f"{PREFIX_CAUSE}{content_history_id}:off_topic")],
    ])
    await update.effective_chat.send_message(
        text="Selecciona la causa del rechazo:",
        reply_markup=keyboard,
    )

async def handle_cause(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()  # REQUIRED

    parts = query.data[len(PREFIX_CAUSE):].rsplit(":", 1)
    content_history_id, cause_code = parts[0], parts[1]

    approval_svc = ApprovalService()
    if approval_svc.is_already_actioned(content_history_id):
        await update.effective_chat.send_message("Ya procesado.")
        return

    approval_svc.record_reject(content_history_id, cause_code)
    # Write rejection constraint (persists until approved run in same category)
    approval_svc.write_rejection_constraint(cause_code)

    # Check daily retry limit
    retry_count = approval_svc.get_today_rejection_count()
    if retry_count >= 2:
        await update.effective_chat.send_message(
            f"Daily limit reached, next run tomorrow at 07:00 AM."
        )
        return

    # Trigger immediate re-run (new script + new video)
    await update.effective_chat.send_message(
        f"⚠️ Rejected ({cause_code}) — new video incoming in ~15 minutes"
    )
    # Dispatch immediate pipeline re-run via APScheduler
    from app.scheduler.jobs.daily_pipeline import trigger_immediate_rerun
    trigger_immediate_rerun()

def register_approval_handlers(app: Application) -> None:
    app.add_handler(CallbackQueryHandler(handle_approve, pattern=f"^{PREFIX_APPROVE}"))
    app.add_handler(CallbackQueryHandler(handle_reject,  pattern=f"^{PREFIX_REJECT}"))
    app.add_handler(CallbackQueryHandler(handle_cause,   pattern=f"^{PREFIX_CAUSE}"))
```

### Pattern 3: Thumbnail Generation via ffmpeg

**What:** Download video bytes from Supabase URL, pipe through ffmpeg to extract frame 1 at timestamp 00:00:01, output JPEG bytes via pipe:1. Wrap in BytesIO for `bot.send_photo()`.

**Recommendation (Claude's Discretion):** Use ffmpeg frame extraction — not a static cover image. The video is already downloaded for audio processing so the pattern is proven. For the approval message, download the Supabase Storage public URL (which is stable), extract frame 1 second in, pass as BytesIO.

**Why 1 second not 0 seconds:** The first frame (00:00:00) is often black for avatar videos. 1 second gives the avatar in full pose.

**Example:**
```python
# Source: audio_processing.py pattern + ffmpeg frame extraction research
import subprocess, requests
from io import BytesIO

def extract_thumbnail(video_url: str) -> BytesIO:
    """
    Download video from stable Supabase URL and extract frame at t=1s as JPEG.
    Returns BytesIO object ready for bot.send_photo(photo=bio).
    """
    resp = requests.get(video_url, timeout=60)
    resp.raise_for_status()
    video_bytes = resp.content

    result = subprocess.run([
        "ffmpeg",
        "-ss", "00:00:01",     # seek to 1 second (avatar in pose, not black frame)
        "-i", "pipe:0",        # read video from stdin
        "-frames:v", "1",      # extract exactly one frame
        "-f", "image2",        # image output format
        "-c:v", "mjpeg",       # JPEG codec
        "-vf", "scale=320:-1", # scale to max 320px wide (Telegram thumbnail limit)
        "pipe:1",              # output JPEG bytes to stdout
    ], input=video_bytes, capture_output=True, timeout=30)

    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg thumbnail extraction failed: {result.stderr.decode()}")

    bio = BytesIO(result.stdout)
    bio.name = "thumbnail.jpg"  # PTB requires .name attribute on BytesIO
    bio.seek(0)
    return bio
```

### Pattern 4: Sending the Approval Message

**What:** `bot.send_photo()` with JPEG thumbnail bytes, caption containing all required fields, and InlineKeyboardMarkup.

**Telegram API fact (HIGH confidence):** `bot.send_photo()` accepts: file_id (string), HTTPS URL (string), raw bytes, or BytesIO object for the `photo` parameter. For thumbnail purposes, pass the BytesIO from `extract_thumbnail()`.

**Caption limit:** 1024 characters. Keep post copy + metadata within this limit.

**Example:**
```python
# Source: Official PTB docs + verified research
async def send_approval_message(content_history_id: str, video_url: str) -> None:
    settings = get_settings()
    bot = get_telegram_bot()

    # Load row from content_history for metadata
    from app.services.database import get_supabase
    supabase = get_supabase()
    row = supabase.table("content_history").select(
        "script_text, post_copy, background_url, created_at"
    ).eq("id", content_history_id).single().execute().data

    # Generate thumbnail (ffmpeg, 1 second frame)
    from app.services.post_copy import extract_thumbnail
    thumbnail_bio = extract_thumbnail(video_url)

    # Build caption (Spanish)
    word_count = len(row["script_text"].split())
    generation_date = row["created_at"][:10]
    # Load mood profile from most recent mood_profiles row for the week
    mood_resp = supabase.table("mood_profiles").select("profile_text").order(
        "created_at", desc=True
    ).limit(1).execute()
    mood_label = mood_resp.data[0]["profile_text"][:60] if mood_resp.data else "—"
    background_short = (row.get("background_url") or "").split("/")[-1]

    caption = (
        f"{row['post_copy']}\n\n"
        f"---\n"
        f"Video: {video_url}\n"
        f"Fecha: {generation_date} | Mood: {mood_label} | "
        f"Palabras: {word_count} | Fondo: {background_short}"
    )
    # Truncate to 1024 chars (Telegram caption limit)
    if len(caption) > 1024:
        caption = caption[:1021] + "..."

    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Approve",          callback_data=f"appr_approve:{content_history_id}"),
        InlineKeyboardButton("❌ Reject with Cause", callback_data=f"appr_reject:{content_history_id}"),
    ]])

    await bot.send_photo(
        chat_id=settings.telegram_creator_id,
        photo=thumbnail_bio,
        caption=caption,
        reply_markup=keyboard,
        parse_mode=None,    # No markdown — video URL and metadata are plain text
    )
```

### Pattern 5: Database Schema for approval_events

**Recommendation (Claude's Discretion):** Minimal, append-only event log. The table captures the event; `content_history` remains the canonical video record.

```sql
-- Migration 0004: Approval events + post copy column
-- approval_events: append-only log of creator decisions
CREATE TABLE IF NOT EXISTS approval_events (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at          timestamptz DEFAULT now() NOT NULL,
    content_history_id  uuid NOT NULL REFERENCES content_history(id),
    action              text NOT NULL CHECK (action IN ('approved', 'rejected')),
    cause_code          text,  -- NULL for approvals; required for rejections
    -- cause_code values: 'script_error', 'visual_error', 'technical_error', 'off_topic'
    CONSTRAINT rejection_requires_cause CHECK (
        action = 'approved' OR cause_code IS NOT NULL
    )
);

-- Index for idempotency checks and daily count queries
CREATE INDEX IF NOT EXISTS approval_events_content_history_id
    ON approval_events(content_history_id);

CREATE INDEX IF NOT EXISTS approval_events_created_at
    ON approval_events(created_at);

-- Post copy storage alongside the video record
ALTER TABLE content_history
    ADD COLUMN IF NOT EXISTS post_copy text;
```

**Query patterns the ApprovalService will need:**

1. **Idempotency check** (restart-safe — prevents double-processing):
   ```sql
   SELECT id FROM approval_events WHERE content_history_id = $1 LIMIT 1;
   ```

2. **Daily rejection count** (enforces 2-rejection-per-day limit):
   ```sql
   SELECT COUNT(*) FROM approval_events
   WHERE action = 'rejected'
     AND created_at >= CURRENT_DATE
     AND created_at < CURRENT_DATE + INTERVAL '1 day';
   ```

3. **Write rejection constraint** (persists until approved run in same category):
   The rejection constraint goes into the existing `rejection_constraints` table (migration 0002). `expires_at` must be set far in the future (e.g., 365 days) — Phase 4 clears it when an approved run is recorded in the same cause category.

### Pattern 6: Immediate Rejection Re-Run

**What:** After recording a rejection, trigger a new `daily_pipeline_job()` execution immediately via APScheduler's `run_date` trigger (one-shot job in the future, not a new cron).

**How:** Use the `_scheduler` module-level reference from `video_poller.py` (already available via `set_scheduler()`), or add a `trigger_immediate_rerun()` helper to `daily_pipeline.py`.

**Recommendation:** Add `trigger_immediate_rerun()` to `daily_pipeline.py` that schedules the job with `run_date=now+30s`:

```python
# In daily_pipeline.py
def trigger_immediate_rerun() -> None:
    """
    Schedule an immediate pipeline re-run after rejection.
    Uses run_date trigger (one-shot) — fires 30 seconds from now.
    The 30s delay gives APScheduler time to register the job before firing.
    """
    from apscheduler.triggers.date import DateTrigger
    from datetime import datetime, timedelta, timezone
    from app.scheduler.jobs.video_poller import _scheduler

    run_at = datetime.now(tz=timezone.utc) + timedelta(seconds=30)
    _scheduler.add_job(
        daily_pipeline_job,
        trigger=DateTrigger(run_date=run_at),
        id="rejection_rerun",
        name="Rejection-triggered pipeline re-run",
        replace_existing=True,  # Only one re-run queued at a time
    )
    logger.info("Rejection re-run scheduled for %s", run_at.isoformat())
```

**The ~15 minutes shown in the rejection confirmation message** accounts for pipeline generation (~2-3 min) + HeyGen render (~10 min) + audio processing (~2 min).

### Anti-Patterns to Avoid

- **Storing approval state in context.bot_data:** Resets on server restart. All approval state must come from the DB.
- **Using ConversationHandler for the approval flow:** ConversationHandler requires `entry_points` which means a user-initiated command. The approval message is bot-initiated. Use raw `CallbackQueryHandler` with prefix matching — exactly as mood_flow.py does.
- **Forgetting `await query.answer()` in every callback handler:** Causes the Telegram loading spinner to freeze permanently on the creator's device. Required in all three handlers (handle_approve, handle_reject, handle_cause).
- **Passing the video URL as a file upload to Telegram:** The video file is 100-500MB. The decision is to send the URL as text in the caption. Telegram does NOT upload the video.
- **Sending the Supabase signed URL for the thumbnail:** Use the stable public URL (already stored in `content_history.video_url`). The stable URL is what `VideoStorageService.upload()` returns and stores.
- **Setting `expires_at` to a short window on rejection_constraints:** The constraint must persist indefinitely (use 365 days) — it is only cleared when a run in the same cause category gets approved.
- **Triggering the approval message from a scheduled job:** The correct trigger is inside `_process_completed_render()` which is called from both the webhook AND the poller. A scheduled job would miss the event timing.
- **Not using `update.effective_chat.send_message()` for the follow-up:** `update.message` is None in callback query handlers. Use `update.effective_chat.send_message()` instead — this is the PTB-correct API for sending new messages from within a callback.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Inline keyboard with two side-by-side buttons | Custom markup builder | `InlineKeyboardMarkup([[btn1, btn2]])` | Inner list = same row; PTB handles serialization |
| State machine for multi-step rejection | Custom state in memory or bot_data | Prefix-encoded callback_data + DB idempotency check | Works across restarts; proven in mood_flow.py |
| Thumbnail file creation | Temp file + disk I/O | `ffmpeg pipe:1` + `BytesIO` | No temp files; all in-memory; consistent with audio_processing.py |
| Scheduling immediate retry | Custom threading or asyncio.create_task | APScheduler `DateTrigger` one-shot job | Already infrastructure; `_scheduler` already accessible |
| Rejection constraint expiry logic | Cron-based cleanup | `expires_at` column with `now()` comparison | Already in place from migration 0002; script_gen already reads it |

**Key insight:** The entire approval flow can be built as a thin layer over existing infrastructure. No new scheduling infrastructure, no new DB clients, no new async patterns — all of these exist in the codebase.

---

## Common Pitfalls

### Pitfall 1: Double-Processing on Idempotency Failure
**What goes wrong:** Creator taps Approve twice (accidental double-tap), or the bot processes the same callback_query twice after restart.
**Why it happens:** Telegram may re-deliver callback queries if the bot does not answer within the timeout window.
**How to avoid:** The first action in `handle_approve` and `handle_cause` must be a DB read to check if an `approval_events` row already exists for that `content_history_id`. If it does, send "Ya procesado." and return.
**Warning signs:** Duplicate rows in `approval_events`, two re-run jobs scheduled.

### Pitfall 2: callback_data Byte Limit (64 bytes)
**What goes wrong:** `callback_data` exceeds Telegram's 64-byte UTF-8 limit — PTB silently truncates or raises.
**Why it happens:** UUID (36 chars) + prefix (12 chars) + cause_code (16 chars) = 64 chars — borderline.
**How to avoid:** Keep prefixes short. `appr_approve:` (13) + UUID (36) = 49 bytes — OK. `appr_cause:` (11) + UUID (36) + `:` (1) + `technical_error` (15) = 63 bytes — borderline OK but verify. Do not add more data to callback_data.
**Warning signs:** Handlers not firing; PTB warning about invalid callback data.

### Pitfall 3: Thumbnail Download Latency Blocking Event Loop
**What goes wrong:** `extract_thumbnail()` calls `requests.get()` (blocking) from inside an async handler or the FastAPI main event loop.
**Why it happens:** The approval message is sent from `_process_completed_render()` which runs in a ThreadPoolExecutor — that is correct (blocking calls are fine in thread pools). The thumbnail download inside `send_approval_message_sync()` runs in the thread pool context.
**How to avoid:** `send_approval_message_sync()` must be called from the thread pool context (not directly from the PTB async handler). The delivery runs in the same executor as `_process_completed_render()`. Do NOT call thumbnail download inside the async callback handlers.
**Warning signs:** FastAPI event loop blocking; Uvicorn timeout warnings.

### Pitfall 4: Rejection Constraint Not Clearing After Approval
**What goes wrong:** Creator approves a video but the rejection constraint for that category remains active, causing future scripts to keep avoiding the rejected topic class.
**Why it happens:** Phase 4 writes the constraint but must also clear it on approval.
**How to avoid:** In `handle_approve`, after recording the approval event, call `ApprovalService.clear_constraints_for_approved_run(content_history_id)`. This deletes or expires rejection_constraints rows for the cause categories that were active.
**Warning signs:** Indefinitely constrained script generation even after multiple approvals.

### Pitfall 5: Daily Retry Limit Not Accounting for Cross-Restart Counts
**What goes wrong:** Bot restarts reset in-memory retry counter. Bot allows more than 2 rejections on the same day.
**Why it happens:** Retry count stored in memory, not DB.
**How to avoid:** Always read the daily rejection count from `approval_events` table with a `created_at >= CURRENT_DATE` filter. Never use a module-level counter.
**Warning signs:** More than 3 approval messages sent on the same day.

### Pitfall 6: Photo Message vs Plain Text Message for Delivery
**What goes wrong:** The thumbnail frame is not extracted (e.g., ffmpeg fails) so no photo can be sent. Bot silently fails.
**Why it happens:** Transient ffmpeg or download error.
**How to avoid:** Wrap `extract_thumbnail()` in a try/except. If thumbnail fails, fall back to `bot.send_message()` with the video URL embedded directly in the text + the approval buttons. Creator still gets the message.
**Warning signs:** No approval message received by creator; error in logs.

---

## Code Examples

### Registering Handlers in telegram/app.py
```python
# Source: src/app/telegram/app.py — follows existing register_mood_handlers() call pattern
from app.telegram.handlers.approval_flow import register_approval_handlers

def build_telegram_app() -> Application:
    settings = get_settings()
    app = ApplicationBuilder().token(settings.telegram_bot_token).build()
    register_mood_handlers(app)
    register_approval_handlers(app)  # Phase 4: approval callbacks
    return app
```

### Post Copy Generation (Claude Haiku, Spanish)
```python
# Source: services/script_generation.py — follows _call_claude() pattern exactly
# In services/post_copy.py

class PostCopyService:
    """
    Generates Spanish social media post copy for a video.
    Uses the same synchronous Anthropic client pattern as ScriptGenerationService.
    Runs in APScheduler ThreadPoolExecutor — no event loop.
    """

    def __init__(self) -> None:
        settings = get_settings()
        self._client = Anthropic(api_key=settings.anthropic_api_key)
        self._model = settings.claude_generation_model  # claude-haiku-3-5-20241022 by default

    def generate(self, script_text: str, topic_summary: str) -> str:
        """
        Generate Hook + 2-3 body lines + hashtags in Spanish.
        Returns post copy string. Caller stores to content_history.post_copy.
        """
        system = (
            "Eres un redactor de contenido para redes sociales en espanol neutro. "
            "Tu tarea es generar el texto de publicacion para acompanar un video filosofico.\n\n"
            "FORMATO OBLIGATORIO:\n"
            "1. Hook (1 linea impactante que detenga el scroll)\n"
            "2. Cuerpo (2-3 lineas que expandan la idea)\n"
            "3. Hashtags (5-8 hashtags relevantes en espanol)\n\n"
            "REGLAS:\n"
            "- Espanol neutro, tono reflexivo\n"
            "- Sin emojis en el hook ni cuerpo (los hashtags pueden incluirlos si aportan)\n"
            "- Sin 'sigueme' ni llamadas a la accion de seguimiento\n"
            "- Maximo 200 palabras total\n"
            "Devuelve UNICAMENTE el texto de publicacion, sin explicaciones."
        )
        user = (
            f"Guion del video:\n{script_text}\n\n"
            f"Tema: {topic_summary}\n\n"
            "Genera el texto de publicacion."
        )
        message = self._client.messages.create(
            model=self._model,
            max_tokens=300,
            system=system,
            messages=[{"role": "user", "content": user}],
            temperature=0.7,
        )
        return message.content[0].text.strip()
```

### ApprovalService (DB Reads/Writes)
```python
# Source: services/approval.py — follows CircuitBreakerService and MoodService patterns
from app.services.database import get_supabase

class ApprovalService:
    """
    Reads and writes approval state from the approval_events table.
    All methods are synchronous — used from APScheduler threads and callback handlers
    (via asyncio.run_coroutine_threadsafe bridge).
    """

    def __init__(self, supabase=None) -> None:
        self._supabase = supabase or get_supabase()

    def is_already_actioned(self, content_history_id: str) -> bool:
        """True if an approval_events row already exists for this content."""
        result = self._supabase.table("approval_events").select("id").eq(
            "content_history_id", content_history_id
        ).limit(1).execute()
        return bool(result.data)

    def record_approve(self, content_history_id: str) -> None:
        self._supabase.table("approval_events").insert({
            "content_history_id": content_history_id,
            "action": "approved",
        }).execute()

    def record_reject(self, content_history_id: str, cause_code: str) -> None:
        self._supabase.table("approval_events").insert({
            "content_history_id": content_history_id,
            "action": "rejected",
            "cause_code": cause_code,
        }).execute()

    def get_today_rejection_count(self) -> int:
        result = self._supabase.table("approval_events").select(
            "id", count="exact"
        ).eq("action", "rejected").gte(
            "created_at", date.today().isoformat()
        ).lt(
            "created_at", (date.today() + timedelta(days=1)).isoformat()
        ).execute()
        return result.count or 0

    def write_rejection_constraint(self, cause_code: str) -> None:
        """
        Write a rejection constraint to rejection_constraints table.
        expires_at = 365 days (constraint persists until cleared by approval).
        pattern_type mapping:
          script_error     → 'script_class'
          visual_error     → 'topic'
          technical_error  → 'topic'
          off_topic        → 'topic'
        """
        from datetime import datetime, timedelta, timezone
        pattern_type = "script_class" if cause_code == "script_error" else "topic"
        expires_at = (datetime.now(tz=timezone.utc) + timedelta(days=365)).isoformat()
        self._supabase.table("rejection_constraints").insert({
            "reason_text": f"Rejected ({cause_code}) — avoid this pattern",
            "pattern_type": pattern_type,
            "expires_at": expires_at,
        }).execute()

    def clear_constraints_for_approved_run(self, content_history_id: str) -> None:
        """
        On approval: delete active constraints whose cause categories
        match any rejections that preceded this approval.
        Strategy: delete ALL rejection_constraints created in the last 7 days
        that correspond to rejections for today's content.
        """
        # Read what cause codes were rejected for today
        result = self._supabase.table("approval_events").select("cause_code").eq(
            "action", "rejected"
        ).gte("created_at", date.today().isoformat()).execute()
        cause_codes = [row["cause_code"] for row in (result.data or []) if row.get("cause_code")]
        if not cause_codes:
            return
        # Expire those constraints by setting expires_at = now
        from datetime import datetime, timezone
        now_iso = datetime.now(tz=timezone.utc).isoformat()
        self._supabase.table("rejection_constraints").update({
            "expires_at": now_iso
        }).in_("pattern_type", list(set(
            "script_class" if c == "script_error" else "topic" for c in cause_codes
        ))).execute()
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `updater(None)` for outbound-only | `ApplicationBuilder().token().build()` with polling | Phase 1→2 | Polling required for inbound callbacks |
| ConversationHandler for multi-step | CallbackQueryHandler + prefix | Phase 2 decision | Works for bot-initiated flows |
| Video URL sent as Telegram file | Video URL in caption text; thumbnail as photo | Phase 4 decision | Avoids 100-500MB uploads to Telegram |
| context.bot_data for state | Database (approval_events) | Phase 4 decision | Restart-safe |

**Deprecated/outdated:**
- `updater(None)` pattern (Phase 1): replaced by full Application with polling in Phase 2. Do not regress.
- In-memory retry counter: Phase 3 used `pending_render_retry` as a DB sentinel. Phase 4 follows the same pattern for rejection count (read from DB, not memory).

---

## Open Questions

1. **How to retrieve content_history_id inside _process_completed_render()**
   - What we know: `_process_completed_render(video_id, heygen_signed_url)` receives `heygen_job_id` as `video_id`; the content_history row is already queried to get the row for the conditional UPDATE.
   - What's unclear: The current implementation does not capture and return the row `id` after the conditional UPDATE — the id is needed to put in callback_data.
   - Recommendation: Modify the conditional UPDATE to use `.select("id")` chained on the `.update()` call (Supabase PostgREST supports returning the updated rows), or do a `.select("id")` on `heygen_job_id` after the update. Either approach is clean.

2. **How to surface mood profile name in the approval message caption**
   - What we know: `content_history` does not have a `mood_profile` column. The mood profile is stored in `mood_profiles` table by week_start date.
   - What's unclear: The natural join key is week_start = content_history.created_at::date truncated to Monday.
   - Recommendation: Query `mood_profiles` by week_start = date_trunc('week', content_history.created_at). Or add a `mood_profile_id` FK column to content_history in migration 0004.

3. **callback_data 64-byte limit for cause codes**
   - What we know: `appr_cause:` (11) + UUID (36) + `:` (1) + `technical_error` (15) = 63 bytes. Just under limit.
   - What's unclear: Whether PTB enforces this at creation time or Telegram rejects at delivery time.
   - Recommendation: Test with `technical_error` (longest code). If it fails, shorten cause codes to single chars (s/v/t/o) and translate in the handler.

---

## Sources

### Primary (HIGH confidence)
- `src/app/telegram/handlers/mood_flow.py` — Direct codebase evidence of CallbackQueryHandler + prefix + `query.answer()` pattern
- `src/app/telegram/app.py` — `build_telegram_app()` and `register_mood_handlers()` extension point
- `src/app/services/telegram.py` — `send_alert_sync()` asyncio.run_coroutine_threadsafe pattern for thread bridge
- `src/app/services/heygen.py` — `_process_completed_render()` delivery trigger point; existing executor pattern
- `src/app/services/audio_processing.py` — ffmpeg subprocess pattern with stdin/stdout pipes
- `src/app/services/script_generation.py` — synchronous Anthropic client pattern to follow for PostCopyService
- `migrations/0002_script_generation.sql` — `rejection_constraints` table schema (Phase 4 writes to this)
- `migrations/0003_video_columns.sql` — content_history additions pattern for migration 0004
- [Official PTB docs v21.8 InlineKeyboardMarkup](https://docs.python-telegram-bot.org/en/v21.8/telegram.inlinekeyboardmarkup.html) — constructor signature, side-by-side button layout verified
- [PTB GitHub Discussion #3721](https://github.com/python-telegram-bot/python-telegram-bot/discussions/3721) — `update.effective_chat.send_message()` for new message from callback handler verified

### Secondary (MEDIUM confidence)
- [Telegram Bot API sendPhoto docs](https://telegram-bot-sdk.readme.io/reference/sendphoto) — `photo` parameter accepts HTTPS URL or file_id or bytes; 10MB limit
- [Bannerbear FFmpeg article](https://www.bannerbear.com/blog/how-to-extract-images-from-a-video-using-ffmpeg/) — `ffmpeg -ss 00:00:01 -frames:v 1 pipe:1` command verified
- WebSearch cross-verification: `bot.send_photo(photo=BytesIO, caption=..., reply_markup=...)` confirmed as valid PTB 21 call

### Tertiary (LOW confidence)
- Rejection constraint clearing strategy (clear_constraints_for_approved_run): architecture recommendation, not externally documented. Requires validation during implementation.
- ~15 minute retry ETA in rejection confirmation: estimate based on audio_processing.py runtime + HeyGen render times. Actual times may differ.

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries already in pyproject.toml; no new dependencies
- Architecture: HIGH — directly derived from existing codebase patterns (mood_flow.py, send_alert_sync, audio_processing.py)
- PTB API patterns: HIGH — verified via official docs and GitHub discussions
- DB schema: HIGH — follows migration pattern already established in 0001-0003
- Pitfalls: HIGH — directly derived from Phase 2 lessons (query.answer(), effective_chat, bot_data persistence)
- Thumbnail approach: MEDIUM — ffmpeg command verified; BytesIO approach for PTB verified; actual thumbnail quality untested

**Research date:** 2026-02-22
**Valid until:** 2026-03-22 (PTB 21.x is stable; Anthropic Haiku API is stable; all patterns are internal codebase derivations)
