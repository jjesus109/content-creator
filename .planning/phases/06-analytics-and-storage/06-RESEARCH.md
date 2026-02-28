# Phase 6: Analytics and Storage - Research

**Researched:** 2026-02-28
**Domain:** Platform API metrics harvesting, APScheduler job patterns, Cloudflare R2 storage, Telegram inline confirmation flows
**Confidence:** MEDIUM-HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

#### Weekly report (Sunday)
- Show both raw totals AND % change vs prior week
- Include "best performing platform" per video (highest views)
- Show top 5 videos by total views (across all platforms)
- Use simple sparklines (text-based: ▁▂▃▄▅▆▇█) for 4-week trend

#### Virality alert
- Threshold: 500% of rolling 4-week average (per-platform)
- Alert includes: platform, video title, current views, average baseline, percentage above baseline
- One alert per video per platform (no re-alerts unless it resets)
- Alert fires when metrics are harvested (48h after publish)

#### Storage lifecycle
- Hot → Warm → Cold/Deleted (3-tier) — not Supabase native tiers
- Warm = R2 (Cloudflare) — cost-effective cold storage. Hot remains in Supabase
- Viral/Eternal flag = exempt from all lifecycle transitions
- Creator must explicitly confirm before any file deletion
- Confirmation via Telegram inline button
- 24-hour timeout: if no confirmation, file is NOT deleted (safe default)
- When confirmed: delete from R2, update DB status

#### Metrics harvesting
- YouTube: YouTube Data API v3 (views, likes, comments)
- TikTok: TikTok for Developers API (views, shares, likes)
- Instagram: Instagram Basic Display API / Graph API (reach, saves, shares)
- Telegram channel: No API needed — post engagement tracked differently (internal DB)
- Store metrics in a dedicated table per platform per video
- Run at a fixed offset: 48h after publish timestamp

### Claude's Discretion
- How to schedule the 48h-after-publish harvest (job triggered by publish event, or cron that checks)
- Scheduling strategy for the Sunday report (APScheduler cron job)
- Database schema for metrics storage (normalization approach)
- How to handle rate limits and partial failures (retry logic)
- How to compute the rolling 4-week average efficiently
- Error handling when a platform API is unavailable
- Whether to use a separate metrics table per platform or a unified table
- Formatting details for the Telegram messages (beyond the decided fields)
- How to implement text sparklines

### Deferred Ideas (OUT OF SCOPE)
- Multi-user support
- Dashboard/web interface for analytics
- Automated content strategy recommendations based on analytics
- Cross-platform comparison charts (beyond text sparklines)
- Export to CSV/sheets
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| ANLX-01 | System harvests views, shares, and retention metrics from each platform 48 hours after publish | APScheduler DateTrigger pattern (already used in Phase 5 for publish_verify); YouTube Data API v3 videos.list statistics part; Instagram Graph API /{media-id}/insights; TikTok Display API /v2/video/query/ |
| ANLX-02 | Every Sunday, bot sends a weekly report to creator: growth summary and top-performing video | APScheduler CronTrigger day_of_week='sun'; unified platform_metrics table enabling cross-platform aggregation; send_alert_sync pattern from telegram.py |
| ANLX-03 | Bot sends an immediate Telegram alert if any video exceeds 500% of the average performance | Virality check runs inside harvest job; rolling 4-week average computed with SQL AVG over 28-day window; alert fires inline with harvest, not as separate job |
| ANLX-04 | Storage lifecycle auto-manages video files: hot (0-7d), warm (8-45d), cold delete (45d+) — videos flagged as Viral or Eternal are exempt from deletion | Cloudflare R2 via boto3 S3-compatible client; lifecycle cron job queries publish_events for age; Telegram InlineKeyboardButton confirmation before deletion with 24h timeout via DB state |
</phase_requirements>

---

## Summary

Phase 6 adds four orthogonal capabilities to a system that already has APScheduler, Supabase (PostgreSQL + Storage), and the python-telegram-bot stack. The foundation is solid and the patterns from Phases 4–5 map directly: DateTrigger jobs, sync Telegram wrappers, and inline keyboard callbacks are already proven.

The biggest complexity is **three distinct platform API authentication models**: YouTube uses OAuth2 refresh tokens (already implemented in PublishingService), Instagram uses Meta Graph API long-lived tokens (also already wired), and TikTok requires a user-delegated OAuth 2.0 flow via the Display API — the hardest of the three because TikTok requires an approved developer app and the creator must authorize once through a redirect flow. If TikTok API access is not available at implementation time, a graceful skip (log warning, no alert) is the correct default.

The storage lifecycle is **operationally clean**: Supabase hot → Cloudflare R2 warm → confirmed delete. R2 is S3-compatible, so boto3 (not in pyproject.toml yet) is the only new dependency. The Telegram confirmation + 24h timeout pattern mirrors the existing approval flow (Phase 4) and is well-understood.

**Primary recommendation:** Use a single unified `platform_metrics` table (not one table per platform) with a `platform` text column, mirror the `publish_events` schema style. Schedule 48h harvest via DateTrigger at publish time (same pattern as `verify_publish_job`). Schedule Sunday report via CronTrigger day_of_week='sun'. Implement sparklines as a pure Python function (8 chars, no library needed).

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| APScheduler | 3.11.2 (pinned in pyproject.toml) | DateTrigger for 48h harvest jobs; CronTrigger for Sunday report and lifecycle cron | Already installed and proven — Phase 5 uses DateTrigger for publish and verify jobs |
| supabase-py | >=2.0 (already installed) | PostgreSQL queries for metrics and lifecycle state; Storage download for R2 copy | Already installed — `get_supabase()` pattern is consistent across all services |
| boto3 | ~1.34 | S3-compatible Cloudflare R2 client for upload, copy, delete | Official Cloudflare recommendation; pure S3 API compatibility confirmed |
| requests | (transitive via supabase) | YouTube, Instagram, TikTok HTTP calls | Already used by PublishingService — no new dependency |
| tenacity | >=8.0 (already installed) | Retry with exponential backoff for rate-limited platform API calls | Already installed and used by PublishingService |
| python-telegram-bot | ==21.* (pinned) | InlineKeyboardButton for delete confirmation; send_alert_sync for report/alerts | Already installed; inline keyboard pattern already proven in Phase 4 approval flow |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytz | >=2024.1 (already installed) | Timezone-aware Sunday cron scheduling | Already used for audience_timezone in publishing |

### New Dependency (boto3 only)

```bash
uv add boto3
```

boto3 is the only net-new dependency. All other capabilities are already in the stack.

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| boto3 for R2 | cloudflare-python SDK | R2 has no native Python SDK; boto3 S3 compatibility is the official Cloudflare recommendation |
| Unified platform_metrics table | Separate table per platform | Separate tables require schema migration per new platform; unified table is consistent with publish_events pattern |
| DateTrigger for 48h harvest | CronTrigger that polls for due harvests | DateTrigger is simpler and avoids cron polling overhead; same pattern as verify_publish_job already in codebase |
| Pure Python sparklines | sparklines PyPI library | 8 Unicode chars + normalization is 5 lines of code; no external dependency needed |

---

## Architecture Patterns

### Recommended Project Structure

Phase 6 adds to existing structure:

```
src/app/
├── scheduler/jobs/
│   ├── harvest_metrics.py      # ANLX-01: 48h-after-publish harvest job
│   ├── weekly_report.py        # ANLX-02: Sunday report job
│   └── storage_lifecycle.py    # ANLX-04: Hot→Warm→Cold transition job
├── services/
│   ├── metrics.py              # Platform API calls (YouTube, Instagram, TikTok)
│   ├── storage_lifecycle.py    # R2 copy/delete operations via boto3
│   └── analytics.py           # Rolling average, virality check, sparkline, report formatting
├── telegram/handlers/
│   └── storage_confirm.py      # ANLX-04: InlineKeyboard delete confirmation handler
migrations/
└── 0006_analytics.sql          # platform_metrics table + lifecycle columns on content_history
```

### Pattern 1: 48h DateTrigger Harvest (ANLX-01)

**What:** When a publish_events row is inserted with status='published', schedule a DateTrigger job 48 hours later.
**When to use:** Exactly matches Phase 5's verify_publish_job pattern — schedule at publish time.

**Where to trigger it:** Inside `publish_to_platform_job` after inserting the 'published' row:

```python
# Source: existing platform_publish.py pattern (Phase 5)
from apscheduler.triggers.date import DateTrigger
from datetime import datetime, timedelta, timezone

harvest_run_at = datetime.now(tz=timezone.utc) + timedelta(hours=48)
harvest_job_id = f"harvest_{content_history_id}_{platform}"
_scheduler.add_job(
    harvest_metrics_job,
    trigger=DateTrigger(run_date=harvest_run_at),
    args=[content_history_id, platform, external_post_id],
    id=harvest_job_id,
    name=f"Harvest {platform} metrics for {content_history_id[:8]}",
    replace_existing=True,
)
```

**Args pattern:** All args must be strings (picklable for SQLAlchemyJobStore) — same constraint as Phase 5.

### Pattern 2: Sunday Report CronTrigger (ANLX-02)

**What:** Register a weekly CronTrigger in registry.py for Sunday at 9 AM audience timezone.
**When to use:** Consistent with weekly_mood_prompt_job pattern.

```python
# Source: existing registry.py pattern
scheduler.add_job(
    weekly_analytics_report_job,
    trigger="cron",
    day_of_week="sun",
    hour=9,
    minute=0,
    timezone=TIMEZONE,
    id="weekly_analytics_report",
    name="Weekly analytics report",
    replace_existing=True,
)
```

### Pattern 3: YouTube Metrics Harvest

```python
# Source: YouTube Data API v3 docs (https://developers.google.com/youtube/v3/docs/videos/list)
# Quota cost: 1 unit per call. Daily limit: 10,000 units. One video = 1 unit.
access_token = self._refresh_youtube_token()  # reuse existing method in PublishingService
response = requests.get(
    "https://www.googleapis.com/youtube/v3/videos",
    params={
        "part": "statistics",
        "id": video_id,
        "access_token": access_token,
    },
    timeout=15,
)
response.raise_for_status()
items = response.json().get("items", [])
if items:
    stats = items[0]["statistics"]
    views = int(stats.get("viewCount", 0))
    likes = int(stats.get("likeCount", 0))
    comments = int(stats.get("commentCount", 0))
```

**Available statistics fields:** viewCount, likeCount, favoriteCount, commentCount (dislikeCount was hidden in 2021).

### Pattern 4: Instagram Metrics Harvest

```python
# Source: Instagram Graph API /{ig-media-id}/insights
# Required permission: instagram_manage_insights
# Token: existing instagram_access_token from settings
# Note: "views" replaces deprecated "video_views" as of Graph API v21 (Jan 2025)
response = requests.get(
    f"https://graph.instagram.com/v18.0/{media_id}/insights",
    params={
        "metric": "views,reach,saved,shares",
        "access_token": settings.instagram_access_token,
    },
    timeout=15,
)
response.raise_for_status()
data = {item["name"]: item["values"][0]["value"]
        for item in response.json().get("data", [])}
views = data.get("views", 0)
reach = data.get("reach", 0)
saves = data.get("saved", 0)
shares = data.get("shares", 0)
```

**IMPORTANT:** As of January 2025, `video_views` is deprecated for non-Reels in Graph API v21+. Use `views` for Reels. The account must have >1,000 followers for insights to be available.

### Pattern 5: TikTok Metrics Harvest

```python
# Source: TikTok Display API /v2/video/query/
# Requires: user OAuth 2.0 access token (creator grants permission to the app once)
# Scope required: video.list
# Note: TikTok Research API requires institutional approval (universities only)
# Use Display API for creator's own videos
response = requests.post(
    "https://open.tiktokapis.com/v2/video/query/",
    headers={"Authorization": f"Bearer {settings.tiktok_access_token}"},
    json={
        "filters": {"video_ids": [video_id]},
        "fields": ["view_count", "like_count", "comment_count", "share_count"],
    },
    timeout=15,
)
response.raise_for_status()
videos = response.json().get("data", {}).get("videos", [])
if videos:
    v = videos[0]
    views = v.get("view_count", 0)
    likes = v.get("like_count", 0)
    shares = v.get("share_count", 0)
```

**IMPORTANT:** TikTok Display API requires the creator to authorize through OAuth 2.0 redirect flow once. The resulting `access_token` + `refresh_token` must be stored as settings. This is different from the YouTube/Instagram credentials already in place.

### Pattern 6: Cloudflare R2 boto3 Client

```python
# Source: https://developers.cloudflare.com/r2/examples/aws/boto3/
import boto3

def get_r2_client(settings):
    return boto3.client(
        service_name="s3",
        endpoint_url=f"https://{settings.r2_account_id}.r2.cloudflarestorage.com",
        aws_access_key_id=settings.r2_access_key_id,
        aws_secret_access_key=settings.r2_secret_access_key,
        region_name="auto",
    )

# Copy from Supabase URL to R2 (download then upload)
import io
video_bytes = requests.get(supabase_video_url, timeout=300).content
r2.upload_fileobj(
    io.BytesIO(video_bytes),
    Bucket=settings.r2_bucket_name,
    Key=r2_key,          # e.g. "videos/2026-01-15.mp4"
    ExtraArgs={"ContentType": "video/mp4"},
)

# Delete from R2
r2.delete_object(Bucket=settings.r2_bucket_name, Key=r2_key)
```

**R2 credentials needed (new Settings fields):**
- `r2_account_id` — Cloudflare account ID
- `r2_access_key_id` — R2 API token access key
- `r2_secret_access_key` — R2 API token secret key
- `r2_bucket_name` — R2 bucket name (e.g. "content-warm-storage")

**TikTok credentials needed (new Settings fields):**
- `tiktok_access_token` — OAuth 2.0 user access token (refreshable)
- `tiktok_refresh_token` — For refresh when access token expires

### Pattern 7: Text Sparklines (Pure Python)

```python
# Source: Unicode block elements U+2581–U+2588 (8 levels)
# No library needed — 5 lines of code

SPARK_CHARS = "▁▂▃▄▅▆▇█"

def sparkline(values: list[int]) -> str:
    """Convert a list of up to 4 integers to an 8-level sparkline string."""
    if not values or max(values) == 0:
        return "▁" * len(values)
    mn, mx = min(values), max(values)
    if mn == mx:
        return "▄" * len(values)
    return "".join(
        SPARK_CHARS[int((v - mn) / (mx - mn) * 7)]
        for v in values
    )

# Example: sparkline([100, 250, 800, 1200]) → "▁▂▅█"
```

### Pattern 8: Rolling 4-Week Average (SQL)

```sql
-- Compute rolling average for virality check: average views over the 4 weeks prior to harvest
-- Source: PostgreSQL window function / aggregate with date filter
SELECT AVG(views) AS rolling_avg
FROM platform_metrics
WHERE content_history_id = $1
  AND platform = $2
  AND harvested_at >= NOW() - INTERVAL '28 days'
  AND harvested_at < NOW();
```

**For virality check:** if `current_views >= rolling_avg * 5.0` → fire alert.

**For report's % change:** compare this week's metrics to previous week's using a simple date range filter on `harvested_at`.

### Pattern 9: Telegram Delete Confirmation (ANLX-04)

```python
# Source: Phase 4 approval_flow.py pattern (InlineKeyboardButton + CallbackQueryHandler)
# Callback data prefix must stay under 64 bytes total
PREFIX_STORAGE_CONFIRM = "stor_confirm:"   # 13 chars + 36-char UUID = 49 bytes
PREFIX_STORAGE_CANCEL  = "stor_cancel:"   # 12 chars + 36-char UUID = 48 bytes

keyboard = InlineKeyboardMarkup([[
    InlineKeyboardButton("Confirmar Eliminacion", callback_data=f"stor_confirm:{content_history_id}"),
    InlineKeyboardButton("Cancelar",              callback_data=f"stor_cancel:{content_history_id}"),
]])
```

**24h timeout implementation:** Store `deletion_requested_at` timestamptz in `content_history`. The lifecycle cron checks: if `deletion_requested_at < NOW() - INTERVAL '24 hours'` AND no confirmation recorded → skip deletion, log safe default. The confirmation handler checks idempotency before deleting.

### Anti-Patterns to Avoid

- **Scheduling a separate cron to check for 48h elapsed:** Use DateTrigger at publish time — same pattern as verify_publish_job. A polling cron adds complexity with no benefit.
- **One metrics table per platform:** Creates schema drift, complicates the weekly report query. Use a single table with a `platform` column — mirrors publish_events.
- **Storing TikTok Research API credentials:** That API requires institutional/academic approval. Use the Display API for the creator's own videos.
- **Silently skipping deletion on timeout and never cleaning up:** The lifecycle cron must reset `deletion_requested_at = NULL` after the 24h timeout so the next lifecycle run can re-prompt.
- **Downloading video bytes into memory before R2 upload for large files:** Use `upload_fileobj` with streaming `requests.get(..., stream=True)` for files >100 MB to avoid OOM.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| OAuth2 token refresh for YouTube | Custom refresh logic | Reuse `_refresh_youtube_token()` in PublishingService | Already implemented and tested in Phase 5 |
| Exponential backoff on platform API errors | Custom sleep loop | `tenacity` with `retry_if_exception(_is_retryable)` | Already installed; same pattern as PublishingService |
| S3-compatible R2 client | Custom HTTP calls to R2 | `boto3` with `endpoint_url` | Cloudflare's official recommendation; handles multipart automatically for large files |
| Sparkline rendering | External `sparklines` library | 5-line pure Python function with `▁▂▃▄▅▆▇█` | No new dependency; 8 Unicode characters cover all needs |
| Scheduler setup | New BackgroundScheduler | Existing `_scheduler` from `video_poller.py` (injected by registry.py) | All Phase 5 jobs reuse this — follow the same `set_scheduler()` injection pattern |
| Telegram async/sync bridge | New event loop management | Existing `send_alert_sync()` pattern from `telegram.py` | All scheduler jobs already use this pattern |

**Key insight:** Phase 6 adds data and jobs on top of an already-running system. Follow existing patterns exactly — don't introduce new scheduler setup, new async patterns, or new Telegram helpers unless required.

---

## Common Pitfalls

### Pitfall 1: TikTok API Approval Requirement
**What goes wrong:** Trying to use the TikTok Research API (requires academic/institutional approval) instead of the Display API (for creators' own content).
**Why it happens:** The Research API endpoints appear in documentation searches for "TikTok video metrics."
**How to avoid:** Use `https://open.tiktokapis.com/v2/video/query/` (Display API) with the creator's own OAuth 2.0 access token. The creator must authorize the app once via OAuth redirect.
**Warning signs:** API returning "scope_not_authorized" or "research application pending" errors.

### Pitfall 2: Instagram `video_views` Deprecation (Jan 2025)
**What goes wrong:** Requesting `video_views` metric in Instagram Graph API v21+ returns an error or empty data.
**Why it happens:** Meta deprecated `video_views` for non-Reels content in Graph API v21 (January 8, 2025).
**How to avoid:** Use `views` as the metric name for Reels. The `views` metric counts plays for Reels.
**Warning signs:** API returning error on `video_views` field or empty `data` array.

### Pitfall 3: Instagram Insights Follower Threshold
**What goes wrong:** Instagram insights endpoint returns empty data for accounts with fewer than 1,000 followers.
**Why it happens:** Meta restricts insights to business accounts above this threshold.
**How to avoid:** Implement graceful degradation — if insights return empty, log a warning and store NULL metrics rather than failing the harvest job.
**Warning signs:** Empty `data` array with HTTP 200 response.

### Pitfall 4: YouTube Quota Exhaustion
**What goes wrong:** videos.list quota cost is 1 unit per request; 10,000 units/day default. With multiple videos across history, daily harvest could exhaust quota.
**Why it happens:** Harvesting ALL historical metrics daily (not just 48h post-publish) hits quota.
**How to avoid:** Only harvest at the scheduled 48h DateTrigger point. Do NOT add ongoing daily re-harvest of all videos — that is out of scope and quota-expensive.
**Warning signs:** HTTP 403 with `quotaExceeded` reason from YouTube API.

### Pitfall 5: APScheduler Job Args Must Be Picklable Strings
**What goes wrong:** Passing non-string args (UUIDs, datetimes) to DateTrigger jobs causes SQLAlchemyJobStore serialization failures.
**Why it happens:** APScheduler serializes job args via pickle; UUID/datetime objects can fail depending on jobstore version.
**How to avoid:** Pass all args as `str` — same constraint documented in Phase 5's `verify_publish_job` and `publish_to_platform_job`. Cast UUID to string with `str(uuid_value)`.
**Warning signs:** Jobs disappear from store after restart, `AttributeError` during deserialization.

### Pitfall 6: R2 ACL / Tagging Not Supported
**What goes wrong:** Using `ACL='public-read'` or object tagging in boto3 calls to R2 raises errors.
**Why it happens:** R2 does not implement ACL or tagging features of S3 (confirmed in R2 API docs).
**How to avoid:** Never pass `ACL=`, `Tagging=`, or `ChecksumAlgorithm=` parameters. R2 bucket access is controlled at the bucket level (not object level).
**Warning signs:** `AccessControlListNotSupported` error or silent ignoring of tagging.

### Pitfall 7: 24h Deletion Timeout — Cron Re-prompt Loop
**What goes wrong:** Lifecycle cron re-prompts the creator every run after a 24h timeout, flooding them with deletion requests.
**Why it happens:** The timeout logic doesn't reset the `deletion_requested_at` column after expiry.
**How to avoid:** When the cron detects a timed-out request (>24h with no confirmation), reset `deletion_requested_at = NULL` and `storage_status = 'warm'`. The next lifecycle run will treat it as warm (not pending deletion) and only re-prompt when it crosses the 45d threshold again.
**Warning signs:** Multiple deletion confirmation messages for the same video in Telegram.

### Pitfall 8: Virality Alert De-duplication
**What goes wrong:** Every harvest fires a virality alert, spamming the creator for the same viral video on every re-harvest.
**Why it happens:** 48h harvest is a one-shot DateTrigger, so de-duplication is naturally handled. But if harvest logic is ever called more than once, the check must be idempotent.
**How to avoid:** Store `virality_alerted_at` in `platform_metrics` or a dedicated column. Before sending alert, check `WHERE content_history_id = $1 AND platform = $2 AND virality_alerted_at IS NOT NULL`.
**Warning signs:** Duplicate Telegram alerts for the same video.

---

## Code Examples

### Weekly Report Message Format

```python
# Source: decided fields from CONTEXT.md + existing Telegram message patterns
def format_weekly_report(top_videos: list[dict], platform_totals: dict) -> str:
    SPARK_CHARS = "▁▂▃▄▅▆▇█"

    def sparkline(values):
        if not values or max(values) == 0:
            return "▁" * len(values)
        mn, mx = min(values), max(values)
        if mn == mx:
            return "▄" * len(values)
        return "".join(SPARK_CHARS[int((v - mn) / (mx - mn) * 7)] for v in values)

    lines = ["REPORTE SEMANAL\n"]
    for i, v in enumerate(top_videos[:5], 1):
        spark = sparkline(v["last_4_weeks_views"])
        pct = f"+{v['pct_change']:.0f}%" if v['pct_change'] >= 0 else f"{v['pct_change']:.0f}%"
        best_platform = v["best_platform"]
        lines.append(
            f"{i}. {v['topic_summary'][:40]}\n"
            f"   {spark} {v['total_views']:,} views ({pct}) | Mejor: {best_platform}"
        )
    return "\n".join(lines)
```

### Virality Alert Message Format

```python
# Source: decided fields from CONTEXT.md
def format_virality_alert(
    platform: str, topic_summary: str, current_views: int,
    baseline_avg: float, pct_above: float,
) -> str:
    return (
        f"ALERTA DE VIRALIDAD\n\n"
        f"Plataforma: {platform.upper()}\n"
        f"Video: {topic_summary[:60]}\n"
        f"Vistas actuales: {current_views:,}\n"
        f"Promedio base (4 sem): {int(baseline_avg):,}\n"
        f"Sobre la media: +{pct_above:.0f}%"
    )
```

### Storage Deletion Confirmation Message

```python
# Source: Phase 4 approval_flow.py pattern
async def send_deletion_confirmation_request(
    content_history_id: str, video_path: str, days_old: int
) -> None:
    bot = get_telegram_bot()
    settings = get_settings()
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("Confirmar Eliminacion", callback_data=f"stor_confirm:{content_history_id}"),
        InlineKeyboardButton("Cancelar",              callback_data=f"stor_cancel:{content_history_id}"),
    ]])
    await bot.send_message(
        chat_id=settings.telegram_creator_id,
        text=(
            f"ALMACENAMIENTO: Video elegible para eliminacion\n\n"
            f"Video: {video_path}\n"
            f"Edad: {days_old} dias\n\n"
            "Si no confirmas en 24 horas, el archivo NO sera eliminado."
        ),
        reply_markup=keyboard,
    )
```

---

## Database Schema (Migration 0006)

### Recommended: Single Unified Table

```sql
-- Migration 0006: Analytics and Storage — Phase 6
-- platform_metrics: stores per-platform per-video metrics from 48h harvest
-- content_history additions: storage_status, storage_tier, deletion flags

CREATE TABLE IF NOT EXISTS platform_metrics (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at          timestamptz DEFAULT now() NOT NULL,
    harvested_at        timestamptz NOT NULL,
    content_history_id  uuid NOT NULL REFERENCES content_history(id),
    platform            text NOT NULL CHECK (platform IN ('youtube', 'instagram', 'tiktok', 'facebook')),
    external_post_id    text,           -- Platform-native ID (same as publish_events.external_post_id)
    views               integer,
    likes               integer,
    shares              integer,
    comments            integer,
    reach               integer,        -- Instagram-specific (unique accounts)
    saves               integer,        -- Instagram-specific
    virality_alerted_at timestamptz     -- NULL = not alerted; set when alert fires
);

CREATE INDEX IF NOT EXISTS platform_metrics_content_history_idx
    ON platform_metrics(content_history_id);

CREATE INDEX IF NOT EXISTS platform_metrics_platform_harvested_idx
    ON platform_metrics(platform, harvested_at);

-- Storage lifecycle columns on content_history
ALTER TABLE content_history
    ADD COLUMN IF NOT EXISTS storage_status       text DEFAULT 'hot'
        CHECK (storage_status IN ('hot', 'warm', 'pending_deletion', 'deleted', 'exempt')),
    ADD COLUMN IF NOT EXISTS r2_key               text,           -- R2 object key when storage_status = 'warm'
    ADD COLUMN IF NOT EXISTS storage_tier_set_at  timestamptz,    -- When current tier was set
    ADD COLUMN IF NOT EXISTS deletion_requested_at timestamptz,   -- When deletion confirmation was sent
    ADD COLUMN IF NOT EXISTS is_viral             boolean DEFAULT false,
    ADD COLUMN IF NOT EXISTS is_eternal           boolean DEFAULT false;
```

**Rationale for unified table:** The weekly report query (top 5 by total views across all platforms) requires `GROUP BY content_history_id, SUM(views)` across platforms — this is trivial with one table and would require UNION ALL with separate tables. The `platform` CHECK constraint ensures no invalid data.

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Instagram `video_views` metric | Use `views` for Reels | January 8, 2025 (Graph API v21) | Must use `views` not `video_views` in insights requests |
| TikTok v1 API (`/video/query/`) | TikTok v2 Display API (`/v2/video/query/`) | 2023-2024 migration | Use v2 endpoint at `open.tiktokapis.com` |
| R2 requires custom HTTP client | R2 fully supports boto3 S3 | Always | Use boto3 with `endpoint_url` — ACL and tagging not supported |
| YouTube dislike counts public | dislikeCount hidden | December 2021 | Don't attempt to read `dislikeCount` — field exists but is always 0 |
| Supabase Storage for all tiers | Supabase hot + R2 warm | Phase 6 decision | R2 has zero egress fees; $0.015/GB-month vs Supabase's higher cost for warm files |

**Deprecated/outdated:**
- `video_views` on Instagram Graph API: deprecated January 2025 for non-Reels, replaced by `views`
- TikTok API v1 (`open-api.tiktok.com`): use v2 at `open.tiktokapis.com`
- YouTube `dislikeCount`: always 0 since December 2021, do not surface to creator

---

## Open Questions

1. **TikTok OAuth 2.0 initial authorization**
   - What we know: TikTok Display API requires user-delegated OAuth 2.0; the creator must authorize once through a redirect URL
   - What's unclear: Whether a Telegram-only bot can drive this flow, or if a minimal one-time web page is needed for the redirect callback
   - Recommendation: Implement a minimal one-time `/auth/tiktok` FastAPI route for the initial OAuth callback. Store resulting access_token + refresh_token in settings/environment. After first authorization, token refresh is programmatic. If this is too complex at planning time, treat TikTok harvest as gracefully-degraded (log warning, store NULL metrics).

2. **Supabase Storage download for R2 copy — video size**
   - What we know: Videos stored as `videos/YYYY-MM-DD.mp4` in Supabase; download returns bytes
   - What's unclear: Typical video file sizes — if >100 MB, streaming to R2 is better than loading all bytes
   - Recommendation: Use `requests.get(video_url, stream=True)` and pass the response to `boto3.upload_fileobj` to avoid OOM. Always stream regardless of size.

3. **Instagram insights follower threshold**
   - What we know: Insights unavailable for accounts with <1,000 followers
   - What's unclear: Whether the test account crosses this threshold
   - Recommendation: Implement graceful degradation — store NULL metrics and log warning, do not fail the harvest job.

---

## Sources

### Primary (HIGH confidence)

- YouTube Data API v3 docs — `https://developers.google.com/youtube/v3/docs/videos/list` — statistics part, quota cost (1 unit/call)
- Cloudflare R2 boto3 docs — `https://developers.cloudflare.com/r2/examples/aws/boto3/` — endpoint_url pattern, S3 compatibility
- Cloudflare R2 upload docs — `https://developers.cloudflare.com/r2/objects/upload-objects/` — upload_fileobj pattern, multipart threshold
- Cloudflare R2 S3 API docs — `https://developers.cloudflare.com/r2/api/s3/api/` — confirmed ACL/tagging NOT supported
- TikTok Display API docs — `https://developers.tiktok.com/doc/tiktok-api-v2-video-query` — v2 endpoint, fields list
- TikTok Content Posting API docs — `https://developers.tiktok.com/doc/content-posting-api-reference-get-video-status` — confirmed NO engagement metrics from this endpoint
- APScheduler CronTrigger docs — `https://apscheduler.readthedocs.io/en/3.x/modules/triggers/cron.html` — day_of_week='sun' pattern
- APScheduler DateTrigger docs — `https://apscheduler.readthedocs.io/en/3.x/modules/triggers/date.html` — run_date + timedelta pattern
- Existing codebase: `src/app/scheduler/jobs/platform_publish.py`, `publish_verify.py`, `weekly_mood.py`, `registry.py`, `services/publishing.py`, `services/telegram.py`

### Secondary (MEDIUM confidence)

- Instagram Graph API Reels metrics — WebSearch + Supermetrics docs — `views` replaces `video_views` post-Jan 2025; `reach`, `saved`, `shares` available via `/{media-id}/insights`
- R2 pricing — `https://developers.cloudflare.com/r2/pricing/` — $0.015/GB-month, zero egress
- YouTube quota guide — `https://developers.google.com/youtube/v3/determine_quota_cost` — 10,000 units/day default, 1 unit for videos.list
- TikTok Research API — academic-only, requires institutional approval — verified via `https://developers.tiktok.com/doc/research-api-get-started`

### Tertiary (LOW confidence)

- Instagram `views` metric name for Reels (vs `video_views`) — sourced from third-party Supermetrics docs and community posts; should be verified against official Meta Graph API docs before implementation
- TikTok access token refresh mechanism — not fully verified against official docs; assume standard OAuth 2.0 PKCE flow

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries already installed except boto3; all patterns proven in Phases 4–5
- Architecture: HIGH — DateTrigger + CronTrigger patterns are exact copies of Phase 5 patterns
- Platform API fields: MEDIUM — YouTube confirmed HIGH; Instagram metric names MEDIUM (deprecation verified); TikTok v2 endpoint MEDIUM
- Pitfalls: MEDIUM-HIGH — Instagram deprecation and TikTok approval requirements verified from multiple sources
- R2 integration: HIGH — official Cloudflare docs confirm boto3 S3 compatibility

**Research date:** 2026-02-28
**Valid until:** 2026-03-28 (30-day window; Meta Graph API changes frequently — re-verify Instagram metric names before implementation)
