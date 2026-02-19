# Stack Research

**Domain:** AI-automated short-form video content pipeline (solo creator)
**Researched:** 2026-02-19
**Confidence:** MEDIUM — verified against training data through Aug 2025; external API versions (HeyGen, Ayrshare) should be confirmed against live docs before implementation. Core Python ecosystem recommendations are HIGH confidence.

---

## Recommended Stack

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| Python | 3.11 | Runtime | Confirmed in project context; 3.11 offers significant performance gains over 3.10 and has stable async support; 3.12 exists but ecosystem compatibility is smoother on 3.11 for ML/AI libraries |
| FastAPI | 0.111+ | HTTP API layer, webhook receiver | Async-native, auto-generates OpenAPI docs, minimal boilerplate. Fits perfectly for HeyGen webhook callbacks and internal health endpoints. Not needed for UI (no UI). |
| python-telegram-bot | 21.x | Telegram bot framework | The de-facto standard Telegram bot library for Python. Version 21.x uses the Application/ConversationHandler pattern with full async support. Significantly cleaner than v13.x (which required synchronous handlers). |
| APScheduler | 3.10+ | Daily content generation cron | Lightweight in-process scheduler for scheduling the daily pipeline trigger. For a single-creator system, in-process scheduling is sufficient and avoids the infrastructure overhead of Celery + Redis. |
| httpx | 0.27+ | HTTP client for API calls | Async HTTP client used for HeyGen API, ElevenLabs API, Ayrshare API calls. Replaces requests in async contexts. Supports connection pooling, retries, and timeout configuration critical for video polling loops. |
| openai | 1.x | GPT-4o script generation | Official OpenAI Python SDK. Version 1.x (released late 2023) uses the new `client = OpenAI()` interface; the v0.x legacy interface is deprecated. |
| anthropic | 0.25+ | Claude 3.5 script generation | Official Anthropic SDK. Used alongside OpenAI for script generation. Supports streaming and async. |

### Database & Storage

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| Supabase Python Client | 2.x | Postgres ORM + vector search | Official `supabase-py` v2.x. Wraps PostgREST for standard CRUD and exposes pgvector for semantic similarity search. Single dependency handles both relational data and vector anti-repetition checks. |
| pgvector (via Supabase) | Latest | Concept similarity / anti-repetition | Built into Supabase. Use `vector(1536)` column for OpenAI `text-embedding-3-small` embeddings. Cosine similarity query detects >85% similar scripts. No separate vector DB (Pinecone, Weaviate) needed for this scale. |
| boto3 | 1.34+ | S3 video file storage | Official AWS SDK. Used for video lifecycle management: upload from HeyGen, serve to Telegram, apply S3 Lifecycle Rules for Hot→Warm→Cold tiering. |
| SQLAlchemy | 2.x (async) | ORM for Postgres if needed | Optional — only needed if complex SQL queries exceed PostgREST's capabilities. Supabase-py covers 95% of needs. Keep in reserve. |

### Infrastructure

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| Railway.app | Current | Deployment platform | Best fit for this stack: native Python support, environment variables managed via dashboard, persistent services (required for APScheduler to fire), built-in logging. Render is a valid alternative but Railway has better free tier for persistent workers. |
| Docker | 24+ | Container definition | Single Dockerfile defining the FastAPI + bot process. Required by Railway/Render. Enables local parity. |

### AI & Media APIs (External)

| Service | Python Integration | Purpose | Why |
|---------|--------------------|---------|-----|
| HeyGen API v2 | `httpx` (no official SDK) | Avatar video generation | HeyGen exposes a REST API. No official Python SDK as of Aug 2025; integrate directly with `httpx`. Critical pattern: initiate render → poll `/v2/video_status/{video_id}` until `completed`. Use webhook if HeyGen supports it to avoid polling loops. |
| ElevenLabs API | `elevenlabs` 1.x (official SDK) | Voice synthesis | Official Python SDK exists. Used if HeyGen voice is insufficient or for pre-generating voice audio to pass to HeyGen. Typically, HeyGen handles voice via its own voice cloning — ElevenLabs is only needed for preprocessing. |
| OpenAI Embeddings | `openai` 1.x | Generate script embeddings for anti-repetition | Use `text-embedding-3-small` model (1536 dimensions, cheap, effective). Called during script generation to check similarity before committing. |
| Ayrshare API | `httpx` (no official SDK) | Multi-platform publishing | REST API. Single POST to `/post` endpoint supports TikTok, Instagram, Facebook, YouTube simultaneously. Significantly simpler than Buffer's API for multi-platform. **Recommended over Buffer for this use case** (see Alternatives). |

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pydantic | 2.x | Data validation / settings management | Always — FastAPI uses it natively. Use `pydantic-settings` for environment variable parsing (replaces python-dotenv in typed contexts). |
| pydantic-settings | 2.x | Environment variable loading with types | Always — load all API keys, configuration, and secrets with type safety. |
| python-dotenv | 1.x | .env file loading in development | Dev only — loads `.env` file locally; in Railway use dashboard env vars directly. |
| tenacity | 8.x | Retry logic with exponential backoff | Use for HeyGen API calls (video generation can be slow), Ayrshare publishing, and any external API that can fail transiently. |
| structlog | 23.x+ | Structured JSON logging | Use over Python's built-in logging — structured logs are searchable in Railway's log dashboard. |
| pytest | 8.x | Test framework | Use for unit + integration tests. Pair with `pytest-asyncio` for testing async FastAPI endpoints and bot handlers. |
| pytest-asyncio | 0.23+ | Async test support | Required for testing async FastAPI and telegram bot code. |
| ffmpeg-python | 0.2 | Audio post-processing | Used only for dark ambient audio overlay on video. Requires `ffmpeg` binary installed in Docker image. Only if HeyGen doesn't support audio track injection. |

### Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| uv | Fast Python package manager | Use `uv` instead of `pip` for faster dependency resolution and lockfile generation. Generates `uv.lock` for reproducible builds. |
| ruff | Linter + formatter | Replaces black + flake8 + isort in one tool. Zero-config by default, significantly faster. |
| mypy | Type checking | Run in CI; FastAPI + Pydantic make most type errors catchable before runtime. |

---

## Installation

```bash
# Create virtual environment with uv
uv venv --python 3.11
source .venv/bin/activate  # or .venv\Scripts\activate on Windows

# Core dependencies
uv pip install \
  fastapi==0.111.* \
  uvicorn[standard] \
  python-telegram-bot==21.* \
  apscheduler==3.10.* \
  httpx==0.27.* \
  openai==1.* \
  anthropic==0.25.* \
  supabase==2.* \
  boto3==1.34.* \
  pydantic==2.* \
  pydantic-settings==2.* \
  python-dotenv==1.* \
  tenacity==8.* \
  structlog \
  elevenlabs==1.*

# Dev dependencies
uv pip install \
  pytest==8.* \
  pytest-asyncio==0.23.* \
  ruff \
  mypy \
  httpx  # already in core, also used in tests
```

---

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| Ayrshare | Buffer | Buffer if Ayrshare lacks TikTok native publish or hits API rate limits; Buffer's Publish API requires separate connections per platform, more complex |
| APScheduler | Celery + Redis | Celery only if scale grows to multiple workers or jobs need distributed execution; overkill for 1 video/day from a single process |
| APScheduler | Prefect / Airflow | Only if pipeline gains complex DAG dependencies with retry/backfill needs; far too heavy for this scope |
| python-telegram-bot | aiogram | aiogram 3.x is excellent for pure async bot development but has steeper learning curve and smaller community; PTB v21 is better documented for solo projects |
| python-telegram-bot | Telebot (pyTelegramBotAPI) | Telebot is simpler but synchronous by default; PTB v21 async is cleaner for a pipeline that does async I/O |
| httpx | requests | requests is synchronous; in an async FastAPI + bot context, `requests` blocks the event loop. Do not use. |
| pgvector (Supabase) | Pinecone | Pinecone adds a separate paid service for a problem pgvector solves free within Supabase; at <10K vectors (1 video/day = ~365/year), Supabase pgvector is more than sufficient |
| pgvector (Supabase) | Weaviate / Qdrant | Same reasoning as Pinecone; external vector DBs add operational complexity unjustified at this scale |
| boto3 + S3 | Supabase Storage | Supabase Storage is viable and simplifies to one service, but S3 Lifecycle Rules (Hot→Warm→Cold tiering) are more mature; use S3 if tiering is critical, Supabase Storage if simplicity is preferred |
| structlog | Python logging | Standard logging lacks structure; Railway log dashboards filter on JSON fields — structlog output is instantly searchable |
| uv | pip | pip works; uv is 10-100x faster and generates lockfiles automatically |

---

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| requests | Synchronous HTTP — blocks the entire async event loop in FastAPI/PTB context | `httpx` with async |
| Flask | Synchronous web framework; async support is bolted on and inferior to FastAPI's native async | FastAPI |
| Django | Massive overhead for a pipeline with no user-facing web UI; ORM and admin are unused | FastAPI |
| Celery + Redis | Operational overhead (two extra services to deploy) for a single daily job; APScheduler handles this in-process | APScheduler |
| v0.x openai SDK | Deprecated interface (`openai.ChatCompletion.create()`); breaks with current API | `openai` v1.x with `client = OpenAI()` |
| PTB v13.x (python-telegram-bot <20) | Synchronous, callback-heavy architecture; v20+ async rewrite is incompatible but massively better | PTB v21.x |
| Pinecone / Weaviate | Paid external service for a problem pgvector solves free at this scale | pgvector via Supabase |
| moviepy | Unmaintained, slow, poor async support; use ffmpeg-python or direct ffmpeg subprocess for audio overlay | ffmpeg-python |
| SQLite | No vector extension support without third-party patches; no connection pooling | Supabase (Postgres + pgvector) |

---

## Stack Patterns by Variant

**If HeyGen webhook is available (confirm in HeyGen v2 docs):**
- Register a webhook URL pointing to a FastAPI endpoint
- Receive `video_completed` events instead of polling
- Eliminates polling loop complexity

**If HeyGen only supports polling:**
- Use `asyncio.sleep()` loop with `tenacity` retry in the pipeline worker
- Poll `/v2/video_status/{video_id}` every 30s with max 20 retries (10 minute window)
- Log each poll with structlog for observability

**If Ayrshare lacks TikTok API access in your region/tier:**
- Fall back to Buffer Publish API for TikTok
- Use Ayrshare for Instagram + Facebook + YouTube
- Document this split in the publishing service

**If S3 cost is a concern:**
- Use Supabase Storage for Hot tier (0-7 days active)
- Move to S3 Glacier Instant Retrieval for Warm/Cold
- Or: keep all in Supabase Storage and delete at 45 days (simplest)

**For audio post-processing (dark ambient overlay):**
- Only install ffmpeg-python if HeyGen cannot inject a custom audio track
- HeyGen supports custom audio in avatar videos via the `voice` parameter — confirm before adding ffmpeg dependency
- If needed: mix generated video with ambient audio at -18dB using ffmpeg-python

---

## Version Compatibility

| Package | Compatible With | Notes |
|---------|-----------------|-------|
| python-telegram-bot 21.x | Python 3.8-3.12 | Requires Python 3.8+; works on 3.11 |
| FastAPI 0.111.x | Pydantic 2.x | FastAPI 0.100+ requires Pydantic 2; do not mix with Pydantic 1.x |
| Pydantic 2.x | pydantic-settings 2.x | Must match major versions |
| openai 1.x | httpx 0.23+ | OpenAI SDK depends on httpx internally |
| APScheduler 3.10.x | Python 3.11 | APScheduler 4.x (alpha) exists but is not stable; use 3.10.x |
| supabase-py 2.x | Pydantic 2.x | supabase-py 2.x requires Pydantic 2 |
| pytest-asyncio 0.23+ | pytest 8.x | Use `asyncio_mode = "auto"` in pytest.ini for cleaner tests |

---

## HeyGen API Integration Pattern (Critical)

HeyGen has no official Python SDK. Integration is via REST:

```python
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

HEYGEN_BASE = "https://api.heygen.com"

async def generate_avatar_video(script: str, avatar_id: str, voice_id: str) -> str:
    """Initiates video generation. Returns video_id."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{HEYGEN_BASE}/v2/video/generate",
            headers={"X-Api-Key": HEYGEN_API_KEY},
            json={
                "video_inputs": [{
                    "character": {"type": "avatar", "avatar_id": avatar_id},
                    "voice": {"type": "text", "input_text": script, "voice_id": voice_id},
                    "background": {"type": "color", "value": "#0d0d0d"}
                }],
                "aspect_ratio": "9:16",
                "dimension": {"width": 1080, "height": 1920}
            },
            timeout=30.0
        )
        response.raise_for_status()
        return response.json()["data"]["video_id"]

@retry(stop=stop_after_attempt(20), wait=wait_exponential(multiplier=1, min=30, max=60))
async def poll_video_status(video_id: str) -> str:
    """Polls until video is complete. Returns download URL."""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{HEYGEN_BASE}/v2/video_status.get?video_id={video_id}",
            headers={"X-Api-Key": HEYGEN_API_KEY}
        )
        data = response.json()["data"]
        if data["status"] == "completed":
            return data["video_url"]
        if data["status"] == "failed":
            raise ValueError(f"HeyGen render failed: {data.get('error')}")
        raise Exception("Video not ready yet")  # triggers tenacity retry
```

**Confidence: MEDIUM** — HeyGen endpoint structure based on training data; verify exact endpoint paths against HeyGen v2 API docs before implementation.

---

## Ayrshare vs Buffer Decision

**Use Ayrshare.** Rationale:

- Single POST endpoint publishes to all 4 platforms simultaneously (TikTok, Instagram, Facebook, YouTube Shorts)
- Handles platform-specific formatting (aspect ratio hints, caption length) automatically
- Buffer requires separate scheduled posts per platform and has more complex OAuth flows
- Ayrshare has a Social API plan at ~$29/month that includes TikTok + Instagram + Facebook + YouTube
- Buffer's free tier lacks TikTok; paid tiers are more expensive for multi-platform

**Ayrshare integration pattern:**
```python
async def publish_video(video_url: str, caption: str, platforms: list[str]) -> dict:
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://app.ayrshare.com/api/post",
            headers={
                "Authorization": f"Bearer {AYRSHARE_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "post": caption,
                "platforms": platforms,  # ["tiktok", "instagram", "facebook", "youtube"]
                "mediaUrls": [video_url],
                "scheduleDate": optimal_post_time.isoformat()  # ISO 8601
            }
        )
        return response.json()
```

**Confidence: MEDIUM** — Ayrshare API structure verified against training data; confirm current endpoint and auth format against Ayrshare dashboard docs.

---

## Vector Similarity Search Pattern (Anti-Repetition)

Using Supabase + pgvector:

```sql
-- Migration: add vector column to scripts table
ALTER TABLE scripts ADD COLUMN embedding vector(1536);

-- Create index for fast similarity search
CREATE INDEX ON scripts USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
```

```python
from openai import AsyncOpenAI
from supabase import create_client

openai_client = AsyncOpenAI()
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

async def is_too_similar(new_script: str, threshold: float = 0.85) -> bool:
    """Returns True if any prior script is >85% similar."""
    embedding_response = await openai_client.embeddings.create(
        model="text-embedding-3-small",
        input=new_script
    )
    embedding = embedding_response.data[0].embedding

    # Supabase RPC call to pgvector similarity search
    result = supabase.rpc(
        "match_scripts",
        {"query_embedding": embedding, "match_threshold": threshold, "match_count": 1}
    ).execute()

    return len(result.data) > 0
```

```sql
-- Supabase function for vector similarity search
CREATE OR REPLACE FUNCTION match_scripts(
  query_embedding vector(1536),
  match_threshold float,
  match_count int
)
RETURNS TABLE (id uuid, similarity float)
LANGUAGE plpgsql AS $$
BEGIN
  RETURN QUERY
  SELECT scripts.id, 1 - (scripts.embedding <=> query_embedding) AS similarity
  FROM scripts
  WHERE 1 - (scripts.embedding <=> query_embedding) > match_threshold
  ORDER BY scripts.embedding <=> query_embedding
  LIMIT match_count;
END;
$$;
```

**Confidence: HIGH** — pgvector cosine similarity pattern with Supabase RPC is well-documented and stable.

---

## Telegram Bot Architecture Pattern

```python
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler

# Single-user lock: reject all updates from non-creator
CREATOR_TELEGRAM_ID = int(os.getenv("CREATOR_TELEGRAM_ID"))

async def user_guard(update: Update, context) -> bool:
    """Returns False and ignores update if not from creator."""
    user_id = update.effective_user.id
    if user_id != CREATOR_TELEGRAM_ID:
        return False
    return True

async def send_video_for_approval(video_path: str, caption: str, content_id: str):
    """Sends video with inline approve/reject buttons."""
    keyboard = [
        [
            InlineKeyboardButton("Aprobar", callback_data=f"approve:{content_id}"),
            InlineKeyboardButton("Rechazar", callback_data=f"reject:{content_id}")
        ]
    ]
    markup = InlineKeyboardMarkup(keyboard)
    await application.bot.send_video(
        chat_id=CREATOR_TELEGRAM_ID,
        video=open(video_path, "rb"),
        caption=caption,
        reply_markup=markup
    )
```

**Confidence: HIGH** — PTB v21 InlineKeyboard pattern is stable and well-documented.

---

## Sources

- **Training data (Python ecosystem)** — python-telegram-bot v21, APScheduler 3.10, FastAPI 0.111, httpx 0.27, openai 1.x, pydantic 2.x all verified through Aug 2025. Confidence: HIGH for API patterns, MEDIUM for exact current patch versions.
- **HeyGen API** — REST endpoint structure from training data; no official Python SDK confirmed as of Aug 2025. Verify at https://docs.heygen.com/reference before implementation. Confidence: MEDIUM.
- **Ayrshare API** — Single-endpoint multi-platform publish pattern from training data. Verify at https://docs.ayrshare.com before implementation. Confidence: MEDIUM.
- **pgvector via Supabase** — Cosine similarity pattern is stable and documented in Supabase official docs. Confidence: HIGH.
- **ElevenLabs SDK** — Official Python SDK exists; version 1.x from training data. Confidence: MEDIUM (verify against https://github.com/elevenlabs/elevenlabs-python).

---

## Version Validation Checklist (Before Implementation)

Before starting Phase 1, verify these against live sources:

- [ ] HeyGen API v2 endpoint structure — https://docs.heygen.com/reference
- [ ] Ayrshare API endpoint and auth format — https://docs.ayrshare.com
- [ ] python-telegram-bot latest release — https://github.com/python-telegram-bot/python-telegram-bot/releases
- [ ] APScheduler 3.x vs 4.x stability status — https://apscheduler.readthedocs.io
- [ ] Supabase Python client v2.x RPC pattern — https://supabase.com/docs/reference/python

---

*Stack research for: AI automated short-form video content pipeline (solo creator)*
*Researched: 2026-02-19*
