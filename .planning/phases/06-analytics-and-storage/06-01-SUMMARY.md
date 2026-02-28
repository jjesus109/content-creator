---
phase: 06-analytics-and-storage
plan: 01
subsystem: database
tags: [postgres, supabase, pydantic-settings, tiktok, analytics, storage-lifecycle]

# Dependency graph
requires:
  - phase: 05-multi-platform-publishing
    provides: content_history table with platform publish columns; publish_events table
provides:
  - platform_metrics table with 14 columns including retention_rate for weekly report ranking
  - content_history storage lifecycle columns (storage_status, is_viral, is_eternal, storage_tier_set_at, deletion_requested_at)
  - TikTok Display API OAuth settings fields (tiktok_access_token, tiktok_refresh_token) with empty-string defaults
affects: [06-02, 06-03, 06-04, 06-05]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Empty-string defaults for optional OAuth credentials — harvester checks 'if not settings.tiktok_access_token' for graceful degradation"
    - "Append-only metrics rows — one row per platform per harvest cycle, no UNIQUE constraint, idempotency via job ID deduplication"
    - "Storage lifecycle as DB label only — warm tier keeps file in Supabase Storage, cold deletion removes from Supabase Storage via supabase.storage.from_().remove()"

key-files:
  created:
    - migrations/0006_analytics.sql
  modified:
    - src/app/settings.py

key-decisions:
  - "retention_rate float column in platform_metrics used by weekly report to rank top performer — not just views/likes"
  - "No r2_key column and no R2/Cloudflare credentials — warm tier is DB label only, files stay in Supabase Storage"
  - "storage_status CHECK includes 'exempt' for viral/eternal videos that must never be deleted"
  - "No UNIQUE constraint on (content_history_id, platform) — harvest job inserts one row per harvest cycle; idempotency handled at job level"
  - "tiktok_access_token and tiktok_refresh_token use empty-string defaults — Settings loads without TikTok env vars set; harvester skips TikTok with logged warning"

patterns-established:
  - "Migration naming: 000N_descriptive.sql with header comment explaining architecture decisions"
  - "Graceful credential degradation: optional API credentials default to empty string; downstream jobs check and skip with warning"

requirements-completed: [ANLX-01, ANLX-04]

# Metrics
duration: 1min
completed: 2026-02-28
---

# Phase 6 Plan 01: DB Migration and Settings for Analytics Summary

**platform_metrics table (14 columns, 2 indexes) + content_history storage lifecycle columns + TikTok OAuth settings fields with graceful-degradation empty-string defaults**

## Performance

- **Duration:** ~2 min
- **Started:** 2026-02-28T20:16:52Z
- **Completed:** 2026-02-28T20:18:18Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Created migration 0006_analytics.sql with platform_metrics table (14 columns including retention_rate float for weekly report ranking) and two indexes
- Added 5 storage lifecycle columns to content_history (storage_status with exempt value for viral/eternal, storage_tier_set_at, deletion_requested_at, is_viral, is_eternal)
- Extended Settings with tiktok_access_token and tiktok_refresh_token fields (empty-string defaults; no R2/Cloudflare fields added)

## Task Commits

Each task was committed atomically:

1. **Task 1: Write migration 0006_analytics.sql** - `370baad` (feat)
2. **Task 2: Extend Settings with TikTok credentials only (no R2)** - `e81361d` (feat)

## Files Created/Modified

- `migrations/0006_analytics.sql` - CREATE TABLE platform_metrics with 14 columns + 2 indexes + 5 ALTER TABLE columns on content_history
- `src/app/settings.py` - Added tiktok_access_token and tiktok_refresh_token fields with empty-string defaults

## Decisions Made

- No R2/Cloudflare credentials added to Settings per locked CONTEXT.md decision: warm tier is a DB label only, no object storage copy needed
- `storage_status` CHECK constraint includes `'exempt'` as valid status for viral/eternal videos that must never be deleted
- No UNIQUE constraint on (content_history_id, platform) in platform_metrics: harvest job is one-row-per-cycle; idempotency enforced at job level via job ID deduplication
- TikTok fields use empty-string defaults so Settings loads cleanly when TikTok env vars are absent — metrics harvester degrades gracefully

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required for this plan. TikTok OAuth credentials (TIKTOK_ACCESS_TOKEN, TIKTOK_REFRESH_TOKEN) will be populated by the /auth/tiktok route built in a later plan.

## Next Phase Readiness

- Migration 0006_analytics.sql ready to apply to Supabase — all downstream Phase 6 jobs can reference platform_metrics and the new content_history columns
- Settings now exposes TikTok credentials for the metrics harvester (06-02)
- All 4 platform credentials already in Settings from Phase 5 (instagram_access_token, facebook_access_token, youtube_client_id/secret/refresh_token) — harvester can use them immediately

---
*Phase: 06-analytics-and-storage*
*Completed: 2026-02-28*
