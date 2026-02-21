# Phase 03: Video Production - Research

**Researched:** 2026-02-20
**Domain:** HeyGen API v2, ffmpeg audio processing, Supabase Storage, APScheduler polling, FastAPI webhooks
**Confidence:** MEDIUM (HeyGen API verified against live docs; ffmpeg patterns verified against official filters docs; Supabase storage verified against official Python reference; portrait video rendering is a KNOWN ISSUE with LOW confidence on specific dimensions)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

#### HeyGen render configuration
- One fixed avatar ID — single identity, no rotation. Configured as `HEYGEN_AVATAR_ID` in settings.
- Backgrounds use HeyGen built-in scene IDs — pick a curated set of dark/cinematic scenes from their library
- Background rotation rule: no two consecutive videos use the same scene — store last used scene ID in DB, pick any different one for next render. Simple last-used tracking only.
- One fixed voice ID in settings (`HEYGEN_VOICE_ID`) — consistent brand voice, no rotation

#### Completion detection
- Pipeline job submits script to HeyGen and exits immediately — does NOT block waiting for render
- Webhook-first: register a FastAPI webhook endpoint that HeyGen calls on completion; cancels the poller when it fires
- Polling as fallback: separate APScheduler job polls HeyGen status every 60 seconds in case webhook never fires
- Timeout: 20 minutes from submission — if not complete by then, retry once (resubmit same script), then alert creator via Telegram and skip the day
- HeyGen job ID stored in `content_history.heygen_job_id` so the poller can track in-flight renders across restarts

#### Audio post-processing (ffmpeg)
- Both voice processing AND background music mixed together
- Voice: subtle low-shelf EQ boost for warmth — no compression, no reverb
- Background music: 2-4 ambient tracks stored as public files in Supabase Storage (NOT bundled in repo — keeps Docker image lightweight)
- Track rotation: picks a different track per video from the small pool (rotate or random, Claude decides)
- Music volume: ~20-30% relative to voice — audible but never competes with speech
- ffmpeg downloads the audio track from Supabase Storage URL at processing time, no disk cache needed
- ffmpeg filter chain specifics for EQ (frequency, gain, Q values) — Claude's discretion

#### Storage
- Supabase Storage — already in the stack, no new service or credentials required
- Public bucket — permanent, stable public URLs (content will be published anyway)
- File naming: `videos/YYYY-MM-DD.mp4` — human-readable, one video per day
- Schema: add three columns to existing `content_history` table (no new table):
  - `heygen_job_id` — HeyGen render job ID, used by poller and webhook to track completion
  - `video_status` — enum: `pending_render` | `rendering` | `processing` | `ready` | `failed`
  - `video_url` — stable Supabase Storage public URL, set after upload

### Claude's Discretion
- Exact HeyGen API v2 endpoint structure and request body shape (verify against live docs during research)
- ffmpeg filter chain specifics for EQ (frequency, gain, Q values)
- How to handle the case where `videos/YYYY-MM-DD.mp4` already exists (overwrite or append timestamp suffix)
- Poller job schedule timing and whether to use a one-shot job or a recurring job that self-cancels on webhook receipt

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope.
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| VIDP-01 | System submits script to HeyGen async, polls for completion, and downloads the rendered video before the signed URL expires | HeyGen v2 `POST /v2/video/generate` returns `video_id` immediately; `GET /v1/video_status.get?video_id=` polls status; `video_url` field in response is the signed download URL; APScheduler interval job polls every 60s; FastAPI POST webhook fires on `avatar_video.success` |
| VIDP-02 | HeyGen render uses dark aesthetic (high contrast, blacks/grays, 9:16 1080p) with bokeh background; system enforces no repeated background environment in consecutive videos | Background via image/video asset URL (dark cinematic backgrounds uploaded to Supabase Storage and referenced as `url`); dimension `{"width": 1080, "height": 1920}` for 9:16; last-used scene tracked in `content_history` or settings table |
| VIDP-03 | Rendered video receives audio post-processing (dark ambient EQ/atmosphere via ffmpeg) before delivery | ffmpeg `lowshelf` filter for voice warmth + `amix` filter to blend ambient music at 20-25% volume; subprocess + pipe approach for in-memory processing; music tracks fetched from Supabase Storage at runtime |
| VIDP-04 | Completed video is immediately re-hosted to Supabase Storage or S3 after HeyGen render — raw HeyGen URL is never stored as permanent reference | Supabase Storage Python client `upload()` or `update()` with upsert; `get_public_url()` returns permanent URL; `content_history.video_url` updated with stable URL, never with HeyGen signed URL |
</phase_requirements>

---

## Summary

Phase 3 involves three sequential subsystems: (1) async HeyGen render submission with webhook + polling fallback for completion detection, (2) audio post-processing with ffmpeg after the render completes and is downloaded, and (3) immediate re-hosting to Supabase Storage. The HeyGen signed URL expires and must be downloaded immediately upon render completion signal — this is the most time-critical constraint.

The HeyGen API v2 create endpoint (`POST https://api.heygen.com/v2/video/generate`) is verified against live docs. The request body structure is straightforward: a `video_inputs` array with `character`, `voice`, `background`, and optional `dimension` object at the top level. The most significant uncertainty is portrait video rendering: HeyGen API v2 supports custom `dimension` objects but user reports confirm avatar positioning issues when setting portrait dimensions. The avatar ID must be originally created in portrait orientation for clean output — this is a dependency on the creator's HeyGen account configuration, not the code.

The background configuration decision requires reconsideration: there is NO built-in `scene_id` system in HeyGen API v2. The three supported background types are `color`, `image`, and `video`. "Dark/cinematic scenes" must be implemented as image or video assets uploaded to Supabase Storage and referenced by URL in the API request body. This changes the implementation from "pick a scene ID from a library" to "maintain a list of curated background image/video URLs in config or Supabase Storage."

ffmpeg audio processing is straightforward with `subprocess` using `process.communicate(input_bytes)` for in-memory processing. The key insight is that piped MP4 output requires the `-movflags frag_keyframe+empty_moov` flag to avoid seeking back to write the moov atom header. The filter chain for voice EQ + music mix is a single `filter_complex` string.

**Primary recommendation:** HeyGen submission fires from the daily pipeline job (exits immediately after getting `video_id`); webhook fires a FastAPI POST handler that triggers immediate download + ffmpeg processing + Supabase upload; the APScheduler interval poller (60s) self-cancels on webhook receipt or on timeout; `requests` library handles synchronous download in APScheduler thread pool context.

---

## Standard Stack

### Core — New for Phase 3
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| requests | >=2.32 | Synchronous HTTP for HeyGen API calls and video download | Already in `httpx` ecosystem but `requests` is simpler for synchronous APScheduler thread jobs; video download is a blocking call that is correct in thread pool |
| ffmpeg | system binary | Audio post-processing: voice EQ + music mix | Only binary option; installed via `apt-get install -y ffmpeg` in Dockerfile |

### Already in Stack (reused, no install needed)
| Library | Version | Purpose | Phase 3 Usage |
|---------|---------|---------|--------------|
| httpx | >=0.28 | HTTP client | Already installed; can substitute for `requests` if preferred — both work in thread pool |
| supabase | >=2.0 | Supabase client | `storage.from_().upload()` for video upload; `get_public_url()` for stable URL |
| APScheduler | ==3.11.2 | Background scheduler | Polling interval job every 60s; one-shot retry job |
| fastapi | >=0.115 | Web framework | New webhook POST route for HeyGen completion callback |
| pytz | >=2024.1 | Timezone support | No change |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `subprocess` + `process.communicate()` for ffmpeg | `ffmpeg-python` library | ffmpeg-python is unmaintained (last commit 2021, known GitHub issues); subprocess is more explicit and easier to debug filter chains |
| `requests` for video download | `httpx` | Both work in thread pool; `requests` is already a known quantity in the Phase 2 codebase via other imports; choose either |
| APScheduler recurring interval job for polling | One-shot `date` trigger re-scheduled each iteration | Recurring job with self-cancel is simpler: add once with 60s interval, cancel via `job.remove()` when done |
| Supabase Storage for dark background assets | Bundled in repo | Context decision: bundling media in repo bloats Docker image; Supabase Storage keeps image lightweight |

**Installation (new system dependency only):**
```dockerfile
# Add to Dockerfile before the final COPY
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*
```

```bash
# No new Python packages — requests is available via httpx's dependencies, or add explicitly:
uv add requests
```

---

## Architecture Patterns

### Recommended Project Structure Addition
```
src/app/
├── services/
│   ├── heygen.py              # HeyGenService: submit, poll, download
│   ├── audio_processing.py    # AudioProcessingService: ffmpeg filter chain
│   └── video_storage.py       # VideoStorageService: upload to Supabase Storage
├── scheduler/
│   └── jobs/
│       └── video_poller.py    # Polling job: checks HeyGen status every 60s; self-cancels
├── routes/
│   └── webhooks.py            # FastAPI POST /webhooks/heygen — receives completion signal
└── models/
    └── video.py               # VideoStatus enum, HeyGenWebhookPayload Pydantic model
```

**Key architectural boundary:** The daily pipeline job calls `HeyGenService.submit()` and stores the returned `video_id` in `content_history.heygen_job_id` with `video_status = 'pending_render'`, then exits. The webhook handler and the poller both call the same internal `_process_completed_render(video_id)` private function that handles download + ffmpeg + upload. The webhook cancels the poller on first successful receipt.

### Pattern 1: HeyGen Submit (Async Fire-and-Forget from APScheduler Thread)
**What:** Call the HeyGen v2 generate endpoint synchronously, store the returned `video_id`, exit the pipeline job immediately.
**When to use:** End of the daily pipeline job, after script is saved to `content_history`.

```python
# Source: https://docs.heygen.com/reference/create-an-avatar-video-v2 (verified 2026-02-20)
import requests
from app.settings import get_settings

HEYGEN_GENERATE_URL = "https://api.heygen.com/v2/video/generate"

def submit_to_heygen(script_text: str, background_url: str) -> str:
    """
    Submit script to HeyGen for rendering.
    Returns video_id (heygen_job_id) for status tracking.
    Raises on HTTP error.
    """
    settings = get_settings()
    headers = {
        "x-api-key": settings.heygen_api_key,
        "Content-Type": "application/json",
    }
    payload = {
        "video_inputs": [
            {
                "character": {
                    "type": "avatar",
                    "avatar_id": settings.heygen_avatar_id,
                    "avatar_style": "normal",
                },
                "voice": {
                    "type": "text",
                    "voice_id": settings.heygen_voice_id,
                    "input_text": script_text,
                    "speed": 1.0,
                },
                "background": {
                    "type": "image",
                    "url": background_url,  # dark cinematic image from Supabase Storage
                },
            }
        ],
        "dimension": {
            "width": 1080,
            "height": 1920,
        },
        "caption": False,
        "callback_url": settings.heygen_webhook_url,  # FastAPI webhook endpoint
    }
    response = requests.post(HEYGEN_GENERATE_URL, json=payload, headers=headers, timeout=30)
    response.raise_for_status()
    data = response.json()
    return data["data"]["video_id"]
```

### Pattern 2: HeyGen Status Polling (APScheduler Interval Job, Self-Cancelling)
**What:** Every 60 seconds, check the status of the in-flight render. Self-cancel when webhook fires or timeout reached.
**When to use:** Registered in `register_jobs()` after a script is submitted to HeyGen.

```python
# Source: https://docs.heygen.com/reference/video-status (verified 2026-02-20)
# Source: https://apscheduler.readthedocs.io/en/3.x/userguide.html (APScheduler 3.x date trigger)
import logging
from datetime import datetime, timedelta
import requests
from app.services.database import get_supabase
from app.services.telegram import send_alert_sync

HEYGEN_STATUS_URL = "https://api.heygen.com/v1/video_status.get"
POLL_TIMEOUT_MINUTES = 20
logger = logging.getLogger(__name__)


def video_poller_job(video_id: str, submitted_at: datetime, job_ref=None) -> None:
    """
    APScheduler interval job. Checks HeyGen status for video_id.
    Cancels itself (via job_ref.remove()) when render is complete or timed out.
    job_ref is the APScheduler Job object returned by scheduler.add_job().
    """
    settings = get_settings()
    headers = {"x-api-key": settings.heygen_api_key}
    elapsed = datetime.utcnow() - submitted_at

    # Timeout guard: 20 minutes
    if elapsed > timedelta(minutes=POLL_TIMEOUT_MINUTES):
        logger.error("HeyGen render timeout for video_id=%s. Elapsed: %s", video_id, elapsed)
        _handle_timeout(video_id)
        if job_ref:
            job_ref.remove()
        return

    try:
        response = requests.get(
            HEYGEN_STATUS_URL,
            params={"video_id": video_id},
            headers=headers,
            timeout=15,
        )
        response.raise_for_status()
        data = response.json()["data"]
        status = data.get("status")
        logger.info("HeyGen poll: video_id=%s status=%s", video_id, status)

        if status == "completed":
            video_url = data["video_url"]  # signed URL — expires, download immediately
            _process_completed_render(video_id, video_url)
            if job_ref:
                job_ref.remove()
        elif status == "failed":
            error_msg = data.get("error", "unknown error")
            logger.error("HeyGen render failed: video_id=%s error=%s", video_id, error_msg)
            _handle_render_failure(video_id, error_msg)
            if job_ref:
                job_ref.remove()
        # pending/processing/waiting: do nothing, wait for next poll

    except Exception as e:
        logger.error("Poller error for video_id=%s: %s", video_id, e)
        # Do not cancel — retry next interval


def _handle_timeout(video_id: str) -> None:
    """Update DB status to failed, send creator alert."""
    supabase = get_supabase()
    supabase.table("content_history").update(
        {"video_status": "failed"}
    ).eq("heygen_job_id", video_id).execute()
    send_alert_sync(
        f"HeyGen render timeout (20 min) para video_id={video_id}. "
        "Revisa manualmente o acepta saltarte el video de hoy."
    )
```

### Pattern 3: FastAPI Webhook Endpoint for HeyGen Completion
**What:** A POST endpoint HeyGen calls when a render is complete. Validates HMAC signature, extracts `video_id` and `url`, triggers processing, cancels the poller.
**When to use:** Registered in FastAPI app alongside the health router.

```python
# Source: https://docs.heygen.com/docs/write-your-endpoint-to-process-webhook-events (verified 2026-02-20)
# Source: https://fastapi.tiangolo.com/tutorial/body/ (Pydantic model)
import hmac
import hashlib
import logging
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
from typing import Optional

router = APIRouter()
logger = logging.getLogger(__name__)


class HeyGenWebhookEventData(BaseModel):
    video_id: str
    url: Optional[str] = None      # present on success
    msg: Optional[str] = None      # present on failure
    callback_id: Optional[str] = None


class HeyGenWebhookPayload(BaseModel):
    event_type: str                # "avatar_video.success" | "avatar_video.fail"
    event_data: HeyGenWebhookEventData


@router.post("/webhooks/heygen")
async def heygen_webhook(request: Request, payload: HeyGenWebhookPayload) -> dict:
    """
    HeyGen calls this endpoint when a video render completes.
    Validates HMAC-SHA256 signature, triggers download + processing.
    Must return 200 — HeyGen does not retry on non-200.
    """
    # Validate HMAC signature
    signature = request.headers.get("Signature", "")
    body = await request.body()
    settings = get_settings()
    expected = hmac.new(
        settings.heygen_webhook_secret.encode(),
        body,
        hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(signature, expected):
        logger.warning("HeyGen webhook: invalid signature")
        raise HTTPException(status_code=401, detail="Invalid signature")

    video_id = payload.event_data.video_id

    if payload.event_type == "avatar_video.success":
        video_url = payload.event_data.url
        logger.info("HeyGen webhook success: video_id=%s", video_id)
        # Cancel the poller — webhook fired, no need to poll anymore
        _cancel_poller(request.app, video_id)
        # Process in background thread (do not block webhook response)
        import asyncio
        loop = asyncio.get_event_loop()
        loop.run_in_executor(None, _process_completed_render, video_id, video_url)

    elif payload.event_type == "avatar_video.fail":
        error_msg = payload.event_data.msg or "unknown"
        logger.error("HeyGen webhook failure: video_id=%s msg=%s", video_id, error_msg)
        _handle_render_failure(video_id, error_msg)

    return {"status": "ok"}
```

**Note on HMAC:** `hmac.new()` is correct Python stdlib — `hmac.compare_digest()` is timing-safe.

### Pattern 4: ffmpeg Audio Post-Processing (Voice EQ + Music Mix)
**What:** Download video from HeyGen signed URL, download ambient music track from Supabase Storage URL, run ffmpeg filter chain, output processed MP4 bytes.
**When to use:** Called from `_process_completed_render()` immediately after HeyGen signals completion.

```python
# Source: https://ffmpeg.org/ffmpeg-filters.html (lowshelf, amix — verified 2026-02-20)
# Source: https://www.jaburjak.cz/posts/ffmpeg-pipe-mp4/ (frag_keyframe+empty_moov for piped output)
import subprocess
import logging
import requests
import tempfile
import os

logger = logging.getLogger(__name__)


def process_video_audio(
    video_url: str,
    music_url: str,
    music_volume: float = 0.25,
) -> bytes:
    """
    Downloads video and music, applies EQ + mix via ffmpeg, returns processed MP4 bytes.

    Filter chain:
    - Voice: lowshelf boost at 180Hz, +3dB, width Q=0.7 — subtle warmth, no muddiness
    - Music: volume reduced to music_volume (0.25 = 25%)
    - Mix: amix=inputs=2:duration=first (video length governs output duration)

    Returns processed MP4 bytes ready for Supabase Storage upload.
    """
    # Download video bytes from HeyGen signed URL (blocking — correct in thread pool)
    logger.info("Downloading HeyGen video from signed URL...")
    video_resp = requests.get(video_url, timeout=60)
    video_resp.raise_for_status()
    video_bytes = video_resp.content

    # Download music track from Supabase Storage URL
    logger.info("Downloading ambient music track...")
    music_resp = requests.get(music_url, timeout=30)
    music_resp.raise_for_status()
    music_bytes = music_resp.content

    # Write music to a temp file (ffmpeg cannot read two pipe inputs simultaneously)
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp_music:
        tmp_music.write(music_bytes)
        tmp_music_path = tmp_music.name

    try:
        # ffmpeg command:
        # - Input 0: video (from stdin pipe) with voice audio
        # - Input 1: music track (from temp file)
        # - Copy video stream, process audio streams with filter_complex
        # - Output: fragmented MP4 to stdout pipe
        filter_complex = (
            # Apply low-shelf EQ to voice: f=180Hz, g=+3dB, t=lowshelf, w=0.7 (Q-factor as width type 1)
            "[0:a]equalizer=f=180:g=3:t=1:w=0.7[eq_voice];"
            # Reduce music volume to 25%
            f"[1:a]volume={music_volume}[music];"
            # Mix voice+EQ with music; duration=first uses video audio length
            "[eq_voice][music]amix=inputs=2:duration=first:dropout_transition=2[mixed]"
        )
        cmd = [
            "ffmpeg",
            "-i", "pipe:0",           # Input 0: video from stdin
            "-i", tmp_music_path,      # Input 1: music from temp file
            "-filter_complex", filter_complex,
            "-map", "0:v",             # Copy video stream unchanged
            "-map", "[mixed]",         # Use processed audio
            "-c:v", "copy",            # No re-encode of video stream
            "-c:a", "aac",
            "-b:a", "128k",
            "-movflags", "frag_keyframe+empty_moov",  # REQUIRED for piped MP4 output
            "-f", "mp4",
            "pipe:1",                  # Output to stdout
        ]
        result = subprocess.run(
            cmd,
            input=video_bytes,
            capture_output=True,
            timeout=120,
        )
        if result.returncode != 0:
            logger.error("ffmpeg failed: %s", result.stderr.decode(errors="replace"))
            raise RuntimeError(f"ffmpeg exited with code {result.returncode}")

        logger.info("ffmpeg processing complete. Output size: %d bytes", len(result.stdout))
        return result.stdout

    finally:
        os.unlink(tmp_music_path)
```

**ffmpeg EQ parameters (Claude's Discretion — justified):**
- `f=180`: 180 Hz is the low-frequency warmth zone for voice; below 200Hz adds body without muddiness
- `g=3`: +3 dB is subtle — audible warmth but not boomy
- `t=1`: filter type 1 = lowshelf (not peaking equalizer)
- `w=0.7`: Q-factor of 0.7 gives a broad shelving curve appropriate for warmth (not surgical)
- Music volume: 0.25 (25%) — right in the 20-30% decision range, audible but subservient to voice

### Pattern 5: Supabase Storage Upload
**What:** Upload processed MP4 bytes to Supabase Storage public bucket, get permanent stable URL.
**When to use:** After ffmpeg processing completes.

```python
# Source: https://supabase.com/docs/reference/python/storage-from-upload (verified 2026-02-20)
from datetime import date
from app.services.database import get_supabase

VIDEO_BUCKET = "videos"  # public bucket — must exist in Supabase dashboard


def upload_video_to_storage(video_bytes: bytes, target_date: date = None) -> str:
    """
    Upload processed MP4 to Supabase Storage.
    Returns the stable public URL for the uploaded video.

    File naming: videos/YYYY-MM-DD.mp4
    If file already exists (re-run edge case): use upsert=True.

    Decision (Claude's Discretion): Use upsert=True to overwrite.
    Rationale: A re-run on the same date means the earlier render was bad.
    The new render should replace it. CDN propagation delay (~60s) is acceptable
    since the video goes through an approval step before publishing.
    """
    if target_date is None:
        target_date = date.today()

    file_path = f"videos/{target_date.isoformat()}.mp4"
    supabase = get_supabase()

    supabase.storage.from_(VIDEO_BUCKET).upload(
        path=file_path,
        file=video_bytes,
        file_options={
            "content-type": "video/mp4",
            "upsert": "true",          # overwrite if same-day re-run
            "cache-control": "31536000",  # 1 year — content is permanent once approved
        },
    )

    public_url = supabase.storage.from_(VIDEO_BUCKET).get_public_url(file_path)
    return public_url
```

### Pattern 6: Background Selection with Last-Used Tracking
**What:** Pick a dark cinematic background image URL from a configured pool, avoiding the last-used one.
**When to use:** Before calling `submit_to_heygen()` in the daily pipeline job.

```python
# Claude's Discretion — no HeyGen built-in scene_id system exists (see Open Questions #1)
import random
from app.settings import get_settings

def pick_background_url(last_used_url: str | None = None) -> str:
    """
    Selects a background image URL from the configured dark backgrounds pool.
    Enforces no consecutive repeats.

    HEYGEN_DARK_BACKGROUNDS is a comma-separated list of Supabase Storage public URLs
    for curated dark/cinematic images. Set in Railway env vars.
    Minimum 2 URLs required to enforce no-repeat rule.
    """
    settings = get_settings()
    pool = [url.strip() for url in settings.heygen_dark_backgrounds.split(",") if url.strip()]

    if not pool:
        raise ValueError("HEYGEN_DARK_BACKGROUNDS setting is empty — configure at least 2 image URLs")

    if len(pool) == 1:
        return pool[0]  # Only one option — cannot enforce no-repeat

    available = [url for url in pool if url != last_used_url]
    if not available:
        available = pool  # Fallback: all are last-used somehow

    return random.choice(available)
```

**Schema for last-used tracking:** Store last-used background URL in `content_history` as a new column `background_url`, or read the most recent row's `background_url` before submission. Simpler than a separate settings table.

### Pattern 7: Complete `_process_completed_render()` Orchestrator
**What:** Called by both webhook and poller when render is complete. Download, process, upload, update DB.

```python
def _process_completed_render(video_id: str, heygen_signed_url: str) -> None:
    """
    Shared logic for webhook handler and poller.
    1. Download video from HeyGen signed URL (expires — do this FIRST)
    2. Pick ambient music track
    3. ffmpeg EQ + mix
    4. Upload to Supabase Storage
    5. Update content_history: video_url, video_status='ready'
    """
    logger.info("Processing completed render: video_id=%s", video_id)
    supabase = get_supabase()

    try:
        # Step 1: Update status to 'processing'
        supabase.table("content_history").update(
            {"video_status": "processing"}
        ).eq("heygen_job_id", video_id).execute()

        # Step 2: Pick music track (random from pool, no last-track tracking needed for small pool)
        music_url = _pick_music_track()

        # Step 3: ffmpeg processing
        processed_bytes = process_video_audio(
            video_url=heygen_signed_url,
            music_url=music_url,
        )

        # Step 4: Upload to Supabase Storage
        stable_url = upload_video_to_storage(processed_bytes)

        # Step 5: Update DB with stable URL
        supabase.table("content_history").update({
            "video_url": stable_url,
            "video_status": "ready",
        }).eq("heygen_job_id", video_id).execute()

        logger.info("Video ready at stable URL: %s", stable_url)
        send_alert_sync(f"Video listo para revision: {stable_url}")

    except Exception as e:
        logger.error("Error processing render video_id=%s: %s", video_id, e)
        supabase.table("content_history").update(
            {"video_status": "failed"}
        ).eq("heygen_job_id", video_id).execute()
        send_alert_sync(f"Error procesando video {video_id}: {e}")
        raise
```

### Pattern 8: Music Track Rotation (Claude's Discretion)
**What:** Pick a music track from 2-4 Supabase Storage URLs.
**Decision:** Random selection (not sequential rotation). With 2-4 tracks, random provides sufficient variety without tracking state.

```python
import random

def _pick_music_track() -> str:
    """
    Randomly selects an ambient music track URL from settings.
    HEYGEN_AMBIENT_MUSIC_URLS: comma-separated Supabase Storage public URLs.
    """
    settings = get_settings()
    tracks = [url.strip() for url in settings.heygen_ambient_music_urls.split(",") if url.strip()]
    if not tracks:
        raise ValueError("HEYGEN_AMBIENT_MUSIC_URLS is empty — upload music tracks to Supabase Storage")
    return random.choice(tracks)
```

### Anti-Patterns to Avoid
- **Storing the HeyGen signed URL in `content_history.video_url`:** The signed URL expires in ~7 days. Always download and re-host before updating `video_url`. The field must only ever contain the stable Supabase Storage URL.
- **Blocking the daily pipeline job waiting for HeyGen render:** Renders take 2-10 minutes. The pipeline job MUST exit after `submit_to_heygen()` returns a `video_id`. Waiting blocks the APScheduler thread pool.
- **Piping MP4 output from ffmpeg without `frag_keyframe+empty_moov`:** Standard MP4 requires seeking backwards to write the `moov` atom header at the end — impossible when writing to `pipe:1`. Without this flag, ffmpeg exits with an error or produces a corrupt file.
- **Using two stdin pipes in a single ffmpeg subprocess call:** ffmpeg cannot read two pipe:0 inputs. The music track must be written to a temp file or the video must be written to a temp file. The pattern above writes music to temp file since it is smaller.
- **Registering a new HeyGen webhook endpoint on every deploy:** The webhook endpoint registered via `POST /v1/webhook/endpoint.add` is permanent until deleted. Register once manually or via a startup check; do not re-register on every service start.
- **Not verifying the HMAC signature:** Any caller can POST to `/webhooks/heygen`. Always verify the HMAC-SHA256 signature against `settings.heygen_webhook_secret`.
- **Running `_process_completed_render()` inside the async webhook handler without offloading:** ffmpeg processing and file download are blocking. Running them in the async FastAPI handler blocks the event loop. Offload with `loop.run_in_executor(None, ...)`.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Audio EQ and mixing | Custom audio signal processing in Python | `ffmpeg` via subprocess | ffmpeg handles codec compatibility, stream copying, filter precision, and container format — impossible to replicate correctly in Python |
| Polling with self-cancel | Custom loop with `time.sleep()` | APScheduler interval job with `job.remove()` | Existing scheduler infrastructure; survives service restarts since job is re-registered from DB state |
| Signed URL expiry management | TTL tracking in DB | Immediate download on completion signal | The only correct approach — download the moment webhook fires or poller detects `completed` |
| Background image library | HeyGen "scene_id" system (DOES NOT EXIST) | Curated image URLs in Supabase Storage + settings env var | HeyGen API v2 only supports `color`, `image` (by URL or asset_id), and `video` backgrounds — no built-in scene catalog |
| HMAC verification | Custom signature parsing | Python stdlib `hmac.compare_digest()` | Timing-safe comparison — critical for webhook security |

**Key insight:** The HeyGen `video_url` expiry is the governing constraint for the whole phase. Every architectural decision (webhook-first, immediate download, no blocking pipeline job) flows from the requirement to download before expiry.

---

## Common Pitfalls

### Pitfall 1: Portrait Video Avatar Positioning (KNOWN HEYGEN LIMITATION)
**What goes wrong:** Setting `dimension: {width: 1080, height: 1920}` produces portrait video but the avatar appears centered with white/dark gaps above and below — the avatar was created in landscape mode.
**Why it happens:** HeyGen API renders the avatar at its original aspect ratio inside the requested frame. The avatar ID configured as `HEYGEN_AVATAR_ID` must be a portrait-oriented avatar (originally recorded in portrait mode).
**How to avoid:** Before writing a line of integration code, verify in the HeyGen dashboard that `HEYGEN_AVATAR_ID` is a portrait-trained avatar. If not, contact HeyGen support to re-train it. This is a pre-flight check, not a code fix.
**Warning signs:** Test renders show the avatar as a small figure in the center of a large dark background.

### Pitfall 2: HeyGen Has No Built-In Scene/Background Library
**What goes wrong:** Implementation assumes a `scene_id` or `background_type: "scene"` parameter exists — it does not. The API only accepts `color`, `image`, and `video` types.
**Why it happens:** Context.md says "HeyGen built-in scene IDs — pick a curated set of dark/cinematic scenes from their library." This is inaccurate — HeyGen's scene library exists in the visual editor but is NOT exposed via API.
**How to avoid:** Treat dark cinematic backgrounds as custom image assets. Upload 2-5 dark bokeh/cinematic images to Supabase Storage and store their public URLs in a `HEYGEN_DARK_BACKGROUNDS` env var (comma-separated). Reference these URLs in the API call's `background.url` field.
**Warning signs:** API returns 400/422 error on unrecognized background type parameter.

### Pitfall 3: ffmpeg Piped MP4 Output Corrupt Without `frag_keyframe+empty_moov`
**What goes wrong:** ffmpeg process exits with error `mp4 muxer does not support non seekable output` or produces a file that cannot be played.
**Why it happens:** Standard MP4 format requires writing the `moov` atom at the END of the file, then seeking back to the beginning to write the file header. Pipe output is not seekable.
**How to avoid:** Always add `-movflags frag_keyframe+empty_moov` to the ffmpeg command when output goes to `pipe:1`. This produces a fragmented MP4 that writes metadata per-fragment and does not require backward seeks.
**Warning signs:** `subprocess.run()` returns non-zero exit code; stderr contains "moov atom not found" or "not seekable".

### Pitfall 4: HeyGen Webhook OPTIONS Validation Requirement
**What goes wrong:** Webhook registration (`POST /v1/webhook/endpoint.add`) fails validation — HeyGen sends an OPTIONS request to the endpoint URL with a 1-second timeout to verify it exists.
**Why it happens:** HeyGen verifies the endpoint before accepting the registration. If the FastAPI service is not running or does not handle OPTIONS requests, registration fails.
**How to avoid:** FastAPI handles OPTIONS automatically via CORS middleware. Ensure `CORSMiddleware` is installed or FastAPI's default OPTIONS handling is not disabled. Register the webhook endpoint AFTER the service is deployed and running, not before.
**Warning signs:** `POST /v1/webhook/endpoint.add` returns error; HeyGen logs show failed OPTIONS request.

### Pitfall 5: Double-Processing on Webhook + Poller Race
**What goes wrong:** The webhook fires and triggers `_process_completed_render()`. Simultaneously, the 60s interval job polls and sees `completed`, also calling `_process_completed_render()`. The video is processed twice, the second upload overwrites the first (benign but wasteful), and the DB update races.
**Why it happens:** The webhook cancels the poller with `job_ref.remove()`, but the poller may already be mid-execution when the webhook fires.
**How to avoid:** Add a `video_status` guard at the start of `_process_completed_render()`: if `video_status` is already `processing` or `ready`, return early. Check and update in a single Supabase update with a `.eq("video_status", "pending_render")` filter — only proceed if the update matched one row.
**Warning signs:** Duplicate Telegram alerts; ffmpeg runs twice per video in logs.

### Pitfall 6: ffmpeg Temp File Leak on Exception
**What goes wrong:** If `process_video_audio()` raises an exception between writing the temp file and the `os.unlink()` call, the temp file accumulates indefinitely.
**Why it happens:** Exception interrupts the `try/finally` block only if the `finally` itself is not reached — but in the pattern above, `finally` is always reached, so the real risk is if the `with tempfile.NamedTemporaryFile(delete=False)` pattern is used without `try/finally`.
**How to avoid:** Always wrap temp file usage in `try/finally: os.unlink(tmp_music_path)` as shown in the code pattern above. Alternatively, use `delete=True` (automatic deletion on close) and pass the path to ffmpeg before the context manager exits — but this only works if ffmpeg can read before the file is unlinked.
**Warning signs:** `/tmp` directory grows unboundedly over time.

### Pitfall 7: `requests.get()` Timeout on Large Video Files
**What goes wrong:** HeyGen renders can produce 200-500 MB video files for 60-90 second scripts. Default `requests.get()` without `stream=True` loads the entire file into memory, and without a timeout, it can hang indefinitely.
**How to avoid:** Use `requests.get(url, timeout=120)` for video download (2-minute timeout for large files). For very large videos, consider streaming with `stream=True` and `iter_content()`, but since we pass bytes to `subprocess.run(input=video_bytes, ...)`, we need the full bytes in memory anyway — keep `stream=False` but set a generous timeout.
**Warning signs:** APScheduler thread pool is exhausted; poller jobs time out waiting for download to complete.

### Pitfall 8: Supabase Storage Bucket Must Be Public
**What goes wrong:** `get_public_url()` returns a URL that returns 400 or redirects to an auth error because the bucket is private.
**Why it happens:** Supabase buckets are private by default. The URL structure is different for public vs private buckets.
**How to avoid:** Create the `videos` bucket with Public enabled in the Supabase dashboard. Public bucket URLs follow the pattern `https://<project>.supabase.co/storage/v1/object/public/videos/YYYY-MM-DD.mp4` — no auth required. This is appropriate since videos are eventually published publicly anyway.
**Warning signs:** `get_public_url()` returns a URL that 401s or 403s when accessed.

---

## Code Examples

Verified patterns from official sources:

### HeyGen Status Poll Response (Verified)
```python
# Source: https://docs.heygen.com/reference/video-status (2026-02-20)
# GET https://api.heygen.com/v1/video_status.get?video_id=<id>
# Response status values: "pending" | "processing" | "waiting" | "completed" | "failed"
{
    "data": {
        "status": "completed",
        "video_url": "https://files.heygen.com/....mp4?Expires=...",  # signed, expires ~7 days
        "video_url_caption": "...",
        "thumbnail_url": "...",
        "duration": 62.5,
        "gif_url": "...",
        "error": null,
    }
}
```

### HeyGen Webhook Payload (Verified)
```python
# Source: https://docs.heygen.com/docs/using-heygens-webhook-events (2026-02-20)
# avatar_video.success:
{
    "event_type": "avatar_video.success",
    "event_data": {
        "video_id": "<video_id>",
        "url": "<video_url>",           # signed URL — download immediately
        "gif_download_url": "<gif>",
        "video_share_page_url": "<share>",
        "folder_id": "<folder>",
        "callback_id": "<callback_id>",
    }
}

# avatar_video.fail:
{
    "event_type": "avatar_video.fail",
    "event_data": {
        "video_id": "<video_id>",
        "msg": "<failure message>",
        "callback_id": "<callback_id>",
    }
}
```

### Supabase Storage Upload and Public URL (Verified)
```python
# Source: https://supabase.com/docs/reference/python/storage-from-upload (2026-02-20)
response = supabase.storage.from_("videos").upload(
    path="videos/2026-02-20.mp4",
    file=processed_bytes,          # bytes
    file_options={
        "content-type": "video/mp4",
        "upsert": "true",
    },
)

url = supabase.storage.from_("videos").get_public_url("videos/2026-02-20.mp4")
# Returns: "https://<project>.supabase.co/storage/v1/object/public/videos/videos/2026-02-20.mp4"
```

### APScheduler Interval Job with Self-Cancel
```python
# Source: https://apscheduler.readthedocs.io/en/3.x/userguide.html (3.11.2)
# Registering the poller after HeyGen submission:
from datetime import datetime
from apscheduler.triggers.interval import IntervalTrigger

def register_video_poller(scheduler, video_id: str) -> None:
    """Register a 60s interval poll job for this video_id. Job cancels itself when done."""
    submitted_at = datetime.utcnow()

    # APScheduler returns the Job object — pass it into the job via closure or partial
    # Using a closure: job_ref is set after add_job() via a container trick
    job_container = {}

    def _poll():
        video_poller_job(video_id, submitted_at, job_ref=job_container.get("job"))

    job = scheduler.add_job(
        _poll,
        trigger=IntervalTrigger(seconds=60),
        id=f"video_poller_{video_id}",
        name=f"HeyGen poller for {video_id}",
        replace_existing=True,
    )
    job_container["job"] = job
```

### ffmpeg Filter Chain (Verified against ffmpeg docs)
```bash
# Source: https://ffmpeg.org/ffmpeg-filters.html (lowshelf, amix — 2026-02-20)
# filter_complex string breakdown:
# [0:a]equalizer=f=180:g=3:t=1:w=0.7[eq_voice]   — lowshelf EQ on voice stream
# [1:a]volume=0.25[music]                          — reduce music to 25%
# [eq_voice][music]amix=inputs=2:duration=first    — mix both audio streams

ffmpeg \
  -i pipe:0 \                                    # video input from stdin
  -i /tmp/music.mp3 \                            # music from temp file
  -filter_complex "[0:a]equalizer=f=180:g=3:t=1:w=0.7[eq_voice];[1:a]volume=0.25[music];[eq_voice][music]amix=inputs=2:duration=first:dropout_transition=2[mixed]" \
  -map 0:v \                                     # copy video stream
  -map [mixed] \                                 # use processed audio
  -c:v copy \                                    # no video re-encode
  -c:a aac -b:a 128k \                          # encode audio to AAC
  -movflags frag_keyframe+empty_moov \           # REQUIRED for pipe:1 output
  -f mp4 pipe:1                                  # output to stdout
```

### Dockerfile Addition for ffmpeg
```dockerfile
# Add to the builder stage or final stage in Dockerfile
# python:3.12-slim is Debian-based — apt-get works
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| HeyGen scene_id in API | No scene_id system — custom image/video assets by URL | HeyGen API v2 design | Background library must be maintained in Supabase Storage, not configured from a HeyGen catalog |
| Blocking polling loop in main thread | APScheduler interval job + FastAPI webhook, webhook-first | Industry standard (2022+) | Non-blocking pipeline; webhook eliminates most polling calls |
| ffmpeg-python library | subprocess with explicit filter string | ffmpeg-python last commit 2021 | ffmpeg-python is effectively abandoned; subprocess is more reliable and requires no extra dependency |
| Store provider URL as canonical reference | Re-host immediately to own storage | Platform independence (2023+) | Signed URL expiry is unpredictable; own storage URL is permanent |
| Write temp files for ffmpeg in/out | Pipe stdin/stdout with `frag_keyframe+empty_moov` | Best practice (known pattern) | No disk I/O for video data; Docker container stays stateless |

**Deprecated/outdated:**
- `ffmpeg-python` library: Not maintained since 2021 — do not add as a Python dependency
- Polling-only completion detection: Polling every 60s for 10 minutes wastes APScheduler threads — webhook-first reduces polling calls by ~90% on typical runs

---

## Open Questions

1. **CRITICAL: HeyGen background implementation — no built-in scene library**
   - What we know: HeyGen API v2 supports `color`, `image`, and `video` background types. There is no `scene_id` or built-in dark scene catalog via API. The visual editor has scenes but they are not accessible from the API.
   - What's unclear: How the Context.md decision "pick a curated set of dark/cinematic scenes from their library" should be implemented
   - Recommendation: Upload 3-5 curated dark bokeh/cinematic images to Supabase Storage. Store their public URLs in a `HEYGEN_DARK_BACKGROUNDS` Railway env var (comma-separated). The planner should document this translation in the plan and add a manual setup step: "Upload curated background images to Supabase Storage before deploying Phase 3."

2. **Portrait video avatar positioning — pre-flight dependency on avatar configuration**
   - What we know: Setting `dimension: {width: 1080, height: 1920}` creates portrait-format output but avatar positioning depends on whether the avatar was originally created in portrait mode. API returns white/dark gaps if avatar is landscape-trained.
   - What's unclear: Whether the creator's `HEYGEN_AVATAR_ID` is portrait-trained
   - Recommendation: Add a pre-flight check to the Phase 3 deployment checklist: test-render a 5-second script with portrait dimensions before enabling the full pipeline. This must be validated by the creator in their HeyGen dashboard, not in code.

3. **HeyGen `callback_url` in request body vs. registered webhook endpoint**
   - What we know: The v2 generate endpoint accepts a `callback_url` field in the request body (per-request). HeyGen also supports registering a persistent endpoint via `POST /v1/webhook/endpoint.add`.
   - What's unclear: Whether `callback_url` in the request body and the registered endpoint both fire, or only one. Whether `callback_url` requires the registered endpoint's HMAC secret for verification.
   - Recommendation: Use BOTH approaches for redundancy. Register the endpoint once (for `avatar_video.success` and `avatar_video.fail` events) AND pass `callback_url` per-request. The polling fallback covers both failure cases.

4. **HeyGen signed URL exact expiry duration**
   - What we know: The `video_url` field from status/webhook is a signed URL. Official docs say it "expires in 7 days." The URL itself contains `Expires=...` query parameter that is regenerated on each status poll.
   - What's unclear: The exact expiry — some users report 7 days, some report shorter
   - Recommendation: Treat expiry as imminent — download the video within 5 minutes of the completion signal regardless of the stated 7-day window. The code already does this correctly by downloading in `_process_completed_render()`.

5. **Poller job self-cancel pattern — job_ref passing**
   - What we know: APScheduler 3.x `add_job()` returns a `Job` object. The job can call `job.remove()` on itself. Passing the `Job` reference into the job function requires a closure or a container trick since the job does not exist at the time the function is defined.
   - What's unclear: The cleanest way to pass `job_ref` without a global or database lookup
   - Recommendation: Use the closure + container trick shown in Pattern: APScheduler Interval Job with Self-Cancel. An alternative is to call `scheduler.remove_job(job_id)` where `job_id = f"video_poller_{video_id}"` — the job ID is predictable from `video_id`, so the webhook handler can call `scheduler.remove_job()` by ID without needing a direct reference.

---

## Sources

### Primary (HIGH confidence)
- [HeyGen API v2 Create Avatar Video Reference](https://docs.heygen.com/reference/create-an-avatar-video-v2) — endpoint URL, request body schema (video_inputs, character, voice, background, dimension, callback_url), response `video_id`; verified 2026-02-20
- [HeyGen Video Status Reference](https://docs.heygen.com/reference/video-status) — `GET /v1/video_status.get`, status values (pending/processing/waiting/completed/failed), `video_url` field; verified 2026-02-20
- [HeyGen Webhook Events Documentation](https://docs.heygen.com/docs/using-heygens-webhook-events) — `avatar_video.success` and `avatar_video.fail` payload structure, HMAC signature verification requirement; verified 2026-02-20
- [HeyGen Write Webhook Endpoint Documentation](https://docs.heygen.com/docs/write-your-endpoint-to-process-webhook-events) — HMAC-SHA256 verification, 200 status requirement; verified 2026-02-20
- [HeyGen Customize Video Background](https://docs.heygen.com/docs/customize-video-background) — confirmed background types: `color`, `image`, `video` only — NO built-in scene_id system; verified 2026-02-20
- [HeyGen List Voices v2 Reference](https://docs.heygen.com/reference/list-voices-v2) — `GET /v2/voices` endpoint, voice fields including `voice_id`, `language`, `support_locale`; verified 2026-02-20
- [Supabase Storage Python upload reference](https://supabase.com/docs/reference/python/storage-from-upload) — `upload()` method signature, `upsert` option, `get_public_url()` method; verified 2026-02-20
- [Supabase Storage Python update reference](https://supabase.com/docs/reference/python/storage-from-update) — `update()` method for overwriting existing files; verified 2026-02-20
- [FFmpeg Filters Documentation](https://ffmpeg.org/ffmpeg-filters.html) — `equalizer` filter parameters (f, g, t, w), `lowshelf` type, `amix` filter (inputs, duration, dropout_transition); verified 2026-02-20
- [APScheduler 3.x User Guide](https://apscheduler.readthedocs.io/en/3.x/userguide.html) — interval trigger, `job.remove()` for self-cancel, `add_job()` returns Job object; verified 2026-02-20

### Secondary (MEDIUM confidence)
- [HeyGen portrait video discussion thread](https://docs.heygen.com/discuss/673c7deee063cb002ad2ba0e) — confirms no `fit` parameter for avatar positioning in portrait mode; avatar must be created in portrait orientation
- [ffmpeg fragmented MP4 pipe blog post](https://www.jaburjak.cz/posts/ffmpeg-pipe-mp4/) — confirms `frag_keyframe+empty_moov` requirement for piped MP4 output; corroborates official ffmpeg muxer docs
- [HeyGen portrait video rendering issue discussion](https://docs.heygen.com/discuss/67b49dc0faf6ad00317a3d28) — confirms portrait rendering requires portrait-trained avatar source files

### Tertiary (LOW confidence)
- WebSearch results on ffmpeg subprocess + Python patterns — consistent with official ffmpeg docs but multiple sources with varying quality; treat code examples as illustrative, verify against ffmpeg docs before use
- WebSearch on HeyGen Spanish TTS locale support — multiple sources confirm Spanish is supported in multiple locales including es-MX; exact `voice_id` for desired Spanish voice requires API discovery (`GET /v2/voices` filtered by language=Spanish)

---

## Metadata

**Confidence breakdown:**
- HeyGen API structure: HIGH — endpoint URL, request body, status values, webhook payload all verified against official HeyGen docs
- Background "scene" system: HIGH (NEGATIVE) — confirmed via official docs that NO built-in scene_id exists; requires custom image assets
- ffmpeg filter chain: MEDIUM — filter parameters verified against official ffmpeg docs; exact parameter values for EQ (180Hz, 3dB, Q=0.7) are Claude's discretion, not from an authoritative source for this specific use case
- Portrait video rendering: LOW — known limitation documented in HeyGen discussion threads; behavior depends on avatar source file orientation; cannot be resolved in code
- Supabase Storage patterns: HIGH — upload, upsert, and get_public_url verified against official Python reference
- APScheduler self-cancel: MEDIUM — job.remove() and Job object from add_job() confirmed in docs; closure/container trick for job_ref passing is a workaround pattern, not documented in APScheduler docs directly

**Research date:** 2026-02-20
**Valid until:** 2026-03-20 (30 days — HeyGen API is actively developed; check changelog before implementation; ffmpeg and Supabase are stable)
