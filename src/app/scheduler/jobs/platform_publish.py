"""
APScheduler job: publish approved video to a single social media platform.

Fired at the platform's peak hour (scheduled by schedule_platform_publishes() in
publishing.py, which is called from the approval handler in approval_flow.py).

On success:
  - Inserts 'published' row into publish_events with ayrshare_post_id + platform_post_id
  - Sends Telegram success notification to creator
  - Schedules verify_publish_job for 30 minutes later

On failure (after tenacity exhausts retries):
  - Inserts 'failed' row into publish_events with error_message
  - Sends Telegram fallback message: Supabase Storage video URL + platform-specific copy
  - Does NOT raise (APScheduler logs exception, creator already notified via Telegram)
"""
import logging
from datetime import datetime, timedelta, timezone

import pytz
from apscheduler.triggers.date import DateTrigger

from app.services.database import get_supabase
from app.services.publishing import PublishingService
from app.services.telegram import (
    send_platform_failure_sync,
    send_platform_success_sync,
)
from app.settings import get_settings

logger = logging.getLogger(__name__)

# Module-level scheduler — injected by registry.py via set_scheduler() (same pattern as video_poller)
_scheduler = None


def set_scheduler(scheduler) -> None:
    """Called by registry.py before job registration."""
    global _scheduler
    _scheduler = scheduler


def publish_to_platform_job(
    content_history_id: str,
    platform: str,
    video_url: str,
) -> None:
    """
    Publish the approved video to a single platform.

    Args are picklable (str only) — required for SQLAlchemyJobStore serialization.
    """
    supabase = get_supabase()
    settings = get_settings()

    # Load platform-specific copy from content_history
    row_result = supabase.table("content_history").select(
        "post_copy_tiktok, post_copy_instagram, post_copy_facebook, post_copy_youtube, post_copy"
    ).eq("id", content_history_id).single().execute()
    row = row_result.data

    copy_key = f"post_copy_{platform}"
    post_copy = row.get(copy_key) or row.get("post_copy", "")

    try:
        response = PublishingService().publish(
            platform=platform,
            post_text=post_copy,
            video_url=video_url,
        )

        ayrshare_post_id = response.get("postId", "")
        post_ids = response.get("postIds", {})
        platform_post_id = str(post_ids.get(platform, ""))

        # Persist publish event — verification job queries this table
        supabase.table("publish_events").insert({
            "content_history_id": content_history_id,
            "platform": platform,
            "ayrshare_post_id": ayrshare_post_id,
            "platform_post_id": platform_post_id,
            "status": "published",
            "scheduled_at": datetime.now(tz=timezone.utc).isoformat(),
            "published_at": datetime.now(tz=timezone.utc).isoformat(),
        }).execute()

        # Notify creator of successful publish
        send_platform_success_sync(platform, content_history_id)

        # Schedule verification job 30 minutes from now
        verify_job_id = f"verify_{content_history_id}_{platform}"
        from app.scheduler.jobs.publish_verify import verify_publish_job

        run_at = datetime.now(tz=timezone.utc) + timedelta(minutes=30)
        _scheduler.add_job(
            verify_publish_job,
            trigger=DateTrigger(run_date=run_at),
            args=[content_history_id, platform, ayrshare_post_id],
            id=verify_job_id,
            name=f"Verify {platform} for {content_history_id[:8]}",
            replace_existing=True,
        )
        logger.info(
            "Published %s for content_history_id=%s: ayrshare_post_id=%s",
            platform, content_history_id[:8], ayrshare_post_id,
        )

    except Exception as exc:
        error_str = str(exc)[:500]
        logger.error("Failed to publish %s for content_history_id=%s: %s", platform, content_history_id[:8], error_str)

        # Persist failure event
        supabase.table("publish_events").insert({
            "content_history_id": content_history_id,
            "platform": platform,
            "status": "failed",
            "error_message": error_str,
        }).execute()

        # Send fallback: video URL + platform copy (PUBL-04 — link-based, not file upload)
        send_platform_failure_sync(
            platform=platform,
            video_url=video_url,
            post_copy=post_copy,
            error_message=error_str,
        )
