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
    send_alert_sync,
    send_platform_failure_sync,
    send_platform_success_sync,
)
from app.settings import get_settings

logger = logging.getLogger(__name__)

# AI content disclosure label — VID-04 (TikTok/YouTube/Instagram compliance, EU AI Act Aug 2026)
AI_LABEL = "🤖 Creado con IA"

# Module-level scheduler — injected by registry.py via set_scheduler() (same pattern as video_poller)
_scheduler = None


def _apply_ai_label(post_text: str, platform: str) -> str:
    """
    Prepend AI disclosure label to platform content before publishing.

    Uniform label: "🤖 Creado con IA" across all platforms.
    YouTube: label goes in description only (not title) — avoids title length violation.
    All others: label prepended to caption.

    Per CONTEXT.md locked decision: caption prefix used for all platforms.
    TikTok native api_generated flag is skipped (label is sufficient for compliance).

    Args:
        post_text: Platform-specific caption/description. For YouTube, first line is title.
        platform:  One of: tiktok, instagram, facebook, youtube

    Returns:
        post_text with AI label prepended appropriately for the platform.
    """
    if platform == "youtube":
        # Split on first newline: title (line 0) stays clean; label goes in description
        lines = post_text.strip().split("\n", 1)
        title = lines[0] if lines else "Video"
        description = lines[1] if len(lines) > 1 else ""
        labeled_desc = f"{AI_LABEL}\n\n{description}" if description else AI_LABEL
        return f"{title}\n{labeled_desc}"

    # TikTok, Instagram, Facebook: prepend to caption
    if post_text:
        return f"{AI_LABEL}\n{post_text}"
    return AI_LABEL


def _check_music_license_cleared(
    supabase,
    content_history_row: dict,
    platform: str,
    content_history_id: str,
) -> bool:
    """
    Check if the music track assigned to this video is cleared for the given platform.

    Returns True if cleared or no track assigned (fail-open).
    Returns False if blocked; inserts publish_events 'blocked' row and sends Telegram alert.

    Per CONTEXT.md locked decisions:
    - Per-platform isolation: each platform job checks independently
    - Expiry logic: NULL = permanent; non-null compared to datetime.now(timezone.utc)
    - Fail-open on DB error and on missing music_track_id (backward compatibility)
    """
    music_track_id = content_history_row.get("music_track_id")
    if not music_track_id:
        logger.info(
            "No music_track_id for content_history_id=%s; skipping license gate (fail-open)",
            content_history_id,
        )
        return True

    # Query music_pool for this track's platform clearance and expiry
    try:
        track_result = supabase.table("music_pool").select(
            "title, artist, license_expires_at, "
            "platform_tiktok, platform_youtube, platform_instagram, platform_facebook"
        ).eq("id", music_track_id).single().execute()
        track = track_result.data
    except Exception as e:
        logger.error(
            "License gate: failed to query music_pool for track_id=%s: %s — allowing publish (fail-open)",
            music_track_id, e,
        )
        return True

    track_title = track.get("title", "Unknown")
    track_artist = track.get("artist", "Unknown")

    # Check platform clearance flag (e.g. platform_youtube, platform_instagram, platform_facebook)
    platform_flag = f"platform_{platform}"
    is_cleared = track.get(platform_flag, False)

    if not is_cleared:
        error_msg = (
            f"Music license not cleared for {platform}: "
            f"'{track_title}' by {track_artist}"
        )
        logger.warning("License gate blocked publish: %s (content_history_id=%s)", error_msg, content_history_id)

        # 1. Insert blocked row (before alert — so record exists even if alert fails)
        supabase.table("publish_events").insert({
            "content_history_id": content_history_id,
            "platform": platform,
            "status": "blocked",
            "error_message": error_msg,
            "scheduled_at": datetime.now(tz=timezone.utc).isoformat(),
        }).execute()

        # 2. Send Telegram alert with fix suggestion
        alert = (
            f"\U0001f6ab {platform.upper()} publish blocked\n\n"
            f"Track: '{track_title}' by {track_artist}\n"
            f"Reason: Not cleared for {platform}\n\n"
            f"Fix: Update music_pool platform_{platform} = true for this track, "
            f"or assign a different track to this video."
        )
        send_alert_sync(alert)
        return False

    # Check license expiry (NULL = permanent license; non-null = check against now_utc)
    expires_at = track.get("license_expires_at")
    if expires_at is not None:
        now_utc = datetime.now(timezone.utc)
        try:
            expiry = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
            if expiry <= now_utc:  # expired (fail-closed at exact expiry moment)
                error_msg = (
                    f"Music license expired for '{track_title}' "
                    f"(expired {expires_at})"
                )
                logger.warning("License gate blocked publish (expired): %s", error_msg)

                supabase.table("publish_events").insert({
                    "content_history_id": content_history_id,
                    "platform": platform,
                    "status": "blocked",
                    "error_message": error_msg,
                    "scheduled_at": datetime.now(tz=timezone.utc).isoformat(),
                }).execute()

                alert = (
                    f"\U0001f6ab {platform.upper()} publish blocked\n\n"
                    f"Track: '{track_title}' by {track_artist}\n"
                    f"Reason: License expired ({expires_at})\n\n"
                    f"Fix: Assign a track with an active license to this video."
                )
                send_alert_sync(alert)
                return False
        except (ValueError, AttributeError) as e:
            logger.error(
                "License gate: failed to parse expiry date '%s' for track '%s': %s — allowing publish (fail-open)",
                expires_at, track_title, e,
            )
            return True

    logger.info(
        "License gate: '%s' cleared for %s (content_history_id=%s)",
        track_title, platform, content_history_id,
    )
    return True


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
        "post_copy_tiktok, post_copy_instagram, post_copy_facebook, post_copy_youtube, post_copy, music_track_id"
    ).eq("id", content_history_id).single().execute()
    row = row_result.data

    copy_key = f"post_copy_{platform}"
    post_copy = row.get(copy_key) or row.get("post_copy", "")

    # AI content label: apply before publish (VID-04 — TikTok/YouTube/Instagram compliance)
    # Failure fallback: if _apply_ai_label raises, use naive prefix — never skip silently
    try:
        labeled_copy = _apply_ai_label(post_copy, platform)
    except Exception as label_exc:
        logger.error(
            "AI label application failed for platform=%s, falling back to prefix: %s",
            platform, label_exc,
        )
        labeled_copy = f"{AI_LABEL}\n{post_copy}" if post_copy else AI_LABEL

    # PUB-01: Music license gate — check before publishing
    if not _check_music_license_cleared(supabase, row, platform, content_history_id):
        return  # Blocked: publish_events row and Telegram alert already sent

    try:
        response = PublishingService().publish(
            platform=platform,
            post_text=labeled_copy,
            video_url=video_url,
        )

        external_post_id = response.get("external_post_id", "")
        platform_post_id = response.get("platform_post_id", "")

        # Persist publish event — verification job queries this table
        supabase.table("publish_events").insert({
            "content_history_id": content_history_id,
            "platform": platform,
            "external_post_id": external_post_id,
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
            args=[content_history_id, platform, external_post_id],
            id=verify_job_id,
            name=f"Verify {platform} for {content_history_id[:8]}",
            replace_existing=True,
        )
        # Schedule metrics harvest 48 hours after publish (ANLX-01)
        from app.scheduler.jobs.harvest_metrics import harvest_metrics_job

        harvest_run_at = datetime.now(tz=timezone.utc) + timedelta(hours=48)
        harvest_job_id = f"harvest_{content_history_id}_{platform}"
        _scheduler.add_job(
            harvest_metrics_job,
            trigger=DateTrigger(run_date=harvest_run_at),
            args=[content_history_id, platform, external_post_id],
            id=harvest_job_id,
            name=f"Harvest {platform} metrics for {content_history_id[:8]}",
            replace_existing=True,
        )
        logger.info(
            "Scheduled harvest for %s content_history_id=%s at %s",
            platform, content_history_id[:8], harvest_run_at.isoformat(),
        )

        logger.info(
            "Published %s for content_history_id=%s: external_post_id=%s",
            platform, content_history_id[:8], external_post_id,
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
