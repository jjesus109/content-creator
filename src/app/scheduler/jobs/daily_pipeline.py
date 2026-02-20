import logging
from app.services.circuit_breaker import CircuitBreakerService
from app.services.database import get_supabase
from app.services.telegram import send_alert_sync
from app.services.mood import MoodService
from app.services.embeddings import EmbeddingService
from app.services.similarity import SimilarityService
from app.services.script_generation import ScriptGenerationService

logger = logging.getLogger(__name__)

MAX_RETRIES = 2      # 2 retries = 3 total attempts (original + angle retry + topic retry)
                     # Planner decision: balances cost (~3 embed + ~3 topic gen calls max) vs freshness


def daily_pipeline_job() -> None:
    """
    Daily script generation pipeline — registered as 'daily_pipeline_trigger' in registry.py.

    Execution order:
    1. Circuit breaker check (abort if tripped)
    2. Load current week's mood profile (defaults if none set)
    3. For each attempt (max 3):
       a. Generate topic summary (short phrase for embedding)
       b. Embed the topic summary — report cost to CB
       c. Check similarity against content_history — retry on hit
       d. (Pass) Generate full script — report cost to CB
       e. Summarize if over target word count — report cost to CB
       f. Save to content_history with embedding
    4. If all retries exhausted — send creator alert
    """
    supabase = get_supabase()
    cb = CircuitBreakerService(supabase)

    # Step 1: Circuit breaker check
    if cb.is_tripped():
        logger.warning("Daily pipeline skipped — circuit breaker is tripped.")
        send_alert_sync("Pipeline diario omitido: el circuit breaker esta activo. Revisa el gasto del dia.")
        return

    # Step 2: Load mood profile
    mood = MoodService(supabase).get_current_week_mood()
    target_words = mood["target_words"]
    logger.info("Daily pipeline starting. Mood: %s, target_words: %d", mood, target_words)

    # Initialize services
    embedding_svc = EmbeddingService()
    similarity_svc = SimilarityService(supabase)
    script_svc = ScriptGenerationService(supabase)

    # Step 3: Load rejection constraints (Phase 2: empty; Phase 4 writes to this table)
    rejection_constraints = script_svc.load_active_rejection_constraints()
    if rejection_constraints:
        logger.info("Active rejection constraints: %d", len(rejection_constraints))

    # Step 4: Retry loop
    for attempt in range(MAX_RETRIES + 1):
        logger.info("Pipeline attempt %d/%d", attempt + 1, MAX_RETRIES + 1)

        # 4a: Generate topic summary
        topic_summary, topic_cost = script_svc.generate_topic_summary(
            mood=mood,
            attempt=attempt,
            rejection_constraints=rejection_constraints,
        )
        logger.info("Topic summary (attempt %d): %s", attempt + 1, topic_summary)

        # 4b: Embed topic summary — report cost to circuit breaker
        if not cb.record_attempt(topic_cost):
            logger.error("Circuit breaker tripped during topic generation.")
            send_alert_sync("Circuit breaker disparado durante generacion de tema. Pipeline detenido.")
            return

        embedding, embed_cost = embedding_svc.generate(topic_summary)

        if not cb.record_attempt(embed_cost):
            logger.error("Circuit breaker tripped during embedding.")
            send_alert_sync("Circuit breaker disparado durante embedding. Pipeline detenido.")
            return

        # 4c: Similarity check
        if similarity_svc.is_too_similar(embedding):
            logger.info("Topic too similar to existing content — retrying (attempt %d)", attempt + 1)
            if attempt < MAX_RETRIES:
                continue  # retry with next attempt's instructions
            else:
                # All retries exhausted
                logger.error("All %d attempts exhausted due to similarity. Manual intervention needed.", MAX_RETRIES + 1)
                send_alert_sync(
                    f"Pipeline diario: todos los intentos ({MAX_RETRIES + 1}) rechazados por similaridad. "
                    "Por favor interviene manualmente o acepta saltarte el dia de hoy."
                )
                return

        # 4d: Generate full script
        script, gen_cost = script_svc.generate_script(
            topic_summary=topic_summary,
            mood=mood,
            target_words=target_words,
            rejection_constraints=rejection_constraints,
        )

        if not cb.record_attempt(gen_cost):
            logger.error("Circuit breaker tripped during script generation.")
            send_alert_sync("Circuit breaker disparado durante generacion del guion. Pipeline detenido.")
            return

        # 4e: Word count guard — auto-summarize if over limit (SCRP-03)
        script, sum_cost = script_svc.summarize_if_needed(script, target_words)
        if sum_cost > 0.0:
            logger.info("Script summarized to fit target word count.")
            cb.record_attempt(sum_cost)  # summarization cost tracked (non-fatal if CB trips here)

        # 4f: Save to content_history
        _save_to_content_history(supabase, script, topic_summary, embedding, mood)
        logger.info("Daily pipeline complete. Script saved to content_history.")
        return  # Success


def _save_to_content_history(supabase, script: str, topic_summary: str, embedding: list[float], mood: dict) -> None:
    """
    Persist the generated script with its embedding to content_history.
    The embedding is stored so future similarity checks can compare against this script.
    NOTE: mood_profile is NOT a column on content_history — do not insert it here.
    """
    try:
        supabase.table("content_history").insert({
            "script_text": script,
            "topic_summary": topic_summary,
            "embedding": embedding,          # list[float] — Supabase client handles vector serialization
        }).execute()
        logger.info("Saved script to content_history. topic: %s", topic_summary[:60])
    except Exception as e:
        logger.error("Failed to save script to content_history: %s", e)
        # Do not re-raise — the script was generated; losing the DB write is preferable to alerting as failure
        send_alert_sync(f"Script generado pero no guardado en DB: {e}. Revisa manualmente.")
