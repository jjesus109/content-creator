# v2.0 Build Checklist & Integration Points

**Milestone:** v2.0 (Replace HeyGen with AI cat video generation)
**Purpose:** Detailed build order with dependencies and integration checkpoints

---

## Phase 1: Database Schema & Data Seeding (1 day)

### 1.1: Create Migration File
- [ ] Create `migrations/0008_cat_video_schema.sql`
- [ ] Create `scene_categories` table with indexes
- [ ] Create `seasonal_events` table with indexes
- [ ] Create `music_tracks` table with indexes
- [ ] Create `video_generation_jobs` table with indexes
- [ ] Add 5 columns to `content_history` (scene_prompt, video_mood, music_url, runway_task_id, generation_provider)
- [ ] Verify schema with `run_migrations()` test

### 1.2: Create Config Files
- [ ] Create `config/scene_categories.yaml` with location/activity/mood/lighting seed data
- [ ] Create `config/seasonal_events.yaml` with Mexican holiday themes
- [ ] Create `config/music_tracks.yaml` with mood-tagged music URLs

### 1.3: Implement Seeding
- [ ] Implement `SceneCategoryService.seed_from_yaml()`
- [ ] Implement `SeasonalCalendarService.seed_from_yaml()`  (or embed in service)
- [ ] Implement `MusicSelectionService.seed_from_yaml()`
- [ ] Create management command: `python manage.py seed_v2_data`
- [ ] Run seeding on test database, verify row counts

### 1.4: Test Schema
- [ ] Query `scene_categories` by type and is_active
- [ ] Query `seasonal_events` by date range
- [ ] Query `music_tracks` by mood
- [ ] Verify `content_history` new columns are nullable/have proper defaults

**Dependency:** None. Can run in parallel with Phase 2.

---

## Phase 2: Services Foundation (1-2 days)

### 2.1: ScenePromptService
- [ ] Create `src/app/services/scene_prompt.py`
- [ ] Implement `generate_scene_prompt(seasonal_context, attempt, rejection_constraints)`
- [ ] Implement `_load_scene_categories()` (cached)
- [ ] Implement `_call_claude(system, user, max_tokens)` (reuse from ScriptGenerationService)
- [ ] Test: Generate 5 scene prompts manually, verify 40-60 word range
- [ ] Test: Verify retry logic adjusts prompt for attempt=1 and attempt=2

### 2.2: Mood Extraction
- [ ] Implement `ScenePromptService._extract_mood_from_prompt(prompt: str) -> str`
- [ ] Define mood keywords dict: playful, peaceful, energetic, mysterious, melancholic
- [ ] Test: 10 sample prompts with expected mood extraction
- [ ] Verify default mood='peaceful' on no match

### 2.3: SceneCategoryService
- [ ] Create `src/app/services/scene_category.py`
- [ ] Implement `get_all_categories() -> dict[str, list[str]]`
- [ ] Implement caching (1-hour TTL)
- [ ] Implement `seed_from_yaml(yaml_path)`
- [ ] Test: Load categories, verify cache invalidation after 1 hour
- [ ] Test: Upsert from YAML, verify idempotency

### 2.4: SeasonalCalendarService
- [ ] Create `src/app/services/seasonal_calendar.py`
- [ ] Implement `get_theme_context(check_date=None) -> str`
- [ ] Implement date range matching: `start_date <= month_day <= end_date`
- [ ] Implement caching (per day)
- [ ] Test: Query for International Cat Day (08-08), verify theme returns
- [ ] Test: Query for non-event date, verify empty string returns
- [ ] Test: Verify cache resets daily

### 2.5: MusicSelectionService
- [ ] Create `src/app/services/music_selection.py`
- [ ] Implement `pick_music_by_mood(video_mood: str) -> str`
- [ ] Implement mood-keyed caching
- [ ] Implement fallback to full pool if no mood match
- [ ] Test: Pick music for each mood, verify URL returned
- [ ] Test: Pick music for non-existent mood, verify fallback to full pool
- [ ] Test: Verify URL is from active tracks only

**Dependency:** Phase 1 (database schema and seeding must be complete)

---

## Phase 3: Video Generation Service (2-3 days)

### 3.1: RunwayVideoService Structure
- [ ] Create `src/app/services/runway.py`
- [ ] Implement `__init__()` with httpx.Client (sync, not async)
- [ ] Implement `submit_and_poll(scene_prompt, max_wait_seconds=600) -> str`
- [ ] Implement `_submit_generation(scene_prompt) -> str` (POST /v1/generations)
- [ ] Implement `_poll_until_ready(task_id, max_wait_seconds) -> str`

### 3.2: Polling Logic
- [ ] Implement exponential backoff: start=2s, max=30s
- [ ] Implement status check: GET /v1/tasks/{task_id}
- [ ] Handle status='succeeded' → return video URL
- [ ] Handle status='failed' → raise RuntimeError with failure reason
- [ ] Handle status='queued'|'processing' → backoff and retry
- [ ] Implement timeout: raise TimeoutError after max_wait_seconds

### 3.3: Error Handling
- [ ] Test: Successful generation (mock task_id, status='succeeded')
- [ ] Test: Generation failure (mock status='failed')
- [ ] Test: Polling timeout (mock never-completing task)
- [ ] Test: API rate limit (mock 429 response, verify backoff)
- [ ] Test: Network timeout (mock timeout exception)

### 3.4: Integration with Settings
- [ ] Add `runway_api_key` to `app/settings.py`
- [ ] Add `runway_api_base_url` to settings (default: https://api.runwayml.com/v1)
- [ ] Verify API key loading from environment

**Dependency:** None. Can run in parallel with Phase 2.

---

## Phase 4: Audio & Storage (1 day)

### 4.1: Update AudioProcessingService
- [ ] Modify `process_video_audio(video_url, music_url)` signature (add music_url param)
- [ ] Verify ffmpeg filter_complex includes music download + mix
- [ ] Test: Process video with mood-selected music track
- [ ] Verify output MP4 has both video and mixed audio

### 4.2: Update VideoStorageService
- [ ] Verify existing `upload(processed_bytes) -> stable_url` works
- [ ] No changes needed (reuse from v1.0)

**Dependency:** Phase 3 (video generation service must be ready for end-to-end test)

---

## Phase 5: Pipeline Integration (1-2 days)

### 5.1: Refactor daily_pipeline_job()

**Before (HeyGen):**
```python
# Phase 3 (HeyGen): Submit to HeyGen after script is confirmed good
heygen_svc = HeyGenService()
heygen_job_id = heygen_svc.submit(script_text=script, background_url=background_url)
_save_to_content_history(..., heygen_job_id=heygen_job_id, video_status=PENDING_RENDER)
register_video_poller(heygen_job_id)
```

**After (Runway):**
```python
# Phase 3 (Runway): Submit to Runway and poll until complete
runway_svc = RunwayVideoService()
video_url = runway_svc.submit_and_poll(scene_prompt=scene_prompt)
_save_to_content_history(..., video_url=video_url, video_status=READY)
```

### 5.2: Replace ScriptGenerationService with ScenePromptService

**Before:**
```python
script_svc = ScriptGenerationService(supabase)
script, gen_cost = script_svc.generate_script(...)
embedding, embed_cost = embedding_svc.generate(topic_summary)
```

**After:**
```python
scene_svc = ScenePromptService(supabase)
seasonal_svc = SeasonalCalendarService(supabase)
theme_context = seasonal_svc.get_theme_context()
scene_prompt, gen_cost = scene_svc.generate_scene_prompt(seasonal_context=theme_context)
detected_mood, _ = scene_svc.extract_mood_from_prompt(scene_prompt)
embedding, embed_cost = embedding_svc.generate(scene_prompt)  # Full prompt, not topic summary
```

### 5.3: Add Music Selection Step

```python
music_svc = MusicSelectionService(supabase)
music_url = music_svc.pick_music_by_mood(detected_mood)

audio_svc = AudioProcessingService()
processed_bytes = audio_svc.process_video_audio(video_url=video_url, music_url=music_url)
```

### 5.4: Update content_history Saving

**Before:**
```python
_save_to_content_history(
    supabase, script, topic_summary, embedding, mood,
    heygen_job_id=heygen_job_id, background_url=background_url,
)
```

**After:**
```python
_save_to_content_history(
    supabase,
    scene_prompt=scene_prompt,
    embedding=embedding,
    mood_profile=mood,  # Still tracking mood profile
    video_url=video_url,
    video_status=VideoStatus.READY,
    video_mood=detected_mood,
    music_url=music_url,
    runway_task_id=...,  # Optional: from RunwayVideoService
    generation_provider='runway',
)
```

### 5.5: Update _save_to_content_history()

```python
def _save_to_content_history(
    supabase,
    scene_prompt: str,
    embedding: list[float],
    mood_profile: dict,
    video_url: str,
    video_status: str,
    video_mood: str | None = None,
    music_url: str | None = None,
    runway_task_id: str | None = None,
) -> str | None:
    """Save generated cat video content to content_history."""
    row = {
        "scene_prompt": scene_prompt,
        "embedding": embedding,
        "video_url": video_url,
        "video_status": video_status,
        "video_mood": video_mood,
        "music_url": music_url,
        "runway_task_id": runway_task_id,
        "generation_provider": "runway",
    }
    result = supabase.table("content_history").insert(row).execute()
    return result.data[0]["id"] if result.data else None
```

### 5.6: Remove HeyGen References
- [ ] Remove `from app.services.heygen import HeyGenService`
- [ ] Remove `register_video_poller()` call
- [ ] Remove `pick_background_url()` call (no backgrounds for Runway)
- [ ] Keep webhook handler (may be used by other integrations, or deprecate in separate PR)

### 5.7: Update VideoStatus Enum
- [ ] Keep: READY, FAILED, APPROVAL_TIMEOUT
- [ ] Remove: PENDING_RENDER, PENDING_RENDER_RETRY, RENDERING, PROCESSING
- [ ] Reasoning: Runway polling is synchronous; no intermediate states needed

**Dependency:** Phases 1-4 must be complete. Schema migrated, services implemented, Runway service tested.

---

## Phase 6: Integration Testing (2 days)

### 6.1: Unit Tests
- [ ] Test `ScenePromptService.generate_scene_prompt()` with mocked Claude
- [ ] Test `_extract_mood_from_prompt()` with 20+ sample prompts
- [ ] Test `SeasonalCalendarService.get_theme_context()` with date range test cases
- [ ] Test `MusicSelectionService.pick_music_by_mood()` with all moods
- [ ] Test `RunwayVideoService._poll_until_ready()` with mocked HTTP responses

### 6.2: Integration Tests
- [ ] End-to-end daily_pipeline_job() with mocked Runway API
- [ ] Verify scene prompt → mood extraction → music selection flow
- [ ] Verify content_history row saved with all new columns
- [ ] Verify Telegram approval message sent with cat video URL

### 6.3: Load Tests
- [ ] Runway API rate limits: submit 5 videos concurrently, verify queuing
- [ ] Music pool: 100 picks by mood, verify distribution
- [ ] Scene category pool: 100 prompts, verify category diversity

### 6.4: Staging Environment
- [ ] Deploy v2.0 code to staging
- [ ] Run daily_pipeline_job() 3 times, verify 3 cat videos generated
- [ ] Approve/reject videos via Telegram, verify publishing flow
- [ ] Check Supabase Storage URLs are stable (not HeyGen signed URLs)

### 6.5: Backward Compatibility Test
- [ ] Verify v1.0 HeyGen content still queryable (heygen_job_id is not null)
- [ ] Verify v2.0 cat content queryable (runway_task_id is not null)
- [ ] Verify platform publishing works for both v1.0 and v2.0 content

**Dependency:** Phase 5 (integration must be complete)

---

## Integration Checkpoints

### Checkpoint 1: Schema Ready (End of Phase 1)
- [x] Migration file created and tested
- [x] All 4 new tables created with indexes
- [x] 5 new columns added to content_history
- [x] Data seeded from YAML files
- **Blocker?** No. Schema can be created without code changes.

### Checkpoint 2: Services Ready (End of Phase 2)
- [x] ScenePromptService generates prompts
- [x] Mood extraction working
- [x] SeasonalCalendarService returns themes
- [x] MusicSelectionService picks tracks
- **Blocker?** No. Services can be tested independently.

### Checkpoint 3: Video Service Ready (End of Phase 3)
- [x] RunwayVideoService submits and polls
- [x] Timeout handling working
- [x] Error handling tested
- **Blocker?** YES. Pipeline integration depends on this.

### Checkpoint 4: Pipeline Ready (End of Phase 5)
- [x] daily_pipeline_job() refactored to use Runway
- [x] HeyGen references removed
- [x] content_history saves all required columns
- [x] Telegram approval sends cat video URL
- **Blocker?** YES. This is the core integration point.

### Checkpoint 5: Tests Pass (End of Phase 6)
- [x] Unit tests: all services
- [x] Integration tests: end-to-end pipeline
- [x] Load tests: Runway API, music pool
- [x] Staging environment: 3 successful full runs
- **Blocker?** YES. Required before production launch.

---

## Rollback Plan

If v2.0 fails in production:

1. **Immediate rollback:** Deploy v1.0 code (HeyGen-based)
2. **Database:** v2.0 schema additions are backward compatible; no data loss
3. **Content:** v1.0 HeyGen videos unaffected; v2.0 cat videos can be cleaned up or kept as archive
4. **APScheduler:** Revert daily_pipeline_job() to call HeyGenService; re-register HeyGen pollers

**Time to rollback:** ~5 minutes (redeploy v1.0 code, restart APScheduler jobs)

---

## Risk Mitigation Strategies

### Risk: Runway API Unreliable or Too Slow

**Mitigation:**
- Set 10-minute timeout as hard limit
- Alert creator if timeout occurs (don't silently fail)
- Provide Telegram option to retry or skip day
- Monitor API response times in production (add observability)
- Keep HeyGen service code available for fallback (future feature)

### Risk: Mood Extraction Inaccurate

**Mitigation:**
- Default to 'peaceful' (safest mood for ambiguous content)
- Sample 5% of daily videos for manual mood review
- Creator can override music selection via Telegram (future feature)
- Expand keyword dict based on real prompts from staging

### Risk: Scene Repetition (Similarity Check)

**Mitigation:**
- Diversify scene category pool (10+ per type)
- Keep embedding similarity threshold at 0.85 (from v1.0)
- Alert creator if all 3 retry attempts exhausted
- Creator can manually approve similar scene (future feature)

### Risk: APScheduler Thread Pool Saturation

**Mitigation:**
- ThreadPoolExecutor with 4 workers (default)
- One blocking Runway poll per day is acceptable
- Monitor thread pool queue depth in production
- If needed, increase workers to 6 (but adds complexity)

---

## Success Criteria

1. **Cat video generates daily** without creator intervention
2. **Runway API polling** completes in <600 seconds (10 minutes) with <2% timeout rate
3. **Music mood matching** works (playful scenes get playful music, verified by sampling)
4. **Seasonal themes inject** correctly on themed dates (verified on Aug 8, Sep 16, Nov 1-2, Nov 20)
5. **Schema backward compatible** — v1.0 HeyGen content still queryable
6. **Telegram approval flow unchanged** — creator approves/rejects same as before
7. **Publishing works** for both v1.0 and v2.0 content

---

## Timeline Estimate

- Phase 1 (Schema): 1 day
- Phase 2 (Services): 1-2 days
- Phase 3 (Video Service): 2-3 days
- Phase 4 (Audio): 1 day
- Phase 5 (Integration): 1-2 days
- Phase 6 (Testing): 2 days

**Total: 8-11 days** (including buffer for debugging and fixes)

**Recommended:** 2-week sprint (14 days) with 3-day buffer for unknown issues.
