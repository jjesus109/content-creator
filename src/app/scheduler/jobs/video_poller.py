import logging
import requests
from datetime import datetime, timedelta, timezone
from app.settings import get_settings
from app.services.database import get_supabase
from app.services.telegram import send_alert_sync
from app.models.video import VideoStatus

logger = logging.getLogger(__name__)

HEYGEN_STATUS_URL = "https://api.heygen.com/v1/video_status.get"
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
    Checks HeyGen render status for video_id.
    Self-cancels when render is completed, failed, or exhausted retries.
    video_id and submitted_at are passed via APScheduler args= for pickle serializability.
    """
    settings = get_settings()
    elapsed = datetime.now(tz=timezone.utc) - submitted_at

    # Timeout guard: 20 minutes from submission
    if elapsed > timedelta(minutes=POLL_TIMEOUT_MINUTES):
        logger.error(
            "HeyGen render timeout (20 min) for video_id=%s. Elapsed: %s",
            video_id, elapsed
        )
        _retry_or_fail(video_id)
        return

    try:
        response = requests.get(
            HEYGEN_STATUS_URL,
            params={"video_id": video_id},
            headers={"x-api-key": settings.heygen_api_key},
            timeout=15,
        )
        response.raise_for_status()
        data = response.json().get("data", {})
        status = data.get("status")
        logger.info("HeyGen poll: video_id=%s status=%s elapsed=%s", video_id, status, elapsed)

        if status == "completed":
            signed_url = data.get("video_url")
            logger.info("Poller: render complete for video_id=%s, triggering processing", video_id)
            from app.services.heygen import _process_completed_render
            _process_completed_render(video_id, signed_url)
            _cancel_self(video_id)

        elif status == "failed":
            error_msg = data.get("error") or "unknown"
            logger.error("Poller: HeyGen render failed for video_id=%s error=%s", video_id, error_msg)
            from app.services.heygen import _handle_render_failure
            _handle_render_failure(video_id, error_msg)
            _cancel_self(video_id)

        # pending / processing / waiting: do nothing — next interval will check again

    except Exception as exc:
        logger.error("Poller error for video_id=%s: %s", video_id, exc)
        # Do NOT cancel — retry on next interval; transient network errors are recoverable


def _retry_or_fail(video_id: str) -> None:
    """
    Retry-once logic for 20-minute timeout (locked decision: retry once, then alert and skip).

    Uses video_status as a sentinel:
    - If status is pending_render or rendering: this is the FIRST timeout.
      Resubmit same script to HeyGen, update heygen_job_id, reset status to
      pending_render_retry, register a new poller. Cancel current poller.
    - If status is pending_render_retry: this is the SECOND timeout.
      Mark failed, alert creator via Telegram, cancel poller.
    """
    from app.services.heygen import HeyGenService
    supabase = get_supabase()

    # Read current row to get script_text and video_status
    result = supabase.table("content_history").select(
        "script_text, background_url, video_status"
    ).eq("heygen_job_id", video_id).single().execute()

    if not result.data:
        logger.error("_retry_or_fail: no row found for heygen_job_id=%s — cannot retry", video_id)
        _cancel_self(video_id)
        return

    current_status = result.data.get("video_status")
    script_text = result.data.get("script_text")
    background_url = result.data.get("background_url")

    is_first_timeout = current_status in (
        VideoStatus.PENDING_RENDER.value,
        VideoStatus.RENDERING.value,
    )
    is_second_timeout = current_status == VideoStatus.PENDING_RENDER_RETRY.value

    if is_first_timeout:
        logger.warning(
            "First timeout for video_id=%s — retrying HeyGen submission (per user decision)",
            video_id,
        )
        try:
            heygen_svc = HeyGenService()
            new_job_id = heygen_svc.submit(script_text=script_text, background_url=background_url)
            logger.info("Retry submitted to HeyGen: old_job_id=%s new_job_id=%s", video_id, new_job_id)

            # Update DB: new heygen_job_id + status sentinel marking retry in progress
            supabase.table("content_history").update({
                "heygen_job_id": new_job_id,
                "video_status": VideoStatus.PENDING_RENDER_RETRY.value,
            }).eq("heygen_job_id", video_id).execute()

            # Register a new poller for the new job ID
            register_video_poller(new_job_id)

        except Exception as exc:
            logger.error("HeyGen retry submission failed for video_id=%s: %s", video_id, exc)
            # Retry submission itself failed — fall through to failure path
            supabase.table("content_history").update(
                {"video_status": VideoStatus.FAILED.value}
            ).eq("heygen_job_id", video_id).execute()
            send_alert_sync(
                f"Timeout de render HeyGen para video_id={video_id}. "
                f"Reintento fallido: {exc}. Video del dia omitido."
            )

        finally:
            # Cancel the current poller regardless of outcome — new poller registered above
            _cancel_self(video_id)

    elif is_second_timeout:
        logger.error(
            "Second timeout for video_id=%s — marking failed, alerting creator (per user decision)",
            video_id,
        )
        supabase.table("content_history").update(
            {"video_status": VideoStatus.FAILED.value}
        ).eq("heygen_job_id", video_id).execute()
        send_alert_sync(
            f"Render HeyGen agotado (2 intentos, 40 min) para video_id={video_id}. "
            "Video del dia omitido."
        )
        _cancel_self(video_id)

    else:
        # Unexpected status (e.g., already processing/ready/failed) — cancel and do nothing
        logger.warning(
            "_retry_or_fail: unexpected status=%s for video_id=%s — cancelling poller",
            current_status, video_id,
        )
        _cancel_self(video_id)


def register_video_poller(video_id: str) -> None:
    """
    Register a 60-second interval job to poll HeyGen status for video_id.
    Uses predictable job_id so webhook can cancel by ID: f"video_poller_{video_id}".
    video_id and submitted_at are passed via APScheduler args= — no closures, fully picklable.
    Called from daily_pipeline_job after HeyGen submission, and from _retry_or_fail on retry.
    """
    submitted_at = datetime.now(tz=timezone.utc)

    from apscheduler.triggers.interval import IntervalTrigger
    _scheduler.add_job(
        video_poller_job,
        args=[video_id, submitted_at],
        trigger=IntervalTrigger(seconds=60),
        id=f"{POLLER_JOB_ID_PREFIX}{video_id}",
        name=f"HeyGen poller for {video_id}",
        replace_existing=True,
    )
    logger.info("Registered video poller for video_id=%s", video_id)


def _cancel_self(video_id: str) -> None:
    """Cancel the poller job by predictable ID."""
    try:
        _scheduler.remove_job(f"{POLLER_JOB_ID_PREFIX}{video_id}")
    except Exception:
        pass  # Already removed (webhook fired first) — not an error
