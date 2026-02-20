---
phase: 02-script-generation
verified: 2026-02-20T23:00:00Z
status: passed
score: 4/4 must-haves verified
re_verification: false
notes:
  - "REQUIREMENTS.md SCRP-01 says '5-Pillar' and 'GPT-4o' but implementation uses 6-Pillar and Claude (Anthropic). Intentional evolution documented in 02-CONTEXT.md and 02-RESEARCH.md. Not a functional gap."
  - "Plan frontmatter requirement IDs are inconsistently labeled: 02-02 claims SCRP-02 (mood) but builds EmbeddingService; 02-03 claims SCRP-04 (auto-summarize) but builds mood handlers. All four requirements are fully implemented. Labels are documentation-level inaccuracies only."
---

# Phase 2: Script Generation Verification Report

**Phase Goal:** The system generates a Spanish script daily using the 6-Pillar framework, rejects semantically similar topics, learns from rejection feedback, and takes weekly mood direction (pool, tone, duration) from the creator
**Verified:** 2026-02-20T23:00:00Z
**Status:** PASSED
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths (from ROADMAP.md Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|---------|
| 1 | Script is in neutral Spanish, does not exceed target word count, follows Hook + Development + CTA structure governed by the 6-Pillar prompt | VERIFIED | `ScriptGenerationService.generate_script()` in `script_generation.py` uses a Spanish system prompt with all 6 pillars (RAIZ FILOSOFICA, TENSION UNIVERSAL, GIRO DE PERSPECTIVA, ANCLA EMOCIONAL, CTA REFLEXIVO, ARQUETIPO DEL CREADOR). `summarize_if_needed()` enforces word count ceiling with a hard truncation fallback. |
| 2 | When a topic exceeds 85% similarity to any script in history, the system automatically generates a new angle without creator intervention | VERIFIED | `SimilarityService.is_too_similar()` calls `supabase.rpc("check_script_similarity")` with 0.85 threshold. `daily_pipeline_job()` retries up to 3 attempts with escalating diversity instructions (attempt=0 normal, attempt=1 different angle, attempt=2 completely different topic). Creator alert sent only after all retries exhausted. |
| 3 | When a script exceeds its target word count, it is automatically summarized before being passed downstream — the creator never sees an over-length script | VERIFIED | `summarize_if_needed()` checks `_word_count(script) <= target_words`. If over, makes a second Claude call with an explicit summarization prompt naming pillars to preserve. Falls back to sentence-boundary truncation if Claude overshoots. Returns `(script, 0.0)` when within limit. |
| 4 | The bot prompts the creator once per week via Telegram for a mood profile (thematic pool + tone + duration); the creator's response is injected into the next generation as contextual direction | VERIFIED | `weekly_mood_prompt_job` fires Mon 9 AM Mexico City; `weekly_mood_reminder_job` fires Mon 1 PM if no response. 3-step inline keyboard (pool → tone → duration) in `mood_flow.py`. `handle_duration()` calls `MoodService().save_mood_profile()`. `daily_pipeline_job()` loads mood via `MoodService.get_current_week_mood()` and passes it to both `generate_topic_summary()` and `generate_script()`. |

**Score:** 4/4 truths verified

---

## Required Artifacts

### Plan 02-01 Artifacts

| Artifact | Provides | Exists | Substantive | Wired | Status |
|----------|----------|--------|-------------|-------|--------|
| `migrations/0002_script_generation.sql` | `check_script_similarity` SQL function + `rejection_constraints` table | Yes | Yes — both sections present, correct cosine-distance inversion `1 - (embedding <=> query)`, correct threshold filter | Applied via `run_migrations()` in FastAPI lifespan | VERIFIED |
| `src/app/telegram/app.py` | `build_telegram_app()`, `start_telegram_polling()`, `stop_telegram_polling()` | Yes | Yes — all three functions present, uses `ApplicationBuilder`, registers mood handlers via `register_mood_handlers(app)` | Called from `main.py` lifespan; result stored on `app.state.telegram_app` | VERIFIED |
| `src/app/settings.py` | `anthropic_api_key`, `openai_api_key`, `claude_generation_model` | Yes | Yes — all three fields present as Pydantic fields; `claude_generation_model` defaults to `claude-haiku-3-5-20241022` | Used by `ScriptGenerationService`, `EmbeddingService` | VERIFIED |
| `src/app/main.py` | Updated lifespan with Telegram polling lifecycle | Yes | Yes — builds app, starts polling, stores on `app.state.telegram_app`, calls `set_fastapi_app(app)`, stops on shutdown | Entry point — chains to all downstream services | VERIFIED |

### Plan 02-02 Artifacts

| Artifact | Provides | Exists | Substantive | Wired | Status |
|----------|----------|--------|-------------|-------|--------|
| `src/app/services/embeddings.py` | `EmbeddingService.generate(text) -> tuple[list[float], float]` | Yes | Yes — synchronous `OpenAI` client (not AsyncOpenAI), calls `client.embeddings.create`, returns `(embedding, cost_usd)` tuple | Called by `daily_pipeline_job()` — `embedding_svc.generate(topic_summary)` | VERIFIED |
| `src/app/services/similarity.py` | `SimilarityService.is_too_similar(embedding) -> bool` | Yes | Yes — uses `.rpc("check_script_similarity")`, returns False on empty result (no false positives), fails open on exception | Called by `daily_pipeline_job()` — `similarity_svc.is_too_similar(embedding)` | VERIFIED |

### Plan 02-03 Artifacts

| Artifact | Provides | Exists | Substantive | Wired | Status |
|----------|----------|--------|-------------|-------|--------|
| `src/app/services/mood.py` | `MoodService.get_current_week_mood()`, `save_mood_profile()`, `has_profile_this_week()` | Yes | Yes — all three methods present, returns dict with `pool/tone/duration/target_words`, falls back to defaults, uses `DURATION_WORD_COUNTS` | `get_current_week_mood()` called in `daily_pipeline_job()`; `save_mood_profile()` called in `handle_duration()` | VERIFIED |
| `src/app/telegram/handlers/mood_flow.py` | 3-step inline keyboard handlers, `register_mood_handlers()`, `send_mood_prompt_sync()` | Yes | Yes — `handle_pool`, `handle_tone`, `handle_duration` all call `await query.answer()` (3/3 present); uses `CallbackQueryHandler` prefix matching, NOT `ConversationHandler` | `register_mood_handlers()` called in `build_telegram_app()`; `send_mood_prompt_sync()` called by scheduler jobs | VERIFIED |
| `src/app/scheduler/jobs/weekly_mood.py` | `weekly_mood_prompt_job()`, `weekly_mood_reminder_job()` | Yes | Yes — prompt fires Mon 9 AM; reminder checks `has_profile_this_week()` before sending; both use `run_coroutine_threadsafe` pattern | Both registered in `registry.py` with `cron` triggers | VERIFIED |

### Plan 02-04 Artifacts

| Artifact | Provides | Exists | Substantive | Wired | Status |
|----------|----------|--------|-------------|-------|--------|
| `src/app/services/script_generation.py` | `ScriptGenerationService.generate_topic_summary()`, `generate_script()`, `summarize_if_needed()`, `load_active_rejection_constraints()` | Yes | Yes — 6-pillar system prompt in Spanish with all 6 pillar names; retry instructions differ for attempt 0/1/2; `summarize_if_needed()` names pillars to preserve; sync `Anthropic` client (not AsyncAnthropic); `_word_count()` uses `len(text.split())` | All three methods called by `daily_pipeline_job()` | VERIFIED |

### Plan 02-05 Artifacts

| Artifact | Provides | Exists | Substantive | Wired | Status |
|----------|----------|--------|-------------|-------|--------|
| `src/app/scheduler/jobs/daily_pipeline.py` | `daily_pipeline_job()` — complete orchestration | Yes | Yes — CB check, mood load, topic gen, embed, similarity retry loop (3 attempts), script gen, auto-summarize, save to `content_history` with embedding. `MAX_RETRIES = 2`. `_save_to_content_history()` inserts `script_text`, `topic_summary`, `embedding`. | Registered as `daily_pipeline_trigger` in `registry.py`; replaces `heartbeat_job` | VERIFIED |

---

## Key Link Verification

| From | To | Via | Status | Evidence |
|------|----|----|--------|---------|
| `src/app/main.py` (lifespan) | `src/app/telegram/app.py` | `build_telegram_app()` called, stored as `app.state.telegram_app` | WIRED | `main.py` line 37-39: `tg_app = build_telegram_app()` / `await start_telegram_polling(tg_app)` / `app.state.telegram_app = tg_app` |
| `src/app/services/telegram.py` | `src/app/telegram/app.py` | `get_telegram_bot()` reads `_fastapi_app.state.telegram_app.bot` | WIRED | `telegram.py` line 27: `return _fastapi_app.state.telegram_app.bot`; `set_fastapi_app(app)` called from `main.py` line 40 |
| `migrations/0002_script_generation.sql` | `content_history.embedding` | SQL function uses `<=>` on the `vector(1536)` column with distance-to-similarity inversion | WIRED | Migration line 18-23: `1 - (ch.embedding <=> query_embedding) AS similarity` with filter `(1 - (ch.embedding <=> query_embedding)) > similarity_threshold` |
| `src/app/services/similarity.py` | `supabase.rpc('check_script_similarity')` | `SimilarityService.is_too_similar()` calls `.rpc()` with embedding as `list[float]` | WIRED | `similarity.py` lines 43-50: `self._supabase.rpc("check_script_similarity", {"query_embedding": embedding, ...})` |
| `src/app/services/embeddings.py` | `openai.embeddings.create` | Synchronous `OpenAI` client (thread-pool-safe) | WIRED | `embeddings.py` lines 37-40: `self._client.embeddings.create(model=EMBEDDING_MODEL, input=text)` |
| `src/app/scheduler/jobs/weekly_mood.py` | `src/app/telegram/handlers/mood_flow.py` | `weekly_mood_prompt_job` calls `send_mood_prompt_sync` via `run_coroutine_threadsafe` | WIRED | `weekly_mood.py` lines 28-29: local import + `send_mood_prompt_sync(bot, settings.telegram_creator_id, loop)` |
| `src/app/telegram/handlers/mood_flow.py` | `src/app/services/mood.py` | `handle_duration()` calls `MoodService().save_mood_profile()` after step 3 | WIRED | `mood_flow.py` lines 144-146: local import `from app.services.mood import MoodService` + `MoodService().save_mood_profile(mood)` |
| `src/app/telegram/app.py` | `src/app/telegram/handlers/mood_flow.py` | `build_telegram_app()` calls `register_mood_handlers(app)` | WIRED | `app.py` line 5 (module-level import) + line 21: `register_mood_handlers(app)` |
| `src/app/scheduler/registry.py` | `src/app/scheduler/jobs/daily_pipeline.py` | `daily_pipeline_trigger` job calls `daily_pipeline_job` | WIRED | `registry.py` line 4 import + line 25: `scheduler.add_job(daily_pipeline_job, ...)` |
| `src/app/scheduler/jobs/daily_pipeline.py` | `src/app/services/script_generation.py` | `ScriptGenerationService` called for topic, script, summarize | WIRED | `daily_pipeline.py` lines 61, 96, 109: `generate_topic_summary()`, `generate_script()`, `summarize_if_needed()` |
| `src/app/scheduler/jobs/daily_pipeline.py` | `src/app/services/embeddings.py` | `EmbeddingService.generate()` called after topic summary | WIRED | `daily_pipeline.py` line 74: `embedding, embed_cost = embedding_svc.generate(topic_summary)` |
| `src/app/scheduler/jobs/daily_pipeline.py` | `content_history` (Supabase) | `_save_to_content_history()` inserts `script_text`, `topic_summary`, `embedding` | WIRED | `daily_pipeline.py` lines 127-131: `supabase.table("content_history").insert({...}).execute()` |

---

## Requirements Coverage

| Requirement | REQUIREMENTS.md Description | Source Plans | Implementation Evidence | Status |
|-------------|----------------------------|-------------|------------------------|--------|
| SCRP-01 | Generates a 140-word max script in neutral Spanish using the 5-Pillar system prompt (structured as Aggressive Hook + Philosophical Development + Reflective CTA) | 02-04, 02-05 | `ScriptGenerationService.generate_script()` with 6-pillar Spanish system prompt; `summarize_if_needed()` enforces word count ceiling. Framework evolved from 5 to 6 pillars per CONTEXT.md — intentional, documented decision. | SATISFIED |
| SCRP-02 | Creator sets weekly mood profile via Telegram; profile feeds into script generation as contextual direction | 02-01, 02-02, 02-05 | `weekly_mood_prompt_job` + `weekly_mood_reminder_job` (Mon 9 AM and 1 PM); 3-step inline keyboard flow in `mood_flow.py`; `MoodService.save_mood_profile()` persists to DB; `daily_pipeline_job()` reads via `get_current_week_mood()` and passes to generation services. | SATISFIED |
| SCRP-03 | Anti-repetition guard queries pgvector before generation; if topic exceeds 0.85 cosine similarity, system generates a new angle automatically | 02-02, 02-04, 02-05 | `SimilarityService.is_too_similar()` calls `check_script_similarity` SQL function via `.rpc()`. `daily_pipeline_job()` retries up to 3 attempts with differentiated topic instructions before alerting creator. | SATISFIED |
| SCRP-04 | Script automatically summarized by AI if it exceeds 140 words before being submitted downstream | 02-01, 02-03, 02-04, 02-05 | `ScriptGenerationService.summarize_if_needed()` checks word count, makes a second Claude call if over, preserves Philosophical Root + Emotional Anchor + Reflective CTA explicitly in compression prompt, hard-truncates at sentence boundary if Claude overshoots. | SATISFIED |

**Note on requirement ID labeling in plan frontmatter:** The `requirements:` fields in plan frontmatter do not accurately reflect which requirements each plan's code actually implements. Plan 02-02 claims SCRP-02 (mood collection) but builds the embedding/similarity services; Plan 02-03 claims SCRP-04 (auto-summarize) but builds the mood Telegram flow. This is a documentation inconsistency only — all four requirements are substantively implemented and wired end-to-end. No functional gap exists.

**Note on SCRP-01 wording vs implementation:** REQUIREMENTS.md describes SCRP-01 as using "GPT-4o" and a "5-Pillar system prompt." The implementation uses Claude (Anthropic) and a 6-pillar framework. The ROADMAP.md Phase 2 goal and CONTEXT.md both specify "6-Pillar framework" and Claude — this is a resolved decision documented in planning artifacts. REQUIREMENTS.md was not updated to reflect the pillar count evolution or the model switch. This is a documentation staleness issue, not a functional gap.

---

## Anti-Patterns Found

| File | Pattern | Severity | Finding |
|------|---------|----------|---------|
| `src/app/services/telegram.py` | `updater(None)` | N/A | NOT present in live code — only referenced in a comment inside `telegram/app.py` noting it was the Phase 1 pattern that was removed. CLEAN. |
| `src/app/services/embeddings.py` | `AsyncOpenAI` | N/A | NOT present — uses synchronous `OpenAI`. Anti-pattern was explicitly guarded against in comments. CLEAN. |
| `src/app/services/script_generation.py` | `AsyncAnthropic` | N/A | NOT present — uses synchronous `Anthropic`. CLEAN. |
| `src/app/services/similarity.py` | `.table()` query for vector comparison | N/A | The single `.table(` occurrence is inside a comment (line 16). All live code uses `.rpc("check_script_similarity")`. CLEAN. |
| `src/app/telegram/handlers/mood_flow.py` | `ConversationHandler` | N/A | NOT present — uses `CallbackQueryHandler` with prefix matching as required. CLEAN. |
| `src/app/scheduler/jobs/heartbeat.py` | Deprecated function still referenced in registry | N/A | `heartbeat_job` is NOT imported or registered in `registry.py`. File has deprecation comment at top. `daily_pipeline_trigger` now correctly points to `daily_pipeline_job`. CLEAN. |

No blocker or warning anti-patterns found in any Phase 2 file.

---

## Human Verification Required

### 1. End-to-End Pipeline Execution Against Live DB

**Test:** Populate `.env` with valid `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `SUPABASE_URL`, `SUPABASE_KEY`, `DATABASE_URL`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CREATOR_ID`. Start the service. Wait for the 7 AM scheduled trigger (or manually invoke `daily_pipeline_job()`). Inspect Supabase `content_history` table.
**Expected:** A new row appears with a non-empty `script_text` (Spanish, ~70-200 words depending on mood), a non-null `topic_summary`, and a non-null `embedding` vector.
**Why human:** Requires live API credentials and a running Supabase instance. Cannot be verified from the codebase alone.

### 2. Mood Flow — 3-Step Telegram Interaction

**Test:** With the service running and Telegram configured, manually call `send_pool_prompt()` for the creator chat ID. Tap through all three inline keyboard steps: pool → tone → duration.
**Expected:** Each step transitions to the next prompt. After tapping duration, the creator sees a Spanish confirmation message, and a new row appears in the `mood_profiles` table with the correct `week_start` and JSON `profile_text`.
**Why human:** Interactive Telegram callback flow cannot be verified programmatically without a live bot.

### 3. Anti-Repetition Guard Behavior at 85% Threshold

**Test:** Run the pipeline twice with a seeded `content_history` containing a script on the same topic. Observe whether the second run triggers the similarity retry loop.
**Expected:** On similarity hit, pipeline logs "Topic too similar — retrying" and generates a new topic summary for attempt=1 with different angle instructions.
**Why human:** Requires live pgvector comparison with actual embedding vectors. The threshold calibration (0.85) for Spanish philosophical content has not been empirically validated — SUMMARY.md explicitly flags this as a known open item.

### 4. Similarity Threshold Calibration (Open Item from SUMMARY.md)

**Test:** Over several real generation runs, monitor whether the 0.85 cosine similarity threshold produces the expected false-positive rate for Spanish philosophical content.
**Expected:** Threshold rejects genuinely repetitive topics without rejecting topically adjacent but sufficiently distinct scripts.
**Why human:** Requires real operational data to calibrate. Explicitly called out in `02-05-SUMMARY.md` as an uncalibrated parameter.

---

## Gaps Summary

No functional gaps. All four Phase 2 Success Criteria from ROADMAP.md are fully implemented and wired end-to-end in the codebase:

1. The 6-pillar generation pipeline exists in `ScriptGenerationService` and is invoked daily by `daily_pipeline_job()`.
2. The anti-repetition guard is live via `SimilarityService.is_too_similar()` calling the `check_script_similarity` SQL function.
3. Auto-summarization is enforced by `summarize_if_needed()` before the script exits the pipeline.
4. Weekly mood collection is scheduled (Mon 9 AM + 1 PM reminder), stored via `MoodService.save_mood_profile()`, and injected into every generation via `get_current_week_mood()`.

Documentation-level inconsistencies exist (REQUIREMENTS.md says 5-Pillar/GPT-4o; plan frontmatter requirement IDs are mis-mapped) but these do not affect system behavior. Phase 2 goal is achieved.

---

*Verified: 2026-02-20T23:00:00Z*
*Verifier: Claude (gsd-verifier)*
