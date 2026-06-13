# v2.0 Architecture Research Summary

**Project:** Autonomous Content Machine — Mexican Cat Content
**Milestone:** v2.0 (Replace HeyGen with AI cat video generation)
**Date:** 2026-03-19
**Status:** Complete

---

## Research Questions Answered

### Q1: How does scene prompt generation replace ScriptGenerationService?

**Answer:** New `ScenePromptService` generates 40-60 word visual descriptions (instead of 90-word philosophical scripts). Same Claude API, different output format.

- **ScriptGenerationService**: 6-pillar framework, abstract ideas, narrative
- **ScenePromptService**: Visual elements, cat actions, mood, lighting

Same cost tracking and embedding/similarity logic. Retry logic unchanged (3 attempts max).

---

### Q2: How does the new AI video API integrate with APScheduler ThreadPoolExecutor?

**Answer:** Synchronous polling wrapper inside the daily job. No async context, no separate poller job, no webhooks.

**Key decision:** Use blocking `RunwayVideoService.submit_and_poll()` that polls synchronously until complete (~30-60 seconds typical).

**Why:**
- APScheduler ThreadPoolExecutor runs synchronous jobs
- Runway Gen-4 typically completes in 30-60 seconds (acceptable)
- Avoids mixing asyncio event loop (FastAPI) with threading pool
- Simpler state machine (skip pending_render → rendering states)

**Integration:** Replace HeyGen submission in `daily_pipeline_job()` with Runway call. Video ready immediately after polling completes.

---

### Q3: How should the curated scene category library be stored?

**Answer:** Database table + YAML config seeding + Python enums for types only.

**Storage model:**

| What | Where | Why |
|------|-------|-----|
| Available categories (locations, activities, moods, lighting) | `scene_categories` table | Easy to add/disable without redeploy |
| Default library | `config/scene_categories.yaml` | Version-controlled, human-readable |
| Type enums (e.g., `location`, `activity`) | Python constants | Immutable, compile-time validation |

**Not a Python constant:** `LOCATIONS = ["sunny_bedroom", "kitchen"]` — this comes from the DB via `SceneCategoryService`.

---

### Q4: How should the seasonal calendar service work?

**Answer:** Simple lookup table + month-day (MM-DD) matching. No year logic.

**Implementation:**

```sql
CREATE TABLE seasonal_events (
    event_name text,
    start_date date,      -- MM-DD format
    end_date date,        -- MM-DD format
    theme_context text,   -- Prompt injection
)
```

**Lookup:** `WHERE start_date <= today_month_day AND end_date >= today_month_day`

**Why month-day only:**
- Same holiday every year (Aug 8 is always Aug 8)
- Avoids leap year complexity
- Simple range matching in SQL

**Integration:** `SeasonalCalendarService.get_theme_context(date)` returns theme string injected into Claude prompt.

---

### Q5: How should music selection work?

**Answer:** Pre-curated pool (reuse HeyGen) + mood tagging + heuristic mood extraction.

**Storage:**

```sql
CREATE TABLE music_tracks (
    url text,
    mood text,  -- 'playful', 'peaceful', 'energetic', 'mysterious', 'melancholic'
    title text,
    duration_sec integer
)
```

**Workflow:**

1. `ScenePromptService` generates scene prompt
2. `ScenePromptService._extract_mood_from_prompt()` detects mood (keyword heuristic)
3. `MusicSelectionService.pick_music_by_mood()` selects random track matching mood
4. `AudioProcessingService` uses selected music URL

**Fallback:** If no mood-specific tracks, use full pool.

---

### Q6: What DB schema changes are needed?

**Answer:** 4 new tables + 5 new columns on `content_history`. No breaking changes.

**New tables:**
- `scene_categories` — location, activity, mood, lighting options
- `seasonal_events` — themed event context
- `music_tracks` — pre-curated music with mood tagging
- `video_generation_jobs` — Runway task tracking (future-proofing for multi-provider)

**Modified `content_history`:**
- `scene_prompt` (text) — replaces `script_text` for cat videos
- `video_mood` (text) — detected mood ('playful', 'peaceful', etc.)
- `music_url` (text) — which track was selected
- `runway_task_id` (text) — Runway's task ID
- `generation_provider` (text) — 'runway' (future: 'pika', 'kling')

**Backward compatibility:** v1.0 HeyGen rows keep `script_text` + `heygen_job_id`. v2.0 cat videos use `scene_prompt` + `runway_task_id`.

---

## Architecture Summary

### Data Flow

```
daily_pipeline_job()
  → Load seasonal theme
  → Generate scene prompt (with seasonal context)
  → Extract mood from prompt
  → Check similarity (reuse v1.0 logic)
  → Submit to Runway + poll (blocking, ~30-60s)
  → Pick music by mood
  → Process audio (EQ + mix)
  → Upload to Supabase Storage
  → Save to content_history
  → Send Telegram approval
```

### New vs Modified Components

**New:**
- `ScenePromptService`
- `RunwayVideoService`
- `SceneCategoryService`
- `SeasonalCalendarService`
- `MusicSelectionService`

**Modified:**
- `daily_pipeline_job()` — replace HeyGen with Runway
- `content_history` schema — add 5 columns
- `AudioProcessingService` — mood-aware music selection
- `VideoStatus` enum — remove pending_render states

**Unchanged:**
- FastAPI app
- APScheduler + ThreadPoolExecutor
- Telegram approval flow
- Platform publishing
- Analytics

---

## Build Order

1. **Database & Seeding** (1 day)
   - Migration `0008_cat_video_schema.sql`
   - Seed scene categories, seasonal events, music tracks from YAML

2. **Services Foundation** (1-2 days)
   - `ScenePromptService` + mood extraction
   - `SceneCategoryService` + `SeasonalCalendarService`
   - `MusicSelectionService`

3. **Video Generation** (2-3 days)
   - `RunwayVideoService` (submit + polling with backoff)
   - Timeout and failure handling

4. **Pipeline Integration** (1-2 days)
   - Refactor `daily_pipeline_job()` to use Runway
   - Remove HeyGen calls
   - End-to-end test

5. **Testing & Hardening** (2 days)
   - Load testing (Runway rate limits)
   - Timeout scenarios
   - Fallback logic

---

## Key Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| **Runway API timeout** | 10-min timeout guard + creator alert |
| **Mood extraction wrong** | Default to 'peaceful' + manual review sampling |
| **Scene repetition** | Diversify category pool (10+ per type) |
| **Music URL broken** | Weekly validation + pool >5 per mood |
| **APScheduler blocking** | 4-worker ThreadPoolExecutor handles one blocking job |

---

## Confidence Levels

| Area | Level | Reason |
|------|-------|--------|
| Scene generation | HIGH | Claude API proven in v1.0, only output format changes |
| Runway integration | MEDIUM-HIGH | API documented, polling pattern standard, untested in production |
| DB schema | HIGH | Straightforward additions, backward compatible |
| Music selection | HIGH | Simple heuristic, proven pattern from HeyGen |
| Seasonal calendar | HIGH | Trivial date lookup, data-driven |
| Sync integration | HIGH | ThreadPoolExecutor + blocking calls proven in codebase |

---

## Next Steps (for Build Phase)

1. **Create migration file** `migrations/0008_cat_video_schema.sql`
2. **Implement `ScenePromptService`** with mood extraction
3. **Implement `RunwayVideoService`** with polling + timeout
4. **Seed data** (scene categories, seasonal events, music tracks)
5. **Refactor `daily_pipeline_job()`** to use new services
6. **End-to-end test** before launch

---

## Resources

All research findings documented in:
- `.planning/research/ARCHITECTURE-V2.md` — Complete 6-question breakdown with code examples
- `.planning/research/V2-RESEARCH-SUMMARY.md` — This document
