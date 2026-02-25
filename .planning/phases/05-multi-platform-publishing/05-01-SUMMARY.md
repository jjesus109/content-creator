---
phase: 05-multi-platform-publishing
plan: "01"
subsystem: database
tags: [postgresql, pydantic, ayrshare, tenacity, migrations, settings]

requires:
  - phase: 04-telegram-approval-loop
    provides: content_history table with post_copy column; approval flow foundation
  - phase: 01-foundation
    provides: Settings BaseSettings pattern; Pydantic env var loading

provides:
  - publish_events table (append-only log of publishing outcomes per platform)
  - 4 platform copy columns on content_history (tiktok, instagram, facebook, youtube)
  - ayrshare_api_key setting (required, no default)
  - audience_timezone setting (default US/Eastern)
  - 4 peak_hour_* settings with research-backed defaults
  - tenacity production dependency for retry logic

affects:
  - 05-02 (PublishJob reads publish_events, needs ayrshare_api_key)
  - 05-03 (PostCopyService writes to platform copy columns)
  - 05-04 (VerificationJob queries publish_events by content_history_id + platform)

tech-stack:
  added: [tenacity>=8.0]
  patterns:
    - "publish_events is append-only — never UPDATE rows, only INSERT new events"
    - "platform copy columns on content_history — generated before Telegram delivery, read at publish time"
    - "ayrshare_api_key required with no default — Pydantic raises at startup if AYRSHARE_API_KEY not set"

key-files:
  created:
    - migrations/0005_publishing.sql
  modified:
    - src/app/settings.py
    - pyproject.toml

key-decisions:
  - "publish_events uses append-only insert pattern — no UPDATE; verification job inserts new 'verified' or 'verify_failed' row rather than updating 'published' row"
  - "4 platform copy columns on content_history (not a separate table) — Phase 5 reads them at publish time alongside video_url and post_copy"
  - "ayrshare_api_key has no default — Pydantic raises clear ValidationError at startup if env var missing, same pattern as heygen_api_key"
  - "audience_timezone defaults to US/Eastern — matches target audience; overridable via Railway env var without redeploy"
  - "tenacity added to [project].dependencies (not dev) — used by PublishJob retry logic in production"

patterns-established:
  - "Peak hour defaults: TikTok 19 (7PM), Instagram 11 (11AM), Facebook 13 (1PM), YouTube 12 (12PM)"
  - "status CHECK constraint: published → failed → verified/verify_failed lifecycle"

requirements-completed: [PUBL-01, PUBL-02]

duration: 2min
completed: 2026-02-25
---

# Phase 5 Plan 01: Publishing Schema Foundation Summary

**publish_events append-only table + 4 platform copy columns on content_history + Ayrshare settings with tenacity production dependency**

## Performance

- **Duration:** 2 min
- **Started:** 2026-02-25T18:11:45Z
- **Completed:** 2026-02-25T18:13:07Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- Created `migrations/0005_publishing.sql` with publish_events table (9 columns, platform+status CHECK constraints, 2 indexes) and 4 platform copy columns on content_history
- Extended `src/app/settings.py` with 6 publishing fields: ayrshare_api_key (required), audience_timezone, and 4 peak_hour_* defaults
- Added tenacity>=8.0 to production dependencies in pyproject.toml

## Task Commits

Each task was committed atomically:

1. **Task 1: Migration 0005 — publish_events table + platform copy columns** - `7435ab1` (feat)
2. **Task 2: Settings extension + tenacity dependency** - `ad7ee9f` (feat)

**Plan metadata:** (docs commit below)

## Files Created/Modified
- `migrations/0005_publishing.sql` - publish_events table, 4 platform copy columns on content_history, 2 indexes
- `src/app/settings.py` - 6 new publishing fields: ayrshare_api_key, audience_timezone, peak_hour_tiktok/instagram/facebook/youtube
- `pyproject.toml` - tenacity>=8.0 added to [project].dependencies (production, not dev)

## Decisions Made
- `publish_events` is append-only — verification job inserts new verified/verify_failed rows rather than updating published rows; enables full audit trail
- 4 platform copy columns live on `content_history` (not a separate table) — consistent with existing `post_copy` pattern from Phase 4; publish job reads them alongside video_url
- `ayrshare_api_key` has no default — Pydantic raises ValidationError at startup if `AYRSHARE_API_KEY` env var not set; same pattern as heygen_api_key
- `audience_timezone` defaults to `US/Eastern` — matches creator's target audience; overridable via Railway env var
- `tenacity` in production deps — used by PublishJob HTTP retry logic at runtime, not a dev/test tool

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None — Settings model field verification ran successfully using project venv at `.venv/bin/python` with `PYTHONPATH=src`.

## User Setup Required
**AYRSHARE_API_KEY must be added to Railway environment variables** before the publish job can run. Get the key from the Ayrshare dashboard under API Keys. The service will fail at startup with a clear Pydantic ValidationError if this env var is missing.

## Next Phase Readiness
- Migration 0005 ready to apply in Supabase SQL editor
- Settings foundation complete — all Phase 5 services can call `get_settings().ayrshare_api_key`
- tenacity available for PublishJob retry decorator
- Blockers: AYRSHARE_API_KEY must be set in Railway env vars before Phase 5 goes live

---
*Phase: 05-multi-platform-publishing*
*Completed: 2026-02-25*
