---
phase: 04-telegram-approval-loop
plan: "01"
subsystem: database
tags: [postgres, sql, migrations, supabase, approval-events]

# Dependency graph
requires:
  - phase: 03-video-production
    provides: content_history table with video columns (video_url, video_status, heygen_job_id)

provides:
  - approval_events table as append-only event log for creator decisions
  - cause_code constraint (script_error, visual_error, technical_error, off_topic)
  - rejection_requires_cause constraint ensuring every rejection has a cause
  - approval_events_content_history_id_idx for idempotency lookup
  - approval_events_created_at_idx for daily rejection count queries
  - post_copy text column on content_history for Spanish social media captions

affects: [04-02-approval-service, 04-03-post-copy-service, 05-publish-flow]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Append-only event table pattern for restart-safe state: query approval_events before sending, never mutate"
    - "CHECK + CONSTRAINT combination for conditional NOT NULL: action/cause_code pair enforced at DB level"

key-files:
  created:
    - migrations/0004_approval_events.sql
  modified: []

key-decisions:
  - "cause_code CHECK constraint added on column (not just on rejection_requires_cause) to restrict values to the 4 defined codes even for future direct inserts"
  - "No mood_profile_id FK added to content_history — simpler query-by-week_start approach preferred; Phase 5 can add FK if needed"
  - "post_copy stored on content_history (not approval_events) — it belongs to the content record, not the decision event"

patterns-established:
  - "Migration comment style: brief header block explaining purpose, then per-section comments with column/constraint rationale"
  - "IF NOT EXISTS guards on all DDL: table, index, and column additions are all idempotent"

requirements-completed: [TGAP-01, TGAP-04]

# Metrics
duration: 1min
completed: 2026-02-22
---

# Phase 4 Plan 01: Approval Events Schema Summary

**Append-only approval_events table with cause_code constraint and post_copy column on content_history — Phase 4 database foundation**

## Performance

- **Duration:** 1 min
- **Started:** 2026-02-22T18:23:03Z
- **Completed:** 2026-02-22T18:23:52Z
- **Tasks:** 1
- **Files modified:** 1

## Accomplishments

- approval_events table created with FK to content_history, action CHECK ('approved'/'rejected'), and cause_code constrained to the 4 defined rejection codes
- rejection_requires_cause table constraint ensures every rejected event carries a cause_code at the database level
- Two indexes added: content_history_id_idx for is_already_actioned() lookup and created_at_idx for get_today_rejection_count() date-range query
- post_copy text column added to content_history with ADD COLUMN IF NOT EXISTS guard — stores Spanish social media captions alongside the video record

## Task Commits

Each task was committed atomically:

1. **Task 1: Create migration 0004 — approval_events table and post_copy column** - `9b30b22` (feat)

**Plan metadata:** _(added in final commit)_

## Files Created/Modified

- `migrations/0004_approval_events.sql` - Approval flow schema: approval_events table, two indexes, post_copy column on content_history

## Decisions Made

- cause_code has its own CHECK constraint (not just covered by rejection_requires_cause) to restrict values to 'script_error', 'visual_error', 'technical_error', 'off_topic' even for direct DB inserts bypassing the service layer.
- No mood_profile_id FK column added to content_history — the research recommended two approaches; the simpler one (query mood_profiles by week_start) keeps the migration minimal. Phase 5 can add FK if needed.
- post_copy belongs on content_history (alongside the content), not on approval_events (which records the decision). This aligns with how Phase 5 will read it at publish time.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required. Migration must be executed against Supabase before plan 02 services run.

## Next Phase Readiness

- Migration 0004 is ready to execute against Supabase — ApprovalService (plan 02) and PostCopyService (plan 02) can safely write to approval_events and read/write post_copy on content_history
- No blockers for plan 02

## Self-Check: PASSED

- FOUND: migrations/0004_approval_events.sql
- FOUND: .planning/phases/04-telegram-approval-loop/04-01-SUMMARY.md
- FOUND: commit 9b30b22

---
*Phase: 04-telegram-approval-loop*
*Completed: 2026-02-22*
