---
phase: 13-kitten-scenario-video-generation-hook-climax-conclusion-stories
plan: "01"
subsystem: scene-engine
tags: [scene-engine, gpt-4o, scenario-arc, categories, migration, tenacity]
dependency_graph:
  requires:
    - Phase 12 SceneEngine (scene_generation.py base class)
    - categories.json (new data file)
  provides:
    - pick_scenario_arc() method on SceneEngine
    - _generate_scenario_with_backoff module-level function
    - CATEGORIES_JSON_PATH and SCENARIO_TYPE_CATEGORIES constants
    - migration 0012 (prompt_embedding column + check_prompt_similarity function)
  affects:
    - src/app/services/scene_generation.py
    - migrations/0012_phase13_schema.sql
    - src/app/data/categories.json
tech_stack:
  added:
    - categories.json (6 scenario type categories data file)
    - _generate_scenario_with_backoff (module-level tenacity-decorated GPT-4o function)
  patterns:
    - Module-level tenacity retry function for ThreadPoolExecutor compatibility (mirrors prompt_generation.py)
    - categories.json loaded once at SceneEngine.__init__ (mirrors scenes.json pattern)
    - response_format=json_object GPT-4o call returning 4 keys (scenario_description, arc_prompt, caption, mood)
key_files:
  created:
    - src/app/data/categories.json
    - migrations/0012_phase13_schema.sql
  modified:
    - src/app/services/scene_generation.py
decisions:
  - "_generate_scenario_with_backoff is module-level (not instance method) — required for tenacity decorator compatibility in APScheduler ThreadPoolExecutor context; mirrors _call_gpt4o_with_backoff pattern from prompt_generation.py"
  - "categories.json loaded once at SceneEngine.__init__ via _load_categories() — consistent with _load_scene_library() pattern; avoids per-call disk I/O"
  - "pick_scenario_arc() returns 5-tuple (scenario_description, arc_prompt, caption, mood, cost_usd) — adds scenario_description vs pick_scene() 4-tuple for downstream semantic embedding"
  - "Mood validation falls back to 'playful' on unexpected values — avoids pipeline halt for minor GPT-4o drift"
  - "prompt_embedding column type is extensions.vector(1536) — matches scene_embedding column type; text-embedding-3-small dimension"
metrics:
  duration_seconds: 177
  completed_date: "2026-03-30T04:18:46Z"
  tasks_completed: 2
  tasks_total: 2
  files_created: 3
  files_modified: 1
---

# Phase 13 Plan 01: Story-Arc Foundation (Categories, Migration, SceneEngine Extension) Summary

**One-liner:** Hook-climax-conclusion scenario arc foundation: 6-category JSON, prompt_embedding migration 0012, and SceneEngine.pick_scenario_arc() via module-level GPT-4o tenacity backoff function.

## What Was Built

### Task 1: categories.json + Migration 0012

Created `src/app/data/categories.json` with 6 scenario type categories that define the arc-generation guardrails for Phase 13 kitten videos:
- `slapstick` — physical comedy chaos
- `reaction_surprise` — emotional/exaggerated reactions
- `chase` — pursuit building to frantic cute peak
- `investigation_gone_wrong` — curiosity leading to surprise
- `unexpected_nap` — kitten naps in absurd places
- `overconfident_leap` — risky jump with endearing outcome

Created `migrations/0012_phase13_schema.sql` which:
- Adds `prompt_embedding extensions.vector(1536)` column to `content_history` (idempotent ADD COLUMN IF NOT EXISTS)
- Creates `check_prompt_similarity()` SQL function mirroring `check_scene_similarity()` but querying `prompt_embedding` — catches Kling prompt-level stylistic repetition in addition to scenario-level semantic repetition

### Task 2: SceneEngine Extended with pick_scenario_arc()

Extended `src/app/services/scene_generation.py` with:

**Module-level constants:**
- `CATEGORIES_JSON_PATH` — resolved absolute path to categories.json
- `SCENARIO_TYPE_CATEGORIES` — list of 6 category name strings for validation

**Module-level function:**
- `_generate_scenario_with_backoff(client, filled_prompt)` — tenacity-decorated GPT-4o call with 3 attempts (2s→8s→16s backoff), `response_format=json_object`, temperature 0.9, max_tokens 600. Returns `(scenario_data dict, cost_usd)`. Module-level for ThreadPoolExecutor compatibility.

**New SceneEngine methods:**
- `_load_categories()` — loads categories.json once at init, raises on missing/empty
- `_build_scenario_system_prompt(category, rejection_constraints, seasonal_overlay)` — builds hook→climax→conclusion GPT-4o prompt with flowing prose instruction (no timecodes), Mexican domestic setting, arc-aware Spanish caption rules
- `pick_scenario_arc(attempt, rejection_constraints)` — selects random category, calls GPT-4o via backoff function, validates 4 required keys, mood-fallback to "playful", returns `(scenario_description, arc_prompt, caption, mood, cost_usd)` 5-tuple

**Preserved unchanged:** `pick_scene()`, `SeasonalCalendarService`, `SEASONAL_OVERLAYS`, `_build_system_prompt()`, `load_active_scene_rejections()`, `store_scene_rejection()`

## Verification Results

```
categories.json: 6 categories OK
migration 0012 OK (ADD COLUMN IF NOT EXISTS prompt_embedding + check_prompt_similarity)
imports OK (SceneEngine, CATEGORIES_JSON_PATH, SCENARIO_TYPE_CATEGORIES, _generate_scenario_with_backoff)
test_scene_engine.py: 5 passed
test_seasonal_calendar.py: 6 passed
```

## Commits

| Task | Hash | Message |
|------|------|---------|
| 1 | 759ff82 | feat(13-01): add categories.json and migration 0012 for phase 13 schema |
| 2 | 534e416 | feat(13-01): extend SceneEngine with pick_scenario_arc() and scenario arc generation |

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None — no stub values, placeholders, or hardcoded empty data. `pick_scenario_arc()` is fully wired to GPT-4o via `_generate_scenario_with_backoff`. The pipeline call (daily_pipeline.py) is wired in Plan 13-02, not here.

## Self-Check: PASSED

- [x] src/app/data/categories.json exists
- [x] migrations/0012_phase13_schema.sql exists
- [x] src/app/services/scene_generation.py modified
- [x] Commit 759ff82 exists (git log verified)
- [x] Commit 534e416 exists (git log verified)
- [x] All 11 tests pass (5 scene_engine + 6 seasonal_calendar)
