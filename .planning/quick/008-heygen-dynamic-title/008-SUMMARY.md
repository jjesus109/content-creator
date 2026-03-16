---
phase: quick-008
plan: 01
subsystem: video-production
tags: [heygen, pipeline, title, dashboard]
dependency_graph:
  requires: []
  provides: [dynamic-heygen-title]
  affects: [heygen-submit, daily-pipeline]
tech_stack:
  added: []
  patterns: [optional-param-with-fallback, lazy-import-inline]
key_files:
  created: []
  modified:
    - src/app/services/heygen.py
    - src/app/scheduler/jobs/daily_pipeline.py
key_decisions:
  - "Inline 'from datetime import date' import follows lazy-import convention already used in this file rather than adding to module top"
  - "resolved_title truncated to 100 chars in heygen.py, not at the call site — enforcement is centralized in the service"
metrics:
  duration: 2 min
  completed: 2026-03-16
  tasks_completed: 2
  files_modified: 2
---

# Quick Task 008: HeyGen Dynamic Title Summary

**One-liner:** HeyGenService.submit() now accepts an optional title param, falling back to 'Video YYYY-MM-DD'; daily_pipeline.py passes topic_summary as the title so every HeyGen render is identifiable by its content topic in the dashboard.

## What Was Built

Replaced the hardcoded `"Daily video"` title in the HeyGen API payload with a dynamic value derived from the pipeline's `topic_summary`. When no title is supplied the service builds a date-based fallback (`"Video YYYY-MM-DD"`), and all values are truncated to 100 characters before submission.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Add optional title param to HeyGenService.submit() | 820cefa | src/app/services/heygen.py |
| 2 | Pass topic_summary as title at call site in daily_pipeline.py | f4378c7 | src/app/scheduler/jobs/daily_pipeline.py |

## Changes Made

### src/app/services/heygen.py

- Changed `submit()` signature from `(self, script_text, background_url)` to `(self, script_text, background_url, title: str | None = None)`
- Added inline `from datetime import date` import (follows lazy-import convention already used in this file)
- Added `resolved_title = (title or f"Video {date.today().isoformat()}")[:100]` before payload construction
- Replaced `"title": "Daily video"` in payload with `"title": resolved_title`
- Updated docstring to document new `title` param with fallback and truncation behavior

### src/app/scheduler/jobs/daily_pipeline.py

- Changed `heygen_svc.submit(script_text=script, background_url=background_url)` to include `title=topic_summary`
- `topic_summary` is already in scope at the call site (assigned at the top of the attempt loop at line 75)

## Deviations from Plan

None — plan executed exactly as written.

## Test Results

- 21 tests pass, 2 skipped
- 1 pre-existing failure: `test_hard_word_limit_constant` in `tests/test_quick_001_script_generation.py` asserts `HARD_WORD_LIMIT == 120` but the constant was already changed to `90` in a prior commit (`31df53e`). This failure predates and is unrelated to quick-008 changes (confirmed by `git stash` round-trip).
- Hardcoded `"Daily video"` string: absent from `src/app/services/heygen.py` (grep returns no output)

## Self-Check: PASSED

Files modified:
- FOUND: /Users/jesusalbino/Projects/content-creation/src/app/services/heygen.py
- FOUND: /Users/jesusalbino/Projects/content-creation/src/app/scheduler/jobs/daily_pipeline.py

Commits:
- FOUND: 820cefa — feat(quick-008): add optional title param to HeyGenService.submit()
- FOUND: f4378c7 — feat(quick-008): pass topic_summary as title to heygen_svc.submit()
