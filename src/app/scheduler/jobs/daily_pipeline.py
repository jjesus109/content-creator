import logging
from app.logging_config import PipelineLogger
from app.services.circuit_breaker import CircuitBreakerService
from app.services.database import get_supabase
from app.services.telegram import send_alert_sync
from app.services.embeddings import EmbeddingService
from app.services.similarity import SimilarityService
from app.services.scene_generation import SceneEngine
from app.services.music_matcher import MusicMatcher
from app.services.prompt_generation import PromptGenerationService
from app.settings import get_settings

logger = logging.getLogger(__name__)

MAX_RETRIES = 2      # 2 retries = 3 total attempts (original + angle retry + topic retry)
                     # Planner decision: balances cost (~3 embed + ~3 scene gen calls max) vs freshness


def daily_pipeline_job() -> None:
    """
    Daily scene generation pipeline (v2.0) — registered as 'daily_pipeline_trigger' in registry.py.

    Execution order:
    0. Mark any unanswered 'ready' rows from previous pipeline runs as approval_timeout
    1. Circuit breaker check (abort if tripped)
    2. Initialize scene generation services (SceneEngine, MusicMatcher, EmbeddingService, SimilarityService)
    3. Load active scene rejection constraints
    4. For each attempt (max 3):
       a. Generate scene prompt + caption via GPT-4o (SceneEngine.pick_scene)
       b. Record scene generation cost to circuit breaker
       c. Embed scene prompt for anti-repetition check
       d. Anti-repetition check (7-day window, 0.78 threshold); gated by scene_anti_repetition_enabled
       e. Select music track matching scene mood (MusicMatcher.pick_track)
       f. Generate unified animated-style prompt via PromptGenerationService (GPT-4o)
       g. Record unified prompt generation cost to circuit breaker
       h. Kling circuit breaker check; submit unified_prompt to Kling AI 3.0 via fal.ai
       i. Save unified_prompt (as script_text) + scene_prompt + music_track_id + scene_embedding + kling_job_id to content_history
       j. Register APScheduler polling fallback
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

    # Step 2 (v2.0): Initialize scene generation services
    settings = get_settings()
    scene_engine = SceneEngine(supabase)
    music_matcher = MusicMatcher(supabase)
    embedding_svc = EmbeddingService()
    similarity_svc = SimilarityService(supabase)
    prompt_gen_svc = PromptGenerationService()

    plog.extra["pipeline_step"] = "scene_gen"
    plog.info("Daily pipeline starting (v2.0 Scene Engine).")

    # Step 3 (v2.0): Load active scene rejection constraints
    rejection_constraints = scene_engine.load_active_scene_rejections()
    if rejection_constraints:
        plog.info("Active scene rejection constraints: %d", len(rejection_constraints))

    # Step 4 (v2.0): Scene generation retry loop
    for attempt in range(MAX_RETRIES + 1):
        plog.info("Scene engine attempt %d/%d", attempt + 1, MAX_RETRIES + 1)

        # 4a: Generate scene prompt + caption via GPT-4o (single call)
        try:
            scene_prompt, caption, mood, scene_cost = scene_engine.pick_scene(
                attempt=attempt,
                rejection_constraints=rejection_constraints,
            )
        except Exception as exc:
            plog.error("SceneEngine failed: %s", exc)
            send_alert_sync(f"SceneEngine falló al generar escena: {exc}. Pipeline detenido.")
            return

        plog.info("Scene selected: mood=%s, caption='%s'", mood, caption)

        # 4b: Record scene generation cost to circuit breaker
        if not cb.record_attempt(scene_cost):
            plog.error("Circuit breaker tripped during scene generation.")
            send_alert_sync("Circuit breaker disparado durante generación de escena. Pipeline detenido.")
            return

        # 4c: Embed scene prompt for anti-repetition check
        scene_embedding, embed_cost = embedding_svc.generate(scene_prompt)
        if not cb.record_attempt(embed_cost):
            plog.error("Circuit breaker tripped during scene embedding.")
            send_alert_sync("Circuit breaker disparado durante embedding de escena. Pipeline detenido.")
            return

        # 4d: Anti-repetition check (7-day window, 75-80% threshold)
        is_scene_similar = similarity_svc.is_too_similar_scene(scene_embedding)
        if is_scene_similar:
            if settings.scene_anti_repetition_enabled:
                plog.info("Scene too similar to recent content — retrying (attempt %d)", attempt + 1)
                if attempt < MAX_RETRIES:
                    continue
                else:
                    plog.error(
                        "All %d scene attempts rejected by anti-repetition check. Manual intervention needed.",
                        MAX_RETRIES + 1,
                    )
                    send_alert_sync(
                        f"Pipeline v2.0: todos los intentos ({MAX_RETRIES + 1}) rechazados por "
                        "similaridad de escena. Intervención manual requerida."
                    )
                    return
            else:
                plog.warning(
                    "Scene similarity detected (%.0f%% threshold) but anti-repetition is in "
                    "log-only mode (scene_anti_repetition_enabled=False). Proceeding.",
                    0.78 * 100,
                )

        # 4e (v2.0): Select music track matching scene mood
        try:
            music_track = music_matcher.pick_track(mood=mood, target_platform="tiktok")
            plog.info(
                "Music track selected: '%s' by %s (bpm=%d)",
                music_track.get("title"), music_track.get("artist"), music_track.get("bpm", 0),
            )
        except ValueError as exc:
            plog.error("MusicMatcher failed: %s", exc)
            send_alert_sync(
                f"No se encontró música para mood='{mood}'. "
                "Verifica music_pool en la base de datos. Pipeline detenido."
            )
            return

        # 4f (v3.0): Generate unified animated-style prompt via PromptGenerationService
        unified_prompt = prompt_gen_svc.generate_unified_prompt(scene_prompt)
        plog.info(
            "Unified prompt generated (chars=%d, cost=$%.6f)",
            len(unified_prompt),
            prompt_gen_svc._last_cost_usd,
        )
        if prompt_gen_svc._last_cost_usd > 0.0:
            if not cb.record_attempt(prompt_gen_svc._last_cost_usd):
                plog.error("Circuit breaker tripped during unified prompt generation.")
                send_alert_sync("Circuit breaker disparado durante generación de prompt unificado. Pipeline detenido.")
                return

        # 4h: Kling CB check (unchanged from Phase 9)
        from app.services.kling import KlingService
        from app.scheduler.jobs.video_poller import register_video_poller
        from app.services.kling_circuit_breaker import KlingCircuitBreakerService

        kling_cb = KlingCircuitBreakerService(supabase)
        if kling_cb.is_open():
            plog.warning("Kling circuit breaker is open — skipping video generation for today.")
            send_alert_sync(
                "Kling AI circuit breaker activo — pipeline de video detenido hoy. "
                "Escribe /resume para reanudar."
            )
            return

        kling_svc = KlingService()
        plog.extra["pipeline_step"] = "kling_submit"
        try:
            kling_job_id = kling_svc.submit(unified_prompt)
            plog.info("Kling job submitted: job_id=%s", kling_job_id)
        except Exception as exc:
            plog.error("Kling submission failed: %s", exc)
            send_alert_sync(f"Error al enviar escena a Kling AI: {exc}. Escena guardada sin video.")
            _save_to_content_history(
                supabase, scene_prompt, caption, scene_embedding,
                music_track_id=music_track["id"],
                unified_prompt=unified_prompt,
            )
            return

        # Save scene + Kling job ID + music track atomically
        new_id = _save_to_content_history(
            supabase,
            scene_prompt=scene_prompt,
            caption=caption,
            scene_embedding=scene_embedding,
            music_track_id=music_track["id"],
            kling_job_id=kling_job_id,
            unified_prompt=unified_prompt,
        )
        plog.extra["content_history_id"] = new_id or ""
        plog.extra["pipeline_step"] = "pipeline_complete"

        register_video_poller(kling_job_id)

        plog.info(
            "Daily pipeline (v2.0) complete. Scene saved. Kling render in progress: %s",
            kling_job_id,
        )
        return  # Success


def _save_to_content_history(
    supabase,
    scene_prompt: str,
    caption: str,
    scene_embedding: list[float],
    music_track_id: str | None = None,
    kling_job_id: str | None = None,
    unified_prompt: str | None = None,
) -> str | None:
    """
    Persist the generated scene with its embedding to content_history.
    v2.0: uses scene_prompt, caption, scene_embedding, music_track_id.
    v3.0: unified_prompt overwrites script_text (Phase 12 decision); scene_prompt column retains raw SceneEngine output.
    script_text and topic_summary set for backward compatibility.
    Returns the new content_history id, or None on failure.
    """
    from app.models.video import VideoStatus
    # unified_prompt overwrites script_text (Phase 12 decision); scene_prompt column retains raw SceneEngine output
    effective_script = unified_prompt if unified_prompt else scene_prompt
    row = {
        "script_text": effective_script,
        "topic_summary": caption[:100] if caption else "",  # backward compat
        "embedding": scene_embedding,   # reuse existing embedding column for scene embedding
        "scene_prompt": scene_prompt,   # raw SceneEngine output preserved
        "caption": caption,
        "scene_embedding": scene_embedding,
    }
    if music_track_id:
        row["music_track_id"] = music_track_id
    if kling_job_id:
        row["kling_job_id"] = kling_job_id
        row["video_status"] = VideoStatus.KLING_PENDING.value
    try:
        result = supabase.table("content_history").insert(row).execute()
        new_id = result.data[0]["id"] if result.data else None
        logger.info(
            "Saved scene to content_history. caption: %s",
            caption[:60] if caption else "(none)",
            extra={"pipeline_step": "pipeline_complete", "content_history_id": new_id or ""},
        )
        return new_id
    except Exception as e:
        logger.error(
            "Failed to save scene to content_history: %s", e,
            extra={"pipeline_step": "pipeline_error", "content_history_id": ""},
        )
        send_alert_sync(f"Escena generada pero no guardada en DB: {e}. Revisa manualmente.")
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
