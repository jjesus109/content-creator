# Phase 12: Grey Kitten Unified Prompt Generation - Context

**Gathered:** 2026-03-21
**Status:** Ready for planning

<domain>
## Phase Boundary

Replace the `CHARACTER_BIBLE` string concatenation in `KlingService.submit()` with a GPT-4o call that generates a unified, animated-style scene prompt naturally fusing the new grey kitten character with the scene description. Persist the unified prompt by overwriting `script_text` in `content_history`. No new DB columns, no migration. Telegram notification already reads `script_text` so the creator automatically receives the new prompt.

</domain>

<decisions>
## Implementation Decisions

### Character Identity
- Orange tabby Mochi is **retired**. The new character completely replaces `CHARACTER_BIBLE`.
- New character constant: "A full-body, high-definition 3D render of an ultra-cute, sitting light grey kitten. The kitten has huge, wide, expressive blue eyes and a cheerful, open-mouthed smile showing its pink tongue. Its soft fur texture is highly detailed."
- Update the `CHARACTER_BIBLE` Python constant in `kling.py` with this new description.

### Unified Prompt Generation
- A new `PromptGenerationService` is responsible for the GPT-4o call — separate from `SceneEngine` and `KlingService`. Clean single-responsibility separation.
- GPT-4o system prompt instructs **animated/ultra-cute style** — not technical "3D render" framing. The goal is to produce visually vibrant, cute prompts that capture audience attention on TikTok/Reels.
- GPT-4o should **weave the character naturally into the scene**, preserving the scene's location/activity/mood intent from `SceneEngine`. Claude's discretion on how much creative rewriting is allowed vs strict preservation.
- The unified prompt replaces the old `f"{CHARACTER_BIBLE}\n\n{script_text}"` concatenation in `KlingService.submit()`. `KlingService` receives the already-unified prompt and sends it directly to Kling — no internal concatenation.

### content_history Persistence
- No new columns, no migration.
- The unified prompt **overwrites `script_text`** in `content_history`. The `scene_prompt` column retains the raw SceneEngine output for reference.
- `daily_pipeline.py`'s `_save_to_content_history()` stores the unified prompt as `script_text`.

### Telegram Notification
- No changes to Telegram code. `send_approval_message()` already reads `script_text` — it will automatically show the unified prompt.
- Word count (`Palabras:`) will reflect the unified prompt length — acceptable, no label change needed.
- `PostCopyService` continues to generate `post_copy` from `script_text` (now the unified prompt) — no changes.

### Fallback on GPT-4o Failure
- **Retry first**: use tenacity (consistent with `_submit_with_backoff` pattern in `kling.py`) for 2-3 attempts with exponential backoff.
- **Then fall back** to old concatenation: `CHARACTER_BIBLE + "\n\n" + scene_prompt`. Pipeline continues without interruption.
- Log a `logger.warning()` on fallback — no DB flag, no schema change.

### Claude's Discretion
- Exact tenacity retry configuration for `PromptGenerationService` (attempts, wait multiplier)
- How much scene rewriting latitude GPT-4o gets (preserve intent vs creative rewrite)
- Temperature for the unified prompt GPT-4o call
- Whether `PromptGenerationService` tracks cost (consistent with `SceneEngine`'s cost tracking pattern)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Character & Video Generation
- `src/app/services/kling.py` — `CHARACTER_BIBLE` constant (to be replaced), `KlingService.submit()` (concatenation to be removed), `_submit_with_backoff` tenacity pattern (reuse for PromptGenerationService retry)

### Scene Generation Pattern
- `src/app/services/scene_generation.py` — `SceneEngine.pick_scene()` GPT-4o call pattern, `_build_system_prompt()`, cost tracking (`GPT4O_COST_INPUT_PER_MTOK`/`GPT4O_COST_OUTPUT_PER_MTOK`), `OpenAI` client initialization

### Pipeline Integration
- `src/app/scheduler/jobs/daily_pipeline.py` — `daily_pipeline_job()` call chain, `_save_to_content_history()` for `script_text` field, where `PromptGenerationService` must be inserted between `SceneEngine.pick_scene()` and `KlingService.submit()`

### Telegram Notification
- `src/app/services/telegram.py` — `send_approval_message()` reads `script_text` from `content_history` (lines ~99-101, ~157-173). No changes needed but must verify field name.

No external specs — requirements fully captured in decisions above.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `OpenAI` client in `scene_generation.py`: `self._client = OpenAI(api_key=settings.openai_api_key)` — same pattern for `PromptGenerationService`
- `_submit_with_backoff` tenacity decorator in `kling.py`: reuse this retry pattern for GPT-4o unified prompt call
- `GPT4O_COST_INPUT_PER_MTOK` / `GPT4O_COST_OUTPUT_PER_MTOK` constants in `scene_generation.py`: reference for cost tracking if desired

### Established Patterns
- GPT-4o service calls return structured JSON via `response_format=json_object` — `PromptGenerationService` may return a simple string instead since the unified prompt is unstructured text
- Services raise `ValueError` on invalid GPT-4o responses (see `SceneEngine`) — consistent error propagation
- Module-level functions (not instance methods) used for tenacity decorators due to APScheduler ThreadPoolExecutor context

### Integration Points
- `daily_pipeline.py` line ~158: `kling_svc.submit(scene_prompt)` — this becomes `kling_svc.submit(unified_prompt)` where `unified_prompt` comes from `PromptGenerationService`
- `daily_pipeline.py` `_save_to_content_history()` line ~205: `"script_text": scene_prompt` — this becomes `"script_text": unified_prompt`
- `kling.py` `KlingService.submit()` line ~95: `full_prompt = f"{CHARACTER_BIBLE}\n\n{script_text}"` — this concatenation is removed; `script_text` param becomes the already-unified prompt

</code_context>

<specifics>
## Specific Ideas

- The animated/ultra-cute style is non-negotiable — GPT-4o system prompt must explicitly frame the output as an animated, cute, attention-grabbing short-form video prompt (not a live-action or photorealistic description).
- The grey kitten's key visual hooks (huge blue eyes, open-mouthed smile, pink tongue, light grey soft fur) should naturally appear in the unified prompt — not just the character description prepended.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 12-grey-kitten-unified-prompt-generation*
*Context gathered: 2026-03-21*
