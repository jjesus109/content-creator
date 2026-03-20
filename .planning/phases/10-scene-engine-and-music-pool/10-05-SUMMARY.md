---
phase: 10-scene-engine-and-music-pool
plan: "05"
subsystem: pipeline-integration
tags: [pipeline, scene-engine, music-matcher, daily-pipeline, integration-tests]
dependency_graph:
  requires: [10-02, 10-03, 10-04]
  provides: [SCN-01, SCN-02, SCN-03, SCN-04, SCN-05, MUS-01, MUS-02, MUS-03]
  affects: [daily_pipeline.py, content_history, platform_publish.py]
tech_stack:
  added: []
  patterns: [scene-engine-orchestration, music-mood-matching, anti-repetition-feature-flag, v2-pipeline-wiring]
key_files:
  created: []
  modified:
    - src/app/scheduler/jobs/daily_pipeline.py
    - tests/test_pipeline_wiring.py
    - tests/test_kling_backoff.py
decisions:
  - "SceneEngine replaces ScriptGenerationService + MoodService entirely in daily_pipeline.py — v1.0 mood flow deprecated"
  - "scene_embedding stored in both embedding column (backward compat) and scene_embedding column"
  - "KlingService.submit() receives scene_prompt (not caption) — scene_prompt is the Kling-optimized 2-3 sentence description"
  - "Anti-repetition check runs always; pipeline only blocks on scene_anti_repetition_enabled=True"
  - "MusicMatcher ValueError halts pipeline with Telegram alert — graceful degradation, no silent failure"
metrics:
  duration_minutes: 60
  tasks_completed: 2
  files_modified: 3
  completed_date: "2026-03-20"
---

# Phase 10 Plan 05: Pipeline Integration Summary

**One-liner:** SceneEngine + MusicMatcher wired into daily_pipeline.py replacing v1.0 script generation, with 7 integration tests covering all orchestration paths including graceful halts and anti-repetition modes.

## What Was Built

### Task 1: Rewrite daily_pipeline.py to use SceneEngine + MusicMatcher

Rewrote the v1.0 daily pipeline to use Phase 10 services end-to-end:

- **Removed:** `MoodService`, `ScriptGenerationService`, and all v1.0 mood profile logic
- **Added:** `SceneEngine`, `MusicMatcher`, `get_settings` imports
- **New retry loop:**
  1. `scene_engine.pick_scene(attempt, rejection_constraints)` → `(scene_prompt, caption, mood, cost)`
  2. Circuit breaker records scene generation cost
  3. `embedding_svc.generate(scene_prompt)` → scene_embedding for anti-repetition
  4. `similarity_svc.is_too_similar_scene(scene_embedding)` — gated by `scene_anti_repetition_enabled`
  5. `music_matcher.pick_track(mood, target_platform="tiktok")` — ValueError halts with Telegram alert
  6. Kling CB check → `kling_svc.submit(scene_prompt)`
  7. `_save_to_content_history(scene_prompt, caption, scene_embedding, music_track_id, kling_job_id)`
- **Updated `_save_to_content_history`:** v2.0 signature — saves scene_prompt, caption, scene_embedding, music_track_id; script_text/topic_summary kept for backward compatibility

### Task 2: Activate pipeline wiring integration tests

Replaced 3 skipped stubs in `test_pipeline_wiring.py` with 7 real mock-based integration tests:

1. `test_scene_engine_replaces_script_generation` — SceneEngine.pick_scene() called (not ScriptGenerationService)
2. `test_music_matcher_called_with_scene_mood` — MusicMatcher called with mood from SceneEngine
3. `test_scene_prompt_passed_to_kling_not_caption` — KlingService receives scene_prompt
4. `test_music_track_id_saved_to_content_history` — music_track_id in content_history insert
5. `test_caption_saved_to_content_history` — caption column populated
6. `test_music_matcher_failure_sends_alert_and_halts` — ValueError → Telegram alert + pipeline halt
7. `test_anti_repetition_log_only_mode_does_not_retry` — log-only mode does not block pipeline

All 7 pass, 0 skips.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed test_kling_backoff.py::test_daily_pipeline_skips_kling_when_cb_open**
- **Found during:** Task 1 full test suite run
- **Issue:** test_kling_backoff.py test `test_daily_pipeline_skips_kling_when_cb_open` was written for v1.0 pipeline — it patched `MoodService` and `ScriptGenerationService` which are now removed, causing `pydantic_settings ValidationError` (Settings requires env vars not provided in test context because `get_settings()` was reached before mocks took effect)
- **Fix:** Updated test to use v2.0 mock pattern — patches `SceneEngine`, `MusicMatcher`, `get_settings` at `app.scheduler.jobs.daily_pipeline` level, consistent with `_run_pipeline_with_mocks()` pattern in test_pipeline_wiring.py
- **Files modified:** `tests/test_kling_backoff.py`
- **Commit:** `725c230` (included in Task 1 commit)

## Verification Results

```
uv run pytest tests/test_pipeline_wiring.py -v --tb=short
→ 7 passed in 0.78s

uv run pytest tests/ -x -q --tb=short
→ 149 passed, 5 skipped in 0.94s
```

Done criteria:
- SceneEngine: imported and instantiated in daily_pipeline.py
- MusicMatcher: imported and instantiated in daily_pipeline.py
- pick_scene: called in retry loop
- pick_track: called with mood from SceneEngine
- music_track_id: saved to content_history
- scene_embedding: saved to content_history
- scene_anti_repetition_enabled: feature flag checked
- ScriptGenerationService: absent from daily_pipeline.py
- MoodService: absent from daily_pipeline.py
- Full test suite: 149 passed, 5 skipped (0 failures)

## Self-Check: PASSED

- `src/app/scheduler/jobs/daily_pipeline.py`: FOUND
- `tests/test_pipeline_wiring.py`: FOUND
- Task 1 commit `725c230`: FOUND
- Task 2 commit `29b6799`: FOUND

## Status

Tasks 1 and 2 complete. Awaiting human checkpoint (task 3: `checkpoint:human-verify`) — creator approves visual inspection of pipeline structure and full test suite.
