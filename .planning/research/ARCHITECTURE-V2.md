# Architecture: AI Cat Video Generation Pipeline v2.0

**Project:** Autonomous Content Machine — Mexican Cat Content
**Milestone:** v2.0 (Replace HeyGen with AI cat video generation)
**Researched:** 2026-03-19
**Focus:** Integration architecture for AI cat video pipeline replacement
**Confidence:** MEDIUM-HIGH (API patterns verified via official docs; polling pattern validated in research)

---

## Executive Summary

v2.0 replaces HeyGen avatar video generation with AI-generated cat video generation while keeping the FastAPI + APScheduler + Telegram approval flow intact. The architecture change is **scoped narrowly: swap the video generation provider** while reusing script generation infrastructure with minor modifications.

### Key Architecture Decisions

1. **Scene Prompt Generation**: Replaces `ScriptGenerationService` output (90-word philosophical scripts) with **curated scene prompts** (~50 words). Claude generates within guardrails (location, activity, mood categories).

2. **Video API Integration**: Runway Gen-4 (async polling job queue) integrates with APScheduler's ThreadPoolExecutor via **blocking wrapper** — no async context needed. Polling happens **inside** the daily job (synchronous).

3. **Scene Category Library**: **Database table** (`scene_categories`) with hierarchical structure (location, activity, mood, lighting). YAML config file provides defaults; Python constants only for enum-like statuses.

4. **Seasonal Calendar**: **Simple lookup table** (`seasonal_events`) mapping date ranges to themed context. Service does `date >= start_date AND date < end_date` lookup on pipeline startup.

5. **Music Selection**: **Pre-curated pool** (same as HeyGen flow) with **mood tagging per video**. Music service picks from pool matching generated video's mood.

6. **DB Schema**: New tables (`scene_categories`, `seasonal_events`, `music_tracks`, `video_generation_jobs`). Modified `content_history` adds 5 new columns. No rewrites to existing schema.

---

## Detailed Answers: 6 Architectural Questions

### Q1: How does scene prompt generation replace ScriptGenerationService?

**Current (v1.0):** `ScriptGenerationService.generate_script()` → 90-word philosophical narrative in Spanish.

**v2.0 Approach:** Two-layer prompt generation:

#### Layer 1: Scene Prompt Generation (Replaces Script Generation)

New service: `ScenePromptService` — generates visual descriptions instead of narrative scripts.

**Key difference:**

| Aspect | ScriptGenerationService | ScenePromptService |
|--------|------------------------|-------------------|
| Output type | Philosophical script (90 words) | Scene description (40-60 words) |
| Content | Abstract ideas, 6-pillar framework | Visual elements, cat actions, mood |
| Model | claude-haiku (long context) | claude-haiku (compact, same model) |
| Embedding | Topic summary embedded for similarity check | Entire scene prompt embedded |
| Cost tracking | Tracked per attempt (3 max) | Same cost tracking |

**Implementation pattern:**

```python
class ScenePromptService:
    """
    Generates scene prompts for AI cat video generation.
    Replaces ScriptGenerationService for cat content (NOT philosophical content).
    """

    def __init__(self, supabase: Client) -> None:
        self._supabase = supabase
        self._client = Anthropic(api_key=get_settings().anthropic_api_key)

    def generate_scene_prompt(
        self,
        seasonal_context: str = "",  # e.g., "International Cat Day (Aug 8)"
        attempt: int = 0,            # for retry diversity
        rejection_constraints: list[dict] | None = None,
    ) -> tuple[str, float]:
        """
        Generate a scene prompt (~50 words) for AI video generation.

        Output format:
            "A fluffy orange tabby cat in a sunny bedroom, playing with a feather toy,
             energetic and playful mood, soft golden light through window"

        Returns: (scene_prompt, cost_usd)
        """
        # Load curated categories (location, activity, mood, lighting)
        categories = self._load_scene_categories()

        # Build prompt within guardrails
        system = (
            "Eres un artista de videos que describe escenas de gatos adorables. "
            "Devuelve SOLO una descripcion viva de una escena (40-60 palabras) sin explicaciones extra. "
            "Incluye: ubicacion, actividad del gato, estado de animo, iluminacion."
        )

        retry_instruction = ""
        if attempt == 1:
            retry_instruction = (
                "IMPORTANTE: Este es un segundo intento. Elige UNA DIFERENTE ubicacion y actividad."
            )
        elif attempt >= 2:
            retry_instruction = (
                "IMPORTANTE: Este es el tercer intento. Crea una escena COMPLETAMENTE diferente."
            )

        user = (
            f"Crea una escena nueva de un gato adorable usando estas categorias:\n"
            f"Ubicaciones: {', '.join(categories['locations'])}\n"
            f"Actividades: {', '.join(categories['activities'])}\n"
            f"Estados de animo: {', '.join(categories['moods'])}\n"
            f"Iluminacion: {', '.join(categories['lighting'])}\n"
            f"{f'Contexto estacional: {seasonal_context}' if seasonal_context else ''}\n"
            f"{retry_instruction}"
        )

        return self._call_claude(system, user, max_tokens=100)
```

**Integration into daily_pipeline_job:**

```python
# Current (v1.0):
script, gen_cost = script_svc.generate_script(topic_summary, mood, target_words)

# v2.0:
scene_prompt, gen_cost = scene_svc.generate_scene_prompt(seasonal_context, attempt)
```

#### Why Replace Rather Than Extend?

- **Different output**: Philosophical scripts → visual descriptions
- **Different embedding**: Scene as a whole (not topic summary) for similarity checking
- **Different downstream**: AI video API (not HeyGen avatar)
- **Different constraints**: Category guardrails (not 6-pillar framework)

---

### Q2: How does the new AI video API integrate with APScheduler ThreadPoolExecutor (sync vs async)?

**Current (HeyGen):** Synchronous `requests.post()` in ThreadPoolExecutor, then separate webhook/poller for completion.

**v2.0 (Runway Gen-4):** **Synchronous polling wrapper** — submit and poll inside the daily job (no webhooks, no separate poller).

#### Architecture Decision: Sync Wrapper, Not Async

APScheduler's ThreadPoolExecutor runs **synchronous** job functions. Runway's API uses async polling pattern, but we integrate it synchronously:

```python
class RunwayVideoService:
    """
    Synchronous wrapper around Runway Gen-4 API.
    Handles job submission → polling → result retrieval.
    Runs in APScheduler ThreadPoolExecutor (NOT async context).

    Uses httpx.Client (sync), NOT httpx.AsyncClient.
    Polling blocks until complete (acceptable in daily job).
    """

    def __init__(self) -> None:
        self._settings = get_settings()
        # Synchronous client for ThreadPoolExecutor context
        self._http = httpx.Client(
            headers={"Authorization": f"Bearer {self._settings.runway_api_key}"},
            timeout=30.0
        )

    def submit_and_poll(
        self,
        scene_prompt: str,
        max_wait_seconds: int = 600,  # 10 min timeout
    ) -> str:
        """
        Submit video generation to Runway and poll until complete.

        Blocking call (OK in ThreadPoolExecutor context).
        Returns stable video URL when ready.

        DO NOT use in async context (telegram handlers, FastAPI endpoints).
        """
        # Step 1: POST submission
        task_id = self._submit_generation(scene_prompt)

        # Step 2: Poll with exponential backoff
        video_url = self._poll_until_ready(task_id, max_wait_seconds)

        return video_url

    def _submit_generation(self, scene_prompt: str) -> str:
        """POST generation request, return task_id."""
        payload = {
            "input_prompt": scene_prompt,
            "duration": 24,           # 24 seconds (within 15-60s range)
            "aspect_ratio": "9:16",   # vertical for mobile
        }

        response = self._http.post(
            "https://api.runwayml.com/v1/generations",
            json=payload
        )
        response.raise_for_status()
        return response.json()["id"]

    def _poll_until_ready(
        self,
        task_id: str,
        max_wait_seconds: int
    ) -> str:
        """
        Poll task status with exponential backoff.
        Returns video URL when status == 'succeeded'.
        Raises RuntimeError if failed or timeout.
        """
        import time

        start = time.time()
        backoff = 2.0

        while time.time() - start < max_wait_seconds:
            response = self._http.get(
                f"https://api.runwayml.com/v1/tasks/{task_id}"
            )
            response.raise_for_status()

            data = response.json()
            status = data.get("status")

            if status == "succeeded":
                return data["output"][0]["url"]  # stable URL
            elif status == "failed":
                raise RuntimeError(
                    f"Runway generation failed: {data.get('failure_reason')}"
                )

            # Not ready — backoff and retry
            time.sleep(backoff)
            backoff = min(backoff * 1.5, 30.0)  # max 30s between polls

        raise TimeoutError(
            f"Runway generation timeout after {max_wait_seconds}s"
        )
```

#### Integration into daily_pipeline_job

Replace HeyGen submission with Runway:

```python
# In daily_pipeline_job() — replace HeyGen step:

from app.services.runway import RunwayVideoService

runway_svc = RunwayVideoService()

try:
    # scene_prompt replaces script_text
    video_url = runway_svc.submit_and_poll(
        scene_prompt=scene_prompt,
        max_wait_seconds=600  # 10 min timeout
    )

    # Video is already ready (polling completed)
    # No need for separate webhook/poller
    _save_to_content_history(
        supabase,
        scene_prompt=scene_prompt,
        video_url=video_url,
        video_status=VideoStatus.READY,  # Skip pending_render states
    )

except TimeoutError as e:
    plog.error("Runway timeout: %s", e)
    send_alert_sync("Runway video generation timeout. Revisa o rechaza para reintentar.")
    return
except Exception as e:
    plog.error("Runway submission failed: %s", e)
    send_alert_sync(f"Error en Runway: {e}")
    return
```

#### Why Sync Wrapper, Not Async?

| Approach | Pros | Cons |
|----------|------|------|
| **Sync polling (chosen)** | Simple, ThreadPoolExecutor native, no event loop conflicts | Blocks job thread for 30-120s |
| **Async submission + poller** | Non-blocking, scales better | Adds async/sync complexity, requires separate job |

**Decision rationale:**

- Runway Gen-4 typically completes in **30-60 seconds** (acceptable blocking time)
- ThreadPoolExecutor has **4 workers** (one job blocking is OK; multiple jobs can run)
- Simpler state machine: no `pending_render → rendering → processing` states
- Avoids mixing asyncio event loop (FastAPI) with threading pool (APScheduler)

---

### Q3: How should the curated scene category library be stored?

**Answer: Database table + YAML config seeding + Python enums for types only.**

#### Database Table: `scene_categories`

```sql
CREATE TABLE IF NOT EXISTS scene_categories (
    id              uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    category_type   text NOT NULL CHECK (category_type IN (
        'location',      -- where the cat is
        'activity',      -- what the cat is doing
        'mood',          -- emotional tone of scene
        'lighting'       -- time of day / light quality
    )),
    category_name   text NOT NULL,
    display_name    text,           -- human-readable label
    description     text,           -- for generation prompts
    is_active       boolean DEFAULT true,
    sort_order      integer DEFAULT 0,
    created_at      timestamptz DEFAULT now(),
    UNIQUE (category_type, category_name)
);

CREATE INDEX scene_categories_type_active
    ON scene_categories(category_type, is_active);
```

#### Seeding: YAML Config File

Store defaults in `config/scene_categories.yaml`:

```yaml
# config/scene_categories.yaml
# Seed data for scene_categories table (loaded on startup)

locations:
  - name: "sunny_bedroom"
    display: "Sunny Bedroom"
    description: "Bright bedroom with sunlight through window"
  - name: "kitchen"
    display: "Kitchen"
    description: "Cozy kitchen with warm lighting"
  - name: "garden"
    display: "Garden"
    description: "Outdoor garden with natural elements"
  - name: "living_room"
    display: "Living Room"
    description: "Comfortable living area with furniture"

activities:
  - name: "playing_toy"
    display: "Playing with Toy"
    description: "Pouncing and playing with a toy"
  - name: "sleeping"
    display: "Sleeping"
    description: "Peacefully napping"
  - name: "stretching"
    display: "Stretching"
    description: "Stretching and yawning"

moods:
  - name: "playful"
    display: "Playful"
    description: "Energetic and joyful"
  - name: "peaceful"
    display: "Peaceful"
    description: "Calm and serene"
  - name: "curious"
    display: "Curious"
    description: "Inquisitive and alert"

lighting:
  - name: "golden_hour"
    display: "Golden Hour"
    description: "Warm, soft light from sunset/sunrise"
  - name: "bright_sunny"
    display: "Bright Sunny"
    description: "Direct sunlight, high contrast"
  - name: "soft_indoor"
    display: "Soft Indoor"
    description: "Warm artificial lighting"
```

#### Service Layer: `SceneCategoryService`

```python
class SceneCategoryService:
    """
    Loads and caches scene categories from database.
    Provides hierarchical access for prompt generation.
    """

    def __init__(self, supabase: Client) -> None:
        self._supabase = supabase
        self._cache = None
        self._cache_loaded_at = None

    def get_all_categories(self) -> dict[str, list[str]]:
        """
        Returns:
        {
            'locations': ['sunny_bedroom', 'kitchen', ...],
            'activities': ['playing_toy', 'sleeping', ...],
            'moods': ['playful', 'peaceful', ...],
            'lighting': ['golden_hour', 'bright_sunny', ...]
        }
        """
        import time

        # Cache for 1 hour
        if self._cache and (time.time() - self._cache_loaded_at) < 3600:
            return self._cache

        result = self._supabase.table("scene_categories").select(
            "category_type, category_name"
        ).eq("is_active", True).order("sort_order").execute()

        categories = {
            'locations': [],
            'activities': [],
            'moods': [],
            'lighting': []
        }

        for row in result.data:
            cat_type = row['category_type']
            if cat_type in categories:
                categories[cat_type].append(row['category_name'])

        self._cache = categories
        self._cache_loaded_at = time.time()
        return categories

    def seed_from_yaml(self, yaml_path: str) -> None:
        """
        Load categories from YAML file and upsert into DB.
        Called once at deployment time (idempotent).
        """
        import yaml

        with open(yaml_path) as f:
            config = yaml.safe_load(f)

        # Upsert categories
        for cat_type_plural, items in config.items():
            cat_type = cat_type_plural.rstrip('s')  # 'locations' → 'location'
            for i, item in enumerate(items):
                self._supabase.table("scene_categories").upsert({
                    "category_type": cat_type,
                    "category_name": item['name'],
                    "display_name": item.get('display', item['name']),
                    "description": item.get('description', ''),
                    "sort_order": i,
                    "is_active": True
                }).execute()
```

#### Python Constants: ONLY for Type Enums

Use Python constants **only** for immutable, compile-time types:

```python
# app/models/scene.py

class SceneCategoryType(str, Enum):
    """Fixed category types — never change."""
    LOCATION = "location"
    ACTIVITY = "activity"
    MOOD = "mood"
    LIGHTING = "lighting"

# NOT a constant table:
# LOCATIONS = ["sunny_bedroom", "kitchen", ...]  # ← DON'T DO THIS
# These come from DB, loaded via SceneCategoryService
```

#### Why This Hybrid?

| Storage | Use | Rationale |
|---------|-----|-----------|
| **DB table** | Available categories | Easy to add/disable without redeploy. Queryable. |
| **YAML config** | Default library | Version-controlled, human-readable, deployed with code. |
| **Python enums** | Type constants | Immutable, validated at parse time. |

---

### Q4: How should the seasonal calendar service work?

**Answer: Simple lookup table + date range matching (month-day only).**

#### Database Table: `seasonal_events`

```sql
CREATE TABLE IF NOT EXISTS seasonal_events (
    id              uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    event_name      text NOT NULL,
    description     text,
    start_date      date NOT NULL,  -- MM-DD format (year-independent)
    end_date        date NOT NULL,  -- Inclusive end
    theme_context   text NOT NULL,  -- Prompt injection for scene generation
    is_active       boolean DEFAULT true,
    created_at      timestamptz DEFAULT now()
);

CREATE INDEX seasonal_events_date_range
    ON seasonal_events(start_date, end_date);
```

#### Seeding: YAML Config

```yaml
# config/seasonal_events.yaml

- event_name: "international_cat_day"
  start_date: "08-08"
  end_date: "08-08"
  theme_context: "International Cat Day — emphasize adorable, celebratory mood. Add confetti, party atmosphere."

- event_name: "mexican_independence"
  start_date: "09-16"
  end_date: "09-16"
  theme_context: "Mexican Independence Day — incorporate patriotic colors or Mexican settings."

- event_name: "day_of_dead"
  start_date: "11-01"
  end_date: "11-02"
  theme_context: "Day of the Dead season — warm, nostalgic, golden lighting. Hint at celebration and remembrance."

- event_name: "mexican_revolution"
  start_date: "11-20"
  end_date: "11-20"
  theme_context: "Mexican Revolution Day — reflective, historical mood."
```

#### Service: `SeasonalCalendarService`

```python
class SeasonalCalendarService:
    """
    Retrieves seasonal theme context for today's generation.
    Returns theme injection string for scene prompt.
    """

    def __init__(self, supabase: Client) -> None:
        self._supabase = supabase
        self._cache = None
        self._cache_date = None

    def get_theme_context(self, check_date: date | None = None) -> str:
        """
        Get theme context for a given date (default: today).

        Returns:
            Theme context string if matching seasonal event, else empty string.
        """
        from datetime import date

        check_date = check_date or date.today()

        # Reload cache daily
        if self._cache_date != check_date:
            month_day = check_date.strftime("%m-%d")  # "08-08", "09-16", etc.

            result = self._supabase.table("seasonal_events").select(
                "event_name, theme_context"
            ).eq("is_active", True).gte("start_date", month_day).lte(
                "end_date", month_day
            ).execute()

            if result.data:
                # Return first match (or join multiple if multiple events same day)
                self._cache = result.data[0]['theme_context']
            else:
                self._cache = ""

            self._cache_date = check_date

        return self._cache
```

#### Integration: Scene Prompt Generation

```python
class ScenePromptService:
    def generate_scene_prompt(
        self,
        attempt: int = 0,
        rejection_constraints: list[dict] | None = None,
    ) -> tuple[str, float]:
        # Get seasonal context
        seasonal_svc = SeasonalCalendarService(self._supabase)
        theme_context = seasonal_svc.get_theme_context()

        user_prompt = (
            f"Crea una escena nueva de un gato adorable...\n"
            f"{f'Contexto estacional: {theme_context}' if theme_context else 'No hay tema estacional hoy.'}"
        )

        return self._call_claude(system, user_prompt, max_tokens=100)
```

#### Why Month-Day Only?

- **No year dependency**: Same holiday every year (08-08 is always Aug 8)
- **Avoids leap year logic**: YYYY-MM-DD would require handling Feb 29
- **Simple range matching**: `start_date <= today_month_day <= end_date`
- **Easy manual adjustment**: Edit `start_date`/`end_date` without code logic

---

### Q5: How should music selection work?

**Answer: Pre-curated pool + mood tagging + heuristic or Claude classification.**

#### Reuse Existing HeyGen Pool

Keep the existing HeyGen music pool (comma-separated URLs in settings). Add metadata layer.

#### Database Table: `music_tracks`

```sql
CREATE TABLE IF NOT EXISTS music_tracks (
    id              uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    url             text NOT NULL UNIQUE,
    title           text,
    mood            text NOT NULL CHECK (mood IN (
        'playful',
        'peaceful',
        'energetic',
        'mysterious',
        'melancholic'
    )),
    duration_sec    integer,
    is_active       boolean DEFAULT true,
    created_at      timestamptz DEFAULT now()
);

CREATE INDEX music_tracks_mood_active
    ON music_tracks(mood, is_active);
```

#### Seeding: Config + Manual Tagging

```yaml
# config/music_tracks.yaml

- url: "https://bucket/ambient-1.mp3"
  title: "Peaceful Piano"
  mood: "peaceful"
  duration_sec: 45

- url: "https://bucket/playful-2.mp3"
  title: "Cheerful Strings"
  mood: "playful"
  duration_sec: 60

- url: "https://bucket/mysterious-3.mp3"
  title: "Ambient Synth"
  mood: "mysterious"
  duration_sec: 52
```

#### Extract Mood from Scene Prompt

```python
class ScenePromptService:
    def generate_scene_prompt_with_mood(
        self, ...
    ) -> tuple[str, str, float]:
        """
        Generate scene prompt AND extract mood from response.

        Returns: (scene_prompt, mood, cost_usd)
        """
        scene_prompt, cost = self.generate_scene_prompt(...)

        # Extract mood from prompt
        mood = self._extract_mood_from_prompt(scene_prompt)

        return scene_prompt, mood, cost

    def _extract_mood_from_prompt(self, prompt: str) -> str:
        """
        Heuristic: look for mood keywords in the prompt.
        'playful', 'peaceful', 'curious', 'energetic', 'mysterious'
        """
        mood_keywords = {
            'playful': ['playful', 'jugueton', 'energetic', 'dinamico'],
            'peaceful': ['peaceful', 'sereno', 'calm', 'tranquilo', 'dormir'],
            'curious': ['curious', 'curioso', 'alert', 'atento'],
            'mysterious': ['mysterious', 'misterioso', 'intrigued'],
            'melancholic': ['melancholic', 'triste', 'nostalgic'],
        }

        prompt_lower = prompt.lower()
        for mood, keywords in mood_keywords.items():
            if any(kw in prompt_lower for kw in keywords):
                return mood

        return 'peaceful'  # safe default
```

#### Service: `MusicSelectionService`

```python
class MusicSelectionService:
    """
    Selects background music matching generated video mood.
    """

    def __init__(self, supabase: Client) -> None:
        self._supabase = supabase
        self._mood_cache = {}

    def pick_music_by_mood(self, video_mood: str) -> str:
        """
        Select a random track matching the video mood.
        Falls back to full pool if no mood-specific tracks.

        Args:
            video_mood: One of 'playful', 'peaceful', 'energetic', etc.

        Returns:
            URL of selected music track.
        """
        # Load mood-keyed cache
        if video_mood not in self._mood_cache:
            result = self._supabase.table("music_tracks").select("url").eq(
                "mood", video_mood
            ).eq("is_active", True).execute()

            self._mood_cache[video_mood] = [
                row['url'] for row in result.data
            ]

        tracks = self._mood_cache[video_mood]

        if not tracks:
            # Fallback: return random from full active pool
            result = self._supabase.table("music_tracks").select("url").eq(
                "is_active", True
            ).execute()
            tracks = [row['url'] for row in result.data]

        if not tracks:
            raise ValueError("No active music tracks configured")

        return random.choice(tracks)
```

#### Integration: daily_pipeline_job

```python
# In daily_pipeline_job():

scene_prompt, detected_mood, scene_cost = scene_svc.generate_scene_prompt_with_mood()

# Later, when processing audio:
music_svc = MusicSelectionService(supabase)
music_url = music_svc.pick_music_by_mood(detected_mood)

audio_svc = AudioProcessingService()
processed_bytes = audio_svc.process_video_audio(
    video_url=video_url,
    music_url=music_url
)
```

---

### Q6: What DB schema changes are needed?

**Answer: 4 new tables + 5 new columns on `content_history`.**

#### New Tables

##### 1. `scene_categories` (from Q3)

```sql
CREATE TABLE IF NOT EXISTS scene_categories (
    id              uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    category_type   text NOT NULL CHECK (category_type IN (
        'location', 'activity', 'mood', 'lighting'
    )),
    category_name   text NOT NULL,
    display_name    text,
    description     text,
    is_active       boolean DEFAULT true,
    sort_order      integer DEFAULT 0,
    created_at      timestamptz DEFAULT now(),
    UNIQUE (category_type, category_name)
);

CREATE INDEX scene_categories_type_active ON scene_categories(category_type, is_active);
```

##### 2. `seasonal_events` (from Q4)

```sql
CREATE TABLE IF NOT EXISTS seasonal_events (
    id              uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    event_name      text NOT NULL,
    description     text,
    start_date      date NOT NULL,
    end_date        date NOT NULL,
    theme_context   text NOT NULL,
    is_active       boolean DEFAULT true,
    created_at      timestamptz DEFAULT now()
);

CREATE INDEX seasonal_events_date_range ON seasonal_events(start_date, end_date);
```

##### 3. `music_tracks` (from Q5)

```sql
CREATE TABLE IF NOT EXISTS music_tracks (
    id              uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    url             text NOT NULL UNIQUE,
    title           text,
    mood            text NOT NULL CHECK (mood IN (
        'playful', 'peaceful', 'energetic', 'mysterious', 'melancholic'
    )),
    duration_sec    integer,
    is_active       boolean DEFAULT true,
    created_at      timestamptz DEFAULT now()
);

CREATE INDEX music_tracks_mood_active ON music_tracks(mood, is_active);
```

##### 4. `video_generation_jobs`

```sql
CREATE TABLE IF NOT EXISTS video_generation_jobs (
    id              uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    content_history_id  uuid NOT NULL REFERENCES content_history(id) ON DELETE CASCADE,
    provider        text NOT NULL CHECK (provider = 'runway'),
    runway_task_id  text,
    status          text NOT NULL CHECK (status IN (
        'queued', 'processing', 'succeeded', 'failed'
    )),
    error_message   text,
    submitted_at    timestamptz DEFAULT now(),
    completed_at    timestamptz,
    UNIQUE (runway_task_id)
);

CREATE INDEX video_generation_jobs_task_id ON video_generation_jobs(runway_task_id);
CREATE INDEX video_generation_jobs_content_id ON video_generation_jobs(content_history_id);
```

#### Modified `content_history` Columns

Add **5 new columns** to existing `content_history`:

```sql
ALTER TABLE content_history ADD COLUMN IF NOT EXISTS
    scene_prompt        text,           -- replaces script_text for cat videos
    video_mood          text CHECK (video_mood IN (
        'playful', 'peaceful', 'energetic', 'mysterious', 'melancholic'
    )),
    music_url           text,           -- which track was selected
    runway_task_id      text UNIQUE,    -- references video_generation_jobs
    generation_provider text DEFAULT 'runway' CHECK (
        generation_provider IN ('runway', 'pika', 'kling')
    );
```

#### Complete Migration File

```sql
-- migrations/0008_cat_video_schema.sql
-- Adds scene categories, seasonal events, music tracks, and video generation job tracking

CREATE TABLE IF NOT EXISTS scene_categories (
    id              uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    category_type   text NOT NULL CHECK (category_type IN (
        'location', 'activity', 'mood', 'lighting'
    )),
    category_name   text NOT NULL,
    display_name    text,
    description     text,
    is_active       boolean DEFAULT true,
    sort_order      integer DEFAULT 0,
    created_at      timestamptz DEFAULT now(),
    UNIQUE (category_type, category_name)
);

CREATE INDEX scene_categories_type_active ON scene_categories(category_type, is_active);

CREATE TABLE IF NOT EXISTS seasonal_events (
    id              uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    event_name      text NOT NULL,
    description     text,
    start_date      date NOT NULL,
    end_date        date NOT NULL,
    theme_context   text NOT NULL,
    is_active       boolean DEFAULT true,
    created_at      timestamptz DEFAULT now()
);

CREATE INDEX seasonal_events_date_range ON seasonal_events(start_date, end_date);

CREATE TABLE IF NOT EXISTS music_tracks (
    id              uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    url             text NOT NULL UNIQUE,
    title           text,
    mood            text NOT NULL CHECK (mood IN (
        'playful', 'peaceful', 'energetic', 'mysterious', 'melancholic'
    )),
    duration_sec    integer,
    is_active       boolean DEFAULT true,
    created_at      timestamptz DEFAULT now()
);

CREATE INDEX music_tracks_mood_active ON music_tracks(mood, is_active);

CREATE TABLE IF NOT EXISTS video_generation_jobs (
    id              uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    content_history_id  uuid NOT NULL REFERENCES content_history(id) ON DELETE CASCADE,
    provider        text NOT NULL CHECK (provider = 'runway'),
    runway_task_id  text,
    status          text NOT NULL CHECK (status IN (
        'queued', 'processing', 'succeeded', 'failed'
    )),
    error_message   text,
    submitted_at    timestamptz DEFAULT now(),
    completed_at    timestamptz,
    UNIQUE (runway_task_id)
);

CREATE INDEX video_generation_jobs_task_id ON video_generation_jobs(runway_task_id);
CREATE INDEX video_generation_jobs_content_id ON video_generation_jobs(content_history_id);

ALTER TABLE content_history ADD COLUMN IF NOT EXISTS scene_prompt text;
ALTER TABLE content_history ADD COLUMN IF NOT EXISTS video_mood text
    CHECK (video_mood IS NULL OR video_mood IN (
        'playful', 'peaceful', 'energetic', 'mysterious', 'melancholic'
    ));
ALTER TABLE content_history ADD COLUMN IF NOT EXISTS music_url text;
ALTER TABLE content_history ADD COLUMN IF NOT EXISTS runway_task_id text;
ALTER TABLE content_history ADD COLUMN IF NOT EXISTS generation_provider text DEFAULT 'runway'
    CHECK (generation_provider IN ('runway', 'pika', 'kling'));
```

#### Backward Compatibility

Existing v1.0 HeyGen rows keep `script_text` and `heygen_job_id`. New v2.0 rows have `scene_prompt` and `runway_task_id`. Query appropriately:

```python
# Distinguish v1.0 (HeyGen) from v2.0 (Runway) content
heygen_content = supabase.table("content_history").select("*").is_not("heygen_job_id", "null")
cat_content = supabase.table("content_history").select("*").is_not("runway_task_id", "null")
```

---

## Complete Integration Points

### New Components (Build These First)

1. **`ScenePromptService`** — Replaces ScriptGenerationService output
2. **`RunwayVideoService`** — Submits to Runway, polls for completion
3. **`SceneCategoryService`** — Loads scene categories from DB
4. **`SeasonalCalendarService`** — Looks up seasonal themes by date
5. **`MusicSelectionService`** — Picks music by mood

### Modified Components

1. **`daily_pipeline_job()`** — Replace HeyGen submission with Runway
2. **`content_history` DB** — Add 5 new columns (scene_prompt, video_mood, music_url, runway_task_id, generation_provider)
3. **`AudioProcessingService`** — Add mood-aware music selection parameter
4. **`VideoStatus` enum** — Remove `pending_render`, `rendering`, `pending_render_retry` states (polling is synchronous)

### Unchanged Components

- FastAPI app structure
- APScheduler BackgroundScheduler + ThreadPoolExecutor
- Telegram bot approval flow
- Platform publishing services
- Analytics and metrics
- Circuit breaker and cost tracking

---

## Data Flow: v2.0 Daily Pipeline

```
daily_pipeline_job() [ThreadPoolExecutor]
    ↓
[1] Load seasonal theme → SeasonalCalendarService.get_theme_context()
    ↓
[2] Generate scene prompt → ScenePromptService.generate_scene_prompt(theme_context)
    ↓
[3] Extract mood → ScenePromptService._extract_mood_from_prompt()
    ↓
[4] Check similarity → EmbeddingService + SimilarityService (reuse from v1.0)
    ↓ [if too similar, retry 2x]
    ↓
[5] Submit to Runway + poll → RunwayVideoService.submit_and_poll(scene_prompt)
    ↓ [blocks until complete, ~30-60s]
    ↓
[6] Pick music by mood → MusicSelectionService.pick_music_by_mood(video_mood)
    ↓
[7] Process audio (EQ + mix) → AudioProcessingService.process_video_audio(video_url, music_url)
    ↓
[8] Upload to Supabase Storage → VideoStorageService.upload(processed_bytes)
    ↓
[9] Save to content_history → scene_prompt, video_url, video_mood, music_url, runway_task_id
    ↓
[10] Send Telegram approval → TelegramService.send_approval_message_sync(content_history_id)
```

**Key difference from v1.0:** No webhook or separate poller job needed. Runway polling is synchronous within the daily job.

---

## Build Order & Dependencies

### Phase 1: Database & Seeding (1 day)
- Create migration `0008_cat_video_schema.sql`
- Implement `SceneCategoryService.seed_from_yaml()`
- Implement `SeasonalCalendarService.seed_from_yaml()`
- Implement `MusicSelectionService.seed_from_yaml()`
- Verify schema creates successfully

### Phase 2: Services Foundation (1-2 days)
- Implement `ScenePromptService.generate_scene_prompt()`
- Implement `SceneCategoryService.get_all_categories()`
- Implement `SeasonalCalendarService.get_theme_context()`
- Test mood extraction logic

### Phase 3: Video Generation (2-3 days)
- Implement `RunwayVideoService` (submit + polling)
- Test submission + task_id retrieval
- Test polling with backoff
- Test timeout and failure handling

### Phase 4: Music & Audio (1 day)
- Implement `MusicSelectionService.pick_music_by_mood()`
- Update `AudioProcessingService` to accept mood_url parameter
- Integration test with actual music files

### Phase 5: Pipeline Integration (1-2 days)
- Refactor `daily_pipeline_job()` to use Runway instead of HeyGen
- Remove HeyGen service calls
- Update video status lifecycle (remove pending_render states)
- End-to-end pipeline test

### Phase 6: Testing & Hardening (2 days)
- Load testing: Runway API rate limits
- Timeout scenarios
- Mood extraction edge cases
- Music fallback scenarios

---

## Pitfalls & Mitigations

| Pitfall | Impact | Mitigation |
|---------|--------|-----------|
| **Runway API timeout (>10min)** | Daily pipeline hangs | Set 10-min timeout. Alert creator. Fail gracefully. |
| **Mood extraction wrong** | Wrong music selected | Default to 'peaceful'. Heuristic validated by manual review. |
| **Scene category pool too small** | High repetition | Seed 10+ categories per type. Creator can add via Telegram. |
| **Seasonal events overlap** | Ambiguous theme | Return first match. Document precedence. |
| **Music URL broken** | Audio processing fails | Validate URLs weekly. Keep pool >5 per mood. Alert on missing. |
| **Content history ID mismatch** | Wrong video approved | Add foreign key constraint. Test referential integrity. |
| **Polling backoff too aggressive** | API rate limit | Start at 2s, max 30s. Monitor Runway rate limits. |
| **Scene prompt too similar to previous** | Daily pipeline retries exhaust | Keep retry count at 2 (3 total attempts). Adjust category pool diversity. |

---

## Confidence Assessment

| Area | Level | Rationale |
|------|-------|-----------|
| **Scene prompt generation** | HIGH | Claude API proven in v1.0. Only output format changes (visual vs narrative). |
| **Runway API integration** | MEDIUM-HIGH | Gen-4 documented, polling pattern standard. Untested in production. Recommend 2-week staging. |
| **DB schema** | HIGH | Straightforward additions. No existing data migration. Backward compatible. |
| **Music selection** | HIGH | Mood matching simple heuristic. Proven pattern from HeyGen flow. |
| **Seasonal calendar** | HIGH | Date lookup trivial. Data-driven via config. |
| **APScheduler sync** | HIGH | ThreadPoolExecutor + blocking calls proven in existing codebase. |

---

## Sources

- [Runway API Documentation](https://docs.dev.runwayml.com/)
- [Complete Guide to AI Video Generation APIs in 2026 | WaveSpeedAI](https://wavespeed.ai/blog/posts/complete-guide-ai-video-apis-2026/)
- [Runway Gen-4 vs Pika Comparison 2026 | is4.ai](https://is4.ai/blog/our-blog-1/runway-gen-3-vs-pika-comparison-2026-326)
- [Best Text-to-Video API in 2026 | WaveSpeedAI](https://wavespeed.ai/blog/posts/best-text-to-video-api-2026/)
- [APScheduler 3.11.2 Documentation](https://apscheduler.readthedocs.io/en/3.x/userguide.html)
- [Python calendar Module - Real Python](https://realpython.com/python-calendar-module/)
