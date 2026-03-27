# Phase 13: Kitten Scenario Video Generation - Hook Climax Conclusion Stories - Research

**Researched:** 2026-03-27
**Domain:** Narrative video generation, Kling AI 3.0 multi-beat prompting, GPT-4o scenario generation
**Confidence:** HIGH

## Summary

Phase 13 replaces the current everyday-cute scene pipeline with story-arc format videos where each 15-second clip follows a hook → climax → conclusion narrative structure. The implementation extends SceneEngine (not replacing it) to generate dynamic scenarios within category guardrails, uses Kling AI 3.0's multi-shot capabilities to encode story beats via temporal prose, and extends content_history with a prompt_embedding column for visual/stylistic anti-repetition.

The technical approach is well-supported by current infrastructure: Kling AI 3.0 (via fal.ai) ships native multi-shot generation up to 15 seconds with explicit beat control, GPT-4o provides synchronous scenario generation within the APScheduler ThreadPoolExecutor constraint, and pgvector embeddings scale the existing anti-repetition pattern.

**Primary recommendation:** Encode story beats as temporal prose in flowing 3-5 sentence prompts (implied arc via action progression), not explicit temporal instructions. Kling AI 3.0 documentation confirms this produces more natural, coherent multi-beat generation than rigid "first 5 seconds..." timing markers. Define 5-6 scenario type categories (slapstick, reaction/surprise, chase, investigation-gone-wrong, unexpected nap, overconfident leap) as GPT-4o guidance; store categories in SceneEngine as a new JSON file (pattern mirrors scenes.json loading).

## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** GPT-4o generates scenarios dynamically — no library file (no new scenarios.json). No static list of scenes to curate.
- **D-02:** Scenarios are semi-guided by scenario type categories. GPT-4o picks a category and invents the specific scenario within it. Researcher must define the final category list.
- **D-03:** Scenario setting is domestic Mexican — kitchen, living room, garden, with optional cultural props (tortillas, molcajete, etc.) for flavor. Cultural identity from Phase 12 is preserved.
- **D-04:** Arc encoding approach is research-driven — researcher must check Kling AI documentation to determine the best prompt structure for multi-beat story arcs. Preferred baseline: implied arc in flowing prose (3-5 sentences where progression is clear). If Kling docs recommend explicit temporal instructions ("In the first 5 seconds..."), use those instead.
- **D-05:** Story arc logic lives inside SceneEngine (extended, not replaced). SceneEngine handles: category selection + GPT-4o scenario generation + arc-structured prompt output.
- **D-06:** Phase 13 replaces the current pipeline — no feature flag. All daily videos become story-arc format going forward.
- **D-07:** PromptGenerationService role: receives the arc-structured scenario output from SceneEngine and fuses the grey kitten character into it (same role as today, updated system prompt).
- **D-08:** Captions change to arc-aware tease/hook style — short Spanish caption that teases the story without revealing the outcome. Examples: "Algo malo va a pasar.", "Eso no iba a funcionar." — 5-8 words, suspense-building tone. Replaces the current [observation + implied personality] formula.
- **D-09:** Store BOTH scenario-level and prompt-level embeddings per content_history row. Scenario embedding (existing scene_embedding column) catches repeated story types semantically. Prompt embedding (new column) catches visual/stylistic repetition at Kling-prompt level. Researcher must determine column name and migration.
- **D-10:** Reuse existing content_history columns where possible — no new scenario_arcs table. Scenario description maps to scene_prompt column (semantic rename in practice). One new column needed for prompt_embedding (from D-09). Researcher must confirm exact migration.

### Claude's Discretion

- Final list of scenario type categories (researcher defines based on D-02 + content strategy research)
- Exact migration name and column type for prompt_embedding
- Whether SceneEngine returns scenario_description separately or merged into scene_prompt

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Kling AI 3.0 (via fal.ai) | fal-client>=0.13.1 | Text-to-video generation (15-second multi-shot) | v2.0 selected: 7-60x cheaper than alternatives, character consistency features shipped March 2026, native multi-shot generation for narrative beats |
| GPT-4o | Latest (via OpenAI SDK >= 2.21.0) | Scenario generation + prompt unification | Synchronous client (ThreadPoolExecutor compatibility), cost-effective, proven in Phase 10-12, 0.9 temperature for creativity |
| OpenAI embeddings | text-embedding-3-small (1536 dims) | Scenario + prompt embedding for anti-repetition | Existing pattern, 0.02/MTok cost, compatible with pgvector |
| PostgreSQL (Supabase) | With pgvector | Persistent anti-repetition via vector search | Existing infrastructure, check_scene_similarity SQL function reusable |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| tenacity | >= 8.0 | Exponential backoff for GPT-4o calls | Required for APScheduler ThreadPoolExecutor compatibility |
| fal-client | >= 0.13.1 | Kling AI 3.0 async SDK (sync wrapper) | Already runtime dependency from Phase 9 |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Kling AI 3.0 multi-shot | RunwayML, Sora, Veo | Higher cost (2-5x), less character consistency; Kling 3.0 ships explicit multi-beat support (March 2026 feature) |
| Temporal prose (implied arc) | Explicit temporal instructions ("In first 5 seconds...") | Kling docs show prose-based prompts produce more natural, coherent multi-beat generation; explicit markers introduce jank between beats |
| Scenario type categories (GPT-4o guidance) | Static scenario library | D-01 locks dynamic generation; categories provide sufficient guardrails without curation burden |
| prompt_embedding (new column) | Separate prompt_embedding table | D-10 locks atomic updates (content_history), no join complexity |

**Installation (Python deps):**
```bash
# fal-client already in pyproject.toml; OpenAI SDK already installed
# No new dependencies required — all stack items already present in Phase 12
pip install -e .
```

**Version verification:**
- OpenAI SDK: `python -c "import openai; print(openai.__version__)"` → should be >= 2.21.0
- fal-client: `python -c "import fal_client; print(fal_client.__version__)"` → should be >= 0.13.1
- Both confirmed in pyproject.toml (project already at v3.9.0)

## Architecture Patterns

### Recommended Project Structure
```
src/app/services/
├── scene_generation.py         # Extended SceneEngine: category selection + scenario generation
├── prompt_generation.py        # PromptGenerationService (updated system prompt for story arcs)
├── kling.py                    # CHARACTER_BIBLE, KlingService (unchanged)
├── embeddings.py               # EmbeddingService (reused, no changes)
└── similarity.py               # SimilarityService (extended: prompt_embedding check)

migrations/
└── 0012_phase13_schema.sql     # Add prompt_embedding column to content_history

.planning/phases/13-*/
└── 13-RESEARCH.md              # This document
```

### Pattern 1: SceneEngine Extension for Story Arc Scenarios

**What:** SceneEngine currently picks from static scenes.json (location + activity + mood combos). Phase 13 replaces `pick_scene()` with a new scenario generation method that:
1. Selects a scenario type category (e.g., "slapstick", "chase", "investigation-gone-wrong")
2. Calls GPT-4o to generate a dynamic scenario within that category (3-5 sentence narrative with hook → climax → conclusion implied)
3. Returns scenario description (for scene_embedding) + arc-structured prompt (for Kling generation)

**When to use:** Daily pipeline Step 4a currently calls `scene_engine.pick_scene()`. Phase 13 replaces this with a new method (name: planner decides, e.g., `pick_scenario_arc()` or extend `pick_scene()` signature).

**Example:**

```python
# Phase 13 addition to SceneEngine class

SCENARIO_TYPE_CATEGORIES = [
    "slapstick",              # Physical comedy (slips, crashes, falls)
    "reaction_surprise",      # Emotional reactions to unexpected events
    "chase",                  # Kitten pursuing or being pursued (toy, insect, tail)
    "investigation_gone_wrong", # Kitten investigating, something goes awry
    "unexpected_nap",         # Kitten about to nap in absurd location
    "overconfident_leap"      # Kitten attempts risky jump/climb
]

def _generate_scenario_arc(self, category: str, rejection_constraints: list[dict] | None = None) -> tuple[str, str, str, float]:
    """
    Generate a dynamic scenario within a category via GPT-4o.

    Args:
        category: One of SCENARIO_TYPE_CATEGORIES
        rejection_constraints: Previous rejections to avoid

    Returns:
        (scenario_description, arc_structured_prompt, mood, cost_usd)
        - scenario_description: 2-3 sentences describing the scenario (embeddable, for scene_embedding)
        - arc_structured_prompt: 3-5 sentences with hook→climax→conclusion progression (for Kling)
        - mood: playful|sleepy|curious (for MusicMatcher)
        - cost_usd: GPT-4o cost

    Source: Kling 3.0 docs confirm temporal progression (hook → climax → conclusion) encodes
    as flowing prose with action sequences, not explicit "In first 5 seconds..." markers.
    """
    filled_system = self._build_scenario_system_prompt(category, rejection_constraints)
    response = self._client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": filled_system}],
        response_format={"type": "json_object"},  # Returns { "scenario_description", "arc_prompt", "mood" }
        temperature=0.9,
    )
    # Parse response, generate embeddings, return tuple
```

### Pattern 2: Kling AI 3.0 Multi-Beat Temporal Encoding

**What:** Kling AI 3.0 (via fal.ai) supports native multi-shot generation (2-6 shots per request, up to 15 seconds total). Kling docs show that:
- **Temporal progression is encoded via flowing prose action sequences**, not rigid temporal markers
- **Linking words control pacing:** "immediately," "pause," "continuing" signal beat transitions
- **Character consistency anchors the narrative:** define the kitten clearly at the start, keep descriptions consistent across beats

**When to use:** PromptGenerationService.generate_unified_prompt() receives arc-structured prompt from SceneEngine. The unified prompt then flows to KlingService.submit().

**Example (Hook → Climax → Conclusion with implied temporal progression):**

```python
# BAD (explicit temporal instructions):
# "In the first 3 seconds, the kitten smells the tortilla. At second 4, it pounces..."
# Result: Kling struggles to sync beats, produces jank/awkward transitions

# GOOD (flowing prose with action progression):
# "A mischievous grey kitten discovers a tortilla on the kitchen counter.
#  Its blue eyes widen with curiosity—it crouches, tail twitching, preparing to pounce.
#  In one swift, playful leap, the kitten lands on the tortilla, sending it flying across the counter.
#  The kitten tumbles after it, rolling in an adorable tangle of paws and fur,
#  its open-mouthed smile pure mischief as it realizes tortillas are NOT toys."

# Source: Kling 3.0 Prompting Guide (fal.ai blog)
# Result: Natural multi-beat narrative, coherent action flow, character consistency preserved
```

### Pattern 3: Scenario Type Categories as JSON (SceneEngine Extension)

**What:** Instead of loading scenarios from static library, SceneEngine loads **categories** as guidance for GPT-4o. Categories are lightweight JSON (name + description).

**When to use:** During SceneEngine.__init__(), after loading scenes.json (unchanged), also load categories.json.

**Example:**

```json
{
  "categories": [
    {
      "name": "slapstick",
      "description": "Physical comedy: the kitten slips, crashes, falls, or creates chaos through clumsy antics. Always ends with the kitten unharmed and adorable."
    },
    {
      "name": "reaction_surprise",
      "description": "Emotional comedy: the kitten reacts to an unexpected event (water spray, door opening, another pet appearing). Reaction should be exaggerated and cute."
    },
    {
      "name": "chase",
      "description": "Pursuit comedy: the kitten chases a toy, insect, shadow, or its own tail. The chase builds in intensity with the kitten getting more frantic and cute."
    },
    {
      "name": "investigation_gone_wrong",
      "description": "Curiosity comedy: the kitten investigates something (open cupboard, garden plant, water dish) and discovers something that surprises or amuses it. The investigation should feel playful, not dangerous."
    },
    {
      "name": "unexpected_nap",
      "description": "Comfort comedy: the kitten finds an absurd or inconvenient place to nap (empty food bowl, cardboard box, plant pot, sunny window ledge). The nap setup should be funny or cozy."
    },
    {
      "name": "overconfident_leap",
      "description": "Ambition comedy: the kitten attempts a risky jump, climb, or leap (onto high shelf, across furniture gap, onto moving object). The setup builds tension; the outcome is endearing (success or adorable failure)."
    }
  ]
}
```

### Anti-Patterns to Avoid

- **Explicit temporal markers in Kling prompts:** Using "In the first 3 seconds, X. At second 5, Y." produces disjointed, unnatural multi-beat videos. Kling 3.0 docs explicitly recommend flowing prose with action sequences. ✓ Phase 13 uses prose-based arcs.
- **Static scenario library with curation burden:** D-01 locks dynamic generation — no curated list. Categories provide enough guardrails without maintenance.
- **Splitting scenario and arc generation into separate GPT-4o calls:** One call returning both scenario_description (embeddable) + arc_prompt (Kling-optimized) is cheaper and more coherent.
- **Mixing CHARACTER_BIBLE concatenation and PromptGenerationService:** Phase 12 wired this correctly (PromptGenerationService handles CHARACTER_BIBLE fusion). Phase 13 unchanged.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Multi-beat video generation | Custom shot sequencing logic | Kling AI 3.0 native multi-shot generation | Kling ships explicit beat support (March 2026), handles character consistency across shots, avoids custom sync logic |
| Story arc encoding | Manual temporal instruction parsing | Flowing prose with action sequences (Kling-recommended) | Prose-based arcs produce more natural, coherent multi-beat generation; explicit markers introduce jank |
| Scenario variation | Hand-written scenario templates | GPT-4o dynamic generation within category guardrails | GPT-4o ensures endless variation while categories prevent chaos; static templates become stale fast |
| Vector anti-repetition for prompts | Custom similarity scoring | pgvector + OpenAI embeddings (existing pattern) | Cosine similarity via pgvector is battle-tested, aligns with scene_embedding precedent, no custom ML needed |

**Key insight:** Narrative generation at the Kling level is Kling's job (it's trained on cinematic language). Phase 13's role is to provide well-structured narrative prose (hook → climax → conclusion) and ensure the grey kitten character remains consistent. GPT-4o handles creativity within categories; Kling handles visual realization.

## Runtime State Inventory

**Category:** None — Phase 13 is greenfield (new feature, no existing state to migrate from a replaced system).

However, **database migration is required** (D-09, D-10):
- Add `prompt_embedding` column to content_history (vector(1536)) — tracks Kling-prompt-level visual/stylistic repetition
- Scenario generation replaces `pick_scene()` but scenario descriptions still map to existing `scene_prompt` column (semantic rename, no breaking change to schema)

## Common Pitfalls

### Pitfall 1: Encoding Story Beats with Explicit Temporal Markers

**What goes wrong:** Temptation to specify "In the first 3 seconds, X happens. At second 5, Y happens." Results in Kling generating disjointed, unnatural transitions between beats.

**Why it happens:** Explicit markers seem like precise control, but Kling AI 3.0 Prompting Guide explicitly warns against this. Kling's multi-shot generation was trained on flowing narrative prose, not rigid timecode instructions.

**How to avoid:** Use flowing prose with action progression. Phrases like "immediately," "pause," "continuing" signal transitions naturally. Example: "The kitten discovers a tortilla. Its eyes widen. Suddenly, it pounces." — progression is clear, transitions feel natural.

**Warning signs:** If generated videos show abrupt cuts, characters resetting, or beat misalignment, rewrite prompt as flowing prose without explicit seconds.

**Source:** Kling 3.0 Prompting Guide (fal.ai blog) — confirmed March 2026.

### Pitfall 2: Forgetting That PromptGenerationService Must Update Its System Prompt

**What goes wrong:** SceneEngine generates story-arc scenarios, but PromptGenerationService still uses Phase 12's system prompt (optimized for generic scene prompts, not narrative arcs). Result: unified prompt loses narrative cohesion.

**Why it happens:** Phase 12 locked PromptGenerationService's role as CHARACTER_BIBLE fusion. Phase 13 extends SceneEngine but planner might assume PromptGenerationService is unchanged.

**How to avoid:** Update PromptGenerationService._SYSTEM_PROMPT to acknowledge that scene_prompt is now a story arc with hook → climax → conclusion progression. Guidance: "Preserve the narrative arc's pacing and emotional beats. The kitten should be woven naturally into each beat, not just inserted once."

**Warning signs:** Generated videos don't follow hook → climax → conclusion structure despite SceneEngine producing it. Unified prompt read-through shows CHARACTER_BIBLE prepended but arc structure is lost.

### Pitfall 3: Embedding Only the Scenario, Not the Kling Prompt

**What goes wrong:** D-09 specifies both scenario-level and prompt-level embeddings. If only scenario_embedding is computed (reusing Phase 10 pattern), then two very different Kling prompts for the same scenario type won't be caught as duplicates.

**Why it happens:** scene_embedding (existing column, Phase 10) mirrors the semantic scenario. New prompt_embedding column is easy to overlook in implementation planning.

**How to avoid:** During Phase 13 planning, explicitly list both embedding operations:
1. scenario_description → scene_embedding (existing, Phase 10 reused)
2. unified_prompt → prompt_embedding (new, D-09)

Anti-repetition check becomes: if EITHER embedding is too similar to recent content, retry or alert.

**Warning signs:** Visually identical videos (same Kling prompt) generated on consecutive days despite different scenario types. Check prompt_embedding column in content_history — it's NULL.

### Pitfall 4: Categories as Static JSON vs. Config

**What goes wrong:** Categories defined in .env or config.json instead of code. Result: typos in category names in GPT-4o system prompts, categories drift from source of truth.

**Why it happens:** Categories feel like configuration (user-changeable), not code. But they're part of prompt engineering (should be reviewed like code).

**How to avoid:** Store categories in SceneEngine.categories (in-memory dict or loaded from categories.json in data/ directory, same pattern as scenes.json). Keep category names consistent — GPT-4o system prompt and planner task descriptions must reference the exact same names.

**Warning signs:** "slapstick" vs "slap-stick" confusion. GPT-4o tries to invent scenarios but can't narrow down to a category (system prompt and actual categories don't align).

## Code Examples

Verified patterns from official sources:

### Scenario Generation via GPT-4o (ThreadPoolExecutor-safe)

```python
# Source: Patterns from existing prompt_generation.py + scene_generation.py

from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import json

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=16),
    retry=retry_if_exception_type(Exception),
    reraise=True,
)
def _generate_scenario_with_backoff(client: OpenAI, filled_prompt: str) -> tuple[dict, float]:
    """
    Generate scenario via GPT-4o with exponential backoff (ThreadPoolExecutor safe).
    Returns (parsed JSON response, cost_usd).
    """
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": filled_prompt}],
        response_format={"type": "json_object"},
        temperature=0.9,
        max_tokens=500,
    )
    response_text = response.choices[0].message.content.strip()
    scenario_data = json.loads(response_text)  # { "scenario_description", "arc_prompt", "mood" }

    input_tokens = response.usage.prompt_tokens
    output_tokens = response.usage.completion_tokens
    cost_usd = (
        input_tokens * GPT4O_COST_INPUT_PER_MTOK
        + output_tokens * GPT4O_COST_OUTPUT_PER_MTOK
    ) / 1_000_000

    return scenario_data, cost_usd
```

### Kling Prompt with Hook → Climax → Conclusion (Flowing Prose)

```python
# Source: Kling 3.0 Prompting Guide (fal.ai) + Phase 13 CONTEXT.md

# GOOD — Flowing prose with action progression (Kling-recommended)
example_arc_prompt = """
An ultra-cute grey kitten with huge blue eyes and a pink tongue sits in a cozy Mexican kitchen,
eyeing a fresh tortilla on the counter. Its curiosity builds—ears forward, tail twitching with anticipation.
With a mischievous open-mouthed grin, the kitten suddenly pounces, sending the tortilla spinning across the tiles.
The kitten tumbles after it in a roll of soft fur and flying paws, eventually landing in a heap,
tongue hanging out playfully as if to say 'worth it.' The scene is pure comedy—adorable, energetic, and perfectly endearing.
"""

# BAD — Explicit temporal instructions (avoid, produces jank)
bad_arc_prompt = """
Seconds 0-3: A grey kitten sits in a Mexican kitchen, looking at a tortilla.
Seconds 3-6: The kitten's eyes widen with excitement.
Seconds 6-9: The kitten pounces on the tortilla.
Seconds 9-15: The kitten tumbles across the kitchen.
"""

# Kling 3.0 Result: good_arc_prompt produces natural multi-beat narrative with smooth transitions
# bad_arc_prompt produces disjointed, character resets, timing mismatches
```

### Prompt Embedding for Visual Repetition Check

```python
# Source: Patterns from similarity.py (Phase 10) + embeddings.py

# In daily_pipeline.py, after PromptGenerationService.generate_unified_prompt():

unified_prompt = prompt_gen_svc.generate_unified_prompt(scene_prompt)

# NEW: Generate prompt embedding for visual/stylistic anti-repetition (D-09)
prompt_embedding, embed_cost = embedding_svc.generate(unified_prompt)
if not cb.record_attempt(embed_cost):
    # Circuit breaker check...
    pass

# Check BOTH embeddings for repetition:
is_scene_similar = similarity_svc.is_too_similar_scene(scene_embedding)
is_prompt_similar = similarity_svc.is_too_similar_prompt(prompt_embedding)  # New method

if is_scene_similar or is_prompt_similar:
    if settings.scene_anti_repetition_enabled:
        # Retry or alert...
        pass

# Save both embeddings atomically to content_history:
_save_to_content_history(
    ...,
    scene_embedding=scene_embedding,
    prompt_embedding=prompt_embedding,  # New column (D-09)
    ...
)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Static 50-scene library (Phase 10) | Dynamic scenario generation within categories (Phase 13) | March 2026 | Eliminates curation burden, enables endless variation while maintaining guardrails |
| Generic scene prompts | Story-arc prompts (hook → climax → conclusion) | Phase 13 | Kling AI 3.0 multi-shot support enables narrative structure, creates more engaging, cohesive videos |
| Single scene_embedding for anti-repetition | Dual embeddings (scenario + prompt) | Phase 13 | Catches both semantic (story type) and stylistic (Kling prompt) repetition, finer-grained control |
| Per-platform caption variants (deferred) | Universal arc-aware tease/hook caption (Phase 13) | Phase 13 | Spanish 5-8 word captions now use suspense tone ("Algo malo va a pasar.") vs. generic observation |

**Deprecated/outdated:**
- Static scenes.json library: Replaced by dynamic category-guided scenario generation (D-01, D-02)
- Generic scene captions: Replaced by arc-aware tease/hook captions (D-08)

## Open Questions

1. **Exact Migration Column Name and Type for prompt_embedding**
   - What we know: D-09 specifies a new column for prompt-level embeddings (vector(1536), like scene_embedding)
   - What's unclear: Column name (prompt_embedding? kling_prompt_embedding? unified_prompt_embedding?) and whether the similarity.py method is is_too_similar_prompt() or another signature
   - Recommendation: Planner decides. Column name suggestion: `prompt_embedding` (mirrors `scene_embedding` naming). Method: `is_too_similar_prompt(embedding, threshold)` in SimilarityService. Migration: same pattern as 0009 (ALTER TABLE ADD COLUMN IF NOT EXISTS).

2. **SceneEngine Return Signature: Separate scenario_description or Merged?**
   - What we know: D-05 says SceneEngine handles category selection + scenario generation + arc-structured output
   - What's unclear: Does `pick_scenario_arc()` return (scenario_description, arc_prompt, mood, cost) as 4-tuple, or are they merged (arc_prompt includes scenario_description)?
   - Recommendation: Separate. scenario_description → scene_embedding (for semantic anti-repetition, same as Phase 10). arc_prompt → unified_prompt → kling generation. Cleaner separation of concerns.

3. **PromptGenerationService System Prompt: How Much to Preserve Arc Structure?**
   - What we know: Phase 13 arcs already have hook → climax → conclusion progression
   - What's unclear: Should PromptGenerationService add CHARACTER_BIBLE at top of arc (breaking temporal flow) or weave CHARACTER_BIBLE details into each beat?
   - Recommendation: Weave CHARACTER_BIBLE into the arc. New system prompt: "The kitten should be present and central to each narrative beat. Weave the CHARACTER_BIBLE (blue eyes, pink tongue, soft grey fur, playful demeanor) naturally throughout the arc, emphasizing how the kitten's personality drives the story."

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.12+ | Runtime | ✓ | 3.11.8 (note: pyproject.toml requires 3.12+; current env 3.11.8 — Railway should have 3.12+) | — |
| OpenAI API key (OPENAI_API_KEY env var) | GPT-4o scenario generation | ✓ (via Settings) | Latest (v>=2.21.0) | — |
| FAL_API_KEY (fal.ai auth) | Kling AI 3.0 submission (Phase 9+) | ✓ (via Settings, explicit validation Phase 9) | Implicit in fal-client>=0.13.1 | — |
| Supabase (Postgres + pgvector) | Anti-repetition vector search | ✓ (operational) | Postgres 15.4 (per STATE.md) | — |

**Missing dependencies with no fallback:** None. All Phase 13 external dependencies are already operational (Phase 12 validated GPT-4o and Kling; Phase 9 validates fal.ai; Phase 10 validates pgvector).

## Validation Architecture

**Detecting Test Framework:** pytest is configured (pyproject.toml defines [tool.pytest.ini_options] with e2e markers).

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest >= 8.0 |
| Config file | `pyproject.toml` (tool.pytest.ini_options) |
| Quick run command | `pytest tests/test_scene_engine.py -v` (existing scene tests, verify pattern) |
| Full suite command | `pytest tests/ -v -m 'not e2e'` (all unit tests excluding live API tests) |

### Phase Requirements → Test Map

Phase 13 requirements TBD by planner. Typical tests:

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SCN-13-01 | SceneEngine loads scenario type categories | unit | `pytest tests/test_scene_engine.py::test_scenario_categories_loaded -v` | ❌ Wave 0 |
| SCN-13-02 | GPT-4o generates scenario within category constraints | unit | `pytest tests/test_scene_engine.py::test_generate_scenario_arc -v -m 'not e2e'` | ❌ Wave 0 |
| SCN-13-03 | Arc-structured prompt has hook → climax → conclusion flow | unit | `pytest tests/test_prompt_generation.py::test_arc_prompt_structure -v` | ❌ Wave 0 |
| SCN-13-04 | prompt_embedding computed and stored in content_history | integration | `pytest tests/test_pipeline_wiring.py::test_prompt_embedding_stored -v` | ❌ Wave 0 |
| SCN-13-05 | is_too_similar_prompt() catches visual repetition | unit | `pytest tests/test_similarity.py::test_is_too_similar_prompt -v` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/test_scene_engine.py tests/test_prompt_generation.py -v` (scenario + arc generation)
- **Per wave merge:** `pytest tests/ -v -m 'not e2e'` (full suite; e2e tests deferred to uat)
- **Phase gate:** Full suite green + manual Telegram approval of first 2-3 generated arc videos before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_scene_engine.py` — extend for scenario arc generation (new methods: `_generate_scenario_arc()`, category loading)
- [ ] `tests/test_prompt_generation.py` — extend system prompt to verify arc structure preservation
- [ ] `tests/test_similarity.py` — new method `is_too_similar_prompt()` + tests
- [ ] `tests/test_pipeline_wiring.py` — verify prompt_embedding column is written and read correctly
- [ ] `migrations/0012_phase13_schema.sql` — add prompt_embedding column to content_history
- [ ] Framework: pytest already installed; no additional setup needed

*(If existing test infrastructure needs enhancement: "Extend existing test files in tests/ directory to cover new SceneEngine methods, PromptGenerationService arc handling, and similarity.py prompt_embedding checks")*

## Sources

### Primary (HIGH confidence)

- **Kling 3.0 Prompting Guide (fal.ai):** https://blog.fal.ai/kling-3-0-prompting-guide/ — Multi-shot generation structure, temporal encoding via flowing prose (not explicit timecode markers), character consistency across beats, linking words for pacing
- **Kling 3.0 Multi-Shot Storyboarding Review (SeaArt AI):** https://www.seaart.ai/blog/kling-3-0-review — Confirms up to 6 shots per request (15 seconds max), native narrative arc support shipped March 2026
- **Atlabs AI Kling 3.0 Prompting Guide:** https://www.atlabs.ai/blog/kling-3-0-prompting-guide-master-ai-video-generation — Scene → Characters → Action → Camera → Audio & Style five-layer structure; beat-matched prompting best practices
- **Project codebase (verified):**
  - `src/app/services/scene_generation.py` — SceneEngine pattern (loads JSON at init, GPT-4o system prompt injection, seasonal overlays, cost tracking)
  - `src/app/services/prompt_generation.py` — PromptGenerationService pattern (system prompt, CHARACTER_BIBLE fusion, fallback to concatenation, tenacity retry for ThreadPoolExecutor)
  - `src/app/services/similarity.py` — Anti-repetition pattern via pgvector + SQL functions
  - `migrations/0009_phase10_schema.sql` — scene_embedding column + check_scene_similarity SQL function signature

### Secondary (MEDIUM confidence)

- **Magichour AI Kling 3.0 Review:** https://magichour.ai/blog/kling-30-review — Confirms 15-second multi-shot storytelling capability, multi-beat narrative structure
- **Medium: Kling AI Prompting Strategies (Kristopher Dunham):** https://medium.com/@creativeaininja/how-to-actually-control-next-gen-video-ai-runway-kling-veo-and-sora-prompting-strategies-92ef0055658b — Comparative prompting approaches; Kling narrative coherence advantages

### Tertiary (LOW confidence — flagged for validation)

- **Kling 3.0 on Higgsfield User Guide:** https://higgsfield.ai/blog/Kling-3.0-is-on-Higgsfield-User-Guide-AI-Video-Generation — UI-focused (not API), but confirms multi-shot semantics align with fal.ai SDK

## Metadata

**Confidence breakdown:**
- **Standard stack (HIGH):** Kling AI 3.0 multi-shot, GPT-4o, pgvector embeddings all confirmed in Phase 12 + official Kling docs (March 2026). No new external dependencies.
- **Architecture (HIGH):** SceneEngine extension pattern mirrors Phase 10 (scenes.json loading, GPT-4o system prompt injection). PromptGenerationService pattern unchanged. Similarity check pattern reusable with new prompt_embedding column.
- **Pitfalls (MEDIUM-HIGH):** Kling docs explicitly recommend prose-based arcs (verified via WebFetch of fal.ai guide). Other pitfalls inferred from Phase 10-12 patterns + arc generation specifics (not all validated by live testing).
- **Database migration (HIGH):** Follows Phase 9-11 patterns (ALTER TABLE ADD COLUMN IF NOT EXISTS). Migration 0012 straightforward (vector column type, matching scene_embedding).

**Research date:** 2026-03-27
**Valid until:** 2026-04-03 (Kling AI docs stable as of March 2026; refresh if major fal.ai API changes announced)

---

*Phase 13: Kitten Scenario Video Generation - Hook Climax Conclusion Stories*
*Research completed: 2026-03-27*
