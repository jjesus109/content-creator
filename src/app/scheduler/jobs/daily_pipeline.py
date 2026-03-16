import logging
from app.logging_config import PipelineLogger
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
    0. Mark any unanswered 'ready' rows from previous pipeline runs as approval_timeout
    1. Circuit breaker check (abort if tripped)
    2. Load current week's mood profile (defaults if none set)
    3. For each attempt (max 3):
       a. Generate topic summary (short phrase for embedding)
       b. Embed the topic summary — report cost to CB
       c. Check similarity against content_history — retry on hit
       d. (Pass) Generate full script — report cost to CB
       e. Summarize if over target word count — report cost to CB
       f. Submit to HeyGen, save to content_history with embedding + heygen_job_id, register poller
    4. If all retries exhausted — send creator alert
    """
    # Step 0: Mark any unanswered 'ready' rows from previous pipeline runs as approval_timeout
    _expire_stale_approvals()

    supabase = get_supabase()
    cb = CircuitBreakerService(supabase)
    plog = PipelineLogger(logger, {"pipeline_step": "pipeline_start", "content_history_id": ""})

    # Step 1: Circuit breaker check
    if cb.is_tripped():
        plog.warning("Daily pipeline skipped — circuit breaker is tripped.")
        send_alert_sync("Pipeline diario omitido: el circuit breaker esta activo. Revisa el gasto del dia.")
        return

    if cb.is_daily_halted():
        plog.extra["pipeline_step"] = "pipeline_halt_check"
        plog.warning(
            "daily_pipeline_job: circuit breaker daily halt active — skipping. Send /resume to unblock.",
        )
        return

    # Step 2: Load mood profile
    mood = MoodService(supabase).get_current_week_mood()
    target_words = mood["target_words"]
    plog.extra["pipeline_step"] = "script_gen"
    plog.info("Daily pipeline starting. Mood: %s, target_words: %d", mood, target_words)

    # Initialize services
    embedding_svc = EmbeddingService()
    similarity_svc = SimilarityService(supabase)
    script_svc = ScriptGenerationService(supabase)

    # Step 3: Load rejection constraints (Phase 2: empty; Phase 4 writes to this table)
    rejection_constraints = script_svc.load_active_rejection_constraints()
    if rejection_constraints:
        plog.info("Active rejection constraints: %d", len(rejection_constraints))

    # Step 4: Retry loop
    for attempt in range(MAX_RETRIES + 1):
        plog.info("Pipeline attempt %d/%d", attempt + 1, MAX_RETRIES + 1)

        # 4a: Generate topic summary
        topic_summary, topic_cost = script_svc.generate_topic_summary(
            mood=mood,
            attempt=attempt,
            rejection_constraints=rejection_constraints,
        )
        plog.info("Topic summary (attempt %d): %s", attempt + 1, topic_summary)

        # 4b: Embed topic summary — report cost to circuit breaker
        if not cb.record_attempt(topic_cost):
            plog.error("Circuit breaker tripped during topic generation.")
            send_alert_sync("Circuit breaker disparado durante generacion de tema. Pipeline detenido.")
            return

        embedding, embed_cost = embedding_svc.generate(topic_summary)

        if not cb.record_attempt(embed_cost):
            plog.error("Circuit breaker tripped during embedding.")
            send_alert_sync("Circuit breaker disparado durante embedding. Pipeline detenido.")
            return

        # 4c: Similarity check
        if similarity_svc.is_too_similar(embedding):
            plog.info("Topic too similar to existing content — retrying (attempt %d)", attempt + 1)
            if attempt < MAX_RETRIES:
                continue  # retry with next attempt's instructions
            else:
                # All retries exhausted
                plog.error("All %d attempts exhausted due to similarity. Manual intervention needed.", MAX_RETRIES + 1)
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
            plog.error("Circuit breaker tripped during script generation.")
            send_alert_sync("Circuit breaker disparado durante generacion del guion. Pipeline detenido.")
            return

        # 4e: Word count guard — auto-summarize if over limit (SCRP-03)
        script, sum_cost = script_svc.summarize_if_needed(script, target_words)
        if sum_cost > 0.0:
            plog.info("Script summarized to fit target word count.")
            cb.record_attempt(sum_cost)  # summarization cost tracked (non-fatal if CB trips here)

        # 4f: Phase 3 — Submit to HeyGen after script is confirmed good
        from app.services.heygen import HeyGenService, pick_background_url
        from app.scheduler.jobs.video_poller import register_video_poller

        # Pick background — read last-used URL from most recent content_history row
        last_background_resp = supabase.table("content_history").select(
            "background_url"
        ).order("created_at", desc=True).limit(1).execute()
        last_background = (
            last_background_resp.data[0]["background_url"]
            if last_background_resp.data else None
        )
        background_url = pick_background_url(last_used_url=last_background)

        heygen_svc = HeyGenService()
        plog.extra["pipeline_step"] = "heygen_submit"
        try:
            heygen_job_id = heygen_svc.submit(script_text=script, background_url=background_url, title=topic_summary)
            plog.info("HeyGen job submitted: video_id=%s background=%s", heygen_job_id, background_url)
        except Exception as exc:
            plog.error("HeyGen submission failed: %s", exc)
            send_alert_sync(f"Error al enviar a HeyGen: {exc}. Script guardado sin video.")
            # Fail-soft: save script without HeyGen fields; do not abort pipeline
            _save_to_content_history(supabase, script, topic_summary, embedding, mood)
            return

        # Save script + HeyGen job ID atomically
        new_id = _save_to_content_history(
            supabase, script, topic_summary, embedding, mood,
            heygen_job_id=heygen_job_id,
            background_url=background_url,
        )
        plog.extra["content_history_id"] = new_id or ""
        plog.extra["pipeline_step"] = "pipeline_complete"

        # Register APScheduler polling fallback
        register_video_poller(heygen_job_id)

        plog.info("Daily pipeline complete. Script saved. HeyGen render in progress: %s", heygen_job_id)
        # Exit immediately — render happens asynchronously via webhook (primary) or poller (fallback)
        return  # Success


def _save_to_content_history(
    supabase, script: str, topic_summary: str, embedding: list[float], mood: dict,
    heygen_job_id: str | None = None,
    background_url: str | None = None,
) -> str | None:
    """
    Persist the generated script with its embedding to content_history.
    Phase 3 adds: heygen_job_id, video_status=pending_render, background_url.
    NOTE: mood_profile is NOT a column on content_history — do not insert it here.
    Returns the new content_history id, or None on failure.
    """
    from app.models.video import VideoStatus
    row = {
        "script_text": script,
        "topic_summary": topic_summary,
        "embedding": embedding,          # list[float] — Supabase client handles vector serialization
    }
    if heygen_job_id:
        row["heygen_job_id"] = heygen_job_id
        row["video_status"] = VideoStatus.PENDING_RENDER.value
        row["background_url"] = background_url
    try:
        result = supabase.table("content_history").insert(row).execute()
        new_id = result.data[0]["id"] if result.data else None
        logger.info(
            "Saved script to content_history. topic: %s",
            topic_summary[:60],
            extra={"pipeline_step": "pipeline_complete", "content_history_id": new_id or ""},
        )
        return new_id
    except Exception as e:
        logger.error(
            "Failed to save script to content_history: %s", e,
            extra={"pipeline_step": "pipeline_error", "content_history_id": ""},
        )
        send_alert_sync(f"Script generado pero no guardado en DB: {e}. Revisa manualmente.")
        return None


def _expire_stale_approvals() -> None:
    """
    Mark any content_history rows with video_status='ready' that have no corresponding
    approval_events row as 'approval_timeout'. Called at the start of every pipeline run.

    This prevents the pipeline from hanging indefinitely on unanswered approvals.
    Keeps queries simple: fetch ready IDs, then check each for approval_events individually.
    Supabase Python client has no JOIN query support, so we iterate IDs in a loop.
    """
    from app.models.video import VideoStatus

    supabase = get_supabase()

    # Fetch all content_history rows with video_status='ready'
    ready_result = (
        supabase.table("content_history")
        .select("id")
        .eq("video_status", VideoStatus.READY.value)
        .execute()
    )
    if not ready_result.data:
        return

    for row in ready_result.data:
        content_history_id = row["id"]

        # Check if there is a corresponding approval_events row
        events_result = (
            supabase.table("approval_events")
            .select("id")
            .eq("content_history_id", content_history_id)
            .execute()
        )
        if events_result.data:
            # Creator already responded — leave status as-is
            continue

        # No approval event found — mark as approval_timeout
        supabase.table("content_history").update(
            {"video_status": VideoStatus.APPROVAL_TIMEOUT.value}
        ).eq("id", content_history_id).execute()
        logger.info(
            "Marking content_history %s as approval_timeout — no creator response.",
            content_history_id,
            extra={"pipeline_step": "pipeline_start", "content_history_id": content_history_id},
        )


def trigger_immediate_rerun() -> None:
    """
    Schedule an immediate pipeline re-run after rejection.
    Uses APScheduler DateTrigger (one-shot job, fires 30 seconds from now).
    The 30-second delay gives APScheduler time to register the job before it fires.
    replace_existing=True ensures only one re-run is queued at a time.

    Called from: telegram/handlers/approval_flow.handle_cause() after rejection recorded.
    Uses _scheduler from video_poller module (already injected by registry.py at startup).
    """
    from apscheduler.triggers.date import DateTrigger
    from datetime import datetime, timedelta, timezone
    from app.scheduler.jobs.video_poller import _scheduler

    run_at = datetime.now(tz=timezone.utc) + timedelta(seconds=30)
    _scheduler.add_job(
        daily_pipeline_job,
        trigger=DateTrigger(run_date=run_at),
        id="rejection_rerun",
        name="Rejection-triggered pipeline re-run",
        replace_existing=True,
    )
    logger.info(
        "Rejection re-run scheduled for %s", run_at.isoformat(),
        extra={"pipeline_step": "pipeline_start", "content_history_id": ""},
    )
