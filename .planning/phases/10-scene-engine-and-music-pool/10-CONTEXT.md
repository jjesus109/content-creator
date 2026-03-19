# Phase 10: Scene Engine and Music Pool - Context

**Gathered:** 2026-03-19
**Status:** Ready for planning

<domain>
## Phase Boundary

Scene Engine and Music Pool: daily scene prompt drawn from a curated 40-60 combo library via GPT-4o, seasonal calendar overlays for Mexican holidays + Cat Day, anti-repetition via pgvector (recalibrated 7-day window, 75-80% threshold), 200+ track music pool with mood-to-BPM matching and per-platform license matrix, universal Spanish caption generator (5-8 words), and full wiring into daily_pipeline.py. Video generation (Kling) and publishing infrastructure are unchanged.

</domain>

<decisions>
## Implementation Decisions

### Scene library format
- Library lives in a **JSON file in the repo** (e.g., `src/app/data/scenes.json`) — version-controlled, no DB dependency, editable without touching Python
- **Explicit pre-combined entries**: each entry is a full `{location, activity, mood}` tuple (e.g., `{"location": "cocina", "activity": "inspeccionar olla", "mood": "curious"}`) — not separate category pools
- GPT-4o receives the raw selected combo + Character Bible and **expands it into a 2-3 sentence Kling-optimized prompt**; caption is generated in the same GPT-4o call (one API call returns both scene prompt and Spanish caption)

### Scene selection and prompt construction
- GPT-4o selects one combo from the library (weighted or random, researcher decides) and outputs: (1) expanded Kling prompt, (2) 5-8 word Spanish caption following `[observation] + [implied personality]` formula
- Seasonal calendar overlays are injected as additional context into the same GPT-4o call when the current date matches a holiday — no separate generation pass
- Combo + expanded prompt + caption all saved to content_history row alongside the Kling job ID

### Music pool DB schema
- New `music_pool` table with columns: `title`, `artist`, `file_url` (Supabase Storage path or external URL), `mood` (playful/sleepy/curious), `bpm` (integer), `tiktok_cleared` (boolean), `youtube_cleared` (boolean), `instagram_cleared` (boolean), `license_expires_at` (date, nullable)
- License flags on the `music_pool` table itself — not a separate `license_matrix` table (Phase 11 queries `music_pool` directly)
- Pool seeded via **manual CSV/JSON → DB migration** (Plan 10-01 delivers the seed file + migration)

### Anti-repetition for scenes
- **New `check_scene_similarity` pgvector SQL function** alongside the existing `check_script_similarity` — keeps 7-day lookback and 75-80% threshold independent from the 90-day script lookback
- What gets embedded: the **full expanded scene prompt** (2-3 sentences GPT-4o produces), not the raw combo label — captures semantic meaning of the visual scene
- New `scene_embeddings` table (or `scene_embedding` column on `content_history`) stores the scene prompt embedding alongside the existing script embedding
- **Empirical threshold calibration via dry-run script** before automation enabled: a one-off script tests scene prompt pairs at various thresholds and prints similarity scores; developer reviews and confirms threshold in STATE.md before the check is enforced in production
- Automation gated behind a feature flag or explicit STATE.md sign-off — anti-repetition runs in log-only mode until calibrated

### Rejection feedback (SCN-04)
- When creator rejects a video, **scene combo + rejection reason text** stored (not full Kling prompt, not just caption)
- On next generation, rejected scene combos + reasons injected into the GPT-4o scene selection prompt as negative context (same pattern as existing `rejection_constraints` in `ScriptGenerationService`)
- New rejection storage: extend existing rejection constraints table or add scene-specific columns — researcher decides based on current schema

### Pipeline wiring
- **`SceneEngine.pick_scene()` replaces `generate_topic_summary()` + `generate_script()`** entirely in `daily_pipeline.py` — no parallel path, no toggle flag; v1.0 script generation is deprecated in v2.0
- `MusicMatcher.pick_track(mood)` called after scene selection, before Kling submission — music track ID saved to content_history
- Caption stored on content_history and passed to `platform_publish.py` as the universal caption (replaces `post_copy` service for v2.0)
- Pipeline retry loop adapted: on scene similarity rejection, call `SceneEngine.pick_scene()` again (up to MAX_RETRIES) rather than re-prompting topic summary

### Claude's Discretion
- JSON structure of scenes.json (field names, optional weight field, ordering)
- GPT-4o system prompt for scene expansion + caption generation
- Whether mood-to-BPM range is hardcoded in MusicMatcher or read from config
- Exact SQL for check_scene_similarity (mirror of check_script_similarity with adjusted params)
- Whether scene embedding is a new column on content_history or a separate table

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements
- `.planning/REQUIREMENTS.md` — SCN-01 through SCN-05 and MUS-01 through MUS-03 acceptance criteria (the source of truth for Phase 10 scope)
- `.planning/STATE.md` — Accumulated v2.0 decisions, known blockers (anti-repetition threshold calibration required, deployment env vars)

### Existing codebase (read before modifying)
- `src/app/scheduler/jobs/daily_pipeline.py` — Entry point to refactor: SceneEngine replaces generate_topic_summary + generate_script; MusicMatcher added; rejection loop adapted
- `src/app/services/embeddings.py` — EmbeddingService.generate() to reuse for scene prompt embeddings (same model, same vector dimensions)
- `src/app/services/similarity.py` — check_script_similarity RPC pattern to mirror for new check_scene_similarity function (same RPC call convention via Supabase)
- `src/app/services/script_generation.py` — load_active_rejection_constraints() pattern to extend or replicate for scene rejection constraints
- `src/app/services/kling.py` — KlingService.submit() receives the final scene prompt; CHARACTER_BIBLE is already embedded here (no change)
- `src/app/settings.py` — Where new settings (e.g., SCENE_LIBRARY_PATH, anti-repetition feature flag) should be added

### DB migration reference
- `src/app/db/migrations.py` — Migration registration pattern; new migrations needed: music_pool table, scene_embedding column/table, check_scene_similarity function

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `EmbeddingService` (`src/app/services/embeddings.py`): Reuse as-is for scene prompt embeddings — same model, same 1536-dim vector, same sync-safe pattern
- `SimilarityService` (`src/app/services/similarity.py`): Mirror its RPC call pattern for `check_scene_similarity`; the `is_too_similar()` logic is identical, only the SQL function name and default params change
- `ScriptGenerationService.load_active_rejection_constraints()` (`src/app/services/script_generation.py`): Extend or replicate for scene rejection constraints; same pattern of loading DB rows and formatting as negative context
- `send_alert_sync` (`src/app/services/telegram.py`): Use for music pool empty / no cleared tracks alerts

### Established Patterns
- Rejection constraints: loaded from DB at pipeline start, injected into GPT-4o prompt as structured negative context — SceneEngine follows the same pattern
- APScheduler ThreadPoolExecutor: all services must be sync-safe (OpenAI sync client already established, same rule applies to GPT-4o scene generation call)
- `get_settings()` + env var injection: any new config (feature flag, scene library path) follows this pattern
- Supabase RPC for pgvector queries: `.rpc("function_name", {...}).execute()` — never raw SQL via psycopg

### Integration Points
- `daily_pipeline.py` line ~65: topic summary + script generation replaced by `SceneEngine.pick_scene()` call
- `daily_pipeline.py`: music track selection added after scene pick, before `KlingService.submit()`
- `content_history` table: needs `scene_prompt`, `caption`, `music_track_id` columns (v2.0 migration)
- `platform_publish.py`: universal caption read from `content_history.caption` column (replaces post_copy service lookup)

</code_context>

<specifics>
## Specific Ideas

- Scene library JSON should be loaded once at module import (not per call) — similar to how CHARACTER_BIBLE is a module-level constant
- The dry-run calibration script should output a similarity matrix for 20-30 test scene prompt pairs so the developer can visually inspect clustering before committing to a threshold
- Seasonal overlays: Sep 16 = "Día de Independencia" theme, Nov 1-2 = "Día de Muertos" theme, Nov 20 = "Día de la Revolución" theme, Aug 8 = "Día Internacional del Gato" theme — each injects a short thematic modifier into the GPT-4o prompt, not a full scene override

</specifics>

<deferred>
## Deferred Ideas

- None — discussion stayed within phase scope

</deferred>

---

*Phase: 10-scene-engine-and-music-pool*
*Context gathered: 2026-03-19*
