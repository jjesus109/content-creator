---
phase: 12-grey-kitten-unified-prompt-generation
plan: 02
subsystem: pipeline-wiring
tags: [pipeline, kling, prompt-generation, integration]
requirements: [GREY-01, GREY-02, GREY-03]

dependency_graph:
  requires: [12-01]
  provides: [pipeline-uses-unified-prompt, kling-passthrough]
  affects: [daily_pipeline.py, kling.py, content_history.script_text]

tech_stack:
  added: []
  patterns:
    - PromptGenerationService instantiated once in Step 2 alongside other services
    - unified_prompt flows: SceneEngine -> PromptGenerationService -> KlingService -> DB
    - effective_script fallback: unified_prompt if set, else scene_prompt

key_files:
  created: []
  modified:
    - src/app/scheduler/jobs/daily_pipeline.py
    - src/app/services/kling.py
    - tests/test_pipeline_wiring.py
    - tests/test_kling_service.py
    - tests/test_kling_backoff.py
    - tests/test_character_bible.py

decisions:
  - "[Phase 12-02]: unified_prompt stored as script_text in content_history; raw scene_prompt preserved in scene_prompt column"
  - "[Phase 12-02]: CB cost tracking for PromptGenerationService only when _last_cost_usd > 0.0 (fallback path returns 0.0 cost)"
  - "[Phase 12-02]: KlingService.submit() is now a pure passthrough — no concatenation, no CHARACTER_BIBLE prepend"

metrics:
  duration_seconds: 302
  completed_date: "2026-03-21"
  tasks_completed: 2
  files_modified: 6
---

# Phase 12 Plan 02: Pipeline Wiring Summary

**One-liner:** Wired PromptGenerationService between SceneEngine and KlingService so the pipeline produces unified animated-style grey kitten prompts; KlingService now passes prompts through directly without CHARACTER_BIBLE concatenation.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Wire PromptGenerationService into daily_pipeline.py | a836eb4 | src/app/scheduler/jobs/daily_pipeline.py |
| 2 | Remove CHARACTER_BIBLE concatenation from KlingService.submit() | 176fe63 | src/app/services/kling.py |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed test_pipeline_wiring tests broken by new PromptGenerationService instantiation**
- **Found during:** Post-task verification
- **Issue:** `PromptGenerationService()` is instantiated in Step 2 (before the retry loop), but `_run_pipeline_with_mocks()` helper and `test_music_matcher_failure_sends_alert_and_halts` did not mock it — `Settings()` was called without env vars causing all pipeline wiring tests to fail
- **Fix:** Added `PromptGenerationService` mock to `_run_pipeline_with_mocks()` helper and to `test_music_matcher_failure_sends_alert_and_halts`; updated `test_scene_prompt_passed_to_kling_not_caption` to assert the new flow (generate_unified_prompt called with scene_prompt, Kling does not receive caption)
- **Files modified:** tests/test_pipeline_wiring.py
- **Commit:** 9e01794

**2. [Rule 1 - Bug] Fixed test_kling_service and test_kling_backoff for Phase 12 behavior**
- **Found during:** Full test suite run
- **Issue:** `test_kling_prompt_includes_character_bible_unchanged` asserted old concatenation behavior (now removed); `test_kling_fal_arguments_locked_spec` asserted `duration=20` but actual constant is `DEFAULT_KLING_DURATION = 15`; `test_daily_pipeline_skips_kling_when_cb_open` lacked PromptGenerationService mock
- **Fix:** Renamed test to `test_kling_submit_passes_prompt_directly` asserting passthrough behavior; fixed duration to 15; added PromptGenerationService mock to backoff test
- **Files modified:** tests/test_kling_service.py, tests/test_kling_backoff.py
- **Commit:** 14a9319

**3. [Rule 1 - Bug] Fixed test_character_bible for v3.0 grey kitten character**
- **Found during:** Full test suite run
- **Issue:** `test_character_bible_mentions_orange_tabby` and `test_character_bible_mentions_mexican_setting` tested the old Phase 09 orange tabby / Mexican household character; CHARACTER_BIBLE was updated in Plan 01 to grey kitten
- **Fix:** Replaced with `test_character_bible_mentions_grey_kitten` (checks for "grey"/"gray") and `test_character_bible_mentions_key_visual_hooks` (checks for blue eyes + pink tongue)
- **Files modified:** tests/test_character_bible.py
- **Commit:** 14a9319

## Verification Results

- daily_pipeline.py assertions passed (PromptGenerationService, prompt_gen_svc, generate_unified_prompt, unified_prompt, kling_svc.submit(unified_prompt), effective_script all present)
- KlingService.submit() de-concatenation verified (full_prompt concatenation line absent, prompt argument uses script_text directly)
- Pipeline module imports cleanly: `from app.scheduler.jobs.daily_pipeline import daily_pipeline_job, _save_to_content_history`
- Full test suite: 162 passed, 5 skipped, 0 failed

## Self-Check: PASSED

Files modified exist and commits are present:
- src/app/scheduler/jobs/daily_pipeline.py — FOUND
- src/app/services/kling.py — FOUND
- tests/test_pipeline_wiring.py — FOUND
- tests/test_kling_service.py — FOUND
- tests/test_kling_backoff.py — FOUND
- tests/test_character_bible.py — FOUND
- Commits: a836eb4, 176fe63, 9e01794, 14a9319 — all present
