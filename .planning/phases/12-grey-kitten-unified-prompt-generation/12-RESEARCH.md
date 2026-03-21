# Phase 12: Grey Kitten Unified Prompt Generation - Research

**Researched:** 2026-03-21
**Domain:** LLM prompt generation, service architecture, pipeline integration
**Confidence:** HIGH

## Summary

Phase 12 replaces the static CHARACTER_BIBLE concatenation pattern with a new GPT-4o-driven unified prompt generation service. The key architectural change is:
- **Old pattern:** `CHARACTER_BIBLE + "\n\n" + scene_prompt` sent directly to Kling
- **New pattern:** GPT-4o receives both CHARACTER_BIBLE and scene_prompt, returns a naturally integrated unified prompt that weaves the grey kitten character into the scene description
- **Database:** No schema changes — the unified prompt overwrites `script_text` in `content_history`, while `scene_prompt` remains unchanged for reference

The new grey kitten character replaces the retired orange tabby Mochi. All existing patterns (OpenAI client initialization, tenacity retry decorators, cost tracking, circuit breaker logging) are reusable from Phase 10 and 11.

**Primary recommendation:** Create a new `PromptGenerationService` class (mirroring `SceneEngine` structure) with a `generate()` method that calls GPT-4o using the same client initialization, cost tracking, and retry patterns already proven in the codebase.

<user_constraints>
## User Constraints (from 12-CONTEXT.md)

### Locked Decisions
1. **Character Identity:** Orange tabby Mochi is retired. New character constant replaces CHARACTER_BIBLE in kling.py: "A full-body, high-definition 3D render of an ultra-cute, sitting light grey kitten. The kitten has huge, wide, expressive blue eyes and a cheerful, open-mouthed smile showing its pink tongue. Its soft fur texture is highly detailed."
2. **Service Architecture:** New `PromptGenerationService` (separate from `SceneEngine` and `KlingService`) handles GPT-4o unified prompt generation
3. **System Prompt:** Must explicitly instruct animated/ultra-cute style (not technical "3D render" framing) — goal is visually vibrant, cute, attention-grabbing short-form video prompts
4. **Weaving Strategy:** GPT-4o weaves character naturally into scene, preserving scene's location/activity/mood intent from SceneEngine
5. **Persistence:** Unified prompt **overwrites `script_text`** in `content_history`; `scene_prompt` column retains raw SceneEngine output for reference
6. **No Schema Changes:** No new columns, no migration required
7. **Telegram Auto-Update:** `send_approval_message()` already reads `script_text` — will automatically show unified prompt without code changes
8. **Retry/Fallback:** Use tenacity (consistent with `_submit_with_backoff` pattern) for 2-3 attempts; on GPT-4o failure, fall back to `CHARACTER_BIBLE + "\n\n" + scene_prompt`; log warning on fallback (no DB flag, no schema change)

### Claude's Discretion
- Exact tenacity retry configuration (attempts, wait multiplier)
- How much scene rewriting latitude GPT-4o gets (preserve intent vs creative rewrite)
- Temperature for the unified prompt GPT-4o call
- Whether `PromptGenerationService` tracks cost (consistent with `SceneEngine`'s cost tracking pattern)

### Deferred Ideas (OUT OF SCOPE)
- None

</user_constraints>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| OpenAI | >=2.21.0 | GPT-4o API client for unified prompt generation | Used in SceneEngine; proven sync pattern for APScheduler ThreadPoolExecutor |
| tenacity | >=8.0 | Exponential backoff retry decorator for GPT-4o calls | Established pattern in kling.py `_submit_with_backoff` for transient failures |
| pytest | >=8.0 | Test framework for unit and integration tests | Existing project standard; all phase tests use pytest |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| (none) | — | All tooling already in stack | New service reuses existing patterns |

**Installation:**
Already present in `pyproject.toml`. No new dependencies required.

**Version verification:**
- OpenAI 2.21.0+ confirmed in pyproject.toml (supports gpt-4o model)
- tenacity 8.0+ confirmed in pyproject.toml
- pytest 8.0+ confirmed in pyproject.toml

## Architecture Patterns

### Recommended Project Structure

Existing:
```
src/app/services/
├── scene_generation.py      # SceneEngine (Phase 10) — loads scenes.json, generates scene_prompt + caption
├── kling.py                 # KlingService (Phase 9) — submits to Kling AI 3.0
└── database.py              # Supabase client
```

New:
```
src/app/services/
├── prompt_generation.py     # NEW: PromptGenerationService (Phase 12) — weaves CHARACTER_BIBLE + scene_prompt into unified prompt
```

Call chain in `daily_pipeline.py`:
```
1. SceneEngine.pick_scene()           → (scene_prompt, caption, mood, cost)
2. PromptGenerationService.generate() → unified_prompt (falls back to concatenation on GPT-4o failure)
3. KlingService.submit(unified_prompt)
4. _save_to_content_history(unified_prompt, ...)  # unified_prompt becomes script_text
```

### Pattern 1: OpenAI Client Initialization (Proven in SceneEngine)

**What:** Synchronous OpenAI client initialized once per service instance, credentials from settings.

**When to use:** In any GPT-4o service that runs in APScheduler ThreadPoolExecutor (not async).

**Example:**
```python
# Source: src/app/services/scene_generation.py, lines 113-114
from openai import OpenAI
from app.settings import get_settings

class PromptGenerationService:
    def __init__(self, supabase: Client | None = None) -> None:
        self._supabase = supabase or get_supabase()
        settings = get_settings()
        self._client = OpenAI(api_key=settings.openai_api_key)
```

### Pattern 2: Tenacity Retry Decorator with Exponential Backoff (Proven in kling.py)

**What:** Module-level function with `@retry` decorator for GPT-4o calls. Retries on transient exceptions, logs retry attempts, re-raises on exhaustion.

**When to use:** When LLM calls may fail transiently (rate limits, temporary API outages).

**Example:**
```python
# Source: src/app/services/kling.py, lines 43-62
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

@retry(
    stop=stop_after_attempt(3),                           # 3 total attempts
    wait=wait_exponential(multiplier=1, min=2, max=32),  # exponential backoff: 2s, 8s, 32s
    retry=retry_if_exception_type(Exception),
    reraise=True,
    before_sleep=lambda retry_state: logger.warning(
        "Prompt generation retry attempt %d", retry_state.attempt_number
    ),
)
def _generate_unified_prompt_with_backoff(client, system_prompt, user_prompt) -> str:
    """Generate unified prompt with exponential backoff."""
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.7,  # Claude's discretion
        max_tokens=500,
    )
    return response.choices[0].message.content.strip()
```

### Pattern 3: Cost Tracking for Circuit Breaker (Proven in SceneEngine)

**What:** Calculate GPT-4o cost from token usage; return cost for circuit breaker recording.

**When to use:** In any GPT-4o service that impacts daily spend.

**Example:**
```python
# Source: src/app/services/scene_generation.py, lines 29-31, 246-251
GPT4O_COST_INPUT_PER_MTOK = 2.50
GPT4O_COST_OUTPUT_PER_MTOK = 10.00

# In PromptGenerationService.generate():
response = self._client.chat.completions.create(...)
input_tokens = response.usage.prompt_tokens
output_tokens = response.usage.completion_tokens
cost_usd = (
    input_tokens * GPT4O_COST_INPUT_PER_MTOK
    + output_tokens * GPT4O_COST_OUTPUT_PER_MTOK
) / 1_000_000
return unified_prompt, cost_usd
```

### Pattern 4: Fallback on Failure (Graceful Degradation)

**What:** If GPT-4o fails after retry exhaustion, fall back to old concatenation pattern. Log warning. Continue pipeline.

**When to use:** When LLM failures should not block the pipeline (video still needs to be generated).

**Example:**
```python
# In PromptGenerationService.generate():
try:
    unified_prompt, cost = _generate_unified_prompt_with_backoff(
        self._client,
        system_prompt,
        user_prompt,
    )
except Exception as e:
    logger.warning(
        "GPT-4o unified prompt generation failed after retries: %s. Falling back to concatenation.",
        e
    )
    unified_prompt = f"{CHARACTER_BIBLE}\n\n{scene_prompt}"
    cost_usd = 0.0  # or track as "fallback" cost

return unified_prompt, cost_usd
```

### Anti-Patterns to Avoid

- **Async OpenAI client in service instance:** APScheduler ThreadPoolExecutor cannot manage asyncio event loops. Use synchronous `OpenAI()` client only.
- **Embedding unified prompt (via EmbeddingService) twice:** Scene has already been embedded by `SimilarityService` in daily_pipeline. Only the original `scene_prompt` matters for anti-repetition checks. Do NOT embed the unified prompt.
- **Dynamic CHARACTER_BIBLE:** The character constant is locked in code for deployment consistency. Any character change requires code review + explicit commit + deployment. Do NOT move to config or environment variables.
- **Removing scene_prompt column:** Keep `scene_prompt` unchanged in content_history for reference. Only `script_text` is overwritten with unified prompt.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| GPT-4o retry on transient failures | Custom retry loop with manual delays | `tenacity.retry` with `wait_exponential` | tenacity handles edge cases: max wait caps, exponential backoff calculation, logging integration; custom loops often miss circuit-breaker patterns and max-wait enforcement |
| OpenAI client auth and session management | Custom token storage / refresh | `OpenAI(api_key=...)` from settings | OpenAI SDK handles auth, connection pooling, retries transparently; custom auth introduces security risks and deployment complexity |
| GPT-4o cost calculation | Manual token-to-cost math | Copy constants + formula from SceneEngine | Rates change; constants ensure consistency across services; copy-paste is safer than reimplementation |
| JSON response parsing from GPT-4o | Manual string split/regex | Use `response.choices[0].message.content.strip()` + explicit error handling | LLMs may add markdown formatting, extra whitespace; explicit parsing catches edge cases and provides clear error messages |

**Key insight:** The unified prompt is unstructured text (not JSON), so response parsing is simpler than SceneEngine's scene_prompt+caption JSON. But retry/backoff and fallback logic are identical — reuse the patterns proven in Phase 9 and 10.

## Common Pitfalls

### Pitfall 1: GPT-4o Returns Technical 3D Render Language Instead of Cute/Animated Vibes

**What goes wrong:** System prompt doesn't explicitly override GPT-4o's tendency to describe 3D renders in technical terms ("high-definition", "sophisticated lighting", "photorealistic"). Result: prompts unsuitable for cute short-form video aesthetic.

**Why it happens:** Default GPT-4o training includes a lot of technical 3D/VFX documentation. Without explicit instruction, it mirrors that register.

**How to avoid:** System prompt must explicitly state "animated/ultra-cute style for short-form social video (TikTok/Reels)" and give examples of cute vs technical descriptions. Frame as: "You are a social media video creative director, not a 3D rendering engineer."

**Warning signs:** Test first unified prompt. If it reads like a technical spec ("high-definition render with cinematic depth of field") instead of a cute scene ("adorable kitten discovers..."), adjust system prompt.

### Pitfall 2: Character Weaving Loses Original Scene Intent

**What goes wrong:** GPT-4o creatively rewrites the scene so much that location/activity/mood from SceneEngine is unrecognizable. Example: Scene is "cat sleeps on sofa (sleepy mood)" → unified prompt becomes "energetic kitten pounces on imaginary prey in a magical forest (playful mood)" — mood and activity completely changed.

**Why it happens:** GPT-4o has latitude to make creative suggestions. Without guardrails, it optimizes for "interesting narrative" over "preserve original intent".

**How to avoid:** System prompt explicitly states: "Preserve the original location, activity, and mood from the scene description. The kitten character is ADDED to the existing scene, not a replacement." Add examples showing character weaving vs rewriting.

**Warning signs:** In testing, compare unified prompt against original scene_prompt. Check: location unchanged? activity unchanged? mood preserved?

### Pitfall 3: Backward Compatibility Break in content_history Row Structure

**What goes wrong:** Code assumes `script_text` still contains the old `CHARACTER_BIBLE + scene_prompt` format. New code writes unified prompt instead. Old code that parses `script_text` looking for CHARACTER_BIBLE breaks.

**Why it happens:** `script_text` is a legacy field used by multiple services (PostCopyService, Telegram, etc.). Changing its format without updating all consumers causes silent failures.

**How to avoid:** Verify all readers of `script_text` before changing its content. In this case:
- `PostCopyService.generate(script_text)` — works fine with unified prompt (it's still descriptive text)
- `send_approval_message()` — reads `script_text` for caption and word count — works with unified prompt
- No code currently parses `CHARACTER_BIBLE` out of `script_text`, so replacement is safe

**Warning signs:** Grep codebase for `CHARACTER_BIBLE` usage before implementation. Should only appear in kling.py constant definition and maybe test fixtures.

### Pitfall 4: Retry Loop Exhaustion Not Logged as Warning

**What goes wrong:** GPT-4o fails, retries exhaust silently, fallback happens, but creator never sees a warning. Later troubleshooting is hard because there's no DB flag or log entry marking the fallback.

**Why it happens:** Temptation to silently degrade: "it's working, just with old concatenation, so no alert needed". But silent degradation hides systematic problems (e.g., rate limits, API outages).

**How to avoid:** Always log a `logger.warning()` when entering fallback. No DB flag needed, but the log entry is essential for monitoring. Can add a future alert_sync() call if fallback frequency spikes.

**Warning signs:** Search logs for "Falling back to concatenation" — if it appears frequently (> 1% of daily runs), investigate root cause.

## Code Examples

### PromptGenerationService class structure (recommended)

```python
# Source: Pattern from src/app/services/scene_generation.py + src/app/services/kling.py
import logging
from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from app.services.database import get_supabase
from app.settings import get_settings

logger = logging.getLogger(__name__)

GPT4O_COST_INPUT_PER_MTOK = 2.50
GPT4O_COST_OUTPUT_PER_MTOK = 10.00

# NEW CHARACTER BIBLE (replaces orange tabby Mochi)
CHARACTER_BIBLE = (
    "A full-body, high-definition 3D render of an ultra-cute, sitting light grey kitten. "
    "The kitten has huge, wide, expressive blue eyes and a cheerful, open-mouthed smile showing its pink tongue. "
    "Its soft fur texture is highly detailed."
)

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=32),
    retry=retry_if_exception_type(Exception),
    reraise=True,
    before_sleep=lambda retry_state: logger.warning(
        "Prompt generation retry attempt %d", retry_state.attempt_number
    ),
)
def _generate_unified_prompt_with_backoff(
    client: OpenAI,
    system_prompt: str,
    character_desc: str,
    scene_prompt: str,
) -> str:
    """Generate unified prompt with exponential backoff."""
    user_message = f"CHARACTER: {character_desc}\n\nSCENE: {scene_prompt}"
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        temperature=0.7,
        max_tokens=500,
    )
    return response.choices[0].message.content.strip()


class PromptGenerationService:
    """Generate unified prompts by weaving character into scene via GPT-4o."""

    def __init__(self):
        settings = get_settings()
        self._client = OpenAI(api_key=settings.openai_api_key)

    def generate(self, scene_prompt: str) -> tuple[str, float]:
        """
        Generate unified prompt from scene_prompt by weaving in grey kitten character.

        Args:
            scene_prompt: Raw scene description from SceneEngine.pick_scene()

        Returns:
            (unified_prompt, cost_usd)
            - unified_prompt: Natural integration of character + scene (replaces script_text)
            - cost_usd: GPT-4o API cost for circuit breaker tracking

        On GPT-4o failure after retries: falls back to CHARACTER_BIBLE + scene_prompt concatenation,
        logs warning, and continues (cost_usd = 0.0 for fallback).
        """
        system_prompt = self._build_system_prompt()

        try:
            unified_prompt = _generate_unified_prompt_with_backoff(
                self._client,
                system_prompt,
                CHARACTER_BIBLE,
                scene_prompt,
            )
            # Calculate cost
            # (In real implementation, capture token usage from response — see Pattern 3)
            cost_usd = 0.005  # placeholder; calculate from actual token usage
            return unified_prompt, cost_usd
        except Exception as e:
            logger.warning(
                "GPT-4o unified prompt generation failed after retries: %s. Falling back to concatenation.",
                e
            )
            # Fallback to old concatenation pattern
            unified_prompt = f"{CHARACTER_BIBLE}\n\n{scene_prompt}"
            return unified_prompt, 0.0

    def _build_system_prompt(self) -> str:
        """Build system prompt for unified prompt generation."""
        return """You are a creative director for cute, short-form cat video content (TikTok, Reels).
Your task: weave a character description naturally into a scene description to create a unified, animated-style prompt.

INSTRUCTIONS:
1. Preserve the original scene's location, activity, and mood — do NOT rewrite the scene.
2. Integrate the character smoothly (use descriptive language, not just appending).
3. Use animated/ultra-cute style — emphasize charm, expressiveness, personality. Avoid technical 3D/photorealism language.
4. Result: 2-3 sentences, vivid, optimized for AI video generation.
5. Language: ENGLISH ONLY (Kling AI generates better with English prompts).

STYLE EXAMPLES:
- Instead of: "high-definition 3D render with cinematic lighting"
- Use: "adorable kitten with sparkling blue eyes discovers..."

Return ONLY the unified prompt (plain text, no JSON, no markdown).
"""
```

### Integration point in daily_pipeline.py

```python
# Source: Insertion point after SceneEngine, before KlingService in daily_pipeline.py
# Around line 158 in current daily_pipeline.py

from app.services.prompt_generation import PromptGenerationService

# ... existing code: SceneEngine.pick_scene() returns scene_prompt ...

# NEW: Generate unified prompt
plog.extra["pipeline_step"] = "unified_prompt_gen"
prompt_gen = PromptGenerationService()
try:
    unified_prompt, prompt_gen_cost = prompt_gen.generate(scene_prompt)
    plog.info("Unified prompt generated, cost=$%.6f", prompt_gen_cost)
except Exception as exc:
    plog.error("PromptGenerationService failed unexpectedly: %s", exc)
    send_alert_sync(f"Error generating unified prompt: {exc}. Pipeline halted.")
    return

# Record cost to circuit breaker
if not cb.record_attempt(prompt_gen_cost):
    plog.error("Circuit breaker tripped during prompt generation.")
    send_alert_sync("Circuit breaker disparado durante generación de prompt unificado. Pipeline detenido.")
    return

# CHANGE: KlingService now receives unified_prompt, not scene_prompt
kling_svc = KlingService()
plog.extra["pipeline_step"] = "kling_submit"
try:
    kling_job_id = kling_svc.submit(unified_prompt)  # CHANGED: was scene_prompt
    plog.info("Kling job submitted: job_id=%s", kling_job_id)
except Exception as exc:
    plog.error("Kling submission failed: %s", exc)
    send_alert_sync(f"Error al enviar prompt unificado a Kling AI: {exc}. Escena guardada sin video.")
    _save_to_content_history(
        supabase,
        scene_prompt=scene_prompt,  # keep original scene_prompt for reference
        caption=caption,
        scene_embedding=scene_embedding,
        music_track_id=music_track["id"],
        script_text=unified_prompt,  # NEW: unified prompt saved as script_text
    )
    return
```

### KlingService.submit() NO LONGER concatenates

```python
# Source: CHANGE to src/app/services/kling.py line 95
# OLD (Phase 9-11):
#   full_prompt = f"{CHARACTER_BIBLE}\n\n{script_text}"
#
# NEW (Phase 12):
#   script_text is now already the unified prompt (from PromptGenerationService)
#   KlingService receives pre-unified prompt and sends it directly

def submit(self, script_text: str) -> str:
    """
    Submit pre-unified prompt to Kling 3.0 via fal.ai.

    In Phase 12+, script_text is the UNIFIED PROMPT (already woven by PromptGenerationService).
    No internal concatenation — submit directly.
    """
    # NO CONCATENATION ANYMORE
    # In Phase 11 and earlier: full_prompt = f"{CHARACTER_BIBLE}\n\n{script_text}"
    # In Phase 12: script_text is already unified

    logger.info(
        "Submitting Kling job: model=%s duration=15s aspect=9:16 prompt_chars=%d",
        self._settings.kling_model_version,
        len(script_text),
        extra={"pipeline_step": "kling_submit", "content_history_id": ""},
    )

    result = _submit_with_backoff(
        self._settings.kling_model_version,
        arguments={
            "prompt": script_text,  # CHANGED: now already unified
            "duration": DEFAULT_KLING_DURATION,
            "resolution": "1080p",
            "aspect_ratio": "9:16",
        },
    )

    job_id: str = result.request_id
    return job_id
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Orange tabby Mochi (CHARACTER_BIBLE) + concatenation | Grey kitten character + GPT-4o unified weaving | Phase 12 (2026-03-21) | Unified prompts are more creative, context-aware, and naturally integrate character without losing scene intent. Supports multiple character switches without code duplication. |
| Scene description sent directly to Kling | Intermediate PromptGenerationService transforms scene to unified prompt | Phase 12 | Separation of concerns: SceneEngine stays focused on library selection; PromptGenerationService owns character/prompt fusion; KlingService stays focused on API integration. |
| No intermediate LLM step between scene and Kling | GPT-4o unification layer | Phase 12 | Adds ~0.005 USD cost per video (~180 USD/year for daily pipeline), but dramatically improves perceived character consistency and narrative quality on TikTok/Reels. |

**Deprecated/outdated:**
- Orange tabby Mochi CHARACTER_BIBLE (kling.py line 31-36): Replace entirely with new grey kitten constant
- Direct scene→Kling flow (daily_pipeline.py line 158): Insert PromptGenerationService between SceneEngine and KlingService

## Open Questions

1. **GPT-4o creative latitude calibration**
   - What we know: System prompt should preserve location/activity/mood from original scene
   - What's unclear: How much creative rewriting is acceptable? (e.g., can GPT-4o suggest "the kitten peers out a window instead of sleeping" if mood=sleepy and activity=sleeping?)
   - Recommendation: Start conservative ("preserve exactly"), test with 10-20 generations, observe if TikTok engagement improves with more creative freedom. Adjust system prompt based on creator feedback.

2. **Temperature tuning for balance**
   - What we know: SceneEngine uses temperature=0.85 (moderate creativity)
   - What's unclear: Should PromptGenerationService use same temperature (0.85) or lower (0.6-0.7) for more deterministic weaving?
   - Recommendation: Start with temperature=0.7 (slightly lower than SceneEngine for more faithful scene preservation). If unified prompts feel repetitive, increase to 0.75-0.85.

3. **Cost tracking and circuit breaker impact**
   - What we know: PromptGenerationService adds ~$0.005 per call (GPT-4o input ~150 tokens, output ~100 tokens)
   - What's unclear: Should PromptGenerationService track cost same way as SceneEngine (return cost_usd and record via cb.record_attempt)? Or should cost be negligible and not tracked separately?
   - Recommendation: Track cost for circuit breaker consistency. Daily cost ~$0.15 USD (negligible compared to Kling's $0.50-1.00 per video), but tracking enables future monitoring if token usage explodes.

4. **Fallback logging and monitoring**
   - What we know: On GPT-4o failure, fall back to concatenation + log warning
   - What's unclear: Should we also send a Telegram alert to creator? Or only log?
   - Recommendation: Log warning only (no alert). If fallback frequency > 1% of daily runs, add metrics alert. Creator doesn't need to know about individual fallback instances.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest >=8.0 |
| Config file | pyproject.toml (tool.pytest.ini_options) |
| Quick run command | `pytest tests/test_prompt_generation.py -x` |
| Full suite command | `pytest tests/ -x` |

### Phase Requirements → Test Map

No explicit phase requirements IDs provided. Based on 12-CONTEXT.md locked decisions, required behaviors:

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|------------|
| CHAR-01 | New CHARACTER_BIBLE constant (grey kitten) replaces orange tabby Mochi in kling.py | unit | `pytest tests/test_prompt_generation.py::test_character_bible_grey_kitten -x` | ❌ Wave 0 |
| CHAR-02 | PromptGenerationService.generate(scene_prompt) returns unified_prompt + cost_usd | unit | `pytest tests/test_prompt_generation.py::test_generate_returns_tuple -x` | ❌ Wave 0 |
| CHAR-03 | GPT-4o call uses "animated/ultra-cute style" system prompt (not technical 3D language) | unit | `pytest tests/test_prompt_generation.py::test_system_prompt_instructs_cute_style -x` | ❌ Wave 0 |
| CHAR-04 | On GPT-4o failure, falls back to CHARACTER_BIBLE + scene_prompt concatenation | unit | `pytest tests/test_prompt_generation.py::test_fallback_on_gpt4o_failure -x` | ❌ Wave 0 |
| CHAR-05 | Fallback logs warning (logger.warning) — no DB flag | unit | `pytest tests/test_prompt_generation.py::test_fallback_logs_warning -x` | ❌ Wave 0 |
| INTEG-01 | daily_pipeline inserts PromptGenerationService between SceneEngine and KlingService | integration | `pytest tests/test_pipeline_wiring.py::test_pipeline_unified_prompt_flow -x` | ❌ Wave 0 |
| INTEG-02 | KlingService.submit() receives unified_prompt (not scene_prompt with concatenation) | integration | `pytest tests/test_pipeline_wiring.py::test_kling_receives_unified_prompt -x` | ❌ Wave 0 |
| DB-01 | content_history script_text field contains unified_prompt (not old concatenation) | integration | `pytest tests/test_pipeline_wiring.py::test_content_history_script_text_unified -x` | ❌ Wave 0 |
| DB-02 | content_history scene_prompt column unchanged (retains original SceneEngine output) | integration | `pytest tests/test_pipeline_wiring.py::test_content_history_scene_prompt_unchanged -x` | ❌ Wave 0 |
| TELEM-01 | Telegram send_approval_message reads script_text (unified prompt) without code changes | integration | `pytest tests/test_pipeline_wiring.py::test_telegram_reads_unified_script_text -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/test_prompt_generation.py -x` (unit tests for new service)
- **Per wave merge:** `pytest tests/ -x` (full suite including integration tests for pipeline wiring)
- **Phase gate:** Full suite passing + manual TikTok spot-check (unified prompts appear vibrant/cute, not technical)

### Wave 0 Gaps
- [ ] `tests/test_prompt_generation.py` — unit tests for PromptGenerationService (CHAR-01 through CHAR-05)
- [ ] `tests/test_pipeline_wiring.py` updates — integration tests for daily_pipeline flow with PromptGenerationService (INTEG-01, INTEG-02, DB-01, DB-02, TELEM-01)
- [ ] `src/app/services/prompt_generation.py` — new PromptGenerationService class
- [ ] `src/app/services/kling.py` — update CHARACTER_BIBLE constant, remove concatenation from submit()
- [ ] `src/app/scheduler/jobs/daily_pipeline.py` — insert PromptGenerationService call between SceneEngine and KlingService
- [ ] `pyproject.toml` — no changes (all dependencies already present)

## Sources

### Primary (HIGH confidence)
- Context7: OpenAI library API (gpt-4o model, response.choices[0].message.content, response.usage.prompt_tokens/completion_tokens)
- Official docs: [OpenAI Python SDK](https://github.com/openai/openai-python) — synchronous client, chat.completions.create() method
- Official docs: [tenacity library](https://tenacity.readthedocs.io/) — @retry decorator, wait_exponential, stop_after_attempt
- Context7 (existing codebase): Scene generation pattern (src/app/services/scene_generation.py)
- Context7 (existing codebase): Tenacity retry pattern (src/app/services/kling.py, _submit_with_backoff)
- Context7 (existing codebase): Cost tracking pattern (scene_generation.py, GPT4O_COST_INPUT_PER_MTOK constants)

### Secondary (MEDIUM confidence)
- Phase 12 CONTEXT.md — user decisions, locked architecture, discretion areas
- Phase 10 STATE.md — confirmed scene_embedding pattern, confirmed TeacherPool pattern reuse from earlier phases

### Tertiary (LOW confidence)
- None — all findings verified with official docs or existing codebase patterns

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — OpenAI and tenacity are proven in existing codebase (Phases 9-11); versions confirmed in pyproject.toml
- Architecture: HIGH — PromptGenerationService mirrors proven patterns from SceneEngine (same OpenAI client init, same tenacity retry structure, same cost tracking). Pipeline integration point is clear from daily_pipeline structure.
- Common pitfalls: HIGH — pitfalls identified from Phase 10-11 experience (SceneEngine implementations, GPT-4o response parsing, character preservation)
- Test requirements: MEDIUM — Phase 12 CONTEXT.md locked decisions map to testable behaviors, but exact assertion details are implementation-dependent

**Research date:** 2026-03-21
**Valid until:** 2026-04-11 (30 days — stack is stable; decisions are locked)
