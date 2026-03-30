---
phase: 13
plan: "03"
subsystem: pipeline
tags: [pipeline-wiring, story-arc, dual-embedding, anti-repetition, phase-13]
dependency_graph:
  requires: [13-01, 13-02]
  provides: [daily_pipeline Phase 13 wiring, dual embedding anti-repetition, pick_scenario_arc integration]
  affects: [daily_pipeline.py, content_history persistence, prompt_embedding column]
tech_stack:
  added: []
  patterns: [dual embedding anti-repetition, scene_prompt alias (D-10), arc_prompt to PromptGenerationService (D-07)]
key_files:
  created: []
  modified:
    - src/app/scheduler/jobs/daily_pipeline.py
    - tests/test_pipeline_wiring.py
    - tests/test_kling_backoff.py
decisions:
  - "[13-03]: arc_prompt (3-5 sentence flowing prose arc) passed to PromptGenerationService, not scenario_description — D-07 interface spec"
  - "[13-03]: scene_prompt alias = scenario_description — D-10 semantic rename for scene_prompt column persistence"
  - "[13-03]: prompt_embedding conditional persistence (only if not None) — consistent with other optional fields pattern"
metrics:
  duration: "4 minutes"
  completed_date: "2026-03-29"
  tasks_completed: 1
  files_modified: 3
---

# Phase 13 Plan 03: Pipeline Wiring — Story-Arc with Dual Embedding Anti-Repetition Summary

Phase 13 story-arc pipeline wiring: replaced pick_scene() with pick_scenario_arc(), added prompt_embedding generation + is_too_similar_prompt() check (dual embedding D-09), and extended _save_to_content_history to persist prompt_embedding column.

## What Was Built

daily_pipeline_job now runs the full Phase 13 story-arc pipeline:

1. SceneEngine.pick_scenario_arc() replaces pick_scene() — returns 5-tuple (scenario_description, arc_prompt, caption, mood, cost_usd)
2. scene_prompt alias = scenario_description (D-10 semantic rename — maps to scene_prompt column)
3. arc_prompt (3-5 sentence flowing prose arc) passed to PromptGenerationService (D-07)
4. Step 4h: embed unified_prompt → prompt_embedding for visual/stylistic anti-repetition (D-09)
5. Step 4i: is_too_similar_prompt() check gated by scene_anti_repetition_enabled feature flag
6. _save_to_content_history extended with prompt_embedding parameter, persists conditional row["prompt_embedding"]

## Tasks Completed

| Task | Description | Commit | Status |
|------|-------------|--------|--------|
| 1 | Replace pick_scene() with pick_scenario_arc() + add prompt embedding + dual anti-rep | d80658d | DONE |

## Key Files Modified

- `src/app/scheduler/jobs/daily_pipeline.py` — Phase 13 pipeline wiring, dual embedding, extended _save_to_content_history
- `tests/test_pipeline_wiring.py` — Updated to Phase 13 wiring (12 tests, pick_scenario_arc, dual embedding verification)
- `tests/test_kling_backoff.py` — Fixed pick_scene mock to pick_scenario_arc (Rule 1 auto-fix)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Updated test_kling_backoff.py: pick_scene → pick_scenario_arc**
- **Found during:** Task 1 — broader regression suite
- **Issue:** test_daily_pipeline_skips_kling_when_cb_open used pick_scene mock, causing "not enough values to unpack (expected 5, got 0)" error in pipeline
- **Fix:** Updated mock to pick_scenario_arc returning 5-tuple; added is_too_similar_prompt return_value=False to mock similarity service
- **Files modified:** tests/test_kling_backoff.py
- **Commit:** d80658d

### Design Decision Adjustment

**[Rule 2 - Correctness] Used arc_prompt (not scene_prompt alias) for PromptGenerationService**
- **Issue:** Plan's Change 2 set scene_prompt = scenario_description and implied PromptGenerationService would receive scene_prompt alias. However, interfaces spec (D-07) and RESEARCH.md explicitly state arc_prompt (3-5 sentence flowing prose) goes to PromptGenerationService.
- **Fix:** pass arc_prompt to generate_unified_prompt(arc_prompt) — not scene_prompt/scenario_description
- **Impact:** Correct per D-07 specification; scene_prompt alias still used for embedding and column persistence
- **Files modified:** src/app/scheduler/jobs/daily_pipeline.py

## Verification Results

```
Pipeline wiring validated (keyword checks pass)
12 tests in test_pipeline_wiring.py: PASSED
190 total tests (3 skipped, 2 deselected): ALL PASSED
```

## Must-Have Truths Verified

- [x] daily_pipeline_job calls scene_engine.pick_scenario_arc() instead of pick_scene()
- [x] pipeline generates prompt_embedding for the unified_prompt after PromptGenerationService
- [x] both is_too_similar_scene (scenario_description) and is_too_similar_prompt (unified_prompt) are checked
- [x] _save_to_content_history persists prompt_embedding column
- [x] arc-aware caption from pick_scenario_arc() flows through to content_history.caption

## Known Stubs

None — all pipeline wiring is fully functional.

## Self-Check: PASSED
