import logging
import fal_client
from datetime import datetime, timedelta, timezone
from app.settings import get_settings
from app.services.database import get_supabase
from app.services.telegram import send_alert_sync
from app.models.video import VideoStatus

logger = logging.getLogger(__name__)

POLL_TIMEOUT_MINUTES = 20
POLLER_JOB_ID_PREFIX = "video_poller_"

# Module-level scheduler reference — set by registry.py via set_scheduler() before any jobs run.
# Required for APScheduler SQLAlchemyJobStore serialization: lambdas/closures are not picklable,
# so the scheduler cannot be passed as a parameter or captured in a closure.
_scheduler = None


def set_scheduler(scheduler) -> None:
    """Called by registry.py before job registration to inject the scheduler reference."""
    global _scheduler
    _scheduler = scheduler


def video_poller_job(video_id: str, submitted_at: datetime) -> None:
    """
    APScheduler interval job. Runs every 60 seconds.
    Checks Kling/fal.ai render status for video_id via fal_client.status() (sync).
    Self-cancels when render is completed, failed, or exhausted retries.
    video_id and submitted_at are passed via APScheduler args= for pickle serializability.
    """
    elapsed = datetime.now(tz=timezone.utc) - submitted_at

    # Timeout guard: 20 minutes from submission
    if elapsed > timedelta(minutes=POLL_TIMEOUT_MINUTES):
        logger.error(
            "Kling render timeout (20 min) for job_id=%s. Elapsed: %s",
            video_id, elapsed
        )
        _retry_or_fail(video_id)
        return

    try:
        # fal_client.status() is synchronous — correct for APScheduler ThreadPoolExecutor
        settings = get_settings()

        status = fal_client.status(
            settings.kling_model_version,
            video_id,
            with_logs=False,
        )
        logger.info(
            "Kling poll: job_id=%s status=%s elapsed=%s",
            video_id, status.status, elapsed,
        )

        if status.status == "completed":
            # Extract video URL from fal.ai response
            video_url = status.response["video"]["url"]
            logger.info(
                "Poller: Kling render complete for job_id=%s, triggering processing",
                video_id,
            )
            from app.services.kling import _process_completed_render
            _process_completed_render(video_id, video_url)
            _cancel_self(video_id)

        elif status.status == "failed":
            error_msg = str(status.response.get("error", "unknown"))
            logger.error(
                "Poller: Kling render failed for job_id=%s error=%s",
                video_id, error_msg,
            )
            from app.services.kling import _handle_render_failure
            _handle_render_failure(video_id, error_msg)
            _cancel_self(video_id)

        # "queued" or "in_progress" — continue polling on next interval

    except Exception as exc:
        logger.error("Kling poller error for job_id=%s: %s", video_id, exc)
        # Do NOT cancel — retry on next interval; transient errors are recoverable


def _retry_or_fail(video_id: str) -> None:
    """
    Retry-once logic for 20-minute timeout.
    Uses video_status as sentinel:
    - kling_pending or rendering → first timeout: resubmit to Kling, set kling_pending_retry
    - kling_pending_retry → second timeout: mark failed, alert creator
    """
    from app.services.kling import KlingService
    supabase = get_supabase()

    result = supabase.table("content_history").select(
        "script_text, video_status"
    ).eq("kling_job_id", video_id).single().execute()

    if not result.data:
        logger.error("_retry_or_fail: no row found for kling_job_id=%s — cannot retry", video_id)
        _cancel_self(video_id)
        return

    current_status = result.data.get("video_status")
    script_text = result.data.get("script_text")

    is_first_timeout = current_status in (
        VideoStatus.KLING_PENDING.value,
        VideoStatus.RENDERING.value,
    )
    is_second_timeout = current_status == VideoStatus.KLING_PENDING_RETRY.value

    if is_first_timeout:
        logger.warning(
            "First Kling timeout for job_id=%s — retrying submission",
            video_id,
        )
        try:
            kling_svc = KlingService()
            new_job_id = kling_svc.submit(script_text=script_text)
            logger.info(
                "Kling retry submitted: old_job_id=%s new_job_id=%s",
                video_id, new_job_id,
            )
            supabase.table("content_history").update({
                "kling_job_id": new_job_id,
                "video_status": VideoStatus.KLING_PENDING_RETRY.value,
            }).eq("kling_job_id", video_id).execute()
            register_video_poller(new_job_id)
        except Exception as exc:
            logger.error("Kling retry submission failed for job_id=%s: %s", video_id, exc)
            supabase.table("content_history").update(
                {"video_status": VideoStatus.FAILED.value}
            ).eq("kling_job_id", video_id).execute()
            send_alert_sync(
                f"Timeout de render Kling para job_id={video_id}. "
                f"Reintento fallido: {exc}. Video del dia omitido."
            )
        finally:
            _cancel_self(video_id)

    elif is_second_timeout:
        logger.error(
            "Second Kling timeout for job_id=%s — marking failed, alerting creator",
            video_id,
        )
        supabase.table("content_history").update(
            {"video_status": VideoStatus.FAILED.value}
        ).eq("kling_job_id", video_id).execute()
        send_alert_sync(
            f"Render Kling agotado (2 intentos, 40 min) para job_id={video_id}. "
            "Video del dia omitido."
        )
        _cancel_self(video_id)

    else:
        logger.warning(
            "_retry_or_fail: unexpected status=%s for job_id=%s — cancelling poller",
            current_status, video_id,
        )
        _cancel_self(video_id)


def register_video_poller(video_id: str) -> None:
    """
    Register a 60-second interval job to poll Kling/fal.ai status for video_id.
    Uses predictable job_id so poller can cancel by ID: f"video_poller_{video_id}".
    video_id and submitted_at are passed via APScheduler args= — no closures, fully picklable.
    Called from daily_pipeline_job after Kling submission, and from _retry_or_fail on retry.
    """
    submitted_at = datetime.now(tz=timezone.utc)

    from apscheduler.triggers.interval import IntervalTrigger
    _scheduler.add_job(
        video_poller_job,
        args=[video_id, submitted_at],
        trigger=IntervalTrigger(seconds=60),
        id=f"{POLLER_JOB_ID_PREFIX}{video_id}",
        name=f"Kling poller for {video_id}",
        replace_existing=True,
    )
    logger.info("Registered video poller for job_id=%s", video_id)


def _cancel_self(video_id: str) -> None:
    """Cancel the poller job by predictable ID."""
    try:
        _scheduler.remove_job(f"{POLLER_JOB_ID_PREFIX}{video_id}")
    except Exception:
        pass  # Already removed — not an error
