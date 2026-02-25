import logging
import re
from datetime import datetime, timedelta, timezone

import pytz
import requests
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from app.settings import get_settings

logger = logging.getLogger(__name__)

PLATFORM_PEAK_HOURS: dict[str, int] = {
    "tiktok": 19,      # 7 PM — overridden by settings.peak_hour_tiktok
    "instagram": 11,   # 11 AM
    "facebook": 13,    # 1 PM
    "youtube": 12,     # 12 PM
}


def _is_retryable(exc: Exception) -> bool:
    """Retry on 5xx and network errors only. Fail fast on 4xx (policy/auth)."""
    if isinstance(exc, (requests.ConnectTimeout, requests.ReadTimeout, requests.ConnectionError)):
        return True
    if isinstance(exc, requests.HTTPError):
        return exc.response.status_code >= 500
    return False


class PublishingService:
    """
    Wraps the Ayrshare POST /post endpoint with tenacity retry logic.
    Synchronous — runs in APScheduler ThreadPoolExecutor (no event loop).
    """

    AYRSHARE_POST_URL = "https://app.ayrshare.com/api/post"
    AYRSHARE_GET_URL  = "https://app.ayrshare.com/api/post/{post_id}"

    def __init__(self) -> None:
        self._settings = get_settings()

    @retry(
        retry=retry_if_exception(_is_retryable),
        stop=stop_after_attempt(3),              # original + 2 retries
        wait=wait_exponential(multiplier=1, min=2, max=30),  # 2s, 4s, 8s
        reraise=True,
    )
    def _post(self, payload: dict) -> dict:
        """Internal: POST to Ayrshare. Decorated with retry. Called by publish()."""
        response = requests.post(
            self.AYRSHARE_POST_URL,
            json=payload,
            headers={
                "Authorization": f"Bearer {self._settings.ayrshare_api_key}",
                "Content-Type": "application/json",
            },
            timeout=30,
        )
        response.raise_for_status()
        return response.json()

    def publish(
        self,
        platform: str,
        post_text: str,
        video_url: str,
    ) -> dict:
        """
        Publish a video to a single platform via Ayrshare.

        Publishes immediately (no scheduleDate) — the APScheduler DateTrigger
        ensures this job fires at the correct peak hour.

        Args:
            platform:  One of 'tiktok', 'instagram', 'facebook', 'youtube'.
            post_text: Platform-specific copy text.
            video_url: Supabase Storage public URL of the video.

        Returns:
            Ayrshare response JSON including postId and postIds map.

        Raises:
            requests.HTTPError:       On 4xx (fail fast, no retry).
            requests.RequestException: On 5xx/timeout (after 3 attempts).
        """
        payload = {
            "post": post_text,
            "platforms": [platform],
            "mediaUrls": [video_url],
            "isVideo": True,
        }
        logger.info("Publishing to %s: url=%s", platform, video_url[:60])
        return self._post(payload)

    def get_post_status(self, ayrshare_post_id: str) -> dict:
        """
        Query Ayrshare for post status by its internal post ID.
        Used by verify_publish_job 30 minutes after publish.
        No retry — verification failure is not retried (just alerts creator).
        """
        response = requests.get(
            self.AYRSHARE_GET_URL.format(post_id=ayrshare_post_id),
            headers={"Authorization": f"Bearer {self._settings.ayrshare_api_key}"},
            timeout=15,
        )
        response.raise_for_status()
        return response.json()


def schedule_platform_publishes(
    scheduler,
    content_history_id: str,
    video_url: str,
    approval_time: datetime,
) -> dict[str, datetime]:
    """
    Register 4 DateTrigger APScheduler jobs — one per platform — at their peak hours.

    Peak hours come from settings (audience_timezone + peak_hour_* fields).
    Rule: if approval_time <= today_peak_start → today; else → tomorrow.
    Inclusive lower bound (approval_at_or_before_peak → use today's peak).

    Args:
        scheduler:           The BackgroundScheduler instance from app.state.scheduler.
        content_history_id:  UUID of the content_history row to publish.
        video_url:           Supabase Storage public URL of the video.
        approval_time:       UTC datetime when creator approved. Used for today/tomorrow logic.

    Returns:
        dict mapping platform -> scheduled_at (UTC datetime), for building confirmation message.
    """
    from apscheduler.triggers.date import DateTrigger
    from app.scheduler.jobs.platform_publish import publish_to_platform_job

    settings = get_settings()
    audience_tz = pytz.timezone(settings.audience_timezone)
    approval_local = approval_time.astimezone(audience_tz)

    peak_hours = {
        "tiktok":    settings.peak_hour_tiktok,
        "instagram": settings.peak_hour_instagram,
        "facebook":  settings.peak_hour_facebook,
        "youtube":   settings.peak_hour_youtube,
    }

    scheduled_times: dict[str, datetime] = {}

    for platform, peak_hour in peak_hours.items():
        # Today's peak start in audience timezone
        today_peak_start = approval_local.replace(
            hour=peak_hour, minute=0, second=0, microsecond=0
        )

        # Inclusive lower bound: if at or before peak start, use today
        if approval_local <= today_peak_start:
            run_at = today_peak_start
        else:
            run_at = today_peak_start + timedelta(days=1)

        # Stable job ID: idempotent on double-approval or restart
        job_id = f"publish_{content_history_id}_{platform}"

        scheduler.add_job(
            publish_to_platform_job,
            trigger=DateTrigger(run_date=run_at),
            args=[content_history_id, platform, video_url],
            id=job_id,
            name=f"Publish {platform} for {content_history_id[:8]}",
            replace_existing=True,
        )

        scheduled_times[platform] = run_at.astimezone(pytz.UTC)
        logger.info(
            "Scheduled %s publish for content_history_id=%s at %s (%s)",
            platform, content_history_id[:8], run_at.isoformat(), settings.audience_timezone,
        )

    return scheduled_times
