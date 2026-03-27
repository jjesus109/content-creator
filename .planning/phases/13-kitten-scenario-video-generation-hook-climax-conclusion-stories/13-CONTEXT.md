# Phase 13: Kitten Scenario Video Generation - Hook Climax Conclusion Stories - Context

**Gathered:** 2026-03-26
**Status:** Ready for planning

<domain>
## Phase Boundary

Generate 15-second grey kitten videos where each clip follows a hook → climax → conclusion story arc.
Videos must be funny/cute with varied scenario types, set in a domestic Mexican environment.
Phase 13 replaces the current everyday-cute scene pipeline — all daily videos become story-arc format.
</domain>

<decisions>
## Implementation Decisions

### Scenario Generation
- **D-01:** GPT-4o generates scenarios dynamically — no library file (no new scenarios.json). No static list of scenes to curate.
- **D-02:** Scenarios are semi-guided by scenario type categories. GPT-4o picks a category (e.g., slapstick, reaction, chase, investigation-gone-wrong, unexpected nap) and invents the specific scenario within it. Researcher must define the final category list.
- **D-03:** Scenario setting is domestic Mexican — kitchen, living room, garden, with optional cultural props (tortillas, molcajete, etc.) for flavor. Cultural identity from Phase 12 is preserved.

### Arc Encoding
- **D-04:** Arc encoding approach is research-driven — researcher must check Kling AI documentation to determine the best prompt structure for multi-beat story arcs. Preferred baseline: implied arc in flowing prose (3-5 sentences where progression is clear). If Kling docs recommend explicit temporal instructions ("In the first 5 seconds..."), use those instead.

### Service Architecture
- **D-05:** Story arc logic lives inside SceneEngine (extended, not replaced). SceneEngine handles: category selection + GPT-4o scenario generation + arc-structured prompt output.
- **D-06:** Phase 13 replaces the current pipeline — no feature flag. All daily videos become story-arc format going forward.
- **D-07:** PromptGenerationService role: receives the arc-structured scenario output from SceneEngine and fuses the grey kitten character into it (same role as today, updated system prompt).

### Caption
- **D-08:** Captions change to arc-aware tease/hook style — short Spanish caption that teases the story without revealing the outcome. Examples: "Algo malo va a pasar.", "Eso no iba a funcionar." — 5-8 words, suspense-building tone. Replaces the current [observation + implied personality] formula.

### Anti-Repetition
- **D-09:** Store BOTH scenario-level and prompt-level embeddings per content_history row. Scenario embedding (existing scene_embedding column) catches repeated story types semantically. Prompt embedding (new column) catches visual/stylistic repetition at Kling-prompt level. Researcher must determine column name and migration.

### Database / Storage
- **D-10:** Reuse existing content_history columns where possible — no new scenario_arcs table. Scenario description maps to scene_prompt column (semantic rename in practice). One new column needed for prompt_embedding (from D-09). Researcher must confirm exact migration.

### Claude's Discretion
- Final list of scenario type categories (researcher defines based on D-02 + content strategy research)
- Exact migration name and column type for prompt_embedding
- Whether SceneEngine returns scenario_description separately or merged into scene_prompt
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Existing pipeline
- `src/app/services/scene_generation.py` — SceneEngine to be extended; GPT-4o system prompt patterns
- `src/app/services/prompt_generation.py` — PromptGenerationService; CHARACTER_BIBLE fusion logic
- `src/app/services/kling.py` — CHARACTER_BIBLE constant; KlingService.submit(); DEFAULT_KLING_DURATION=15
- `src/app/scheduler/jobs/daily_pipeline.py` — Current pipeline wiring; Step 4 scene generation loop to be replaced
- `src/app/data/scenes.json` — Existing 50-scene library (reference only — not used in Phase 13)

### Prior phase decisions
- `.planning/phases/12-grey-kitten-unified-prompt-generation/` — Phase 12 decisions that shaped CHARACTER_BIBLE and PromptGenerationService

### Kling AI documentation
- Researcher must query Kling AI 3.0 / fal.ai documentation for best prompt structure for story-arc / multi-beat video generation (D-04 is research-dependent)

No external ADRs or specs beyond codebase and Kling docs.
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `SceneEngine.__init__`: loads `scenes.json` at init — pattern for any new static data (categories list, etc.)
- `PromptGenerationService.generate_unified_prompt()`: passthrough to KlingService — interface is stable; system prompt is the only change surface
- `CHARACTER_BIBLE` constant in `kling.py`: 46-word grey kitten identity — must remain embedded in every generation
- `_call_gpt4o_with_backoff()` module-level pattern in `prompt_generation.py`: tenacity retry decorator for APScheduler ThreadPoolExecutor compatibility — same pattern needed for any new GPT-4o call in SceneEngine
- `SEASONAL_OVERLAYS` dict in `scene_generation.py`: shows how optional overlays are injected into GPT-4o system prompt — same injection pattern for scenario type categories

### Established Patterns
- All GPT-4o calls use synchronous OpenAI client (APScheduler ThreadPoolExecutor constraint)
- All retry decorators are at module level (not instance methods) for tenacity compatibility
- Circuit breaker cost recording: every GPT-4o call records cost via `cb.record_attempt(cost_usd)`
- Scene embedding stored in `content_history.scene_embedding` (vector column)
- Anti-repetition check: `SimilarityService.is_too_similar_scene(embedding)` — same interface can be reused for scenario embedding

### Integration Points
- `daily_pipeline.py` Step 4: replace `scene_engine.pick_scene()` call with new SceneEngine arc-generation call
- `content_history` table: existing `scene_prompt` column receives scenario description; new `prompt_embedding` column needed (migration required)
- Telegram approval message: no change in Phase 13 (Telegram changes deferred)
</code_context>

<specifics>
## Specific Ideas

- Caption style examples: "Algo malo va a pasar.", "Eso no iba a funcionar." — tease/hook format, 5-8 words Spanish
- Domestic Mexican setting props (background flavor): tortillas, molcajete, talavera tiles, papel picado
- Scenario category examples (not final — researcher defines): slapstick, reaction/surprise, chase, investigation-gone-wrong, unexpected nap, overconfident leap
</specifics>

<deferred>
## Deferred Ideas

- Telegram approval message showing hook/climax/conclusion story summary — future phase
- Caption A/B testing (standard vs arc-aware) — noted in PROJECT.md out of scope, still deferred

None — discussion stayed within phase scope.
</deferred>

---

*Phase: 13-kitten-scenario-video-generation-hook-climax-conclusion-stories*
*Context gathered: 2026-03-26*
