---
phase: 09-mexican-animated-cat-video-format
plan: 02
subsystem: video-generation
tags: [kling, fal-ai, character-bible, video-poller, daily-pipeline, tdd]
dependency_graph:
  requires: [09-01]
  provides: [kling-service, character-bible, adapted-video-poller, kling-pipeline]
  affects: [src/app/services/kling.py, src/app/scheduler/jobs/video_poller.py, src/app/scheduler/jobs/daily_pipeline.py]
tech_stack:
  added: [fal-client==0.13.1]
  patterns: [fal_client.submit()-sync-in-apscheduler, character-bible-constant, kling_job_id-sentinel-pattern]
key_files:
  created:
    - src/app/services/kling.py
    - tests/test_character_bible.py
    - tests/test_kling_service.py
    - tests/test_kling_poller.py
  modified:
    - src/app/scheduler/jobs/video_poller.py
    - src/app/scheduler/jobs/daily_pipeline.py
    - pyproject.toml
decisions:
  - CHARACTER_BIBLE set to 49 words — orange tabby "Mochi" in Mexican household with serapes, clay pottery, lush plants, adobe architecture
  - fal-client installed as project dependency (not just dev) — required at runtime in APScheduler jobs
  - KlingService.submit() uses local fal_client import — fal_client auto-reads FAL_API_KEY from environment
  - _retry_or_fail preserves exact same retry-once pattern as HeyGen v1.0 — kling_pending + kling_pending_retry sentinels
metrics:
  duration: "6 minutes 25 seconds"
  completed_date: "2026-03-19"
  tasks_completed: 2
  files_changed: 7
  tests_added: 20
---

# Phase 09 Plan 02: Kling Service + Video Poller Adaptation Summary

**One-liner:** KlingService with 49-word CHARACTER_BIBLE (orange tabby Mochi in Mexican household), fal.ai sync polling replacing HeyGen HTTP, and daily_pipeline.py routing to Kling with kling_job_id sentinel.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Create kling.py — CHARACTER_BIBLE + KlingService | 4a3593f | src/app/services/kling.py, pyproject.toml |
| 2 | Adapt video_poller.py + daily_pipeline.py | cc5014b | src/app/scheduler/jobs/video_poller.py, src/app/scheduler/jobs/daily_pipeline.py |

## What Was Built

### src/app/services/kling.py (new, 165 lines)

- `CHARACTER_BIBLE`: 49-word Python constant — orange tabby "Mochi", white chest markings, curious/mischievous, Mexican household (serapes, clay pottery, lush plants, adobe architecture)
- `KlingService.submit(script_text)`: calls `fal_client.submit()` (sync) with `fal-ai/kling-video/v3/standard/text-to-video`, duration=20, resolution="1080p", aspect_ratio="9:16"; returns `result.request_id` as `kling_job_id`
- Prompt construction: `CHARACTER_BIBLE + "\n\n" + script_text` — bible always first, unchanged
- `_process_completed_render(job_id, video_url)`: double-processing guard via `.in_("video_status", ["kling_pending", "kling_pending_retry"])` conditional UPDATE; downloads MP4 bytes, uploads to Supabase Storage, updates DB, sends Telegram approval message
- `_handle_render_failure(job_id, error_msg)`: sets `video_status=failed`, sends `send_alert_sync` Telegram alert

### src/app/scheduler/jobs/video_poller.py (updated)

- Replaced `HEYGEN_STATUS_URL` + `requests.get()` with `fal_client.status(settings.kling_model_version, video_id, with_logs=False)` (sync)
- On `status.status == "completed"`: extracts `status.response["video"]["url"]`, calls `kling._process_completed_render()`
- On `status.status == "failed"`: calls `kling._handle_render_failure()`
- `_retry_or_fail`: queries `kling_job_id` column; first timeout (kling_pending/rendering) → `KlingService().submit()` retry + `kling_pending_retry` sentinel; second timeout → mark failed + alert
- `register_video_poller`: job name updated to `"Kling poller for {video_id}"`

### src/app/scheduler/jobs/daily_pipeline.py (updated)

- Block 4f replaced: `HeyGenService` + `pick_background_url` + `background_url` logic removed; `KlingService().submit(script_text=script)` inserted
- `_save_to_content_history`: signature changed to `kling_job_id: str | None = None` (removed `heygen_job_id`, `background_url`); row uses `kling_job_id` column and `VideoStatus.KLING_PENDING`
- `heygen.py` untouched — audit trail preserved

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] fal-client not installed in project venv**
- **Found during:** Task 1 GREEN phase (tests could not import `app.services.kling` because `fal_client` module was missing)
- **Fix:** `uv add fal-client` — added `fal-client==0.13.1` to `pyproject.toml` dependencies (not just dev group — required at runtime)
- **Files modified:** pyproject.toml
- **Commit:** 4a3593f

**2. [Rule 1 - Bug] CHARACTER_BIBLE word count was 38 words (below 40 minimum)**
- **Found during:** Task 1 GREEN phase test run (`test_character_bible_word_count` failed)
- **Fix:** Extended the bible text with more descriptive phrases — added "chest" (white chest markings), "any background" (distinct contrast), "every corner" (mischievous behavior), "tropical" (plants), "clay" (pottery)
- **Files modified:** src/app/services/kling.py
- **Commit:** 4a3593f

**3. [Rule 1 - Bug] Test for `_retry_or_fail` used incorrect mock patching strategy**
- **Found during:** Task 2 GREEN phase — `patch("app.scheduler.jobs.video_poller.KlingService")` failed because KlingService is imported inside the function body, not at module level
- **Fix:** Updated test to patch at `app.services.kling.KlingService` (the import source) rather than the consuming module; removed `importlib.reload()` approach that caused environment issues
- **Files modified:** tests/test_kling_poller.py
- **Commit:** cc5014b

**4. [Rule 1 - Bug] daily_pipeline.py docstring still contained `heygen_job_id` reference**
- **Found during:** Task 2 GREEN phase — `test_daily_pipeline_uses_kling_job_id` text scan found remaining reference in function docstring
- **Fix:** Updated two docstring lines to replace HeyGen references with Kling/fal.ai equivalents
- **Files modified:** src/app/scheduler/jobs/daily_pipeline.py
- **Commit:** cc5014b

## Self-Check: PASSED

| Check | Result |
|-------|--------|
| src/app/services/kling.py exists | FOUND |
| tests/test_character_bible.py exists | FOUND |
| tests/test_kling_service.py exists | FOUND |
| tests/test_kling_poller.py exists | FOUND |
| Commit 2570b6d (RED tests Task 1) | FOUND |
| Commit 4a3593f (GREEN kling.py + fal-client) | FOUND |
| Commit 150d5e5 (RED tests Task 2) | FOUND |
| Commit cc5014b (GREEN poller + pipeline) | FOUND |
| All 20 tests pass | PASSED |
