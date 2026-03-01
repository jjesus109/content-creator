"""
Approval timeout job — fires 24h after approval message sent; sends last-chance Telegram message
if no creator response. If the creator already approved, exits silently without sending any message.

Design notes:
  - schedule_approval_timeout() is called by send_approval_message_sync() immediately after the
    approval message is delivered. It registers a DateTrigger job 24h in the future.
  - check_approval_timeout_job() checks the approval_events table for a response. If none exists,
    it sends a last-chance Telegram alert AND re-sends the full approval message with the keyboard.
  - The job ID 'approval_timeout_{content_history_id}' allows handle_approve() to cancel the job
    via scheduler.remove_job() before it fires — preventing spurious last-chance messages.
  - Module-level _scheduler follows the same pattern as video_poller.py.
"""
import logging
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

# Module-level scheduler reference — set by registry.py via set_scheduler() before any jobs run.
# Same pattern as video_poller.py.
_scheduler = None


def set_scheduler(scheduler) -> None:
    """Called by registry.py before job registration to inject the scheduler reference."""
    global _scheduler
    _scheduler = scheduler


def schedule_approval_timeout(content_history_id: str) -> None:
    """
    Schedule a 24-hour timeout job for the given content_history row.

    If _scheduler is not yet set (e.g. dev/test environment), logs a warning and returns silently.
    Uses replace_existing=True so re-scheduling is idempotent if called more than once per row.
    """
    from apscheduler.triggers.date import DateTrigger

    if _scheduler is None:
        logger.warning(
            "schedule_approval_timeout: _scheduler is None — cannot schedule timeout for %s",
            content_history_id[:8],
        )
        return

    run_at = datetime.now(tz=timezone.utc) + timedelta(hours=24)
    _scheduler.add_job(
        check_approval_timeout_job,
        trigger=DateTrigger(run_date=run_at),
        args=[content_history_id],
        id=f"approval_timeout_{content_history_id}",
        name=f"Approval 24h timeout for {content_history_id[:8]}",
        replace_existing=True,
    )
    logger.info(
        "Approval timeout job scheduled for content_history_id=%s, fires at %s",
        content_history_id[:8],
        run_at.isoformat(),
    )


def check_approval_timeout_job(content_history_id: str) -> None:
    """
    24-hour timeout job body. Called by APScheduler.

    Steps:
      1. Check approval_events for an existing response. If found, exit silently.
      2. Fetch video_url from content_history.
      3. Send a last-chance alert message to the creator.
      4. Re-send the full approval message with keyboard so the creator can still act.
    """
    from app.services.database import get_supabase

    supabase = get_supabase()

    # Step 1: Check if creator already responded
    events_result = (
        supabase.table("approval_events")
        .select("id")
        .eq("content_history_id", content_history_id)
        .execute()
    )
    if events_result.data:
        logger.info(
            "approval_timeout_job: content_history_id=%s already actioned, skipping.",
            content_history_id[:8],
        )
        return

    # Step 2: Fetch video_url from content_history
    row_result = (
        supabase.table("content_history")
        .select("video_url")
        .eq("id", content_history_id)
        .single()
        .execute()
    )
    video_url = row_result.data.get("video_url", "") if row_result.data else ""

    # Step 3: Send last-chance alert
    # Lazy import avoids circular import through telegram.py
    from app.services.telegram import send_alert_sync, send_approval_message_sync

    send_alert_sync(
        "AVISO: Tu video de hoy aun no ha sido aprobado. "
        "Tienes hasta el proximo pipeline para aprobar o sera omitido."
    )

    # Step 4: Re-send full approval message with keyboard
    send_approval_message_sync(content_history_id, video_url)

    logger.info(
        "approval_timeout_job: last-chance message sent.",
        extra={
            "pipeline_step": "approval_timeout",
            "content_history_id": content_history_id,
        },
    )
