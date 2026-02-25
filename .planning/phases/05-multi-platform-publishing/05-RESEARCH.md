# Phase 5: Multi-Platform Publishing - Research

**Researched:** 2026-02-25
**Domain:** Scheduled social media publishing with platform-specific optimizations and fallback handling
**Confidence:** HIGH

## Summary

Phase 5 implements scheduled publishing of approved videos to four platforms (TikTok, Instagram Reels, Facebook Reels, YouTube Shorts) via Ayrshare at configurable peak engagement hours per platform. The implementation requires: (1) timezone-aware peak hour calculation with failure graceful degradation, (2) platform-specific post copy variants generated during Phase 4 and stored persistently, (3) APScheduler-based delayed job scheduling for staggered publish times, (4) retry logic with exponential backoff for transient failures, and (5) immediate Telegram fallback on any platform failure. The system operates entirely within APScheduler's thread pool context — no async event loop — using synchronous HTTP calls via the `requests` library (matching existing Phase 1–4 patterns).

**Primary recommendation:** Use Ayrshare API with APScheduler delayed jobs (one job per video, fires 4 times at staggered peak hours), retry failures via tenacity with exponential backoff (server errors only), and fallback immediately on unreachable Ayrshare (no extended retry window).

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Peak hour scheduling:**
- Each platform publishes at its own platform-specific peak hour (not all simultaneously)
- Default peak windows (research-based, in audience timezone): TikTok 7–9pm, IG 11am–1pm, FB 1–3pm, YT 12–3pm
- Audience timezone is configurable in settings (fixed, but modifiable) — not derived from creator location
- If approval comes in after today's peak window has passed: schedule for tomorrow's peak, never publish off-hours

**Post copy per platform:**
- Platform-adapted copy — 4 variants generated (TikTok conversational + ~5 hashtags, IG aesthetic + 20-30 hashtags, FB slightly longer, YT SEO title + description)
- Variants generated during video production (before Telegram delivery) — alongside Phase 4 PostCopyService, stored in DB
- All 4 variants shown in the approval Telegram message: stacked in one message with platform labels (e.g., 🎵 TikTok:\n[copy]\n\n📷 Instagram:\n[copy] etc.)

**Telegram confirmation flow:**
- After Approve: send a separate follow-up message with per-platform scheduled times (e.g., "Scheduled: TikTok 7:00pm, IG 11:00am tomorrow, FB 1:00pm tomorrow, YT 12:00pm tomorrow (US/Eastern)")
- Original approval message (video + copy + buttons) is left unchanged — no edits to it
- After each platform successfully publishes: send one notification per platform as they fire throughout the day
- 30-minute post-publish verification: Claude's discretion on format — only surface failures by default

**Failure handling:**
- Fallback triggers on ANY platform failure, not just full Ayrshare failure
- Retry policy: 2–3 retries with exponential backoff ONLY for server-side errors (5xx / network timeouts); fail immediately for client errors (4xx, policy violations)
- If Ayrshare is completely unreachable: send fallback immediately — no extended retry window
- Telegram fallback message: Supabase Storage URL (video link, not file upload) + the failed platform's adapted copy text — creator posts manually

### Claude's Discretion

- 30-minute verification message format (show failures only vs. full report)
- Exact retry backoff intervals and max delay
- How to store the 4 copy variants in DB (new columns on content_history vs. separate table)
- Exact scheduling job architecture (one job per platform vs. one job that fires all)

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within phase scope.

</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| PUBL-01 | Approved video is published to TikTok, Instagram Reels, Facebook Reels, and YouTube Shorts via a single Ayrshare API call | Ayrshare POST /post endpoint supports all 4 platforms via `platforms` array: ["tiktok", "instagram", "facebook", "youtube"]. Single endpoint call publishes to all. |
| PUBL-02 | Publish is scheduled at peak engagement hours per platform, not immediately on approval | APScheduler delayed jobs with cron-based scheduling at user-configurable peak hours per platform. Each platform gets its own job firing at its peak time, scheduled from approval timestamp. |
| PUBL-03 | System verifies post-publish status on each platform 30 minutes after scheduled publish time | APScheduler delayed job registered 30 minutes after each publish, queries Ayrshare API or checks platform-returned post IDs, reports failures to creator via Telegram. |
| PUBL-04 | If Ayrshare publish fails, bot automatically sends the original video file and post copy to Telegram for immediate manual posting | On any platform failure, send Telegram fallback message with Supabase Storage public URL (video) + platform-specific post copy. No file upload — link-based only for message weight. |

</phase_requirements>

## Standard Stack

### Core Publishing
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Ayrshare API | (REST, no SDK) | Multi-platform social media publishing | Single endpoint publishes to 4+ platforms simultaneously. Significantly simpler than Buffer (separate per-platform connections). Supports TikTok, Instagram, Facebook, YouTube natively. |
| APScheduler | 3.10+ (BackgroundScheduler) | Delayed job scheduling for staggered peak hour publishes | Already in use for daily pipeline trigger. Thread-safe, Postgres-backed job store prevents loss on restarts. Critical: cron trigger supports timezone-aware scheduling for peak hour calculation. |
| tenacity | 8.x | Retry logic with exponential backoff for transient Ayrshare failures | Standard for external API resilience. Discriminates 5xx/timeout (retry) vs 4xx (fail fast). Integrates seamlessly with synchronous code (no async overhead). |
| requests | 2.31+ | HTTP library for Ayrshare API calls | Already used for HeyGen calls. Synchronous, fits APScheduler thread context. No httpx needed (not async context). |

### Post Copy Variants
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Anthropic | 0.25+ (sync client) | Generate 4 platform-specific copy variants | Synchronous client mirrors Phase 4 PostCopyService pattern. Thread-safe when called from APScheduler. Single prompt with platform-specific instructions for all 4 variants. |

### Timezone & Scheduling
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pytz | (via APScheduler) | Timezone-aware datetime handling for peak hour calculation | APScheduler's BackgroundScheduler already configured with pytz.timezone("America/Mexico_City"). For audience timezone: add configurable timezone setting, calculate next peak window relative to approval_time in that timezone. |
| datetime (stdlib) | 3.11+ | Datetime arithmetic for peak hour windows | Native Python. Use to calculate: is_peak_window_today(), next_peak_window(), seconds_until_peak(). |

### Supporting (Already in Use)
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| Supabase Python Client | 2.x | Persist platform copy variants + publishing state | Extend content_history table with platform-specific copy columns OR create separate table (Claude's discretion). Read/write publish job IDs and failure metadata. |
| python-telegram-bot | 21.x | Send confirmation + failure notification messages | Async handler wraps with send_approval_message_sync() pattern (Phase 4). Send scheduled times confirmation. Send per-platform success/failure after each job fires. |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Ayrshare | Buffer API | Buffer requires separate connection per platform (4 API calls instead of 1). More overhead. Less unified failure handling. Ayrshare's single endpoint is simpler. |
| APScheduler delayed jobs | Celery + Redis | Overkill for single-creator system. Redis adds infrastructure complexity. APScheduler thread pool + Postgres job store is sufficient. |
| tenacity | Manual retry loops | Custom retry logic introduces bugs (missed edge cases, inconsistent backoff). tenacity is battle-tested, declarative, integrates with logging. |
| requests | httpx | httpx is async-first. APScheduler runs in thread pool (no event loop). requests is synchronous, simpler, matches existing code. |

**Installation:**
```bash
# Already installed: requests, apscheduler, anthropic, tenacity, python-telegram-bot
# Verify versions match:
pip show requests apscheduler tenacity anthropic pytz
```

---

## Architecture Patterns

### Recommended Project Structure

No new top-level directories needed. Extend existing:

```
src/app/
├── services/
│   ├── post_copy.py              # EXTEND: add generate_platform_variants()
│   ├── publishing.py              # NEW: PublishingService (Ayrshare wrapper)
│   └── telegram.py                # EXTEND: add send_publish_confirmation_sync(), send_platform_failure_sync()
├── scheduler/
│   ├── registry.py                # EXTEND: add publish job registration logic (called from approval handler)
│   └── jobs/
│       ├── platform_publish.py    # NEW: publish_to_platform_job() — fires per platform per video
│       └── publish_verify.py      # NEW: verify_publish_job() — fires 30min after each publish
├── models/
│   └── publishing.py              # NEW: PublishJob pydantic model (stores job IDs for later lookup)
└── routes/
    └── approval.py                # EXTEND: approval callback handler triggers publish job scheduling
```

### Pattern 1: Peak Hour Scheduling

**What:** Calculate next available peak hour for each platform in audience timezone, schedule 4 separate APScheduler jobs (one per platform) to fire at those times.

**When to use:** Upon approval — immediately after creator approves video.

**Example:**
```python
# Source: APScheduler documentation + datetime timezone handling
from datetime import datetime, timedelta
import pytz
from apscheduler.schedulers.background import BackgroundScheduler

def calculate_next_peak_hour(approval_time: datetime, platform: str, audience_tz: str) -> datetime:
    """
    Calculate next peak hour window for a platform.

    Peak windows (audience_tz):
      TikTok: 19:00-21:00
      Instagram: 11:00-13:00
      Facebook: 13:00-15:00
      YouTube: 12:00-15:00

    If approval is during today's peak window: schedule for that peak.
    If after today's peak: schedule for tomorrow's peak.
    If before today's peak: schedule for today's peak.
    """
    tz = pytz.timezone(audience_tz)
    approval_local = approval_time.astimezone(tz)

    peak_windows = {
        "tiktok": (19, 21),      # 7-9 PM
        "instagram": (11, 13),   # 11 AM-1 PM
        "facebook": (13, 15),    # 1-3 PM
        "youtube": (12, 15),     # 12-3 PM
    }

    peak_start, peak_end = peak_windows[platform]

    # Check if current time is within today's peak window
    today_peak_start = approval_local.replace(hour=peak_start, minute=0, second=0, microsecond=0)
    today_peak_end = approval_local.replace(hour=peak_end, minute=0, second=0, microsecond=0)

    if approval_local < today_peak_start:
        # Still before today's peak — schedule for today
        return today_peak_start
    elif approval_local < today_peak_end:
        # Within today's peak window — publish at peak start
        return today_peak_start
    else:
        # After today's peak — schedule for tomorrow's peak
        tomorrow_peak_start = (today_peak_start + timedelta(days=1))
        return tomorrow_peak_start

def schedule_platform_publishes(
    content_history_id: str,
    video_url: str,
    approval_time: datetime,
    scheduler: BackgroundScheduler,
    audience_tz: str = "US/Eastern",  # from settings
) -> dict[str, str]:
    """
    Register 4 delayed publish jobs (one per platform) at their respective peak hours.

    Returns:
        dict mapping platform -> APScheduler job ID (for later lookup/cancellation)
    """
    from app.scheduler.jobs.platform_publish import publish_to_platform_job

    job_ids = {}
    platforms = ["tiktok", "instagram", "facebook", "youtube"]

    for platform in platforms:
        peak_time = calculate_next_peak_hour(approval_time, platform, audience_tz)

        job_id = f"publish_{content_history_id}_{platform}"
        scheduler.add_job(
            publish_to_platform_job,
            trigger="date",
            run_date=peak_time,
            args=[content_history_id, platform, video_url],
            id=job_id,
            replace_existing=True,
            name=f"Publish {platform} for {content_history_id[:8]}",
        )
        job_ids[platform] = job_id

    return job_ids
```

### Pattern 2: Ayrshare API Call with Retry Logic

**What:** Wrap Ayrshare POST /post endpoint with tenacity retry decorator. Discriminate 5xx/timeout (retry) vs 4xx (fail fast).

**When to use:** Every platform publish attempt, after scheduling calculates the time to fire.

**Example:**
```python
# Source: Ayrshare docs https://www.ayrshare.com/docs/apis/post/post.md
# + tenacity https://tenacity.readthedocs.io/

from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    retry_if_result,
)
import requests
from requests.exceptions import ConnectTimeout, ReadTimeout, ConnectionError

def is_retryable_error(exception: Exception) -> bool:
    """Retry only on server errors (5xx) and network timeouts."""
    if isinstance(exception, (ConnectTimeout, ReadTimeout, ConnectionError)):
        return True
    if isinstance(exception, requests.HTTPError):
        # Retry 5xx; fail fast on 4xx
        return exception.response.status_code >= 500
    return False

@retry(
    retry=retry_if_exception_type(requests.RequestException),
    stop=stop_after_attempt(3),  # 1 original + 2 retries
    wait=wait_exponential(multiplier=1, min=2, max=30),  # 2s, 4s, 8s...
    reraise=True,  # Re-raise on final failure
)
def publish_to_ayrshare(
    post_text: str,
    video_url: str,
    platforms: list[str],
    schedule_date: str,  # ISO 8601 UTC: "2025-02-26T19:00:00Z"
    api_key: str,
) -> dict:
    """
    POST to Ayrshare /post endpoint.

    Returns:
        Response JSON with postIds (platform-specific post URLs).

    Raises:
        requests.HTTPError: On 4xx (fail fast, no retry).
        requests.RequestException: On 5xx/timeout (retry via decorator).
    """
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "post": post_text,
        "platforms": platforms,
        "mediaUrls": [video_url],
        "isVideo": True,
        "scheduleDate": schedule_date,
    }

    response = requests.post(
        "https://app.ayrshare.com/api/post",
        json=payload,
        headers=headers,
        timeout=30,  # 30s timeout triggers retry
    )
    response.raise_for_status()  # Raises HTTPError on 4xx/5xx
    return response.json()
```

### Pattern 3: Telegram Fallback on Failure

**What:** On any platform publish failure, immediately send Telegram message with Supabase Storage URL + platform-specific copy text.

**When to use:** When publish_to_ayrshare() raises an exception that exhausts retries.

**Example:**
```python
# Source: existing send_alert_sync() pattern in telegram.py

def send_publish_failure_sync(
    platform: str,
    content_history_id: str,
    video_url: str,
    post_copy: str,
    error_message: str,
) -> None:
    """
    Sync wrapper for APScheduler thread pool context.
    Send fallback message with manual posting instructions.
    """
    message = (
        f"❌ PUBLISH FAILED: {platform.upper()}\n\n"
        f"Video: {video_url}\n"
        f"Copy:\n{post_copy}\n\n"
        f"Error: {error_message}\n\n"
        f"Please post manually to {platform}."
    )
    send_alert_sync(message)
```

### Pattern 4: 30-Minute Post-Publish Verification

**What:** 30 minutes after each platform publishes, query Ayrshare or platform APIs to verify publish success. On failure, surface only the failure in Telegram (not full report).

**When to use:** After each of the 4 publish jobs fires successfully.

**Example:**
```python
# Source: APScheduler delayed job pattern + requests

def verify_publish_job(
    content_history_id: str,
    platform: str,
    ayrshare_post_id: str,
    api_key: str,
) -> None:
    """
    Fired 30 minutes after publish. Check platform post status.
    On failure: send Telegram alert only (not full report per user decision).
    """
    headers = {"Authorization": f"Bearer {api_key}"}

    # Query Ayrshare analytics or post status
    response = requests.get(
        f"https://app.ayrshare.com/api/post/{ayrshare_post_id}",
        headers=headers,
        timeout=10,
    )

    if response.status_code == 200:
        post_data = response.json()
        # Check platform-specific post status
        if post_data.get("status") == "completed":
            logger.info(f"Verification passed: {platform} {ayrshare_post_id}")
        else:
            send_alert_sync(f"❌ {platform.upper()} publish verification failed: {post_data.get('status')}")
    else:
        send_alert_sync(f"❌ {platform.upper()} verification API call failed: {response.status_code}")
```

### Anti-Patterns to Avoid

- **Publishing all 4 platforms simultaneously:** Defeats peak hour strategy. WRONG. Schedule each platform independently at its peak. CORRECT.
- **Storing copy variants in separate table:** Adds join complexity. WRONG. Either extend content_history with 4 columns (copy_tiktok, copy_instagram, copy_facebook, copy_youtube) or separate narrow table (content_id + platform + copy). CORRECT.
- **Retrying on 4xx errors:** 4xx = permanent client error (auth, bad request, rate limit hard cap). Won't succeed. WRONG. Retry only 5xx and timeouts. CORRECT.
- **Extended retry window for Ayrshare unreachable:** If Ayrshare is down, 3 retries × exponential backoff = ~30 seconds delay before fallback. User is waiting. WRONG. Fall back immediately (first failure triggers fallback). CORRECT.
- **Uploading video file to Telegram in fallback:** 100MB+ file upload on every failure is heavy. WRONG. Use Supabase Storage public URL (link-based). CORRECT.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Retry logic with exponential backoff | Custom loop with manual sleep() calls | tenacity @retry decorator | Avoids off-by-one errors (original + N retries), jitter, condition evaluation bugs. Tenacity handles edge cases (max delay caps, mixed retry conditions). |
| Timezone-aware peak hour calculation | Manual datetime comparison with UTC conversion | pytz + datetime.astimezone() | Handles DST transitions (spring forward/fall back). Manual UTC math is error-prone. APScheduler's cron trigger is timezone-aware by default — use it. |
| Scheduling multiple future jobs dynamically | Manual APScheduler loop without idempotency checks | APScheduler add_job with replace_existing=True + stable job IDs | Without replace_existing, restarts create duplicate jobs. Without stable IDs, job store queries fail. APScheduler handles this internally. |
| API response parsing + error handling | Try/except blocks with string matching | requests.Response.raise_for_status() + response.json() | raise_for_status() handles all HTTP error codes uniformly. json() raises JSONDecodeError on invalid JSON (catchable). String matching is fragile. |
| Platform-specific copy generation | Separate prompt per platform (4 Claude calls) | Single prompt with 4 structured outputs | Cost: 1 API call vs 4. Risk: prompt drift across calls. Single structured prompt ensures consistency. |

**Key insight:** Ayrshare API abstracts away the complexity of 4 platform-specific publishing mechanics — TikTok's upload format, Instagram's reel specifications, Facebook's content policies, YouTube's shorts requirements. Ayrshare normalizes all of this to a single POST /post call. Don't reimplement per-platform logic; use Ayrshare. Similarly, don't build retry logic, timezone handling, or job scheduling — use proven libraries (tenacity, pytz, APScheduler).

---

## Common Pitfalls

### Pitfall 1: Peak Hour Window Boundaries (Off-by-One)

**What goes wrong:**
- Approval at 18:59 (6:59 PM) in audience timezone. TikTok peak starts at 19:00 (7 PM). Code schedules for tomorrow because `approval_time < peak_start` check is exclusive.
- Approval at 19:00 exactly. Code schedules for tomorrow (should be today).
- Approval at 19:01. Code publishes immediately within the peak window (correct).

**Why it happens:**
- Floating-point comparison without margin. DST transitions change minute values. Timezone conversion errors.

**How to avoid:**
1. Use inclusive lower bound: `if approval_local <= today_peak_start: schedule_for_today()`
2. Convert all times to the audience timezone ONCE at the start. Don't mix UTC/local.
3. Add 1-minute buffer: if approval is at or within 1 minute of peak start, use that peak (gives 59 minutes to publish).
4. **Unit test:** approval times at peak boundaries (18:59, 19:00, 19:01, 20:59, 21:00).

**Warning signs:**
- Publish scheduled for tomorrow when creator approves 1 minute before peak.
- Publish fires immediately (off-peak) even though next peak is in 1 hour.

### Pitfall 2: Ayrshare Job ID Persistence

**What goes wrong:**
- Ayrshare publishes successfully, returns `postIds` (array of platform post URLs). Code doesn't save the Ayrshare job ID or post ID.
- 30 minutes later, verification job fires. It tries to query Ayrshare for the post — but has no ID to query. Verification fails silently.

**Why it happens:**
- Ayrshare response contains rich metadata (postIds, scheduledTime, postId) that gets logged but not persisted to DB.
- Verification job has no way to correlate which post to verify.

**How to avoid:**
1. After successful publish, save to DB: `publish_events` table (content_history_id, platform, ayrshare_post_id, published_at).
2. Verification job queries this table to find the post to verify.
3. Use the post ID in verify_publish_job() to construct the Ayrshare analytics API call.
4. **Unit test:** Publish → immediately query DB for post ID → verify job can read it.

**Warning signs:**
- Verification job succeeds (no error) but never actually checks publish status.
- No way to link back from "TikTok post ID=xyz123" to "content_history_id=abc".

### Pitfall 3: Retry Loop Exhaustion Without Fallback Fallthrough

**What goes wrong:**
- Ayrshare API is down (500 error). Retry loop exhausts after 30 seconds (3 retries × exponential backoff).
- Exception is raised, caught in publish_to_platform_job(). Code logs the error.
- But nothing triggers the fallback — no Telegram message sent.

**Why it happens:**
- publish_to_platform_job() is a background job with no exception handler. Exceptions are logged but not surfaced.
- Developer assumes "exception means someone will notice the log."

**How to avoid:**
1. Wrap publish_to_ayrshare() call in try/except in publish_to_platform_job(). On exception:
   - Log the error
   - Call send_publish_failure_sync() with the exception message
   - Persist failure state to DB (publish_events.status = 'failed')
2. Same pattern for verify_publish_job() — if verification fails, send Telegram alert.
3. **Unit test:** Mock Ayrshare to return 500 error → verify Telegram fallback is sent.

**Warning signs:**
- Creator never receives a fallback Telegram message even when publish fails.
- Logs show "Exception in publish_to_platform_job" but nothing in Telegram.

### Pitfall 4: Duplicate Scheduling on Restart

**What goes wrong:**
- Approval happens at 18:00. 4 publish jobs are registered in APScheduler job store.
- Service crashes, restarts.
- APScheduler reloads jobs from Postgres job store.
- Approval handler fires again (from retry logic or replay).
- 4 MORE jobs are registered.
- At 19:00, the platform publishes TWICE (or more).

**Why it happens:**
- No idempotency check before add_job(). add_job() is called every time handler runs.
- Job IDs are not stable (e.g., using UUID instead of deterministic ID).

**How to avoid:**
1. Use stable job IDs: `f"publish_{content_history_id}_{platform}"` — derived from the video and platform, not random.
2. Use `replace_existing=True` in add_job() — overwrites any existing job with that ID.
3. Verify: when approval handler is called twice, the second call should overwrite the first job, not create a duplicate.
4. **Unit test:** Mock scheduler, call schedule_platform_publishes() twice with same content_history_id → verify only 1 job per platform exists.

**Warning signs:**
- Platform post appears twice (or error from duplicate posting).
- APScheduler job store has multiple jobs with same intent.

### Pitfall 5: Timezone DST Transitions

**What goes wrong:**
- Peak hour is scheduled for 19:00 America/Mexico_City.
- DST transition (spring forward): 2:00 AM → 3:00 AM. Clock jumps 1 hour.
- APScheduler fires at 19:00 "wall time" — but that's now 20:00 UTC (wrong).
- Or APScheduler doesn't fire at all (the 19:00 hour doesn't exist).

**Why it happens:**
- APScheduler's cron trigger uses wall-clock time, not UTC. During DST transitions, wall times are ambiguous or nonexistent.
- pytz handles transitions correctly IF you use `.astimezone()` or APScheduler's native timezone support.
- Manual datetime math without timezone context misses the transition.

**How to avoid:**
1. Always use APScheduler's built-in timezone support: `scheduler.add_job(..., timezone=pytz.timezone("America/Mexico_City"))`.
2. For datetime calculations, use pytz: `tz.localize(naive_dt)` before comparison.
3. Use APScheduler's `coalesce=True` (already set in setup.py) — if a job is missed (e.g., DST jump), run it once, not multiple times.
4. Test with DST transition dates (e.g., 2nd Sunday in March for spring forward).

**Warning signs:**
- Publish fires at wrong hour on DST transition dates.
- Job doesn't fire at all (scheduled time doesn't exist).

---

## Code Examples

Verified patterns from official sources and existing codebase:

### Example 1: Platform-Specific Copy Generation (Single Prompt, 4 Outputs)

```python
# Source: Anthropic SDK (sync client) + Phase 4 PostCopyService pattern
# Located: src/app/services/post_copy.py (extend with new method)

from anthropic import Anthropic
import json
import re

class PostCopyService:
    """Extended with generate_platform_variants()"""

    def __init__(self) -> None:
        settings = get_settings()
        self._client = Anthropic(api_key=settings.anthropic_api_key)
        self._model = settings.claude_generation_model

    def generate_platform_variants(
        self,
        script_text: str,
        topic_summary: str
    ) -> dict[str, str]:
        """
        Generate 4 platform-specific post copy variants in a single API call.

        Returns dict: {
            "tiktok": "Conversational copy + 5 hashtags...",
            "instagram": "Aesthetic copy + 20-30 hashtags...",
            "facebook": "Slightly longer conversational...",
            "youtube": "SEO title + description format..."
        }
        """
        system = (
            "Eres un redactor de redes sociales especializado en contenido filosófico. "
            "Tu tarea es crear copy de publicación OPTIMIZADO PARA CADA PLATAFORMA.\n\n"
            "Genera EXACTAMENTE 4 variantes, una por plataforma:"
        )

        user = (
            f"Tema: {topic_summary}\n\n"
            f"Guion:\n{script_text}\n\n"
            "Genera copy para cada plataforma en este formato JSON:\n"
            "{\n"
            '  "tiktok": "Copy conversacional con ~5 hashtags. Máximo 150 caracteres.",\n'
            '  "instagram": "Copy estético con 20-30 hashtags relevantes. Máximo 2200 caracteres.",\n'
            '  "facebook": "Copy más largo y conversacional. Máximo 500 caracteres.",\n'
            '  "youtube": "Título SEO + descripción. Máximo 500 caracteres."\n'
            "}"
        )

        message = self._client.messages.create(
            model=self._model,
            max_tokens=1000,
            system=system,
            messages=[{"role": "user", "content": user}],
            temperature=0.7,
        )

        text = message.content[0].text.strip()

        # Extract JSON from response (may have markdown fence)
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            json_str = match.group()
            variants = json.loads(json_str)
            return {
                "tiktok": variants.get("tiktok", ""),
                "instagram": variants.get("instagram", ""),
                "facebook": variants.get("facebook", ""),
                "youtube": variants.get("youtube", ""),
            }

        raise ValueError(f"Failed to parse JSON from Claude response: {text}")
```

### Example 2: Schedule Platform Publishes (APScheduler Delayed Jobs)

```python
# Source: APScheduler documentation + existing scheduler pattern
# Located: src/app/scheduler/registry.py or called from approval handler

from datetime import datetime, timedelta
import pytz
import logging

logger = logging.getLogger(__name__)

def schedule_platform_publishes(
    scheduler: BackgroundScheduler,
    content_history_id: str,
    video_url: str,
    approval_time: datetime,
    audience_tz_str: str = "US/Eastern",  # from settings.audience_timezone
) -> dict[str, str]:
    """
    Register 4 delayed publish jobs (one per platform).

    Each job fires at the platform's peak hour in the audience timezone.
    If approval is within or before today's peak: use today.
    If after today's peak: use tomorrow.

    Returns: dict mapping platform -> job_id
    """
    audience_tz = pytz.timezone(audience_tz_str)
    approval_local = approval_time.astimezone(audience_tz)

    peak_windows = {
        "tiktok": (19, 21),      # 7-9 PM
        "instagram": (11, 13),   # 11 AM-1 PM
        "facebook": (13, 15),    # 1-3 PM
        "youtube": (12, 15),     # 12-3 PM
    }

    job_ids = {}

    for platform, (peak_hour, peak_end_hour) in peak_windows.items():
        # Construct today's peak start in audience timezone
        today_peak_start = approval_local.replace(
            hour=peak_hour, minute=0, second=0, microsecond=0
        )

        # Decide: today or tomorrow?
        if approval_local <= today_peak_start:
            # Before or at peak start → use today
            run_at = today_peak_start
        else:
            # After peak start → use tomorrow
            run_at = today_peak_start + timedelta(days=1)

        # Stable job ID for idempotency
        job_id = f"publish_{content_history_id}_{platform}"

        # Register delayed job
        scheduler.add_job(
            publish_to_platform_job,
            trigger="date",
            run_date=run_at,
            args=[content_history_id, platform, video_url],
            id=job_id,
            replace_existing=True,  # Idempotent
            name=f"Publish {platform} for {content_history_id[:8]}",
            timezone=audience_tz_str,
        )

        job_ids[platform] = job_id
        logger.info(
            f"Scheduled {platform} publish for {content_history_id[:8]} at {run_at.isoformat()}"
        )

    return job_ids
```

### Example 3: Publish to Platform with Retry and Fallback

```python
# Source: tenacity docs + requests + existing pattern
# Located: src/app/scheduler/jobs/platform_publish.py (NEW)

import logging
import requests
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception
from app.services.database import get_supabase
from app.services.telegram import send_alert_sync
from app.settings import get_settings

logger = logging.getLogger(__name__)

def is_retryable_http_error(exc: Exception) -> bool:
    """Retry only on 5xx and network errors; fail fast on 4xx."""
    if isinstance(exc, requests.ConnectTimeout):
        return True
    if isinstance(exc, requests.ReadTimeout):
        return True
    if isinstance(exc, requests.ConnectionError):
        return True
    if isinstance(exc, requests.HTTPError):
        return exc.response.status_code >= 500
    return False

@retry(
    retry=retry_if_exception(is_retryable_http_error),
    stop=stop_after_attempt(3),  # Original + 2 retries
    wait=wait_exponential(multiplier=1, min=2, max=30),  # 2s, 4s, 8s...
    reraise=True,
)
def _call_ayrshare(
    post_text: str,
    video_url: str,
    platforms: list[str],
    schedule_date: str,
) -> dict:
    """Actual HTTP call to Ayrshare. Tenacity decorator handles retries."""
    settings = get_settings()

    headers = {
        "Authorization": f"Bearer {settings.ayrshare_api_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "post": post_text,
        "platforms": platforms,
        "mediaUrls": [video_url],
        "isVideo": True,
        "scheduleDate": schedule_date,
    }

    response = requests.post(
        "https://app.ayrshare.com/api/post",
        json=payload,
        headers=headers,
        timeout=30,
    )
    response.raise_for_status()
    return response.json()

def publish_to_platform_job(
    content_history_id: str,
    platform: str,
    video_url: str,
) -> None:
    """
    Scheduled job: publish approved video to a single platform.
    Fires at the platform's peak hour (calculated by schedule_platform_publishes).

    On success: log + save post ID to DB.
    On failure: send Telegram fallback message.
    """
    supabase = get_supabase()
    settings = get_settings()

    # Load content + copy
    row = supabase.table("content_history").select(
        "post_copy, post_copy_tiktok, post_copy_instagram, post_copy_facebook, post_copy_youtube"
    ).eq("id", content_history_id).single().execute()

    content = row.data

    # Get platform-specific copy
    copy_key = f"post_copy_{platform}"
    post_copy = content.get(copy_key) or content.get("post_copy", "")

    try:
        # Call Ayrshare with retry
        response = _call_ayrshare(
            post_text=post_copy,
            video_url=video_url,
            platforms=[platform],
            schedule_date=None,  # Publish immediately (already at peak time)
        )

        # Save post ID
        ayrshare_post_id = response.get("postId")
        post_ids = response.get("postIds", {})
        platform_post_id = post_ids.get(platform)

        supabase.table("publish_events").insert({
            "content_history_id": content_history_id,
            "platform": platform,
            "ayrshare_post_id": ayrshare_post_id,
            "platform_post_id": platform_post_id,
            "status": "published",
        }).execute()

        # Schedule verification job (30 minutes from now)
        from app.scheduler.jobs.publish_verify import verify_publish_job
        from apscheduler.schedulers.background import BackgroundScheduler

        scheduler = ...  # Get from somewhere (e.g., app state)
        verify_job_id = f"verify_{content_history_id}_{platform}"
        scheduler.add_job(
            verify_publish_job,
            trigger="date",
            run_date=datetime.now(tz=pytz.UTC) + timedelta(minutes=30),
            args=[content_history_id, platform, ayrshare_post_id],
            id=verify_job_id,
            replace_existing=True,
        )

        logger.info(f"Published {platform} for {content_history_id[:8]}: {ayrshare_post_id}")

    except Exception as exc:
        logger.error(f"Failed to publish {platform}: {exc}")
        send_alert_sync(
            f"❌ PUBLISH FAILED: {platform.upper()}\n\n"
            f"Video: {video_url}\n"
            f"Copy:\n{post_copy}\n\n"
            f"Please post manually.\n\n"
            f"Error: {str(exc)[:200]}"
        )

        # Record failure
        supabase.table("publish_events").insert({
            "content_history_id": content_history_id,
            "platform": platform,
            "status": "failed",
            "error_message": str(exc)[:500],
        }).execute()
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Manual HTTP retry loops | tenacity decorator-based retries | 2022+ | Cleaner code, fewer bugs. tenacity handles jitter, max delay, condition evaluation. |
| UTC-only datetime handling | Timezone-aware datetime with pytz | 2015+ (but still often missed) | Correct peak hour calculation. Handles DST transitions. |
| Storing post metadata in logs | Persisting post IDs in DB | Always for serious systems | Enables verification, analytics, diagnostics. Logs are ephemeral. |
| Ayrshare direct API + custom multi-platform logic | Ayrshare single /post endpoint | 2024+ (Ayrshare API maturity) | Single API call publishes to 4 platforms. No need for platform-specific SDKs. |
| Celery + Redis for scheduling | APScheduler + Postgres job store | 2020+ for single-creator systems | APScheduler sufficient for one creator. Job store survives restarts. No Redis overhead. |

**Deprecated/outdated:**
- **Buffer API for multi-platform publish:** Requires separate API call per platform. Ayrshare is simpler.
- **Manual timezone conversions (UTC offset):** Breaks during DST. Use pytz. APScheduler's cron trigger is already timezone-aware.
- **Celery for simple scheduling:** Overkill for single creator. APScheduler + Postgres is lighter.

---

## Open Questions

1. **Copy Variant Storage in DB**
   - What we know: CONTEXT.md says "stored in DB" but doesn't specify table structure.
   - What's unclear: New columns on content_history (post_copy_tiktok, post_copy_instagram, post_copy_facebook, post_copy_youtube) OR separate table (content_history_id, platform, copy text)?
   - Recommendation: **Extend content_history with 4 new columns** (simpler queries, no joins, matches existing post_copy pattern). Migration: `ALTER TABLE content_history ADD COLUMN post_copy_tiktok text, ADD COLUMN post_copy_instagram text, ...`

2. **Verification Message Format**
   - What we know: "Only surface failures by default" from CONTEXT.md.
   - What's unclear: What constitutes a "failure" vs. "success"? Full post data in success? Silent on success?
   - Recommendation: **Send Telegram alert only if verification fails.** On success, log silently. If user asks, query DB for publish_events to see all publishes.

3. **Retry Backoff Intervals**
   - What we know: "2–3 retries with exponential backoff" from CONTEXT.md.
   - What's unclear: Min/max delays? Jitter?
   - Recommendation: **wait_exponential(multiplier=1, min=2, max=30)** → retries at 2s, 4s, 8s (stop after 3 attempts = 14s total). Matches HeyGen polling pattern. Add jitter if needed for production.

4. **Scheduling Job Architecture**
   - What we know: CONTEXT.md lists as "Claude's Discretion" — one job per platform vs. one job that fires all.
   - What's unclear: Trade-offs?
   - Recommendation: **One job per platform** (4 separate jobs). Rationale: Each platform publishes at a different peak hour. Separate jobs allow independent scheduling, failure handling, and verification. One job that fires all 4 would require internal delays (defeating the peak hour benefit) or would fire all 4 at the first peak (wrong for the others).

5. **Telegram Confirmation Message Format**
   - What we know: "Scheduled: TikTok 7:00pm, IG 11:00am tomorrow..." from CONTEXT.md.
   - What's unclear: Should it show times in both audience timezone AND creator's local timezone for clarity?
   - Recommendation: **Show scheduled times in audience timezone only.** Creator has already seen platform peak defaults. Showing in audience timezone is consistent with settings. Example: `Scheduled for publication:\n🎵 TikTok: Today 7:00 PM\n📷 Instagram: Tomorrow 11:00 AM\n... (all times in US/Eastern)`

---

## Sources

### Primary (HIGH confidence)

- **Ayrshare API Documentation** (https://www.ayrshare.com/docs/apis/post/post.md) — /post endpoint structure, parameters, platform support (TikTok, Instagram, Facebook, YouTube), response format verified 2026-02-25.
- **APScheduler 3.10+ Documentation** (https://apscheduler.readthedocs.io/en/3.x/userguide.html) — Timezone-aware cron triggers, delayed jobs, job store persistence, coalesce behavior.
- **Existing codebase** — Scheduler setup (src/app/scheduler/setup.py), PostCopyService pattern (src/app/services/post_copy.py), send_alert_sync pattern (src/app/services/telegram.py), Phase 4 migration schema (migrations/0004_approval_events.sql).

### Secondary (MEDIUM confidence)

- **Tenacity 8.x Documentation** (https://tenacity.readthedocs.io/) — Exponential backoff, retry conditions, max attempts. Verified against official docs 2026-02-25.
- **APScheduler Peak Hours / Timezone** (https://apscheduler.readthedocs.io/en/3.x/userguide.html + https://betterstack.com/community/guides/scaling-python/apscheduler-scheduled-tasks/) — Cron trigger timezone support, DST handling, wall-clock time behavior.
- **Requests Library Timeout + HTTPError** (https://docs.python-requests.org/) — Standard error handling for HTTP calls.

### Tertiary (LOW confidence)

- Training data knowledge (pre-Feb 2025) on Ayrshare API maturity and platform coverage — may differ from live service. **Recommendation:** Verify current platform list and auth format against Ayrshare dashboard before first deployment.

---

## Metadata

**Confidence breakdown:**
- Standard stack (Ayrshare, APScheduler, tenacity, requests): **HIGH** — All verified against official docs and existing codebase patterns. Ayrshare API verified against live docs 2026-02-25.
- Architecture (peak hour scheduling, delayed jobs, retry + fallback): **HIGH** — Patterns follow existing Phase 1–4 code. APScheduler already in use. No novel architecture.
- Pitfalls (timezone DST, job ID persistence, retry exhaustion): **MEDIUM** — Based on common scheduling pitfalls; specific to this implementation when integrated.
- Open questions (copy storage, verification format, retry intervals): **MEDIUM** — Identified from CONTEXT.md ambiguities. Require planner/developer discretion.

**Research date:** 2026-02-25
**Valid until:** 2026-03-25 (30 days — Ayrshare API rarely changes; APScheduler stable for 2+ years)
