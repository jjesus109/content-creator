---
phase: quick-260320-dlf
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - src/app/services/scene_generation.py
autonomous: true
requirements: [DLF-01]

must_haves:
  truths:
    - "The scene_prompt passed to KlingService.submit() is always in English"
    - "The caption (for social media posts) remains in Spanish"
    - "Seasonal overlays injected into the GPT-4o system prompt are in English"
    - "Rejection constraint text injected into the system prompt is in English"
  artifacts:
    - path: "src/app/services/scene_generation.py"
      provides: "Updated GPT-4o system prompt that produces scene_prompt in English"
      contains: "scene prompt in English"
  key_links:
    - from: "SceneEngine._build_system_prompt"
      to: "KlingService.submit(scene_prompt)"
      via: "daily_pipeline_job -> kling_svc.submit(scene_prompt)"
      pattern: "scene_prompt.*english"
---

<objective>
Ensure all prompts sent to Kling AI are in English.

The SceneEngine._build_system_prompt() method is written entirely in Spanish, causing GPT-4o
to generate the scene_prompt in Spanish. That Spanish scene_prompt is passed verbatim to
KlingService.submit() and forwarded to Kling AI 3.0, which produces better results with
English prompts.

Purpose: Improve Kling video generation quality by providing English-language prompts.
Output: Updated scene_generation.py with English GPT-4o system prompt that produces
English scene_prompt values while keeping the Spanish caption unchanged.
</objective>

<execution_context>
@/Users/jesusalbino/Projects/content-creation/.claude/get-shit-done/workflows/execute-plan.md
@/Users/jesusalbino/Projects/content-creation/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@src/app/services/scene_generation.py
@src/app/services/kling.py
</context>

<tasks>

<task type="auto">
  <name>Task 1: Rewrite SceneEngine system prompt in English (scene_prompt only)</name>
  <files>src/app/services/scene_generation.py</files>
  <action>
Modify `_build_system_prompt()` in `SceneEngine` and `SEASONAL_OVERLAYS` in `scene_generation.py`
so that GPT-4o produces the `scene_prompt` in English and the `caption` in Spanish.

**Changes to `_build_system_prompt`:**

Replace the entire Spanish system prompt string with an English equivalent. The new prompt must:

1. Instruct GPT-4o to expand the scene combo into a 2-3 sentence English visual prompt for Kling AI video generation (scene_prompt field).
2. Instruct GPT-4o to generate a 5-8 word Spanish caption for the social post (caption field), with the same formula: [observation] + [implied personality].
3. Include the CHARACTER_BIBLE (already in English) unchanged.
4. Include the selected scene combo fields (location, activity, mood) — these can remain as-is since they come from scenes.json and are already in English.
5. Include any seasonal_overlay text — see SEASONAL_OVERLAYS change below.
6. Include any rejection_constraints text — translate the "EVITA estas escenas" block to English ("AVOID these scenes (rejected by creator):").
7. Keep the JSON output instruction requiring exactly two keys: `scene_prompt` and `caption`.

Example replacement for the main instruction block (adapt as needed):
```
You are a creative director for cat video production.
You are given a scene composition (location + activity + mood). Your task:
1. Expand it into a vivid 2-3 sentence visual prompt in ENGLISH for AI video generation (scene_prompt).
2. Generate a Spanish caption of 5-8 words for the social media post, following the formula: [observation] + [implied personality] (caption).

CHARACTER — Character Bible (include in the prompt):
{CHARACTER_BIBLE}

SELECTED SCENE:
- Location: {combo['location']}
- Activity: {combo['activity']}
- Mood: {combo['mood']}

INSTRUCTIONS FOR SCENE PROMPT (scene_prompt):
- 2-3 complete sentences, describing the scene visually for video generation
- Must be in ENGLISH — Kling AI generates better results with English prompts
- Include the name "Mochi" and reference the Character Bible
- Describe the action, environment, lighting, and mood
- Optimized for Kling AI (video generation): specific, visual, cinematic

INSTRUCTIONS FOR CAPTION (caption):
- Exactly 5-8 words in SPANISH
- Formula: [what the cat does/observes] + [implied cat personality]
- Examples: "Mochi descubre los secretos de la cocina", "El gato vigila su territorio con calma"
- NO hashtags, NO emojis

Return ONLY valid JSON with exactly these two keys:
{{"scene_prompt": "...", "caption": "..."}}
```

**Changes to `SEASONAL_OVERLAYS`:**

Translate all overlay text values to English. The theme name keys (e.g. "Día de Independencia") can stay as-is since they are only used for logging. Only the overlay_text strings (the second element of each tuple) need to be in English, since they are injected into the GPT-4o prompt. Translate all 5 entries:

- (9, 16) Día de Independencia: "Today is Mexico's Independence Day (September 16). Subtly incorporate Mexican celebration elements into the scene — for example, a green-white-red flag visible in the background, or colorful lights. Do not change the cat's activity; only add patriotic festive atmosphere."
- (11, 1) Día de Muertos: "Today marks the beginning of Día de Muertos (November 1). Add a subtle visual reference to the tradition — nearby cempasúchil flowers, lit candles, or an altar in the background. Keep the cat's natural behavior; only the atmosphere changes."
- (11, 2) Día de Muertos: "Today is the second day of Día de Muertos (November 2). Add a subtle visual reference to the tradition — nearby cempasúchil flowers, lit candles, or an altar in the background. Keep the cat's natural behavior; only the atmosphere changes."
- (11, 20) Día de la Revolución: "Today is Mexico's Revolution Day (November 20). Add subtle elements of Mexican pride to the environment — flag colors, tricolor decoration in the background. The cat's behavior does not change."
- (8, 8) Día Internacional del Gato: "Today is International Cat Day (August 8). Make the scene especially celebratory for Mochi — perhaps with a special bow, or showing his best side. The atmosphere can be a little more festive than usual."

**Changes to `_build_system_prompt` rejection block:**

Replace the Spanish rejection text template:
```python
rejection_lines = ["\nEVITA estas escenas (rechazadas por el creador):"]
```
with:
```python
rejection_lines = ["\nAVOID these scenes (rejected by creator):"]
```

Also update the seasonal_text block header:
```python
seasonal_text = f"\n\nSPECIAL SEASONAL CONTEXT:\n{seasonal_overlay}"
```
(was `CONTEXTO ESTACIONAL ESPECIAL`)

No other files need changes. CHARACTER_BIBLE in kling.py is already in English. KlingService.submit() and daily_pipeline.py are unchanged.
  </action>
  <verify>
    <automated>cd /Users/jesusalbino/Projects/content-creation && python -m pytest tests/test_scene_engine.py tests/test_seasonal_calendar.py -x -q 2>&1 | tail -20</automated>
  </verify>
  <done>
All scene engine and seasonal calendar tests pass. The GPT-4o system prompt instructs scene_prompt in English and caption in Spanish. SEASONAL_OVERLAYS overlay text strings are in English. The rejection constraint injection and seasonal overlay injection are in English.
  </done>
</task>

<task type="auto">
  <name>Task 2: Verify full test suite still passes</name>
  <files></files>
  <action>
Run the full test suite to confirm no regressions. No code changes — this is a verification step only.

If any test fails due to the system prompt change (e.g., a test asserting Spanish text in the prompt), update that test to match the new English prompt. Tests asserting that `caption` is in Spanish should still pass unchanged since caption language is not tested by unit tests (they use mock responses).
  </action>
  <verify>
    <automated>cd /Users/jesusalbino/Projects/content-creation && python -m pytest tests/ -x -q 2>&1 | tail -30</automated>
  </verify>
  <done>
All tests pass (same count as before this change, currently 149 tests). No regressions introduced.
  </done>
</task>

</tasks>

<verification>
- `SceneEngine._build_system_prompt()` produces a system prompt in English instructing GPT-4o to return scene_prompt in English
- The caption instruction inside the same prompt explicitly requests Spanish output
- `SEASONAL_OVERLAYS` overlay_text values are all in English
- Rejection constraint injection uses English header text
- All 149 existing tests pass with no regressions
- `python -m pytest tests/ -x -q` exits with code 0
</verification>

<success_criteria>
Kling AI receives English scene prompts. The Spanish caption for social posts is unaffected. No test regressions.
</success_criteria>

<output>
After completion, create `.planning/quick/260320-dlf-translate-spanish-prompts-into-english-p/260320-dlf-SUMMARY.md`
</output>
