---
phase: 09-mexican-animated-cat-video-format
plan: "04"
subsystem: publishing
tags: [ai-labels, vid-04, compliance, platform-publish, tiktok, youtube, instagram, pytest]

# Dependency graph
requires:
  - phase: 09-01
    provides: KlingService, Settings fields, migration 0008
  - phase: 09-02
    provides: CHARACTER_BIBLE constant in kling.py
  - phase: 09-03
    provides: KlingCircuitBreakerService, kling_circuit_breaker_state
provides:
  - "_apply_ai_label() in platform_publish.py: AI disclosure label injected before every publish"
  - "AI_LABEL = '🤖 Creado con IA' module-level constant"
  - "tests/test_ai_labels.py: 12 unit tests covering all 4 platforms"
  - "tests/test_smoke.py: 17 structural smoke tests for VID-01 through VID-04"
affects: [publishing, compliance, platform-posting, analytics]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "_apply_ai_label(post_text, platform) pattern: platform-specific label injection with try/except fallback before external service call"
    - "TDD RED-GREEN commit sequence: test commit before implementation commit"
    - "YouTube title/description split: split('\\n', 1) preserves title on line 0, label goes into description"

key-files:
  created:
    - tests/test_ai_labels.py
    - tests/test_smoke.py
  modified:
    - src/app/scheduler/jobs/platform_publish.py

key-decisions:
  - "AI_LABEL applied at publish time (inside platform_publish.py), not before Telegram approval — label injected only when content is actually sent to platform"
  - "Exception fallback uses naive f'{AI_LABEL}\\n{post_copy}' prefix — no silent omission allowed per VID-04"
  - "YouTube: label in description only (not title) — prevents title length violation and preserves SEO title format"
  - "TikTok native api_generated flag skipped — caption prefix is sufficient for platform compliance policy"

patterns-established:
  - "AI label injection pattern: try _apply_ai_label → except → naive fallback → pass labeled_copy to PublishingService"
  - "Smoke test class per requirement ID (TestVID01..., TestVID02...) for traceability"

requirements-completed: [VID-04]

# Metrics
duration: 4min
completed: "2026-03-19"
---

# Phase 09 Plan 04: AI Content Labels + Test Suite Summary

**AI disclosure label '🤖 Creado con IA' injected before every platform publish call via _apply_ai_label(), with 12 unit tests and 17 Phase 9 structural smoke tests all passing**

## Performance

- **Duration:** 4 min
- **Started:** 2026-03-19T14:23:02Z
- **Completed:** 2026-03-19T14:26:16Z
- **Tasks:** 2 (+ checkpoint)
- **Files modified:** 3

## Accomplishments

- Added `AI_LABEL = "🤖 Creado con IA"` constant and `_apply_ai_label(post_text, platform)` to `platform_publish.py` with platform-specific routing (YouTube description-only vs. caption prefix for all others)
- Wired `labeled_copy` as the `post_text` argument to `PublishingService().publish()` — every publish call now carries the AI label
- Added exception fallback: if `_apply_ai_label` raises, a naive prefix is used so the label is never silently omitted (VID-04 compliance)
- Created `tests/test_ai_labels.py` with 12 deterministic unit tests covering TikTok, Instagram, Facebook, YouTube (title/description split), empty inputs, and label constant value
- Created `tests/test_smoke.py` with 17 structural smoke tests covering VID-01 (Kling service), VID-02 (CHARACTER_BIBLE), VID-03 (circuit breaker), and VID-04 (AI labels)

## Task Commits

Each task was committed atomically:

1. **Task 1 RED — Failing tests for _apply_ai_label** - `a4c8f8e` (test)
2. **Task 1 GREEN — _apply_ai_label() implementation + inject before publish** - `638343a` (feat)
3. **Task 2 — Phase 9 smoke tests** - `61cdb6e` (test)

_Note: TDD tasks have RED (test) + GREEN (feat) commits_

## Files Created/Modified

- `src/app/scheduler/jobs/platform_publish.py` - Added `AI_LABEL` constant, `_apply_ai_label()` function, and label injection before `PublishingService().publish()` call
- `tests/test_ai_labels.py` - 12 unit tests for platform-specific AI label injection
- `tests/test_smoke.py` - 17 structural smoke tests for all Phase 9 VID requirements

## Decisions Made

- AI label applied at publish time (inside `platform_publish.py`) not before Telegram approval, keeping creator preview clean
- YouTube label goes in description only — title line (line 0) preserved unchanged to avoid platform title length limits
- TikTok native `api_generated` flag skipped — caption prefix satisfies platform policy
- Exception fallback ensures no silent omission: `f"{AI_LABEL}\n{post_copy}"` used if `_apply_ai_label` raises

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- `python` command not available (macOS uses `python3`); resolved by using `uv run` for all test invocations — no code changes needed.

## User Setup Required

**External services require manual configuration before Phase 9 executes in production:**

- `FAL_API_KEY` — fal.ai dashboard → Settings → API Keys → Create key, add to Railway environment variables
- `KLING_MODEL_VERSION` — Optional override (default: `fal-ai/kling-video/v3/standard/text-to-video`), add to Railway if needed
- Migration `0008_v2_schema.sql` must be applied to Supabase DB before running Phase 9 pipeline

## Next Phase Readiness

Phase 9 is complete: all four plans (09-01 through 09-04) have been executed.

- VID-01: KlingService with CHARACTER_BIBLE prompt assembly
- VID-02: CHARACTER_BIBLE 49-word constant locked in kling.py
- VID-03: KlingCircuitBreakerService with separate kling_circuit_breaker_state table
- VID-04: AI disclosure labels on all platforms before every publish

Awaiting human checkpoint verification (see checkpoint task in 09-04-PLAN.md):
1. Full test suite green: `pytest tests/ -x -q`
2. CHARACTER_BIBLE word count 40-50
3. YouTube title/description split verified
4. Migration 0008 keyword match count >= 5
5. CB threshold = 0.20
6. Railway env vars FAL_API_KEY and KLING_MODEL_VERSION added

## Self-Check: PASSED

All required files exist and all commits verified:
- FOUND: tests/test_ai_labels.py
- FOUND: tests/test_smoke.py
- FOUND: src/app/scheduler/jobs/platform_publish.py
- FOUND: .planning/phases/09-mexican-animated-cat-video-format/09-04-SUMMARY.md
- Commit a4c8f8e: test(09-04): add failing tests for _apply_ai_label AI label injection
- Commit 638343a: feat(09-04): add _apply_ai_label() and inject AI label before publish
- Commit 61cdb6e: test(09-04): add Phase 9 smoke tests for VID-01 through VID-04

---
*Phase: 09-mexican-animated-cat-video-format*
*Completed: 2026-03-19*
