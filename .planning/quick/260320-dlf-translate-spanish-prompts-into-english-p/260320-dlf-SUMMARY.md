---
phase: quick-260320-dlf
plan: 01
subsystem: scene-generation
tags: [scene-engine, kling, gpt4o, english-prompts, localization]
dependency_graph:
  requires: []
  provides: [english-scene-prompts-to-kling]
  affects: [scene_generation.py, test_seasonal_calendar.py]
tech_stack:
  added: []
  patterns: [system-prompt-in-english, caption-in-spanish]
key_files:
  created: []
  modified:
    - src/app/services/scene_generation.py
    - tests/test_seasonal_calendar.py
decisions:
  - "GPT-4o system prompt rewritten in English to produce scene_prompt in English; caption instruction explicitly requests Spanish output"
  - "SEASONAL_OVERLAYS overlay_text values translated to English; theme_name keys (Spanish) unchanged — logging/display only"
  - "Rejection constraint header changed from 'EVITA estas escenas' to 'AVOID these scenes'"
  - "Seasonal overlay section header changed from 'CONTEXTO ESTACIONAL ESPECIAL' to 'SPECIAL SEASONAL CONTEXT'"
metrics:
  duration_minutes: 2
  completed_date: "2026-03-20"
  tasks_completed: 2
  files_modified: 2
---

# Quick Task 260320-dlf: Translate Spanish Prompts to English Summary

**One-liner:** GPT-4o system prompt rewritten in English so Kling AI receives English scene_prompt while Spanish captions for social posts remain unchanged.

## Objective

The `SceneEngine._build_system_prompt()` method was written entirely in Spanish, causing GPT-4o to generate `scene_prompt` in Spanish. Since Kling AI 3.0 produces better video results with English prompts, all prompt instructions directed at GPT-4o (scene_prompt guidance, seasonal overlays, rejection constraints) were translated to English. The caption instruction explicitly requests Spanish output, so social post captions are unaffected.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Rewrite SceneEngine system prompt in English | c0687fb | src/app/services/scene_generation.py, tests/test_seasonal_calendar.py |
| 2 | Verify full test suite still passes | (no code change) | — |

## Changes Made

### src/app/services/scene_generation.py

- `_build_system_prompt()`: Replaced Spanish system prompt string with English equivalent. English instructions produce `scene_prompt` in English. Spanish caption instruction retained explicitly.
- `SEASONAL_OVERLAYS`: Translated all 5 overlay_text values to English. Theme name keys (used for logging only) left in Spanish.
- Rejection constraint block: `"EVITA estas escenas (rechazadas por el creador):"` → `"AVOID these scenes (rejected by creator):"`
- Seasonal overlay header: `"CONTEXTO ESTACIONAL ESPECIAL"` → `"SPECIAL SEASONAL CONTEXT"`
- Rejection constraint default reason: `"sin razón"` → `"no reason given"`

### tests/test_seasonal_calendar.py

- Updated 5 overlay assertions to match English text patterns (e.g., `"septiembre"` → `"September"`, `"noviembre"` → `"November"`, `"agosto"` → `"August"`, `"Revolución"` → `"Revolution"`, `"Independencia"` → `"Independence"`).

## Test Results

- Scene engine + seasonal calendar tests: 11/11 passed
- Full suite: 158 passed, 1 failed (pre-existing, out of scope), 5 skipped
- No regressions introduced by this task

## Deviations from Plan

None — plan executed exactly as written.

## Deferred Items (Out of Scope)

- `test_kling_fal_arguments_locked_spec` fails because a pre-existing uncommitted change in `src/app/services/kling.py` changed `duration` from `20` to `DEFAULT_KLING_DURATION = 15`. This predates this task and is unrelated to prompt translation. Logged for separate resolution.

## Self-Check: PASSED

- [x] `src/app/services/scene_generation.py` modified and committed (c0687fb)
- [x] `tests/test_seasonal_calendar.py` updated and committed (c0687fb)
- [x] All scene engine and seasonal calendar tests pass (11/11)
- [x] No regressions from this task (158 passed, same failures as baseline)
