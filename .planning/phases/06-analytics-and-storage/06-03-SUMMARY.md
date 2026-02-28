---
phase: 06-analytics-and-storage
plan: 03
subsystem: storage
tags: [supabase, storage, telegram, lifecycle, deletion, handlers]

# Dependency graph
requires:
  - phase: 06-01
    provides: content_history storage lifecycle columns (storage_status, deletion_requested_at, is_eternal, storage_tier_set_at)

provides:
  - StorageLifecycleService with transition_to_warm(), delete_from_supabase_storage(), send_7day_warning(), request_deletion_confirmation(), reset_expired_deletion_requests()
  - stor_confirm: handler — creator confirms deletion, file removed from Supabase Storage, DB record kept
  - stor_cancel: handler — resets deletion_requested_at=NULL, storage_status='warm'
  - stor_eternal: handler — marks video is_eternal=true, clears deletion_requested_at
  - stor_warn_ok: handler — acknowledges 7-day warning, no DB update needed
  - register_storage_handlers() called in build_telegram_app()

affects: [06-05-storage-lifecycle-job, any plan reading storage_status or is_eternal]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "StorageLifecycleService follows optional-supabase-in-__init__ testability pattern (same as SimilarityService, VideoStorageService)"
    - "Supabase Storage deletion via supabase.storage.from_(bucket).remove([path]) — no boto3, no R2"
    - "await query.answer() as first async call in all Telegram handlers (prevents loading spinner freeze)"
    - "DB record KEPT after cold deletion — content_history row preserved for analytics history"
    - "Safe-default pattern: expired deletion requests reset to warm (never auto-delete without confirmation)"

key-files:
  created:
    - src/app/services/storage_lifecycle.py
    - src/app/telegram/handlers/storage_confirm.py
  modified:
    - src/app/telegram/app.py

key-decisions:
  - "Warm tier = DB label only; file stays in same Supabase Storage bucket; no copy, no R2, no boto3"
  - "Cold deletion = supabase.storage.from_(bucket).remove([path]); content_history row kept for analytics"
  - "reset_expired_deletion_requests() fetches IDs first then loops — Supabase Python client has no bulk update with compound WHERE clause"
  - "is_viral/is_eternal safety guard in handle_storage_confirm prevents accidental deletion of exempt videos"
  - "handle_storage_warn_ok: no DB update needed; lifecycle job handles idempotency via storage_status='warm' AND deletion_requested_at IS NULL query"

patterns-established:
  - "Storage handler idempotency: check storage_status before acting (already 'deleted' -> skip; already is_eternal -> skip)"
  - "Safety guard pattern: check is_viral || is_eternal in any deletion path"

requirements-completed: [ANLX-04]

# Metrics
duration: 2min
completed: 2026-02-28
---

# Phase 6 Plan 03: Storage Lifecycle Service and Telegram Handlers Summary

**Supabase Storage lifecycle service (no R2/boto3) with warm-label, cold-file-delete, 7-day pre-warning, 45-day deletion confirmation, and four Telegram inline handlers for creator-approval of storage decisions.**

## Performance

- **Duration:** 2 min
- **Started:** 2026-02-28T20:21:06Z
- **Completed:** 2026-02-28T20:23:10Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- Created StorageLifecycleService with Supabase Storage-only operations (no R2, no boto3) — warm = DB label, cold = file deletion via supabase.storage.from_().remove()
- Created four Telegram callback handlers (confirm, cancel, eternal, warn_ok) following the exact same patterns as approval_flow.py
- Registered all storage handlers in build_telegram_app() without breaking existing mood and approval handlers

## Task Commits

Each task was committed atomically:

1. **Task 1: Create StorageLifecycleService (Supabase Storage only, no R2/boto3)** - `c2b5027` (feat)
2. **Task 2: Storage Telegram handlers (confirm, cancel, eternal) + register in app.py** - `1fe5da3` (feat)

## Files Created/Modified

- `src/app/services/storage_lifecycle.py` - StorageLifecycleService: transition_to_warm(), delete_from_supabase_storage(), send_7day_warning(), request_deletion_confirmation(), reset_expired_deletion_requests()
- `src/app/telegram/handlers/storage_confirm.py` - Four callback handlers: stor_confirm:, stor_cancel:, stor_eternal:, stor_warn_ok: with PREFIX constants and register_storage_handlers()
- `src/app/telegram/app.py` - Added import + register_storage_handlers(app) call after register_approval_handlers(app)

## Decisions Made

- **Warm tier = DB label only**: File stays in same Supabase Storage bucket; no copy needed. storage_status = 'warm' is the complete warm-tier operation.
- **Cold deletion = supabase.storage.from_().remove()**: The actual file is deleted; the content_history DB row is NEVER deleted (needed for analytics history).
- **reset_expired_deletion_requests() loops per ID**: Supabase Python client has no bulk update with compound WHERE clause; must fetch IDs first then iterate.
- **is_viral/is_eternal safety guard**: handle_storage_confirm checks both flags before calling delete_from_supabase_storage() — prevents accidental deletion of viral or eternal videos.
- **handle_storage_warn_ok: no DB update**: The lifecycle job uses storage_status='warm' AND deletion_requested_at IS NULL to find videos needing warnings — no sentinel value needed.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required. Supabase Storage deletion uses the same supabase_key already configured.

## Next Phase Readiness

- StorageLifecycleService is ready for use by 06-05 storage_lifecycle_job
- All four Telegram handlers registered and responding to stor_confirm:, stor_cancel:, stor_eternal:, stor_warn_ok: callback prefixes
- No blockers

---
*Phase: 06-analytics-and-storage*
*Completed: 2026-02-28*
