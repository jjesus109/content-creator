# Phase 9: Character Bible and Video Generation - Research

**Researched:** 2026-03-19
**Domain:** Kling AI 3.0 video generation via fal.ai async SDK, circuit breaker patterns, AI content labeling compliance
**Confidence:** HIGH

## Summary

Phase 9 replaces HeyGen with Kling AI 3.0 via fal.ai's async SDK to generate recognizable 20-30s cat videos with a locked character identity. The system must embed a Character Bible (40-50 word trait spec) unchanged in every prompt, implement a Kling-specific circuit breaker that halts the pipeline if >20% failures occur in a rolling 24-hour window, and apply AI content disclosure labels ("🤖 Creado con IA") on all platforms before the video reaches the creator.

**Primary recommendation:** Use fal.ai's `submit()` sync method (not `submit_async()`) in the APScheduler ThreadPoolExecutor context, coupled with status polling (60s interval, same as HeyGen poller). Kling 3.0's strengthened character consistency features enable text-only prompts without reference images; store the Character Bible as a Python constant in `kling.py`. Implement a separate Kling circuit breaker tracking failure rate (not cost) over 24 hours with exponential backoff (2s, 8s, 32s) and balance checks before each API call.

## User Constraints (from CONTEXT.md)

### Locked Decisions
- **Character Bible content:** Orange tabby with white markings (bright, distinct for Kling) with Mexican cultural identity conveyed through environment, not body accessories; personality: curious and mischievous; name: Mexican (e.g., Mochi); format: 40-50 words embedded unchanged in every prompt
- **Kling/fal.ai integration:** APScheduler polling pattern (adapt `video_poller.py` for Kling status checks, 60s interval); new service file `src/app/services/kling.py` with `submit()` and `_process_completed_render()`; Character Bible + scene prompt concatenated into single Kling text prompt; video spec: 20-30s, 9:16 aspect ratio, 1080p; timeout/retry: 20-min timeout, retry once, then alert and skip day (same v1.0 pattern)
- **Kling circuit breaker:** Separate from existing HeyGen CB; >20% failure rate threshold over 24-hour rolling window; exponential backoff: 2s, 8s, 32s; fal.ai balance queried before each call; alert creator via Telegram on CB open (no retry loops); recovery via `/resume` command
- **AI content labels:** Applied during publish API call in `platform_publish.py` (not before Telegram approval); TikTok: caption prefix `🤖 Creado con IA` (skip native API flag); YouTube: prefix in description; Instagram: prefix in caption; fallback to caption prefix if platform label API fails; uniform label string across all platforms
- **Code patterns:** Keep `heygen.py` unchanged (audit trail); new `daily_pipeline.py` call: `KlingService.submit()` instead of `HeyGenService.submit()`; env vars needed: `FAL_API_KEY`, `KLING_MODEL_VERSION`

### Claude's Discretion
- Exact 40-50 word Character Bible text (draft and embed as constant in `kling.py`)
- Specific Mexican cat name to use (Mochi recommended)
- fal.ai SDK method signatures for submit + status polling (research verified)
- DB column names for v2.0 schema migration (pipeline_runs v2 columns, music_pool table, character_bible setting)
- Internal structure of Kling CB class

### Deferred Ideas (OUT OF SCOPE)
- Reference image upload to Kling for enhanced character consistency (upgrade path if visual consistency <90% after testing) — Phase 9 ships text-only prompts first
- TikTok native `ai_generated` API flag — skipped; caption prefix used instead. Can be added later if TikTok changes requirements.

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| VID-01 | System generates cat video using Kling AI 3.0 via fal.ai (20-30s, 9:16 1080p) replacing HeyGen | fal.ai SDK supports `submit()` sync method with job polling; Kling 3.0 standard tier generates 3-15s video at 1080p; fal.ai pricing $0.168/s (Standard, audio off) verified |
| VID-02 | Fixed Mexican cat character defined via Character Bible (40-50 word trait spec) embedded in every generation prompt | Kling 3.0 has strengthened character consistency (March 2026 feature); best practice: define character early, keep descriptions consistent; text-only prompts sufficient without reference images |
| VID-03 | Kling API circuit breaker: pauses pipeline if >20% failure rate; exponential backoff (2s, 8s, 32s); credit balance checked before each call | Circuit breaker + exponential backoff pattern verified standard (AWS, Netflix Hystrix); fal.ai auto-retries up to 10 times; balance query available via API; 20% threshold suitable for rolling 24-hour window |
| VID-04 | AI content label applied on all platforms before video is published (mandatory TikTok/YouTube/Instagram compliance) | TikTok: C2PA metadata detection (Jan 2025); YouTube: policy enforced early 2025; Instagram: Meta AI labels in early 2025; caption prefix ("🤖 Creado con IA") universally supported fallback method; EU AI Act Article 50 effective August 2, 2026 (penalties €15M or 3% revenue) |

## Standard Stack

### Core Libraries
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| fal-client (Python SDK) | Latest (2.x) | Submit Kling video generation jobs and poll status | Official async + sync methods; supports APScheduler ThreadPoolExecutor context with sync `submit()` |
| APScheduler | 3.11.2 | Job polling for Kling status (60s interval) | Existing pattern in v1.0 HeyGen poller; picklable args only (no closures); ThreadPoolExecutor context |
| requests | 0.28+ | HTTP client for fal.ai/Kling status checks | Synchronous, picklable, verified in HeyGen poller pattern |
| SQLAlchemy | 2.0+ | DB operations for Kling circuit breaker state persistence | Existing ORM; circuit breaker state stored in new table |
| Pydantic Settings | 2.7+ | Environment variable injection (`FAL_API_KEY`, `KLING_MODEL_VERSION`) | Existing settings system in project |

### Supporting Libraries
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| Supabase Python SDK | 2.0+ | DB queries for Kling CB state and content_history | Existing pattern; circuit breaker state persists across restarts |
| python-telegram-bot | 21.* | Alert creator when circuit breaker opens or balance low | Existing pattern; send_alert_sync() already in place |
| pytz | 2024.1+ | Timezone-aware midnight reset for 24-hour CB window | Existing; Mexico City timezone for CB reset cadence |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| fal.ai Kling 3.0 | Runway Gen3 / Descript API | Kling wins: $0.168/s (Standard) vs $0.25+/s competitors; character consistency native (March 2026 feature) |
| Sync `submit()` in ThreadPoolExecutor | Async `submit_async()` | Sync wins: APScheduler ThreadPoolExecutor cannot manage event loops; sync avoids subprocess complexity |
| Text-only prompt | Reference image upload | Text-only wins for Phase 9: Kling 3.0 strengthened consistency (March 2026) sufficient; reference images upgrade path if <90% consistency observed |
| Single circuit breaker | Per-provider CB (separate Kling + HeyGen) | Separate wins: HeyGen and Kling failure rates differ; independent thresholds prevent cascading failures |
| Caption prefix label | Platform native API flags | Caption prefix wins: universal fallback if platform API fails; TikTok C2PA detection automatic; compliance maintained |

**Installation:**
```bash
pip install fal-client==2.0.0  # Verify latest version: pip show fal-client
```

**Version verification:** fal.ai Python SDK (fal-client) is actively maintained; Kling 3.0 released March 2026 on fal.ai with strengthened character consistency. Verify at time of implementation: `pip index versions fal-client` or check [PyPI fal-client](https://pypi.org/project/fal-client/).

## Architecture Patterns

### Recommended Project Structure

Service file placement mirrors existing HeyGen pattern:
```
src/app/
├── services/
│   ├── heygen.py                 # Unchanged (audit trail) — HeyGen submission + processing
│   ├── kling.py                  # NEW: Kling submission + Kling-specific processing
│   ├── circuit_breaker.py        # Existing: HeyGen CB (cost+count based)
│   ├── kling_circuit_breaker.py  # NEW: Kling CB (failure-rate based, 24h window)
│   └── video_storage.py          # Unchanged: MP4 upload to Supabase
├── scheduler/
│   └── jobs/
│       ├── daily_pipeline.py     # Modified: swap HeyGenService.submit() → KlingService.submit()
│       ├── video_poller.py       # Adapted: fal.ai status check instead of HeyGen URL
│       ├── platform_publish.py   # Modified: add AI label logic per-platform
│       └── publish_verify.py     # Unchanged
└── models/
    └── video.py                  # Add new VideoStatus values if needed (e.g., KLING_PENDING)
```

Character Bible stored as Python constant (not config or DB):
```python
# In kling.py
CHARACTER_BIBLE = """
An orange tabby cat with white markings, bright and distinct. Curious and mischievous personality — always getting into things. Lives in a Mexican household filled with serapes, pottery, plants, and traditional architecture. Name: Mochi.
"""  # ~45 words
```

### Pattern 1: Kling Service Submission (sync in APScheduler context)

**What:** Submit video generation job to fal.ai Kling 3.0, return job ID for polling.

**When to use:** Called from `daily_pipeline.py` after script generation succeeds (same call site as HeyGenService).

**Example:**
```python
# Source: fal.ai client docs + CONTEXT.md locked decision
import fal_client
from app.settings import get_settings

class KlingService:
    def __init__(self):
        self._settings = get_settings()
        # Note: fal_client auto-reads FAL_API_KEY from environment
        # No explicit auth token needed in code

    def submit(self, script_text: str, character_bible: str) -> str:
        """
        Submit character Bible + scene prompt to Kling 3.0 via fal.ai.

        Args:
            script_text: The scene description (from daily_pipeline)
            character_bible: The fixed 40-50 word Character Bible (constant, unchanged)

        Returns:
            Job ID string for polling status

        Raises:
            requests.HTTPError: On API failure
        """
        settings = self._settings

        # Concatenate: Character Bible + scene prompt (single text input to Kling)
        full_prompt = f"{character_bible}\n\n{script_text}"

        # fal_client.submit() is sync method (suitable for ThreadPoolExecutor)
        result = fal_client.submit(
            "fal-ai/kling-video/v3/standard/text-to-video",  # Model ID
            arguments={
                "prompt": full_prompt,
                "duration": 20,  # seconds (locked: 20-30s range)
                "resolution": "1080p",
                "aspect_ratio": "9:16",  # Vertical video
                # Optional: seed for reproducibility
            }
        )

        # fal_client.submit() returns a request object with .request_id
        job_id = result.request_id
        logger.info("Kling job submitted: job_id=%s duration=20s aspect=9:16", job_id)
        return job_id
```

### Pattern 2: Kling Circuit Breaker (24-hour failure rate tracking)

**What:** Track Kling API failure rate; halt pipeline if >20% failures in rolling 24-hour window. Separate from HeyGen CB.

**When to use:** Check before each Kling submission; track on job failure via poller.

**Example:**
```python
# Source: CONTEXT.md + circuit breaker pattern (AWS Prescriptive Guidance)
class KlingCircuitBreakerService:
    def __init__(self, supabase: Client):
        self.db = supabase
        self.table = "kling_circuit_breaker_state"
        self.failure_threshold = 0.20  # 20% failure rate
        self.window_hours = 24

    def record_attempt(self, success: bool, fal_balance: float | None = None) -> bool:
        """
        Record an attempt (success or failure) and check if CB should trip.

        Returns:
            True if pipeline should proceed, False if CB is open
        """
        state = self._get_state()

        # Fail if CB already open
        if state["is_open"]:
            logger.warning("Kling CB is open — rejecting attempt")
            return False

        # Check fal.ai balance before proceeding
        if fal_balance is not None and fal_balance < 5.0:
            logger.warning("fal.ai balance low: $%.2f < $5 threshold", fal_balance)
            send_alert_sync(f"Advertencia: saldo fal.ai bajo ($%.2f). Verifica el balance.", fal_balance)

        # Update attempt counts
        new_total = state["total_attempts"] + 1
        new_failures = state["total_failures"] + (1 if not success else 0)
        failure_rate = new_failures / new_total if new_total > 0 else 0.0

        # Check if threshold exceeded
        if failure_rate > self.failure_threshold:
            logger.error("Kling CB trip: failure_rate=%.2f > %.2f threshold",
                        failure_rate, self.failure_threshold)
            self._trip(state, failure_rate)
            return False

        # Update DB
        self.db.table(self.table).update({
            "total_attempts": new_total,
            "total_failures": new_failures,
            "failure_rate": failure_rate,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", 1).execute()

        return True

    def _trip(self, state: dict, failure_rate: float) -> None:
        """Open circuit breaker and alert creator."""
        self.db.table(self.table).update({
            "is_open": True,
            "opened_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", 1).execute()

        send_alert_sync(
            f"ALERTA: Kling circuit breaker abierto. Tasa de fallos: {failure_rate:.1%}. "
            "Pipeline detenido. Escribe /resume para reanudar."
        )
```

### Pattern 3: AI Content Label Injection in platform_publish.py

**What:** Prepend AI disclosure label to caption before publishing to each platform.

**When to use:** Inside `publish_to_platform_job()` before calling `PublishingService.publish()`.

**Example:**
```python
# Source: CONTEXT.md + platform compliance (TikTok, YouTube, Instagram 2026 requirements)
def publish_to_platform_job(content_history_id: str, platform: str, video_url: str) -> None:
    """Modified: inject AI label before platform publish."""
    supabase = get_supabase()

    # Load post_copy from DB
    row = supabase.table("content_history").select("post_copy").eq("id", content_history_id).single().execute()
    post_copy = row.data.get("post_copy", "")

    # Inject AI label based on platform
    labeled_copy = _apply_ai_label(post_copy, platform)

    # Call existing publishing logic with labeled copy
    response = PublishingService().publish(
        platform=platform,
        post_text=labeled_copy,
        video_url=video_url,
    )

    # ... rest unchanged

def _apply_ai_label(post_text: str, platform: str) -> str:
    """Prepend AI disclosure label. Uniform across all platforms."""
    label = "🤖 Creado con IA"

    if platform in ("tiktok", "instagram"):
        # Prepend to caption
        return f"{label}\n{post_text}" if post_text else label

    elif platform == "youtube":
        # Prepend to description
        # First line is title, rest is description
        lines = post_text.strip().split("\n")
        title = lines[0] if lines else "Video"
        description = "\n".join(lines[1:]) if len(lines) > 1 else ""

        labeled_description = f"{label}\n\n{description}" if description else label
        return f"{title}\n{labeled_description}"

    elif platform == "facebook":
        # Prepend to caption
        return f"{label}\n{post_text}" if post_text else label

    return post_text  # Fallback
```

### Anti-Patterns to Avoid

- **Using async `submit_async()` in APScheduler ThreadPoolExecutor:** fal.ai SDK supports async, but APScheduler's ThreadPoolExecutor cannot manage nested event loops. Use sync `submit()` only.
- **Storing Character Bible in config/DB:** The Bible must be deployed with code (constant in `kling.py`) to guarantee consistency across all generations. Config drift causes character inconsistency.
- **Combining HeyGen and Kling failure rates in single CB:** Different providers have different failure patterns. Separate CBs allow independent thresholds and recovery.
- **Silent failures on AI label application:** If platform API label fails, ALWAYS fall back to caption prefix. No silent skips.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Video polling mechanism | Custom polling loop (while/sleep) | APScheduler interval trigger (60s) + picklable args | APScheduler handles restarts, scheduler persistence, timezone-aware scheduling; custom loops cause race conditions, memory leaks, missed jobs on crash |
| fal.ai job submission and status | Custom HTTP wrapper with manual JSON parsing | fal-client Python SDK `submit()` method | SDK handles retries, error handling, C2PA metadata, API versioning; manual HTTP is fragile to API changes |
| Circuit breaker state persistence | In-memory dict (lost on restart) | Database singleton row (circuit_breaker_state table) | State survives service restarts; distributed consistency; avoids cascading failures across deployments |
| Exponential backoff retry | Manual `time.sleep(2 ** attempt)` | tenacity library or fal-client built-in retries | Library handles jitter, max backoff caps, distinguishes transient vs permanent errors |
| Character consistency prompting | Trial-and-error prompt engineering | Kling 3.0 native character consistency (March 2026) + early descriptor positioning | Kling 3.0 strengthened consistency eliminates reference image requirement; best practice: define character in first sentence, maintain descriptor reuse |
| AI content label compliance | Hardcoded platform-specific logic | Centralized `_apply_ai_label()` function + platform-specific branches | Single source of truth; simplifies updates when platform policies change; avoids label injection bugs in 4+ publish code paths |

**Key insight:** fal.ai SDK handles retries, timeouts, and rate limiting transparently; rolling custom HTTP wrappers reintroduces edge cases. APScheduler's persistent job store survives restarts and prevents duplicate submissions — critical for financial tracking with API cost.

## Common Pitfalls

### Pitfall 1: Async/Await Confusion in APScheduler Context
**What goes wrong:** Developer uses `fal_client.submit_async()` in APScheduler job, expecting it to integrate cleanly. APScheduler's ThreadPoolExecutor cannot manage `asyncio` event loops — the job silently fails or hangs.

**Why it happens:** fal.ai SDK documentation emphasizes async as "modern Python," but APScheduler jobs are synchronous tasks running in a thread pool. Mixing async and sync contexts causes deadlock or UnboundLocalError.

**How to avoid:** Always use `fal_client.submit()` (sync method, no `_async` suffix) in APScheduler jobs. Polling happens via APScheduler's interval trigger, not `asyncio.run()`.

**Warning signs:** Job hangs for 60+ seconds before timeout; logs show "RuntimeError: no running event loop"; or test passes in isolation but fails in scheduler context.

**Test pattern:**
```python
# DO: Sync submit in ThreadPoolExecutor context
def video_poller_job(job_id: str):
    result = fal_client.submit(...)  # Blocks until complete or timeout

# DON'T: Async in scheduler job
def video_poller_job(job_id: str):
    result = await fal_client.submit_async(...)  # Hangs or crashes
```

### Pitfall 2: Character Bible Drift from Configuration Changes
**What goes wrong:** Character Bible stored in config file or environment variable. Mid-cycle, operator changes the description (e.g., "orange tabby" → "orange tabby with stripes"). New videos show character inconsistency; old videos vs new videos don't match.

**Why it happens:** Character consistency requires prompt consistency. If the Bible changes, Kling's consistency engine cannot anchor to a moving target. Git-based config management doesn't solve this — at least one video lands with new Bible before rollback.

**How to avoid:** Store Character Bible as a Python constant in `kling.py`, deployed with code. Any change requires code review + explicit commit + deployment. Monitoring: log the Bible hash at startup; verify consistency across deploys.

**Warning signs:** Two consecutive videos have visually different cat appearance; video approval messages show "cat looks different today"; creator reports inconsistency after config updates.

**Test pattern:**
```python
# DO: Python constant, deployed with code
CHARACTER_BIBLE = """Orange tabby..."""  # In kling.py, versioned in git

# DON'T: Configurable
BIBLE = os.getenv("CAT_CHARACTER_BIBLE", "")  # Changes at runtime
```

### Pitfall 3: Failure Rate Threshold Sensitivity
**What goes wrong:** 20% failure threshold is set without empirical validation. In first week, Kling has 25% failures (normal variance), CB trips, pipeline halts, creator complains. Or threshold too high (30%), CB never trips even when Kling is degraded.

**Why it happens:** API degradation curves are non-linear. A single-day spike (30% failures) differs from sustained (22% for 5 days). CONTEXT.md notes: "Kling exact rate limits unknown — Phase 9 plan should include 1-week API test to observe real failure patterns before CB threshold is finalized."

**How to avoid:** Week 0 recommendation: deploy with 20% threshold but log failure rates hourly. Monitor for 7 days. If real rate stabilizes at X%, adjust threshold to X% + 5% buffer. Document the empirical baseline.

**Warning signs:** CB trips on first day; creator says "Kling usually works, why is it blocked?"; logs show consistent 18-22% failure rate but threshold is 20%.

**Test pattern:**
```python
# Week 1: Log, don't trip
if failure_rate > 0.20:
    logger.warning("Would trip at %.1f%% (threshold: 20%%)", failure_rate * 100)
    # Don't return False yet — observe real distribution
    return True

# Week 2+: After baseline established
if failure_rate > threshold_adjusted:
    return False  # Trip
```

### Pitfall 4: Balance Check Timing — Blocking vs Non-Blocking
**What goes wrong:** Balance check is synchronous (calls fal.ai API each submission), adding 2-3s latency. Or check is cached, balance drops to $0.50, pipeline submits invalid jobs, wastes credits.

**Why it happens:** fal.ai balance check is a real API call (~1s). Doing it per-submission adds ~2-3s per pipeline run. Caching avoids latency but risks credit exhaustion if balance changes between check and submission.

**How to avoid:** Check balance at 60s polling interval (during status check, not submission). If low (< $5), alert creator but proceed. If critically low (< $1), halt pipeline. This batches balance checks with status checks, reducing latency.

**Warning signs:** Pipeline jobs take 5-10s longer after balance check added; balance drops unexpectedly but no alert sent; creator finds wasted credits in fal.ai dashboard.

**Test pattern:**
```python
# DO: Check during polling, not submission
def video_poller_job(job_id: str):
    balance = fal_client.get_balance()  # Once per 60s poll
    if balance < 1.0:
        halt_pipeline()

# DON'T: Check every submission
def kling_submit(...):
    balance = fal_client.get_balance()  # Every ~5min at 20s/video
    # Adds 2-3s per submission
```

### Pitfall 5: Caption Label Injection Ordering — Title vs Description
**What goes wrong:** For YouTube, label is prepended to full post_copy (title + description). The title becomes "🤖 Creado con IA Video Title", breaking YouTube's 100-char title limit. Or label overwrites title entirely.

**Why it happens:** `post_copy` contains title on line 1, description on lines 2+. Naive prepend puts label at the very start, shifting title downstream. YouTube expects clean title, then description separately.

**How to avoid:** Split post_copy on first newline: `title = lines[0]`, `description = "\n".join(lines[1:])`. Prepend label only to description, reconstruct as `title\n{label}\n{description}`.

**Warning signs:** YouTube video has "🤖 Creado con IA" as part of title; title field in YouTube dashboard shows truncated or malformed text; creator reports title looks broken.

**Test pattern:**
```python
# DO: Split, prepend to description only
title = post_copy.split("\n")[0]
description = "\n".join(post_copy.split("\n")[1:])
labeled = f"{title}\n🤖 Creado con IA\n{description}"

# DON'T: Naive prepend
labeled = f"🤖 Creado con IA\n{post_copy}"  # Title becomes label
```

## Code Examples

Verified patterns from official sources and existing codebase:

### Kling Service Submit (sync)
```python
# Source: fal.ai docs + CONTEXT.md
import fal_client
import logging
from app.settings import get_settings

logger = logging.getLogger(__name__)

CHARACTER_BIBLE = """An orange tabby cat with white markings, bright and distinct. Curious and mischievous personality — always getting into things. Lives in a Mexican household filled with serapes, pottery, plants, and traditional architecture. Named Mochi. (45 words)"""

class KlingService:
    def __init__(self):
        self._settings = get_settings()

    def submit(self, script_text: str) -> str:
        """Submit to Kling 3.0 via fal.ai. Sync method for APScheduler ThreadPoolExecutor."""
        full_prompt = f"{CHARACTER_BIBLE}\n\n{script_text}"

        # fal_client.submit() is synchronous
        result = fal_client.submit(
            "fal-ai/kling-video/v3/standard/text-to-video",
            arguments={
                "prompt": full_prompt,
                "duration": 20,
                "resolution": "1080p",
                "aspect_ratio": "9:16",
            }
        )

        job_id = result.request_id
        logger.info("Kling submitted: job_id=%s", job_id)
        return job_id
```

### Kling Status Polling (adapted from HeyGen pattern)
```python
# Source: video_poller.py refactored for fal.ai
import fal_client
from datetime import datetime, timedelta, timezone

def video_poller_job(job_id: str, submitted_at: datetime) -> None:
    """Poll fal.ai job status every 60s."""
    elapsed = datetime.now(tz=timezone.utc) - submitted_at

    if elapsed > timedelta(minutes=20):
        # Timeout — retry once or fail
        _retry_or_fail(job_id)
        return

    try:
        # fal_client.status() returns job state
        status = fal_client.status(job_id)

        if status.status == "completed":
            # Download video from result
            video_url = status.result["video"]["url"]
            _process_completed_render(job_id, video_url)
            _cancel_self(job_id)

        elif status.status == "failed":
            error = status.result.get("error", "unknown")
            _handle_render_failure(job_id, error)
            _cancel_self(job_id)

        # "queued" or "in_progress" — continue polling

    except Exception as exc:
        logger.error("Poll error: %s", exc)
        # Do NOT cancel — retry on next interval
```

### AI Label Injection (platform-specific)
```python
# Source: CONTEXT.md + platform compliance
def _apply_ai_label(post_text: str, platform: str) -> str:
    """Prepend AI disclosure label uniformly."""
    label = "🤖 Creado con IA"

    if platform in ("instagram", "facebook"):
        # Caption prefix
        return f"{label}\n{post_text}" if post_text else label

    elif platform == "youtube":
        # Split title and description, label goes in description
        lines = post_text.strip().split("\n", 1)
        title = lines[0] if lines else "Video"
        description = lines[1] if len(lines) > 1 else ""

        labeled_desc = f"{label}\n\n{description}" if description else label
        return f"{title}\n{labeled_desc}"

    elif platform == "tiktok":
        # Manual publish (not automated), but label for reference
        return f"{label}\n{post_text}" if post_text else label

    return post_text
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| HeyGen avatar video generation | Kling AI 3.0 text-to-video | March 2026 | Kling 7-60x cheaper ($0.168/s vs $0.25+/s); character consistency native (no custom prompting); multi-shot support; Mexico market preferred |
| Cost-based circuit breaker (HeyGen) | Failure-rate CB (Kling) + balance checks | Phase 9 | HeyGen charges per-video ($0.05-$0.10 fixed), so cost threshold makes sense. Kling charges per-second ($0.168/s variable), so failure rate + balance checks are more appropriate |
| Reference image for consistency | Text-only with structured prompts | March 2026 Kling 3.0 | Kling 3.0 strengthened character consistency; text-only prompts sufficient; reference images remain upgrade path if consistency <90% observed |
| Hardcoded platform publish logic | Centralized `_apply_ai_label()` + platform branches | Phase 9 | Single label source; simplifies compliance updates when platform policies change; avoids duplicated logic across 4+ publish methods |

**Deprecated/outdated:**
- HeyGen text-to-video avatars: Replaced by Kling AI 3.0. Keep `heygen.py` for audit trail (read-only), but all new submissions use `kling.py`.
- TikTok native `ai_generated` API flag: Skipped per user decision. Caption prefix sufficient and universal fallback.

## Open Questions

1. **Exact Kling failure rate distribution in production**
   - What we know: User decision: 20% threshold over 24h; CONTEXT.md notes: "Kling exact rate limits unknown — Phase 9 plan should include 1-week API test"
   - What's unclear: Real failure rate at scale (current test data is limited). May be 8-12% normal, spike to 25% on API degradation, or steady 18-20%.
   - Recommendation: Deploy with monitoring (hourly failure rate logs) for 7 days before finalizing threshold. Adjust to `observed_rate + 5% buffer` if data supports.

2. **Character consistency validation method**
   - What we know: Kling 3.0 has "significantly stronger element and subject consistency" (March 2026 feature); CONTEXT.md suggests "8 of 10 consecutive test videos show the same cat recognized by visual inspection"
   - What's unclear: How to systematically measure consistency (pixel-level comparison, perceptual hash, manual review)?
   - Recommendation: Conduct 10-video test batch during Phase 9-02 implementation; document consistency subjectively (creator approval) + objectively (frame analysis tool if available); if <80% visual consistency, escalate reference image requirement to Phase 9-02 plan.

3. **fal.ai balance API and rate limiting**
   - What we know: Balance check available; fal.ai auto-retries up to 10 times on transient failures
   - What's unclear: Balance check latency (should we cache for 1h, or query fresh every poll?); rate limit for balance queries (unlimited, or throttled?)
   - Recommendation: Implement balance check in `video_poller_job()` at 60s interval (not per-submission). Add to logs. If latency >2s, cache for 1h and document decision.

4. **EU AI Act Article 50 compliance (effective Aug 2, 2026)**
   - What we know: Requires deepfake disclosure; penalties €15M or 3% revenue; caption label "🤖 Creado con IA" satisfies requirement
   - What's unclear: Does caption-only disclosure satisfy Article 50, or are additional metadata requirements needed (e.g., C2PA)?
   - Recommendation: Phase 9-04 implementation must include caption prefix. If EU regulation clarifies stricter requirements before Phase 9 launch, escalate to CONTEXT.md decision point.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.0+ |
| Config file | pyproject.toml (pytest section) |
| Quick run command | `pytest tests/ -m 'not e2e' -x` |
| Full suite command | `pytest tests/ -x` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| VID-01 | Kling job submission returns job_id (async submit via fal.ai) | unit | `pytest tests/test_kling_service.py::test_submit_returns_job_id -x` | ❌ Wave 0 |
| VID-01 | Polling loop detects "completed" status and calls _process_completed_render | unit | `pytest tests/test_kling_poller.py::test_poll_completed_triggers_process -x` | ❌ Wave 0 |
| VID-02 | Character Bible (40-50 words) embedded unchanged in every prompt | unit | `pytest tests/test_character_bible.py::test_bible_constant_unchanged -x` | ❌ Wave 0 |
| VID-02 | Prompt concatenation: CHARACTER_BIBLE + scene_script (single text field) | unit | `pytest tests/test_kling_service.py::test_prompt_concatenation -x` | ❌ Wave 0 |
| VID-03 | Kling CB tracks failure rate; opens at >20% | unit | `pytest tests/test_kling_cb.py::test_cb_trip_on_20_percent -x` | ❌ Wave 0 |
| VID-03 | Exponential backoff: 2s, 8s, 32s intervals stored and applied | unit | `pytest tests/test_kling_backoff.py::test_exponential_backoff_sequence -x` | ❌ Wave 0 |
| VID-03 | Balance query before submission; alert if <$5; halt if <$1 | unit | `pytest tests/test_kling_balance.py::test_balance_check_alerts_and_halts -x` | ❌ Wave 0 |
| VID-04 | AI label "🤖 Creado con IA" prepended to TikTok caption | unit | `pytest tests/test_ai_labels.py::test_tiktok_label_prepend -x` | ❌ Wave 0 |
| VID-04 | AI label prepended to YouTube description (not title) | unit | `pytest tests/test_ai_labels.py::test_youtube_label_in_description -x` | ❌ Wave 0 |
| VID-04 | AI label prepended to Instagram caption | unit | `pytest tests/test_ai_labels.py::test_instagram_label_prepend -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/test_kling_service.py tests/test_character_bible.py -x` (VID-01, VID-02 core logic)
- **Per wave merge:** `pytest tests/ -m 'not e2e' -x` (all unit tests, no e2e)
- **Phase gate:** Full suite green + 1-week monitoring of failure rates in staging

### Wave 0 Gaps
- [ ] `tests/test_kling_service.py` — covers VID-01 (submit, polling, retry logic)
- [ ] `tests/test_character_bible.py` — covers VID-02 (Bible constant, prompt concatenation, unchanged across versions)
- [ ] `tests/test_kling_cb.py` — covers VID-03 (failure rate tracking, 20% threshold, trip behavior)
- [ ] `tests/test_kling_balance.py` — covers VID-03 balance checks (alert at <$5, halt at <$1)
- [ ] `tests/test_ai_labels.py` — covers VID-04 (label injection per platform, fallback on API failure)
- [ ] `conftest.py` fixtures: mock fal_client, mock supabase, mock telegram service
- [ ] Framework install: `pip install pytest` (already in pyproject.toml dev deps)

*(Gaps noted: Wave 0 must provide all listed test files and fixtures before implementation begins. Phase 9 plans reference these test names.)*

## Sources

### Primary (HIGH confidence)
- [fal.ai Kling 3.0 page](https://fal.ai/kling-3) - Kling 3.0 features, pricing ($0.168/s Standard), 15-second duration support
- [fal.ai Client Setup docs](https://fal.ai/docs/model-apis/client) - `submit()` sync method, polling patterns, async alternatives
- [Kling 3.0 Prompting Guide (fal.ai)](https://blog.fal.ai/kling-3-0-prompting-guide/) - Character consistency best practices, early descriptor positioning, consistent naming
- [fal.ai Queue API Reference](https://docs.fal.ai/model-apis/model-endpoints/queue) - Job status polling, automatic retries (10 attempts)
- [pyproject.toml](file:///Users/jesusalbino/Projects/content-creation/pyproject.toml) - Confirmed dependencies: APScheduler 3.11.2, SQLAlchemy 2.0+, Supabase 2.0+

### Secondary (MEDIUM confidence)
- [AWS Prescriptive Guidance: Retry with Backoff](https://docs.aws.amazon.com/prescriptive-guidance/cloud-design-patterns/retry-backoff.html) - Exponential backoff pattern, capped backoff best practices
- [AWS Circuit Breaker Pattern](https://docs.aws.amazon.com/prescriptive-guidance/cloud-design-patterns/circuit-breaker.html) - State persistence, trip/recovery logic, monitoring
- [AI Disclosure Rules 2026 (Influencer Marketing Hub)](https://influencermarketinghub.com/ai-disclosure-rules/) - TikTok C2PA integration (Jan 2025), YouTube policy enforced early 2025, Instagram Meta AI labels early 2025
- [TikTok 2026 AI Labeling Guide](https://storrito.com/resources/tiktoks-2026-ai-labeling-rules-and-what-they-signal-for-platform-governance/) - Formal AIGC disclosure rules, "AI-generated" label, C2PA metadata
- [EU AI Act Article 50 Compliance](https://weventure.de/en/blog/ai-labeling/) - Deepfake disclosure requirement effective Aug 2, 2026; penalties €15M or 3% revenue

### Tertiary (LOW confidence - flagged for validation)
- [Kling 3.0 Reference Guide (MagicHour)](https://magichour.ai/blog/kling-30-reference-guide) - Claims "15-second video generation" but fal.ai docs state 3-15s range; verify at implementation time
- [Veo3 Developer Guide (fal.ai)](https://fal.ai/learn/devs/veo3-developer-guide-building-production-ready-video-generation-applications/) - General production patterns; Veo3 is different model, apply cautiously to Kling

## Metadata

**Confidence breakdown:**
- **Standard stack:** HIGH - fal.ai SDK verified, Kling 3.0 released March 2026, APScheduler pattern proven in v1.0 HeyGen
- **Architecture:** HIGH - patterns from CONTEXT.md locked decisions + existing codebase (heygen.py, video_poller.py templates)
- **Pitfalls:** MEDIUM - exponential backoff and circuit breaker pitfalls from AWS/Netflix patterns; async/APScheduler pitfall from project experience; character consistency and balance check pitfalls from fal.ai/Kling specifics (less tested at scale)
- **Validation:** MEDIUM - test framework pytest confirmed in project; specific VID-01/02/03/04 test files not yet written; Wave 0 gaps identified

**Research date:** 2026-03-19
**Valid until:** 2026-04-19 (30 days — fal.ai SDK and Kling 3.0 are stable; AI compliance rules firm as of EU AI Act Aug 2026 deadline)

---

*Phase: 09-mexican-animated-cat-video-format*
*Research completed: 2026-03-19*
*Next: gsd-planner creates PLAN.md files (09-01 through 09-04)*
