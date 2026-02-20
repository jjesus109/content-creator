---
phase: 02-script-generation
plan: "03"
subsystem: telegram, scheduler, database
tags: [telegram-bot, apscheduler, supabase, inline-keyboard, mood-profile, ptb, callback-query]

# Dependency graph
requires:
  - phase: 02-01
    provides: PTB Application with polling, set_fastapi_app pattern, services/telegram.py with _fastapi_app global
  - phase: 01-foundation
    provides: mood_profiles table (week_start, profile_text columns), scheduler registry pattern, get_supabase() singleton

provides:
  - MoodService: get_current_week_mood() returns structured dict with pool/tone/duration/target_words, save_mood_profile() upserts JSON to mood_profiles, has_profile_this_week() for reminder gating
  - 3-step inline keyboard Telegram flow using CallbackQueryHandler prefix matching (not ConversationHandler)
  - weekly_mood_prompt_job (Mon 9 AM) and weekly_mood_reminder_job (Mon 1 PM) APScheduler jobs
  - Deterministic pool rotation fallback via ISO week number modulo

affects:
  - 02-04 (daily pipeline job reads MoodService.get_current_week_mood() to route topic generation)
  - 02-05 (tone/duration from mood profile affects script generation parameters)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - CallbackQueryHandler with prefix matching for bot-initiated multi-step flows (no ConversationHandler)
    - Manual bot_data state dict for in-progress user sessions across callback steps
    - run_coroutine_threadsafe for APScheduler thread -> asyncio event loop bridging
    - JSON string storage in text column (profile_text) with json.dumps/json.loads

key-files:
  created:
    - src/app/services/mood.py
    - src/app/telegram/handlers/__init__.py
    - src/app/telegram/handlers/mood_flow.py
    - src/app/scheduler/jobs/weekly_mood.py
  modified:
    - src/app/telegram/app.py
    - src/app/scheduler/registry.py

key-decisions:
  - "CallbackQueryHandler with PREFIX_POOL/TONE/DURATION matching used instead of ConversationHandler — bot-initiated flows cannot use ConversationHandler entry_points"
  - "await query.answer() called in all 3 handler steps — required to prevent Telegram loading spinner freezing on creator device"
  - "profile_text stores JSON string — no DB schema change needed, existing text column reused"
  - "Reminder job skips if has_profile_this_week() returns True — prevents double-prompting creator who already responded"
  - "DURATION_WORD_COUNTS (short=70, medium=140, long=200) baked into MoodService so pipeline never needs to map duration to words"

patterns-established:
  - "Bot-initiated multi-step flow: send_pool_prompt() -> handle_pool() -> handle_tone() -> handle_duration() using CallbackQueryHandler prefix matching"
  - "Manual state via context.bot_data['mood_state'][user_id] dict — cleaned up after final step"
  - "APScheduler job accesses bot via _fastapi_app.state.telegram_app.bot (same pattern as Phase 1 send_alert_sync)"

requirements-completed: [SCRP-04]

# Metrics
duration: 4min
completed: 2026-02-20
---

# Phase 2 Plan 03: Weekly Mood Collection System Summary

**Weekly mood profile collection via 3-step Telegram inline keyboard (pool -> tone -> duration) with APScheduler prompt at Mon 9 AM and 4-hour reminder, saving to mood_profiles as JSON for pipeline routing**

## Performance

- **Duration:** 4 min
- **Started:** 2026-02-20T21:37:29Z
- **Completed:** 2026-02-20T21:41:00Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments
- MoodService reads/writes mood_profiles table using JSON in profile_text column, with deterministic fallback rotation across 6 thematic pools when creator doesn't respond
- 3-step Telegram inline keyboard flow using CallbackQueryHandler prefix matching (pool -> tone -> duration) with manual bot_data state dict — no ConversationHandler (which cannot handle bot-initiated entry points)
- Two APScheduler weekly jobs: prompt at Monday 9 AM, reminder at Monday 1 PM (Mexico City), reminder skips if creator already responded
- Full import chain verified: main.py -> telegram/app.py -> handlers/mood_flow.py -> services/mood.py

## Task Commits

Each task was committed atomically:

1. **Task 1: MoodService — read/write mood_profiles with JSON structured fields** - `87167fe` (feat)
2. **Task 2: Mood flow handlers, weekly jobs, wire into Application and registry** - `c2642c0` (feat)

**Plan metadata:** (docs commit — see below)

## Files Created/Modified
- `src/app/services/mood.py` - MoodService with get_current_week_mood(), save_mood_profile(), has_profile_this_week(), _get_default_pool_rotation()
- `src/app/telegram/handlers/__init__.py` - Empty package marker for handlers module
- `src/app/telegram/handlers/mood_flow.py` - 3-step inline keyboard flow: handle_pool, handle_tone, handle_duration, register_mood_handlers, send_mood_prompt_sync
- `src/app/scheduler/jobs/weekly_mood.py` - weekly_mood_prompt_job and weekly_mood_reminder_job for APScheduler
- `src/app/telegram/app.py` - Added register_mood_handlers(app) call inside build_telegram_app()
- `src/app/scheduler/registry.py` - Added weekly_mood_prompt (Mon 9 AM) and weekly_mood_reminder (Mon 1 PM) jobs; 4 total jobs

## Decisions Made
- Used CallbackQueryHandler with prefix matching (PREFIX_POOL/TONE/DURATION) instead of ConversationHandler because the weekly prompt is bot-initiated — ConversationHandler requires user-initiated entry points
- All 3 handlers call `await query.answer()` before any processing to prevent the Telegram loading spinner from freezing on the creator's device
- profile_text column stores JSON string (not separate columns) — reuses existing schema, no migration needed
- Reminder job checks has_profile_this_week() before sending to avoid double-prompting a creator who already responded within 4 hours
- target_words derived inside get_current_week_mood() so callers never manually map duration -> word count

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
- `grep -n "ConversationHandler" mood_flow.py` triggered the verification "FAIL" message, but the match was in a comment in the register_mood_handlers() docstring explaining why ConversationHandler is NOT used. No actual ConversationHandler code was found — verified by inspection.

## User Setup Required
None - no external service configuration required beyond existing credentials.

## Next Phase Readiness
- MoodService.get_current_week_mood() ready for daily pipeline job (Plan 04) to call at script generation time
- Pool, tone, and duration values ready to route topic generation and set script parameters
- Defaults (contemplative, rotating pool, medium/140 words) apply automatically when no mood profile exists for the week

---
*Phase: 02-script-generation*
*Completed: 2026-02-20*

## Self-Check: PASSED

- src/app/services/mood.py: FOUND
- src/app/telegram/handlers/__init__.py: FOUND
- src/app/telegram/handlers/mood_flow.py: FOUND
- src/app/scheduler/jobs/weekly_mood.py: FOUND
- 02-03-SUMMARY.md: FOUND
- Commit 87167fe (Task 1): FOUND
- Commit c2642c0 (Task 2): FOUND
