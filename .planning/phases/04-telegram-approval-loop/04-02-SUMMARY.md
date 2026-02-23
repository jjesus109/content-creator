---
phase: 04-telegram-approval-loop
plan: "02"
subsystem: api
tags: [anthropic, claude-haiku, ffmpeg, supabase, approval-flow, social-media-copy, telegram]

# Dependency graph
requires:
  - phase: 04-01
    provides: approval_events table and rejection_constraints table (migration 0004)
  - phase: 02-01
    provides: rejection_constraints table (migration 0002, Phase 2 created, Phase 4 writes)
  - phase: 03-02
    provides: VideoStorageService pattern (optional supabase client in __init__ for testability)
provides:
  - PostCopyService.generate() — Spanish Hook + body + hashtags via synchronous Claude Haiku
  - extract_thumbnail() — BytesIO JPEG at t=1s via ffmpeg pipe, .name set for PTB
  - ApprovalService.is_already_actioned() — DB-backed idempotency guard
  - ApprovalService.record_approve() / record_reject() — approval_events inserts
  - ApprovalService.get_today_rejection_count() — DB-backed restart-safe count
  - ApprovalService.write_rejection_constraint() — rejection_constraints insert, 365-day expiry
  - ApprovalService.clear_constraints_for_approved_run() — expires today's rejection constraints on approve
affects:
  - 04-03 (Telegram bot handlers that call PostCopyService and ApprovalService)
  - 04-04 (daily pipeline job that calls PostCopyService.generate())
  - 05-publish (reads post_copy from content_history at publish time)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Synchronous Anthropic client for APScheduler thread pool context (no event loop)"
    - "Optional supabase Client in __init__ for testability (mirrors VideoStorageService pattern)"
    - "DB-backed state — no module-level counters, restart-safe by design"
    - "ffmpeg pipe:0/pipe:1 for thumbnail extraction — no temp files for single-input ffmpeg"
    - "cause_code -> pattern_type mapping constant (_CAUSE_TO_PATTERN_TYPE) at module level"

key-files:
  created:
    - src/app/services/post_copy.py
    - src/app/services/approval.py
  modified: []

key-decisions:
  - "PostCopyService uses synchronous Anthropic client — APScheduler ThreadPoolExecutor has no event loop, AsyncAnthropic would fail"
  - "extract_thumbnail() is a module-level function (not class method) — called from thread pool context only, docstring warns against async handler use"
  - "ApprovalService accepts optional supabase Client — follows VideoStorageService and SimilarityService testability pattern"
  - "get_today_rejection_count() reads from DB on every call — no module-level counter, restart-safe"
  - "clear_constraints_for_approved_run() queries ALL today's rejections (not just current content_history_id) — daily rejections share cause categories"

patterns-established:
  - "Service constructor pattern: __init__(self, supabase: Client | None = None) with get_supabase() default"
  - "Thread-context docstring convention: state explicitly whether method is sync-only and why"
  - "DB-backed approval state: every read from DB, no in-memory state"

requirements-completed: [TGAP-01, TGAP-04]

# Metrics
duration: 3min
completed: 2026-02-23
---

# Phase 4 Plan 02: PostCopyService and ApprovalService Summary

**Spanish social media copy generation (Claude Haiku sync client) and DB-backed approval state management (6 methods, restart-safe) — pure service layer with no Telegram coupling**

## Performance

- **Duration:** 3 min
- **Started:** 2026-02-22T18:30:00Z
- **Completed:** 2026-02-22T18:33:00Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- PostCopyService generates Hook + 2-3 body lines + 5-8 hashtags in neutral Spanish using synchronous Claude Haiku at temperature=0.7, max_tokens=300
- extract_thumbnail() downloads video bytes via requests and extracts a JPEG frame at t=1s via ffmpeg pipe:0/pipe:1, returning BytesIO with .name="thumbnail.jpg" for PTB compatibility
- ApprovalService provides 6 DB-backed methods covering the full approval lifecycle: idempotency guard, approve/reject recording, daily rejection counting, constraint writing, and constraint clearing

## Task Commits

Each task was committed atomically:

1. **Task 1: Create services/post_copy.py — PostCopyService and extract_thumbnail** - `312023e` (feat)
2. **Task 2: Create services/approval.py — ApprovalService** - `b72b851` (feat)

**Plan metadata:** (committed in this session)

## Files Created/Modified

- `src/app/services/post_copy.py` — PostCopyService class with generate() method, and extract_thumbnail() module-level function
- `src/app/services/approval.py` — ApprovalService class with 6 methods for DB-backed approval state

## Decisions Made

- PostCopyService uses synchronous `Anthropic` client only — the service runs inside APScheduler's ThreadPoolExecutor where there is no event loop; AsyncAnthropic would raise RuntimeError
- `extract_thumbnail()` implemented as a module-level function (not a class method) to make the threading constraint visible at call site; docstring explicitly warns against calling from async handlers
- ApprovalService constructor follows `__init__(self, supabase: Client | None = None)` pattern (mirrors VideoStorageService and SimilarityService) for unit test compatibility without a live DB
- `get_today_rejection_count()` always reads from DB — no module-level counter — making the count correct after pod restarts and re-deployments
- `clear_constraints_for_approved_run()` queries all today's rejections for ANY content (not just the approved content_history_id) because daily rejections share cause categories across the session

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- PostCopyService and ApprovalService are ready for Phase 4 plan 03 (Telegram bot callback handlers)
- Both services have no Telegram coupling — pure business logic layer
- ApprovalService methods are synchronous — compatible with PTB asyncio bridge (run_in_executor) and APScheduler thread pool
- extract_thumbnail() is ready for use in the Telegram send-for-approval flow (Phase 4 plan 03)

---
*Phase: 04-telegram-approval-loop*
*Completed: 2026-02-23*
