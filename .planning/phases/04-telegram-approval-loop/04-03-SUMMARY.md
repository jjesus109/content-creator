---
phase: 04-telegram-approval-loop
plan: "03"
subsystem: telegram
tags: [python-telegram-bot, callback-query, approval-flow, idempotency, supabase]

# Dependency graph
requires:
  - phase: 04-02
    provides: ApprovalService with is_already_actioned, record_approve, record_reject, get_today_rejection_count, write_rejection_constraint, clear_constraints_for_approved_run
  - phase: 04-01
    provides: approval_events table and rejection_constraints table
provides:
  - "Three PTB CallbackQueryHandlers: handle_approve, handle_reject, handle_cause"
  - "register_approval_handlers() function wired into build_telegram_app()"
  - "Full creator-facing approval interaction layer"
affects:
  - 04-04-PLAN (trigger_immediate_rerun wiring)
  - 05-publish-pipeline (reads approved status from approval_events)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Lazy/local import inside handler body — prevents circular import at module load time (mirrors mood_flow.py)"
    - "update.effective_chat.send_message() for all CBQ outbound messages (update.message is None in CBQ handlers)"
    - "rsplit(':', 1) to parse UUID+cause_code callback payload without splitting on UUID hyphens"
    - "await query.answer() as first async call in all handlers — prevents Telegram spinner freeze"
    - "DB-read-on-every-call idempotency guard — restart-safe, no in-memory state"

key-files:
  created:
    - src/app/telegram/handlers/approval_flow.py
  modified:
    - src/app/telegram/app.py

key-decisions:
  - "Original approval message with Approve/Reject buttons preserved unchanged — no edit_message_reply_markup calls; only new messages sent via effective_chat.send_message()"
  - "Cause keyboard uses each button on its own row (not side-by-side) for single-tap mobile UX"
  - "handle_cause imports trigger_immediate_rerun lazily — function defined in plan 04-04; lazy import avoids NameError at module load time"
  - "Daily limit message uses get_settings().pipeline_hour dynamically — not hardcoded '07:00'"

patterns-established:
  - "Approval handler structure: query.answer() first, lazy import service, idempotency check, DB write, new message"
  - "PREFIX_* constants sized to stay under Telegram 64-byte callback_data limit with UUID payloads"

requirements-completed: [TGAP-02, TGAP-03]

# Metrics
duration: 2min
completed: 2026-02-23
---

# Phase 4 Plan 03: Telegram Approval Flow Handlers Summary

**Three PTB CallbackQueryHandlers implementing the full creator approval loop: Approve records event + clears constraints, Reject opens a 4-cause menu, cause selection records rejection + writes constraint + triggers pipeline rerun or daily limit notification**

## Performance

- **Duration:** 2 min
- **Started:** 2026-02-23T23:54:41Z
- **Completed:** 2026-02-23T23:56:37Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- Created `approval_flow.py` with all three CBQ handlers and `register_approval_handlers()` following mood_flow.py structure
- All three handlers call `await query.answer()` as the first async operation, preventing Telegram spinner freeze
- handle_approve and handle_cause enforce idempotency via DB read on every invocation (restart-safe)
- handle_cause reads `get_settings().pipeline_hour` for a dynamic daily limit message
- Wired `register_approval_handlers(app)` into `build_telegram_app()` after `register_mood_handlers(app)`

## Task Commits

Each task was committed atomically:

1. **Task 1: Create telegram/handlers/approval_flow.py** - `f3d6f02` (feat)
2. **Task 2: Wire register_approval_handlers into telegram/app.py** - `50e7540` (feat)

**Plan metadata:** (docs commit follows)

## Files Created/Modified
- `src/app/telegram/handlers/approval_flow.py` - Full approval CBQ handler module with PREFIX constants, CAUSE_OPTIONS, handle_approve, handle_reject, handle_cause, register_approval_handlers
- `src/app/telegram/app.py` - Added import and call to register_approval_handlers(app) in build_telegram_app()

## Decisions Made
- Original approval message preserved unchanged (no `edit_message_reply_markup`) — new messages only via `effective_chat.send_message()`
- Cause keyboard: each button on its own row for clean mobile tap targets
- `trigger_immediate_rerun` imported lazily in handle_cause body — function to be implemented in plan 04-04; lazy import means module loads fine today
- `get_settings().pipeline_hour` used in daily limit message — not hardcoded, honors environment config

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Approval handler chain complete: CBQ events from Approve/Reject buttons now handled
- `trigger_immediate_rerun()` in daily_pipeline.py must be implemented in plan 04-04 before handle_cause's rerun path can execute without ImportError
- Plan 04-04 wires the complete end-to-end rerun trigger; handlers already call the correct import path

---
*Phase: 04-telegram-approval-loop*
*Completed: 2026-02-23*
