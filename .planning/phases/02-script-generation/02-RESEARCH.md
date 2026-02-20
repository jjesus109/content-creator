# Phase 02: Script Generation - Research

**Researched:** 2026-02-20
**Domain:** Anthropic Claude API, OpenAI Embeddings, pgvector cosine similarity, python-telegram-bot ConversationHandler
**Confidence:** HIGH (core stack verified via official docs and PyPI; architecture patterns verified against existing Phase 1 codebase)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

#### Language
- All generated content is in neutral, natural Spanish — no exceptions

#### 5-Pillar prompt design (6 pillars confirmed)
1. **Philosophical Root** — Every script grounds in a real school, thinker, or concept (Stoicism, Nietzsche, Zen, etc.)
2. **Universal Tension** — Opens with a contradiction or paradox the viewer recognizes in their own life
3. **Insight Flip** — The development reframes the common understanding — not a summary, a perspective shift
4. **Emotional Anchor** — Connects the insight to a specific feeling (peace, ambition, grief, clarity)
5. **Reflective CTA** — Asks the viewer to sit with one question or try one thing — no "follow for more"
6. **Creator Archetype** — Scripts reflect "The Seeker" persona: actively questions, explores openly, admits uncertainty, invites the viewer to think along — not a teacher, a fellow traveler

#### Script length (dynamic)
- Creator picks target video duration in the weekly mood prompt (Step 3)
- 3 duration options:
  - **Short (30s)** → ~70 words — TikTok hook-only format, maximum completion rate
  - **Medium (60s)** → ~140 words — default, all-platform safe
  - **Long (90s)** → ~200 words — YT Shorts max, deeper philosophical development
- Default when creator skips: Medium (60s / ~140 words)
- Hook/Development/CTA proportions are flexible within the target word count — pillar intent governs structure, not fixed section ratios
- Scripts that exceed their target word count are auto-summarized before passing downstream — creator never sees an over-length script

#### Topic selection strategy
- Hybrid model: weekly mood profile routes to one of 6 thematic pools; AI generates within selected pool
- 6 thematic pools:
  1. **Existential questions** — Meaning, identity, free will, the self (Sartre, Camus, Heidegger)
  2. **Practical wisdom** — Stoicism, resilience, decision-making (Marcus Aurelius, Seneca)
  3. **Human nature** — Relationships, loneliness, love, connection (Aristotle, Fromm)
  4. **Modern paradoxes** — Attention, technology, emptiness, abundance (Byung-Chul Han, Bauman)
  5. **Eastern philosophy** — Impermanence, flow, non-attachment (Zen, Taoism, Buddhism)
  6. **The creative life** — Originality, expression, artistic struggle (Nietzsche, Wittgenstein)

#### Mood profile interaction
- Weekly Telegram prompt uses a three-step inline keyboard flow:
  - Step 1: Creator picks which thematic pool for the week
  - Step 2: Creator picks tone for the week
  - Step 3: Creator picks target video duration (30s / 60s / 90s)
- 4 tone options: **Contemplative** / **Provocative** / **Hopeful** / **Raw**
- No-response fallback: one reminder sent after 4 hours; if still no response, default to Contemplative tone + rotate to next pool + Medium (60s) duration
- Mood selection (pool + tone + duration) is injected into the generation prompt as contextual direction

#### Anti-repetition behavior
- Similarity threshold: 85% cosine similarity via pgvector (already established in Phase 1 schema)
- Retry strategy on detection:
  1. First retry: same philosophical root, different angle/lens/thinker
  2. Second retry: completely different topic from the same pool
  - Planner determines exact retry count based on cost/latency tradeoffs
- All retries exhausted: escalate to creator via Telegram alert; creator can manually intervene or skip the day

#### Rejection feedback loop
- When creator rejects a video (Phase 4), the rejection cause is:
  1. Injected as an explicit constraint into the next generation prompt
  2. The rejected pattern (topic, tone, or script class) is avoided for 7 days — not just the next run

### Claude's Discretion
- Exact retry count for anti-repetition (planner decides based on cost/latency)
- Specific pgvector query structure and embedding model choice
- Exact prompt template wording (within pillar framework)
- Mood profile database schema details

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope.
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| SCRP-01 | A generated script is in neutral Spanish, does not exceed target word count, and follows the 5-Pillar prompt framework | Anthropic SDK synchronous client + system prompt injection; word count check post-generation; summarization call when over limit |
| SCRP-02 | When a proposed topic is more than 85% similar to any script in the history table, the system automatically generates a new angle without creator intervention | pgvector cosine distance SQL function via Supabase RPC; threshold = 1 - 0.85 = 0.15 distance; retry strategy baked into ScriptGenerationService |
| SCRP-03 | When a script exceeds target word count, it is automatically summarized before being passed downstream — creator never sees an over-length script | Second Claude API call with explicit word-limit instruction; Python word count via `len(text.split())` |
| SCRP-04 | The bot prompts the creator once per week via Telegram for a mood profile; the creator's response is injected into the next generation as contextual direction | python-telegram-bot ConversationHandler with 3-step InlineKeyboardMarkup; APScheduler weekly CronTrigger sends prompt; mood persisted in mood_profiles table |
</phase_requirements>

---

## Summary

Phase 2 builds three interlinked subsystems on top of the Phase 1 scaffold. The first is a `ScriptGenerationService` that calls the Anthropic Claude API synchronously (suitable for APScheduler thread pool jobs) with a structured 6-pillar system prompt, checks word count, and auto-summarizes if over the target. The second is a pgvector anti-repetition gate that computes cosine similarity between the candidate topic embedding (OpenAI `text-embedding-3-small`) and the `content_history` table, retrying generation on detection above the 85% threshold. The third is a weekly Telegram mood collection flow — a multi-step `ConversationHandler` with `InlineKeyboardMarkup` initiated by an APScheduler weekly `CronTrigger`.

The most architecturally delicate part is the Telegram `ConversationHandler` integration. Phase 1 built the bot in outbound-only mode (`updater(None)`, no polling). Phase 2 needs inbound interaction for the weekly mood prompt. The safest approach is to upgrade the `ApplicationBuilder` to include a proper Updater (enabling `start_polling()`) and manage the async lifecycle within FastAPI's lifespan context manager using `asyncio.create_task()`. The bot runs on FastAPI's own event loop — no second event loop, no threads. This is the pattern documented in the PTB wiki for "running PTB with other asyncio frameworks."

The Anthropic SDK call is synchronous (`Anthropic()`, not `AsyncAnthropic()`) to match the APScheduler `ThreadPoolExecutor` model established in Phase 1. The OpenAI embedding call is also synchronous. Both are blocking I/O calls that are correct to run in a thread pool. Cost is tracked after each generation call and reported to the `CircuitBreakerService.record_attempt()` exactly as established in Phase 1.

**Primary recommendation:** Use `anthropic>=0.83` synchronous client + `openai>=2.21` synchronous client in APScheduler thread jobs; use PTB `ConversationHandler` with `ApplicationBuilder().updater(...)` (not `None`) for inbound mood collection; implement similarity check as a Supabase RPC SQL function returning a boolean; store mood profile as a structured JSON field in `mood_profiles.profile_text`.

---

## Standard Stack

### Core — New for Phase 2
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| anthropic | >=0.83.0 | Anthropic Claude API client for script generation | Official SDK; synchronous client compatible with APScheduler thread pool; `message.usage` gives token counts for cost tracking |
| openai | >=2.21.0 | OpenAI embeddings API for `text-embedding-3-small` | Phase 1 schema uses `vector(1536)` dimensions — matches `text-embedding-3-small`; synchronous client usable in thread pool |

### Already in Phase 1 (reused, no install needed)
| Library | Version | Purpose | Phase 2 Usage |
|---------|---------|---------|--------------|
| python-telegram-bot | ==21.* | Telegram bot framework | Upgrade from outbound-only to full ConversationHandler with polling |
| supabase | >=2.0 | Supabase client for DB operations | `rpc()` call for pgvector similarity check; mood profile persistence |
| APScheduler | ==3.11.2 | Background scheduler | Weekly mood prompt CronTrigger; daily generation job |
| fastapi | >=0.115 | Web framework | No change; lifespan expanded for bot polling |
| pytz | >=2024.1 | Timezone support | No change |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `anthropic` sync client | `AsyncAnthropic` | Async client requires `asyncio.run()` inside APScheduler thread — creates a second event loop; sync is simpler and correct for thread pool jobs |
| `text-embedding-3-small` (1536 dims) | `text-embedding-3-large` (3072 dims) | Schema already has `vector(1536)` — changing dimensions requires a migration and HNSW index rebuild; stick with 3-small |
| Supabase RPC for similarity | Direct psycopg2 query | RPC is the correct pattern since supabase-py uses PostgREST which doesn't support pgvector operators directly |
| `ConversationHandler` + polling | Webhook | Polling is simpler with Railway (no public HTTPS endpoint setup); webhook adds infra complexity not needed at this scale |

**Installation (new packages only):**
```bash
uv add anthropic openai
```

---

## Architecture Patterns

### Recommended Project Structure Addition
```
src/app/
├── services/
│   ├── script_generation.py   # ScriptGenerationService: generate + check + summarize
│   ├── embeddings.py          # EmbeddingService: wrap openai.embeddings.create()
│   ├── similarity.py          # SimilarityService: wrap supabase.rpc() check
│   └── mood.py                # MoodService: read/write mood_profiles table
├── scheduler/
│   └── jobs/
│       ├── daily_pipeline.py  # Orchestrator job: check CB → mood → embed → check similarity → generate → summarize → save
│       └── weekly_mood.py     # Job: send weekly Telegram mood prompt
├── telegram/
│   ├── __init__.py
│   ├── app.py                 # Build PTB Application with ConversationHandler
│   └── handlers/
│       └── mood_flow.py       # 3-step ConversationHandler states
└── models/
    └── mood.py                # Extended MoodProfile with pool/tone/duration fields
```

**Key architectural boundary:** The daily pipeline job calls `ScriptGenerationService` which calls `EmbeddingService` and `SimilarityService` internally. The Telegram mood prompt is a separate weekly job that calls `MoodService` to persist the result. The daily pipeline job reads from `MoodService` at runtime.

### Pattern 1: Synchronous Claude API Call in APScheduler Job
**What:** Call `client.messages.create()` from a thread pool job using the sync Anthropic client. Extract cost from `message.usage` and report to circuit breaker.
**When to use:** All Claude generation calls in this project — they run in APScheduler thread pool jobs.

```python
# Source: https://github.com/anthropics/anthropic-sdk-python
from anthropic import Anthropic
from app.services.circuit_breaker import CircuitBreakerService
from app.settings import get_settings

COST_PER_INPUT_MTOK = 0.80   # claude-haiku-3-5 input: $0.80/MTok
COST_PER_OUTPUT_MTOK = 4.00  # claude-haiku-3-5 output: $4.00/MTok

def call_claude(system_prompt: str, user_prompt: str, max_tokens: int = 300) -> tuple[str, float]:
    """
    Returns (generated_text, cost_usd).
    Uses synchronous client — safe in APScheduler ThreadPoolExecutor.
    """
    settings = get_settings()
    client = Anthropic(api_key=settings.anthropic_api_key)

    message = client.messages.create(
        model="claude-haiku-3-5-20241022",   # cheapest capable model for short creative text
        max_tokens=max_tokens,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
        temperature=0.9,  # creative variation for philosophical scripts
    )

    text = message.content[0].text
    input_cost = (message.usage.input_tokens / 1_000_000) * COST_PER_INPUT_MTOK
    output_cost = (message.usage.output_tokens / 1_000_000) * COST_PER_OUTPUT_MTOK
    total_cost = input_cost + output_cost

    return text, total_cost
```

### Pattern 2: Embedding Generation (Synchronous, Thread-Safe)
**What:** Generate a 1536-dimension embedding for a topic summary using OpenAI's synchronous client. Safe in thread pool jobs.
**When to use:** Before every similarity check and before saving a new script to `content_history`.

```python
# Source: https://platform.openai.com/docs/api-reference/embeddings
from openai import OpenAI
from app.settings import get_settings

def generate_embedding(text: str) -> list[float]:
    """
    Returns a 1536-dimension embedding vector.
    Matches the vector(1536) column in content_history.embedding.
    """
    settings = get_settings()
    client = OpenAI(api_key=settings.openai_api_key)

    response = client.embeddings.create(
        model="text-embedding-3-small",  # 1536 dims — matches Phase 1 schema
        input=text,
    )
    return response.data[0].embedding  # list[float], 1536 elements
```

### Pattern 3: Cosine Similarity Check via Supabase RPC
**What:** Query `content_history` via a Postgres function that uses the pgvector `<=>` operator. PostgREST (used by supabase-py) does not support pgvector operators directly — must use `.rpc()`.
**When to use:** Always — this is the only correct pattern for pgvector queries via supabase-py.

**SQL function to add in a new migration:**
```sql
-- Migration 0002: add similarity check function
-- Source: https://supabase.com/docs/guides/ai/semantic-search
CREATE OR REPLACE FUNCTION check_script_similarity(
    query_embedding extensions.vector(1536),
    similarity_threshold float DEFAULT 0.85,
    lookback_days int DEFAULT 90
)
RETURNS TABLE(
    id uuid,
    topic_summary text,
    similarity float
)
LANGUAGE sql
AS $$
    SELECT
        ch.id,
        ch.topic_summary,
        1 - (ch.embedding <=> query_embedding) AS similarity
    FROM content_history ch
    WHERE
        ch.embedding IS NOT NULL
        AND ch.created_at > NOW() - (lookback_days || ' days')::interval
        AND (1 - (ch.embedding <=> query_embedding)) > similarity_threshold
    ORDER BY similarity DESC
    LIMIT 5;
$$;
```

**Python call:**
```python
# Source: https://supabase.com/docs/guides/ai/semantic-search
def is_too_similar(supabase: Client, embedding: list[float], threshold: float = 0.85) -> bool:
    """
    Returns True if any existing script exceeds the similarity threshold.
    Cosine distance threshold: 1 - similarity_threshold (0.85 sim → 0.15 distance).
    """
    result = supabase.rpc(
        "check_script_similarity",
        {
            "query_embedding": embedding,
            "similarity_threshold": threshold,
            "lookback_days": 90,
        }
    ).execute()

    return len(result.data) > 0  # True = too similar, retry needed
```

### Pattern 4: Word Count Check and Auto-Summarization
**What:** After generation, count words in the Spanish script. If over target, make a second Claude call to summarize to the target word count.
**When to use:** Always after every generation call — creator never sees an over-length script (SCRP-03).

```python
# Source: verified by design — no library needed for Spanish word count
def word_count(text: str) -> int:
    """Simple word count for Spanish text. Splits on whitespace."""
    return len(text.split())


def summarize_to_target(script: str, target_words: int) -> tuple[str, float]:
    """
    Second Claude call to reduce script to target word count.
    Returns (summarized_text, cost_usd).
    Called only when word_count(script) > target_words.
    """
    system = (
        "Eres un editor de guiones en español. "
        "Tu única tarea es reducir el guion al número exacto de palabras indicado, "
        "preservando el tono filosófico y la estructura (gancho, desarrollo, CTA reflexivo). "
        "Devuelve únicamente el guion resumido, sin explicaciones."
    )
    user = (
        f"Resume este guion a exactamente {target_words} palabras:\n\n{script}"
    )
    return call_claude(system, user, max_tokens=target_words * 3)
```

### Pattern 5: Weekly Mood Prompt with ConversationHandler
**What:** A PTB `ConversationHandler` with 3 states (pool selection → tone selection → duration selection) triggered by a weekly APScheduler job. Requires upgrading Phase 1 bot from outbound-only (`updater(None)`) to full polling.
**When to use:** Weekly mood collection — SCRP-04.

**Key architecture change from Phase 1:** The bot in `telegram/app.py` must be built with a proper Updater (remove `updater(None)`) and the `Application` lifecycle must be managed inside FastAPI's lifespan.

```python
# Source: https://docs.python-telegram-bot.org/en/v21.9/ + Architecture wiki
# File: src/app/telegram/app.py

from telegram.ext import (
    Application, ApplicationBuilder, CallbackQueryHandler,
    ConversationHandler, filters
)
from app.telegram.handlers.mood_flow import (
    step_pool, step_tone, step_duration, fallback_handler,
    STEP_POOL, STEP_TONE, STEP_DURATION
)
from app.settings import get_settings

_application: Application | None = None


def build_telegram_app() -> Application:
    settings = get_settings()
    app = (
        ApplicationBuilder()
        .token(settings.telegram_bot_token)
        # No .updater(None) — Phase 2 needs inbound polling
        .build()
    )

    creator_filter = filters.User(user_id=settings.telegram_creator_id)

    mood_handler = ConversationHandler(
        entry_points=[],  # Entry via programmatic message — see weekly_mood job
        states={
            STEP_POOL: [CallbackQueryHandler(step_pool)],
            STEP_TONE: [CallbackQueryHandler(step_tone)],
            STEP_DURATION: [CallbackQueryHandler(step_duration)],
        },
        fallbacks=[fallback_handler],
        per_user=True,
        per_chat=True,
    )
    app.add_handler(mood_handler)
    return app


async def start_telegram_polling(app: Application) -> None:
    """Called from FastAPI lifespan startup."""
    await app.initialize()
    await app.start()
    # Start polling as a background asyncio task
    await app.updater.start_polling(drop_pending_updates=True)


async def stop_telegram_polling(app: Application) -> None:
    """Called from FastAPI lifespan shutdown."""
    await app.updater.stop()
    await app.stop()
    await app.shutdown()
```

**FastAPI lifespan update:**
```python
# Source: PTB wiki + FastAPI lifespan docs
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # Startup
    run_migrations()
    scheduler = create_scheduler()
    register_jobs(scheduler)
    scheduler.start()
    app.state.scheduler = scheduler

    tg_app = build_telegram_app()
    await start_telegram_polling(tg_app)
    app.state.telegram_app = tg_app

    yield

    # Shutdown
    await stop_telegram_polling(tg_app)
    scheduler.shutdown(wait=False)
```

### Pattern 6: 3-Step ConversationHandler States
**What:** Each state presents an `InlineKeyboardMarkup` and returns the next state constant. Final state saves mood to DB.
**When to use:** Mood flow handlers only.

```python
# Source: https://docs.python-telegram-bot.org/en/v21.9/examples.inlinekeyboard2.html
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes, ConversationHandler

STEP_POOL, STEP_TONE, STEP_DURATION = range(3)

POOLS = [
    ("Preguntas existenciales", "existential"),
    ("Sabiduría práctica", "practical"),
    ("Naturaleza humana", "human_nature"),
    ("Paradojas modernas", "modern_paradoxes"),
    ("Filosofía oriental", "eastern"),
    ("La vida creativa", "creative"),
]

TONES = [
    ("Contemplativo", "contemplative"),
    ("Provocativo", "provocative"),
    ("Esperanzador", "hopeful"),
    ("Crudo", "raw"),
]

DURATIONS = [
    ("Corto (30s / ~70 palabras)", "short"),
    ("Medio (60s / ~140 palabras)", "medium"),
    ("Largo (90s / ~200 palabras)", "long"),
]


async def send_pool_prompt(bot, chat_id: int) -> None:
    """Called by weekly APScheduler job (via asyncio.run_coroutine_threadsafe)."""
    keyboard = [
        [InlineKeyboardButton(label, callback_data=f"pool:{val}")]
        for label, val in POOLS
    ]
    await bot.send_message(
        chat_id=chat_id,
        text="Selecciona el area tematica para esta semana:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def step_pool(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """State: STEP_POOL — user selects thematic pool."""
    query = update.callback_query
    await query.answer()  # REQUIRED — prevents Telegram hourglass icon
    pool_value = query.data.split(":")[1]
    context.user_data["pool"] = pool_value

    keyboard = [
        [InlineKeyboardButton(label, callback_data=f"tone:{val}")]
        for label, val in TONES
    ]
    await query.edit_message_text(
        text=f"Pool: {pool_value}\nAhora selecciona el tono:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return STEP_TONE


async def step_tone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """State: STEP_TONE — user selects emotional tone."""
    query = update.callback_query
    await query.answer()
    tone_value = query.data.split(":")[1]
    context.user_data["tone"] = tone_value

    keyboard = [
        [InlineKeyboardButton(label, callback_data=f"duration:{val}")]
        for label, val in DURATIONS
    ]
    await query.edit_message_text(
        text=f"Tono: {tone_value}\nSelecciona la duracion del video:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return STEP_DURATION


async def step_duration(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """State: STEP_DURATION — final step, saves mood profile."""
    query = update.callback_query
    await query.answer()
    duration_value = query.data.split(":")[1]
    context.user_data["duration"] = duration_value

    mood = {
        "pool": context.user_data["pool"],
        "tone": context.user_data["tone"],
        "duration": context.user_data["duration"],
    }

    # Save to mood_profiles table (MoodService handles DB write)
    from app.services.mood import save_mood_profile
    save_mood_profile(mood)  # sync call — MoodService wraps supabase client

    await query.edit_message_text(
        text=f"Perfecto. Esta semana: {mood['pool']} | {mood['tone']} | {mood['duration']}. "
             "Lo tengo en cuenta para el guion de manana."
    )
    return ConversationHandler.END
```

### Pattern 7: Daily Pipeline Job Orchestration
**What:** The APScheduler daily job orchestrates: circuit breaker check → load mood → generate topic → embed → similarity check → retry loop → generate script → word count → summarize if needed → save to DB.
**When to use:** Replaces the current `heartbeat_job` for the `daily_pipeline_trigger` job ID.

```python
# Pseudocode structure — exact prompt wording is Claude's discretion
def daily_pipeline_job():
    """Registered as 'daily_pipeline_trigger' in registry.py."""
    cb = CircuitBreakerService(get_supabase())
    if cb.is_tripped():
        send_alert_sync("Pipeline skipped: circuit breaker is tripped.")
        return

    mood = MoodService(get_supabase()).get_current_week_mood()
    # mood = {"pool": "existential", "tone": "contemplative", "duration": "medium"}
    # or defaults if no mood profile this week

    target_words = {"short": 70, "medium": 140, "long": 200}[mood["duration"]]

    max_retries = 2  # planner decision: 2 retries = 3 total attempts, balances cost vs freshness
    last_rejection = RejectionService(get_supabase()).get_active_rejection_constraints()

    for attempt in range(max_retries + 1):
        # Generate topic summary (not full script yet) for similarity check
        topic_summary, embed_cost = generate_topic_summary(mood, attempt, last_rejection)
        if not cb.record_attempt(embed_cost):
            send_alert_sync("Circuit breaker tripped during topic generation.")
            return

        embedding = generate_embedding(topic_summary)
        if is_too_similar(get_supabase(), embedding):
            continue  # retry — different angle or different topic

        # Topic passes — generate full script
        script, gen_cost = generate_script(topic_summary, mood, target_words, last_rejection)
        if not cb.record_attempt(gen_cost):
            send_alert_sync("Circuit breaker tripped during script generation.")
            return

        # Word count guard (SCRP-03)
        if word_count(script) > target_words:
            script, sum_cost = summarize_to_target(script, target_words)
            cb.record_attempt(sum_cost)

        # Save to content_history
        save_script(get_supabase(), script, topic_summary, embedding, mood)
        return

    # All retries exhausted
    send_alert_sync("All similarity retries exhausted. Manual intervention needed.")
```

### Anti-Patterns to Avoid
- **Using `AsyncAnthropic` inside APScheduler thread pool jobs:** APScheduler's `ThreadPoolExecutor` runs in a thread that may not have an event loop. Use `Anthropic()` (sync) — it blocks correctly in a thread.
- **Checking word count with `len(text)` (character count):** Use `len(text.split())` for word count in Spanish. Character count is meaningless for word limit enforcement.
- **Calling pgvector operators via supabase-py `.table().select()`:** PostgREST does not support `<=>`. Always use `.rpc()` with a SQL function.
- **Keeping `updater(None)` when ConversationHandler is needed:** Phase 1 used `updater(None)` for outbound-only. Phase 2 requires inbound polling for the mood flow. Remove `updater(None)`.
- **Re-initializing `ApplicationBuilder` every time the weekly job fires:** Build the Application once at lifespan startup, store on `app.state.telegram_app`, reuse in job functions via `asyncio.run_coroutine_threadsafe(send_pool_prompt(...), loop)`.
- **Building two event loops:** FastAPI and PTB must share the same asyncio event loop. Never call `asyncio.run()` from inside a FastAPI async context — use `asyncio.run_coroutine_threadsafe()` from the APScheduler thread, or `asyncio.create_task()` from async context.
- **Using `query.answer()` without awaiting:** All callback queries MUST be answered even with no notification. Unanswered queries show a loading indicator forever on the user's client.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Script generation | Custom prompt chaining | `anthropic` SDK `client.messages.create()` | Token counting, error handling, retry, streaming all included |
| Cosine similarity | Python-side dot product | pgvector `<=>` via SQL function | Operates on indexed vectors in DB — no data transfer to Python layer; HNSW index already built in Phase 1 |
| Embedding generation | Local embedding model | `openai text-embedding-3-small` | Schema already committed to 1536 dims; changing would require migration |
| Multi-step Telegram flow | Manual state machine in a dict | `python-telegram-bot ConversationHandler` | Handles concurrent users, timeout states, per-user/per-chat scoping, persistence hooks |
| Word count | Character-based length check | `len(text.split())` | One line, correct for Spanish word boundaries |
| Mood profile fallback | Timed polling loop | APScheduler reminder job + no-response default | Existing scheduler infrastructure; deterministic fallback without polling |

**Key insight:** The similarity check should run entirely in Postgres using the HNSW index. Fetching all embeddings to Python for comparison would be O(n) data transfer and defeats the purpose of pgvector.

---

## Common Pitfalls

### Pitfall 1: `<=>` Returns Distance, Not Similarity
**What goes wrong:** Developer checks `result > 0.85` but `<=>` returns *distance* (0 = identical, 1 = orthogonal). The check passes when it should reject.
**Why it happens:** The operator name is "cosine distance", not "cosine similarity". The relationship is: `similarity = 1 - distance`.
**How to avoid:** In the SQL function, use `WHERE (1 - (embedding <=> query_embedding)) > similarity_threshold` OR `WHERE embedding <=> query_embedding < (1 - similarity_threshold)`. The 85% threshold becomes `< 0.15` in distance terms.
**Warning signs:** All scripts pass the similarity check even when identical topics are re-generated.

### Pitfall 2: `updater(None)` Blocks ConversationHandler
**What goes wrong:** `ConversationHandler` handlers are registered but never fire because the bot has no update source.
**Why it happens:** Phase 1 used `updater(None)` (outbound-only). Without a running Updater, no updates arrive in the update queue.
**How to avoid:** Remove `updater(None)` when building the Phase 2 Application. Call `await app.updater.start_polling()` in lifespan startup, `await app.updater.stop()` in shutdown.
**Warning signs:** Bot sends the weekly prompt successfully but never receives the callback query when creator clicks a button.

### Pitfall 3: `asyncio.run()` Inside FastAPI Lifespan Kills the Event Loop
**What goes wrong:** The weekly APScheduler job (thread pool) tries to send a Telegram message using `asyncio.run(bot.send_message(...))`, which raises `RuntimeError: This event loop is already running` or creates a new loop that conflicts.
**Why it happens:** `asyncio.run()` creates a new event loop; FastAPI's existing event loop is already running.
**How to avoid:** Use the existing pattern from Phase 1's `send_alert_sync()`: `asyncio.run_coroutine_threadsafe(coro, loop)` where `loop` is retrieved via `asyncio.get_event_loop()`.
**Warning signs:** Telegram alerts from scheduler jobs raise `RuntimeError` in logs; mood prompt never fires.

### Pitfall 4: Cost Not Reported for Embedding and Summarization Calls
**What goes wrong:** Circuit breaker only counts one API call per day even though each pipeline run may make 3-5 calls (topic generation + embedding + script generation + optional summarization + retry).
**Why it happens:** Developer only calls `cb.record_attempt()` for the main script generation call.
**How to avoid:** Call `cb.record_attempt(cost)` after every external API call — topic generation, summarization, and optionally embedding (embedding costs are tiny but should be counted toward attempt count). Check `if not cb.record_attempt(cost): return` to halt the pipeline mid-run if limit is hit.
**Warning signs:** Cost in `circuit_breaker_state` is lower than actual API spend; breaker never trips even on expensive days.

### Pitfall 5: Mood Profile Schema Doesn't Support Structured Fields
**What goes wrong:** Phase 1 stored `mood_profiles.profile_text` as a plain text string. Phase 2 needs to read the pool, tone, and duration as separate fields for injection into the generation prompt.
**Why it happens:** Phase 1 schema was designed as a forward placeholder; the JSON structure was not specified.
**How to avoid:** Store mood as JSON in `profile_text` (e.g., `{"pool": "existential", "tone": "contemplative", "duration": "medium"}`). Read with `json.loads(profile_text)`. Add a migration that adds a `CONSTRAINT valid_json CHECK (profile_text::jsonb IS NOT NULL)` if strict validation is desired.
**Warning signs:** Generation prompt receives raw text instead of structured mood direction; pool injection fails.

### Pitfall 6: Rejection Feedback Has No Schema Yet
**What goes wrong:** The rejection feedback loop (CONTEXT.md) says rejection causes are injected for 7 days, but there is no table to store rejection patterns with expiry dates.
**Why it happens:** Phase 1 schema has `rejection_reason text` on `content_history` but no separate rejection constraint table with TTL semantics.
**How to avoid:** Add a `rejection_constraints` table in a new migration with columns: `id`, `reason_text`, `pattern_type` (topic/tone/script_class), `expires_at`. The daily pipeline queries active constraints (`WHERE expires_at > now()`). Phase 4 writes to this table on rejection.
**Warning signs:** Pipeline generates same rejected topic the next day because no constraint was persisted with expiry.

### Pitfall 7: Over-Length Script Summarization Changes Philosophical Grounding
**What goes wrong:** The summarization call reduces word count but strips the philosophical root or CTA, leaving a script that doesn't follow the 5-Pillar framework.
**Why it happens:** Generic summarization prompt doesn't specify which structural elements must survive compression.
**How to avoid:** Summarization system prompt explicitly names the 6 pillars and instructs Claude to preserve the Philosophical Root, Emotional Anchor, and Reflective CTA — compress only the development section if needed.
**Warning signs:** Over-length scripts consistently lose the CTA or philosophical attribution after summarization.

### Pitfall 8: ConversationHandler Entry Points Require Active Message
**What goes wrong:** The weekly mood prompt is sent by the scheduler, but `ConversationHandler.entry_points` expects a user-initiated command or message to start the conversation.
**Why it happens:** PTB's `ConversationHandler` state machine only enters via defined `entry_points`. A bot-sent message does not trigger them.
**How to avoid:** Send the first mood prompt with `InlineKeyboardMarkup` directly (the STEP_POOL keyboard), then register a `CallbackQueryHandler` for STEP_POOL at the top level (outside the ConversationHandler, or as a standalone `add_handler`). The STEP_POOL handler transitions to the ConversationHandler state by returning `STEP_TONE`. Alternatively, use a simpler non-ConversationHandler approach: manage state in a dedicated mood_state dict per user, keyed by chat_id.

> **Recommendation (Claude's Discretion):** Use a lightweight state dict (`app.bot_data["mood_state"]`) rather than ConversationHandler for the weekly flow. ConversationHandler's entry_points design assumes user-initiated conversations; bot-initiated multi-step flows are cleaner with explicit state management. This avoids the entry_point problem entirely.

---

## Code Examples

Verified patterns from official sources:

### Full Anthropic SDK Call with Usage Tracking
```python
# Source: https://github.com/anthropics/anthropic-sdk-python (v0.83.0)
import anthropic

client = anthropic.Anthropic(api_key="...")  # sync client

message = client.messages.create(
    model="claude-haiku-3-5-20241022",
    max_tokens=300,
    system="Tu eres un escritor de filosofia en espanol neutro...",
    messages=[{"role": "user", "content": "Genera un guion sobre..."}],
    temperature=0.9,
)

text = message.content[0].text          # str
input_tokens = message.usage.input_tokens   # int
output_tokens = message.usage.output_tokens  # int

# Cost calculation (Haiku 3.5: $0.80/$4.00 per MTok)
cost = (input_tokens * 0.80 + output_tokens * 4.00) / 1_000_000
```

### OpenAI Embedding (Synchronous)
```python
# Source: https://platform.openai.com/docs/api-reference/embeddings
from openai import OpenAI

client = OpenAI(api_key="...")  # sync client
response = client.embeddings.create(
    model="text-embedding-3-small",
    input="El silencio como forma de escucha activa",  # topic summary, not full script
)
embedding = response.data[0].embedding  # list[float], len=1536
```

### pgvector Similarity SQL Function
```sql
-- Source: https://supabase.com/docs/guides/ai/semantic-search
-- Add in migration 0002_similarity_function.sql
CREATE OR REPLACE FUNCTION check_script_similarity(
    query_embedding extensions.vector(1536),
    similarity_threshold float DEFAULT 0.85,
    lookback_days int DEFAULT 90
)
RETURNS TABLE(id uuid, topic_summary text, similarity float)
LANGUAGE sql
AS $$
    SELECT
        ch.id,
        ch.topic_summary,
        1 - (ch.embedding <=> query_embedding) AS similarity
    FROM content_history ch
    WHERE
        ch.embedding IS NOT NULL
        AND ch.created_at > NOW() - (lookback_days || ' days')::interval
        AND (1 - (ch.embedding <=> query_embedding)) > similarity_threshold
    ORDER BY similarity DESC
    LIMIT 5;
$$;
```

### Supabase RPC Python Call
```python
# Source: https://supabase.com/docs/guides/ai/semantic-search
result = supabase.rpc(
    "check_script_similarity",
    {
        "query_embedding": embedding,   # list[float]
        "similarity_threshold": 0.85,
        "lookback_days": 90,
    }
).execute()

is_similar = len(result.data) > 0
```

### Telegram CallbackQuery — Required answer()
```python
# Source: https://docs.python-telegram-bot.org/en/v21.9/examples.inlinekeyboard2.html
async def step_pool(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()   # REQUIRED — Telegram shows loading spinner if omitted
    # ... process callback data
```

### Bot-Initiated Mood Prompt from APScheduler Thread
```python
# Source: Phase 1 send_alert_sync pattern, extended for inline keyboards
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

def send_mood_prompt_sync(bot, chat_id: int, loop) -> None:
    """Called from APScheduler thread pool job."""
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(label, callback_data=f"pool:{val}")]
        for label, val in POOLS
    ])
    coro = bot.send_message(
        chat_id=chat_id,
        text="Selecciona el area tematica para esta semana:",
        reply_markup=keyboard,
    )
    asyncio.run_coroutine_threadsafe(coro, loop).result(timeout=10)
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `claude-3-opus` for creative tasks | `claude-haiku-3-5` for short creative text | 2024 | Haiku 3.5 at $0.80/$4.00/MTok is dramatically cheaper than Opus at $15/$75; quality gap for 70-200 word scripts is negligible |
| Separate embedding + generation models from same provider | Anthropic (Claude) for generation + OpenAI (text-embedding-3-small) for embeddings | N/A | Anthropic does not offer a standalone embedding API; OpenAI's embedding model is the standard for 1536-dim pgvector setups |
| Polling once per API call for Telegram updates | `updater.start_polling()` inside async context | PTB v20+ | PTB v20+ is async-native; polling runs as a background coroutine, not a blocking thread |
| IVFFlat pgvector index | HNSW index | pgvector 0.5 (2023) | Phase 1 already uses HNSW — no change needed |
| `claude-haiku-3` | `claude-haiku-3-5` | 2024 | 3.5 Haiku is the current cheapest capable model; $0.80/$4.00 vs $0.25/$1.25 — higher cost but meaningfully better at Spanish creative writing |

**Deprecated/outdated:**
- `claude-3-opus-20240229`: Deprecated — very expensive for this use case; Haiku 3.5 is sufficient for 70-200 word philosophical scripts
- `updater(None)` in Phase 1: Must be removed when ConversationHandler or any inbound handling is added
- Embedding with `text-embedding-ada-002`: Replaced by `text-embedding-3-small`; ada-002 is legacy but still available

---

## Open Questions

1. **Model selection: Claude Haiku 3.5 vs Claude Sonnet 4 for script generation**
   - What we know: Haiku 3.5 is $0.80/$4.00/MTok; Sonnet 4 is $3/$15/MTok; for a 140-word Spanish script the total generation cost per Haiku call is ~$0.001-0.003; Sonnet would be ~$0.004-0.010
   - What's unclear: Whether Haiku 3.5 produces sufficiently high-quality philosophical Spanish text for the Creator Archetype persona
   - Recommendation (Claude's Discretion): Start with Haiku 3.5 — it is 3-4x cheaper and the quality bar for short creative scripts is achievable. Make the model configurable via a settings env var (`CLAUDE_GENERATION_MODEL`) so the creator can upgrade to Sonnet without a code deploy.

2. **ConversationHandler vs manual state dict for bot-initiated mood flow**
   - What we know: ConversationHandler expects user-initiated entry_points; bot-initiated flows require workarounds; PTB wiki confirms `process_update()` and `update_queue` as manual paths
   - What's unclear: Whether the ConversationHandler entry_point workaround is maintainable or whether a manual state dict in `bot_data` is cleaner for a 3-step flow
   - Recommendation (Claude's Discretion): Use a manual state dict approach (`bot_data["mood_state"][chat_id] = {"step": "pool", ...}`) for the weekly mood flow. It avoids the entry_point problem, is easier to reason about, and the 3-step flow doesn't benefit from ConversationHandler's timeout/persistence features.

3. **`rejection_constraints` table design**
   - What we know: Phase 1 schema has `rejection_reason text` on `content_history`; Phase 4 is responsible for writing rejection causes; this phase needs to READ them
   - What's unclear: The exact schema for a table that stores rejection patterns with `expires_at` — does this belong in Phase 2 or Phase 4?
   - Recommendation: Define the `rejection_constraints` table schema in Phase 2 migration (so the pipeline can query it safely, returning empty result when no constraints exist), but Phase 4 writes to it. The table can be empty for Phase 2 test runs.

4. **Weekly mood prompt timing**
   - What we know: Pipeline runs at 7 AM Monday-Sunday; mood profile should guide the week's content
   - What's unclear: Which day and time to send the weekly mood prompt — Monday at 8 PM? Sunday at 10 AM?
   - Recommendation (Claude's Discretion): Send weekly mood prompt on Monday at 9 AM Mexico City time (after the first pipeline run of the week has already used defaults). This gives the creator a chance to shape Tuesday onward. Fallback reminder at 1 PM same day.

---

## Sources

### Primary (HIGH confidence)
- [Anthropic Python SDK GitHub (v0.83.0)](https://github.com/anthropics/anthropic-sdk-python) — sync client, `messages.create()`, `message.usage`, `message.content[0].text`
- [Anthropic Messages API reference](https://platform.claude.com/docs/en/api/messages) — model IDs, parameters, response schema
- [Anthropic Pricing page (February 2026)](https://platform.claude.com/docs/en/about-claude/pricing) — Haiku 3.5 $0.80/$4.00/MTok; Sonnet 4 $3/$15/MTok; verified current
- [OpenAI Embeddings API reference](https://platform.openai.com/docs/api-reference/embeddings) — `client.embeddings.create()`, `text-embedding-3-small`, 1536 dimensions
- [Supabase Semantic Search docs](https://supabase.com/docs/guides/ai/semantic-search) — SQL function pattern, `<=>` distance operator, RPC call pattern
- [python-telegram-bot v21.9 Application docs](https://docs.python-telegram-bot.org/en/v21.9/telegram.ext.application.html) — `initialize()`, `start()`, `stop()`, `shutdown()`, asyncio context manager
- [python-telegram-bot v21.9 ConversationHandler](https://docs.python-telegram-bot.org/en/v21.9/telegram.ext.conversationhandler.html) — states, entry_points, per_user, per_chat
- [python-telegram-bot inlinekeyboard2.py example](https://docs.python-telegram-bot.org/en/v21.9/examples.inlinekeyboard2.html) — 3-step inline keyboard flow, `query.answer()`, state transitions
- [python-telegram-bot Architecture wiki](https://github.com/python-telegram-bot/python-telegram-bot/wiki/Architecture) — manual update queue, `process_update()`, asyncio integration pattern
- Phase 1 implemented codebase — `send_alert_sync()`, `CircuitBreakerService`, `get_supabase()`, `register_jobs()`, migration pattern, `app.state.scheduler`

### Secondary (MEDIUM confidence)
- [OpenAI PyPI page](https://pypi.org/pypi/openai/json) — confirmed latest version 2.21.0
- [pgvector cosine distance GitHub issue #12244](https://github.com/supabase/supabase/issues/12244) — confirms `<=>` is distance not similarity; `1 - distance = similarity`
- [Anthropic pricing calculator (Feb 2026) — CostGoat](https://costgoat.com/pricing/claude-api) — corroborates official pricing

### Tertiary (LOW confidence)
- WebSearch results on APScheduler + Anthropic sync/async patterns — consistent with official docs but no single authoritative source for the combined pattern; treat as confirmatory

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — anthropic 0.83.0 and openai 2.21.0 confirmed on PyPI; pricing confirmed on official docs
- Architecture patterns: HIGH — Claude API call pattern verified against SDK; pgvector SQL function pattern verified against Supabase docs; PTB ConversationHandler and lifecycle patterns verified against official docs
- Pitfalls: HIGH (distance vs similarity, updater(None), asyncio.run() in thread) — all verified against official sources; MEDIUM (rejection_constraints schema, entry_points workaround) — design decisions, not technical facts
- Mood flow design: MEDIUM — ConversationHandler alternative (manual state dict) is a design recommendation based on verified PTB docs; not a single canonical source for bot-initiated flows

**Research date:** 2026-02-20
**Valid until:** 2026-03-22 (30 days — anthropic and openai SDKs move fast but the API contract is stable; PTB v21 is stable)
