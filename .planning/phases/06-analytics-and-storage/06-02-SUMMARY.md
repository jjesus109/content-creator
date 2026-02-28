---
phase: 06-analytics-and-storage
plan: 02
subsystem: api
tags: [youtube, instagram, tiktok, facebook, analytics, metrics, tenacity, supabase]

# Dependency graph
requires:
  - phase: 06-01
    provides: platform_metrics table with retention_rate column; content_history storage lifecycle columns; TikTok OAuth settings fields
  - phase: 05-multi-platform-publishing
    provides: facebook_access_token and instagram_access_token in Settings; PublishingService._refresh_youtube_token()
provides:
  - MetricsService with fetch_and_store() and _fetch_youtube/_fetch_instagram/_fetch_tiktok/_fetch_facebook methods
  - AnalyticsService with compute_rolling_average(), check_and_alert_virality(), build_weekly_report()
  - sparkline(), format_virality_alert(), format_weekly_report() module-level functions
affects: [06-04, 06-05]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Optional supabase client in __init__ for testability — same pattern as SimilarityService and VideoStorageService"
    - "fail-soft platform fetchers — fetch_and_store catches all exceptions and returns None, never raises"
    - "tenacity @retry on each platform fetcher — 3 attempts, exponential backoff 2-30s, RequestException only"
    - "48h time-window virality de-duplication — NOT IS NULL; alert fires every harvest cycle while views > 5x rolling avg"

key-files:
  created:
    - src/app/services/metrics.py
    - src/app/services/analytics.py
  modified: []

key-decisions:
  - "Module-level settings = get_settings() removed from metrics.py — caused ValidationError at import time when env vars absent; settings accessed via self._settings inside methods only"
  - "check_and_alert_virality uses 48h time-window de-duplication (virality_alerted_at > NOW()-48h), NOT IS NULL — fires on every harvest cycle while viral (not just once)"
  - "Instagram uses 'views' metric in Insights API, NOT 'video_views' — video_views was deprecated in Graph API v21 (January 2025)"
  - "TikTok retention_rate set to None — video_duration not returned by query endpoint; partial harvest logged at WARNING"
  - "Facebook retention_rate computed as post_video_avg_time_watched / post_video_length * 100 when both fields non-zero"
  - "format_virality_alert is minimal: platform, video date, view count only — no baseline_avg, no pct_above threshold"
  - "Viral videos auto-marked Eternal on alert: is_eternal=True, storage_status=exempt — per CONTEXT.md lifecycle rule"

patterns-established:
  - "fail-soft API callers: each platform fetcher returns None dict on empty response (not raise), logs warning at appropriate level"
  - "Supabase distinct count via Python set comprehension — no .distinct() API; build set from all rows and take len()"

requirements-completed: [ANLX-01, ANLX-02, ANLX-03]

# Metrics
duration: 3min
completed: 2026-02-28
---

# Phase 6 Plan 02: Analytics Service Layer Summary

**MetricsService (4-platform API callers with fail-soft fetching) and AnalyticsService (rolling average, 48h virality detection, sparkline, weekly report) using Supabase platform_metrics table**

## Performance

- **Duration:** ~3 min
- **Started:** 2026-02-28T20:20:58Z
- **Completed:** 2026-02-28T20:24:06Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Created MetricsService with fetch_and_store() routing all 4 platforms (YouTube, Instagram, TikTok, Facebook); TikTok degrades gracefully with no token; Instagram uses non-deprecated `views` metric; retention_rate harvested for all platforms where API permits
- Created AnalyticsService with compute_rolling_average() (28-day window), check_and_alert_virality() with 48h time-window de-duplication, and build_weekly_report() with DB queries
- Created module-level pure functions: sparkline() (8-level Unicode block chars), format_virality_alert() (minimal: date + views only), format_weekly_report() (per-platform YT/IG/TK/FB breakdown, None pct_change as "N/A")

## Task Commits

Each task was committed atomically:

1. **Task 1: Create MetricsService (platform API callers for all 4 platforms)** - `bb99b89` (feat)
2. **Task 2: Create AnalyticsService (rolling average, virality, sparkline, report)** - `ddbe46c` (feat)

## Files Created/Modified

- `src/app/services/metrics.py` - MetricsService with fetch_and_store() routing to _fetch_youtube, _fetch_instagram, _fetch_tiktok, _fetch_facebook; all wrapped with tenacity retry
- `src/app/services/analytics.py` - AnalyticsService with rolling average, virality detection, weekly report; sparkline/format functions at module level

## Decisions Made

- Module-level `settings = get_settings()` was removed from metrics.py (auto-fixed during Task 1 before commit) — calling Settings() at import time causes ValidationError when env vars are absent (dev/test environments); settings accessed via `self._settings` in methods only
- `check_and_alert_virality` uses 48h time-window de-duplication (alerted_at > NOW()-48h), NOT IS NULL — this means the alert fires again on the next harvest cycle if the video stays viral
- Instagram Insights uses `views` metric, not `video_views` — `video_views` was deprecated in Meta Graph API v21 (January 2025)
- Facebook retention_rate computed from `post_video_avg_time_watched / post_video_length * 100`; set to None when either metric is absent or zero
- Viral videos auto-marked Eternal (is_eternal=True, storage_status=exempt) on alert fire, per CONTEXT.md lifecycle rule

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Removed module-level settings = get_settings() from metrics.py**
- **Found during:** Task 1 (MetricsService creation) — discovered during import verification
- **Issue:** `settings = get_settings()` at module level calls Settings() which requires all env vars via pydantic_settings. In dev/test without a .env file, this raises ValidationError on import even though no settings are needed at import time
- **Fix:** Removed the module-level call; settings are now accessed lazily via `self._settings = get_settings()` inside `__init__` only
- **Files modified:** src/app/services/metrics.py
- **Verification:** `uv run python -c "from app.services.metrics import MetricsService; print('OK')"` prints OK
- **Committed in:** bb99b89 (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - Bug)
**Impact on plan:** Fix was necessary for import-time correctness in environments without all env vars set. No scope creep.

## Issues Encountered

None beyond the auto-fixed module-level settings call.

## User Setup Required

None - no external service configuration required for this plan. Platform API credentials (facebook_access_token, instagram_access_token, YouTube OAuth, TikTok access token) must be populated in environment before harvest jobs run, but those were established in earlier phases.

## Next Phase Readiness

- MetricsService ready to be called by harvest_metrics_job (Plan 04)
- AnalyticsService.build_weekly_report() ready for weekly_report_job (Plan 05)
- check_and_alert_virality() ready to be called per-metric in harvest_metrics_job
- All 4 platform fetchers handle missing credentials gracefully — service starts cleanly without TikTok/Facebook tokens

## Self-Check: PASSED

- `src/app/services/metrics.py` — FOUND
- `src/app/services/analytics.py` — FOUND
- Commit `bb99b89` — FOUND (feat(06-02): create MetricsService)
- Commit `ddbe46c` — FOUND (feat(06-02): create AnalyticsService)

---
*Phase: 06-analytics-and-storage*
*Completed: 2026-02-28*
