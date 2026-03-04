---
phase: quick-001
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - src/app/services/script_generation.py
autonomous: true
requirements: []

must_haves:
  truths:
    - "Every generated script begins with an emotional/curiosity hook as its first phrase"
    - "No generated script exceeds 120 words after the pipeline finishes"
    - "The hard cap is enforced at generation time in the prompt AND as a post-generation guard"
  artifacts:
    - path: "src/app/services/script_generation.py"
      provides: "Updated generate_script + summarize_if_needed with hook requirement and 120-word hard cap"
      contains: "HARD_WORD_LIMIT = 120"
  key_links:
    - from: "generate_script guardrails section"
      to: "HARD_WORD_LIMIT constant"
      via: "prompt string interpolation"
      pattern: "HARD_WORD_LIMIT"
    - from: "summarize_if_needed"
      to: "HARD_WORD_LIMIT"
      via: "target_words override logic"
      pattern: "HARD_WORD_LIMIT"
---

<objective>
Tighten script generation in two ways:

1. Add a hard 120-word absolute cap — currently the prompt allows up to `target_words * 1.15` and truncation is a fallback. The new behaviour: the prompt instructs Claude that 120 words is the unbreakable ceiling, and the post-generation guard uses 120 (not `target_words`) as the truncation threshold.

2. Require the first phrase of every script to be an emotional/curiosity hook. The `generate_script` system prompt currently lists the 6 pillars but does not mandate a hook as the literal first words. The `summarize_if_needed` pass has hooks, but not every script goes through that path.

Purpose: Higher viewer retention by leading with an immediate hook and shorter scripts that fit comfortably within 60-second video.

Output: One modified file — `src/app/services/script_generation.py`.
</objective>

<execution_context>
@./.claude/get-shit-done/workflows/execute-plan.md
@./.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@src/app/services/script_generation.py
@src/app/services/mood.py
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Add HARD_WORD_LIMIT constant and update generate_script prompt</name>
  <files>src/app/services/script_generation.py</files>
  <behavior>
    - _word_count("hola mundo") == 2
    - _word_count("") == 0
    - generate_script system prompt contains the string "HARD_WORD_LIMIT" interpolated value (120)
    - generate_script system prompt contains a hook instruction as the mandatory first-phrase requirement
    - HARD_WORD_LIMIT = 120 defined at module level
  </behavior>
  <action>
At the top of `src/app/services/script_generation.py`, immediately after the cost-rate constants, add:

```python
# Hard word cap — applied at generation time and as post-generation guard.
# Overrides target_words when target_words > this limit.
HARD_WORD_LIMIT = 120
```

In `generate_script`, update the `<guardrails>` section of the system prompt:

Replace the line:
```
f"- Objetivo de palabras: ~{target_words} palabras (puedes ir hasta {int(target_words * 1.15)} — se resumira si excedes)\n"
```

With:
```python
f"- Objetivo de palabras: ~{min(target_words, HARD_WORD_LIMIT)} palabras. LIMITE ABSOLUTO: {HARD_WORD_LIMIT} palabras. No se permite ningun guion que exceda este limite bajo ninguna circunstancia.\n"
```

Also add a new mandatory instruction at the top of `<instructions>` (before the 6 pillars), as the first bullet:
```
"0. PRIMERA FRASE OBLIGATORIA: El guion debe comenzar con un hook emocional o de curiosidad — una pregunta inquietante, una contradiccion sorprendente, o una imagen vivida que genere tension inmediata. Esta primera frase es el gancho que decide si el espectador sigue mirando.\n"
```

Number the existing pillar list starting from 1 (unchanged from current numbering — no renumbering needed, they are already 1-6). Insert the new item 0 before item 1.
  </action>
  <verify>
    <automated>cd /Users/jesusalbino/Projects/content-creation && python -c "
from src.app.services.script_generation import HARD_WORD_LIMIT, _word_count
assert HARD_WORD_LIMIT == 120, f'Expected 120, got {HARD_WORD_LIMIT}'
assert _word_count('hola mundo') == 2
assert _word_count('') == 0
print('PASS: HARD_WORD_LIMIT =', HARD_WORD_LIMIT)
"
    </automated>
  </verify>
  <done>HARD_WORD_LIMIT = 120 is importable from script_generation module; generate_script system prompt references 120 as absolute ceiling; hook instruction is the first mandatory item in the instructions block.</done>
</task>

<task type="auto">
  <name>Task 2: Apply hard cap in summarize_if_needed and update its hook instructions</name>
  <files>src/app/services/script_generation.py</files>
  <action>
In `summarize_if_needed`, replace the effective_target logic so it always caps at HARD_WORD_LIMIT:

At the start of the method body (after the docstring), add:
```python
effective_target = min(target_words, HARD_WORD_LIMIT)
```

Replace all subsequent uses of `target_words` within this method with `effective_target`:
- The early-exit check: `if _word_count(script) <= effective_target:`
- The log message: `_word_count(script), effective_target`
- The user prompt: `f"Resume y optimiza este guion a aproximadamente {effective_target} palabras (maximo {int(effective_target * 1.05)}):\n\n"`
- The `_call_claude` max_tokens: `max_tokens=effective_target * 5`
- The overshoot guard: `if final_count > effective_target:` and `words[:effective_target]` and `logger.warning("... target: %d) ...", final_count, effective_target, ...)`

Also update the summarize system prompt `<guardrails>` section — replace the existing word-limit guardrail:
```
"- EL GUION FINAL NO debe exceder de ninguna manera el limite de palabras estricto.\n"
```
With:
```python
f"- EL GUION FINAL NO debe exceder {HARD_WORD_LIMIT} palabras bajo ninguna circunstancia.\n"
f"- La primera frase del guion optimizado DEBE ser un hook emocional o de curiosidad.\n"
```

No changes to the hook list (narrative hook, emotional hook, curiosity hook, contrary POV) — those 4 items already exist in the summarize prompt and are kept.
  </action>
  <verify>
    <automated>cd /Users/jesusalbino/Projects/content-creation && python -c "
import inspect
from src.app.services.script_generation import ScriptGenerationService, HARD_WORD_LIMIT
src = inspect.getsource(ScriptGenerationService.summarize_if_needed)
assert 'effective_target' in src, 'effective_target not found in summarize_if_needed'
assert 'HARD_WORD_LIMIT' in src, 'HARD_WORD_LIMIT not referenced in summarize_if_needed'
print('PASS: summarize_if_needed uses effective_target + HARD_WORD_LIMIT')
"
    </automated>
  </verify>
  <done>summarize_if_needed uses effective_target = min(target_words, HARD_WORD_LIMIT) throughout; the 120-word ceiling is both prompted and enforced in the truncation fallback; hook instruction added to summarize guardrails.</done>
</task>

</tasks>

<verification>
After both tasks complete:

1. Import check: `python -c "from src.app.services.script_generation import HARD_WORD_LIMIT; assert HARD_WORD_LIMIT == 120"`
2. Source inspection: Confirm `generate_script` system prompt contains "120" and hook instruction as item 0.
3. Source inspection: Confirm `summarize_if_needed` uses `effective_target` and references `HARD_WORD_LIMIT`.
4. No regressions: `cd /Users/jesusalbino/Projects/content-creation && python -m pytest tests/ -x -q` — all existing smoke and E2E tests pass.
</verification>

<success_criteria>
- HARD_WORD_LIMIT = 120 defined at module level in script_generation.py
- generate_script prompt: first instruction is a mandatory hook as the opening phrase; word limit set to min(target_words, 120) with 120 as the unbreakable ceiling
- summarize_if_needed: effective_target = min(target_words, 120) used everywhere; truncation guard also uses 120
- All existing tests pass (pytest tests/ -x -q)
- A script with target_words=200 (long duration) is now bounded to 120 words, not 200
</success_criteria>

<output>
After completion, create `.planning/quick/001-improve-script-prompt-word-limit-hook/001-SUMMARY.md`
</output>
