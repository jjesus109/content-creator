---
phase: 05-multi-platform-publishing
plan: "02"
subsystem: api
tags: [anthropic, telegram, post-copy, multi-platform, tiktok, instagram, facebook, youtube]

# Dependency graph
requires:
  - phase: 05-01
    provides: post_copy_tiktok/instagram/facebook/youtube columns on content_history, publish_events table, Ayrshare settings foundation
  - phase: 04-04
    provides: send_approval_message() async function, PostCopyService.generate() baseline
provides:
  - PostCopyService.generate_platform_variants() — single Anthropic call returning 4-key dict
  - send_approval_message extended with 4 platform copy variants in caption
  - Platform variants generated via run_in_executor, persisted to content_history immediately
affects:
  - 05-03 (publisher reads post_copy_tiktok/instagram/facebook/youtube at publish time)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - JSON extraction via re.search(r'\{.*\}', text, re.DOTALL) + json.loads for structured Anthropic response parsing
    - run_in_executor for blocking Anthropic/DB calls inside async function (same executor, no new threading overhead)
    - has_all_variants guard to skip re-generation if platform copy already stored

key-files:
  created: []
  modified:
    - src/app/services/post_copy.py
    - src/app/services/telegram.py

key-decisions:
  - "generate_platform_variants uses max_tokens=1500 (vs 300 for generate()) — 4 variants need significantly more output space"
  - "JSON extraction uses re.search DOTALL pattern — same approach as research doc, handles markdown code fences Claude sometimes wraps output in"
  - "has_all_variants checks all 4 columns before generating — avoids redundant Anthropic call if content_history already populated"
  - "Caption 1024-char truncation applies to the FULL combined caption (post_copy + metadata + all 4 platform variants stacked)"

patterns-established:
  - "Platform variant generation: blocking Anthropic call wrapped in run_in_executor inside async send_approval_message"
  - "Structured JSON response from Anthropic: instruct return-only-JSON in prompt, extract via regex, parse with json.loads, use .get() fallbacks"

requirements-completed:
  - PUBL-01

# Metrics
duration: 2min
completed: 2026-02-25
---

# Phase 5 Plan 02: Multi-Platform Copy Variants Summary

**PostCopyService.generate_platform_variants() generating TikTok/Instagram/Facebook/YouTube copy variants in a single Anthropic call, stored in content_history, shown stacked in approval Telegram message**

## Performance

- **Duration:** 2 min
- **Started:** 2026-02-25T18:15:05Z
- **Completed:** 2026-02-25T18:17:09Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Added `generate_platform_variants()` to PostCopyService with `import json` and `import re` at file top, single Anthropic call returning a 4-key dict (`tiktok`, `instagram`, `facebook`, `youtube`), synchronous client with max_tokens=1500 and temperature=0.7
- Extended `send_approval_message()` SELECT to include all 4 platform columns, generates variants via `run_in_executor` if any are missing, persists all 4 to `content_history` immediately, and shows them stacked with emoji platform labels in the caption
- 1024-char truncation still applied to the full combined caption; Approve/Reject keyboard buttons unchanged

## Task Commits

Each task was committed atomically:

1. **Task 1: Add generate_platform_variants() to PostCopyService** - `34e10c5` (feat)
2. **Task 2: Extend send_approval_message with 4 platform copy variants** - `1d26d5c` (feat)

**Plan metadata:** (docs commit — created below)

## Files Created/Modified

- `src/app/services/post_copy.py` - Added `import json`, `import re`; added `generate_platform_variants(script_text, topic_summary) -> dict[str, str]` method at end of class body
- `src/app/services/telegram.py` - Extended SELECT to include 4 platform columns, added `_generate_and_store_variants` inner function called via `run_in_executor`, extended caption with platform emoji labels section

## Decisions Made

- `generate_platform_variants` uses `max_tokens=1500` vs the existing `generate()` which uses 300 — 4 platform variants require significantly more output space
- JSON extraction uses `re.search(r'\{.*\}', text, re.DOTALL)` pattern — handles cases where Claude wraps output in markdown code fences; same approach described in research doc
- `has_all_variants` guard checks all 4 columns before generating — avoids redundant Anthropic API call if variants already stored from a prior run
- Caption 1024-char Telegram limit applies to the full combined string including all platform variants stacked — no per-section limits

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required beyond what was established in 05-01.

## Next Phase Readiness

- `PostCopyService.generate_platform_variants()` is importable and ready for use
- `content_history.post_copy_tiktok/instagram/facebook/youtube` columns are populated at approval-message time
- Platform copy is available at publish time (05-03) without re-generation
- Creator sees all 4 platform copy variants in the approval Telegram message before approving

## Self-Check: PASSED

- FOUND: .planning/phases/05-multi-platform-publishing/05-02-SUMMARY.md
- FOUND: src/app/services/post_copy.py
- FOUND: src/app/services/telegram.py
- FOUND commit: 34e10c5 (Task 1)
- FOUND commit: 1d26d5c (Task 2)

---
*Phase: 05-multi-platform-publishing*
*Completed: 2026-02-25*
