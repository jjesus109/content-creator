import logging
import time
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

MANUAL_PLATFORMS = {"tiktok"}
AUTO_PLATFORMS   = {"instagram", "facebook", "youtube"}

PLATFORM_PEAK_HOURS: dict[str, int] = {
    "tiktok":    19,   # 7 PM — kept for reference; TikTok is manual
    "instagram": 11,   # 11 AM
    "facebook":  13,   # 1 PM
    "youtube":   12,   # 12 PM
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
    Direct platform API publishing for YouTube, Instagram, and Facebook.
    TikTok is manual — no publish() call should be made for it.
    Synchronous — runs in APScheduler ThreadPoolExecutor (no event loop).
    """

    YOUTUBE_TOKEN_URL   = "https://oauth2.googleapis.com/token"
    YOUTUBE_UPLOAD_URL  = "https://www.googleapis.com/upload/youtube/v3/videos"
    YOUTUBE_VIDEO_URL   = "https://www.googleapis.com/youtube/v3/videos"
    INSTAGRAM_GRAPH_URL = "https://graph.instagram.com/v18.0"
    FACEBOOK_GRAPH_URL  = "https://graph.facebook.com/v18.0"
    FACEBOOK_VIDEO_URL  = "https://graph-video.facebook.com/v18.0"

    def __init__(self) -> None:
        self._settings = get_settings()

    def _refresh_youtube_token(self) -> str:
        """Exchange refresh_token for a fresh access_token via Google OAuth2."""
        s = self._settings
        response = requests.post(
            self.YOUTUBE_TOKEN_URL,
            data={
                "client_id":     s.youtube_client_id,
                "client_secret": s.youtube_client_secret,
                "refresh_token": s.youtube_refresh_token,
                "grant_type":    "refresh_token",
            },
            timeout=30,
        )
        response.raise_for_status()
        return response.json()["access_token"]

    @retry(
        retry=retry_if_exception(_is_retryable),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        reraise=True,
    )
    def _publish_youtube(self, post_text: str, video_url: str) -> dict:
        """
        Upload video to YouTube via Data API v3 resumable upload.
        1. Refresh OAuth2 access_token.
        2. Download video bytes from Supabase Storage.
        3. Create resumable upload session (POST metadata).
        4. Upload binary (PUT to Location header URL).
        """
        access_token = self._refresh_youtube_token()

        # Download video
        video_response = requests.get(video_url, timeout=300)
        video_response.raise_for_status()
        video_bytes = video_response.content

        # Parse post_text: first line -> title, rest -> description
        lines = post_text.strip().splitlines()
        title = lines[0][:100] if lines else "Video"
        description = "\n".join(lines[1:]).strip() if len(lines) > 1 else ""
        description += "\n\n#Shorts"

        # Create resumable upload session
        metadata = {
            "snippet": {
                "title":       title,
                "description": description,
            },
            "status": {
                "privacyStatus": "public",
            },
        }
        session_response = requests.post(
            f"{self.YOUTUBE_UPLOAD_URL}?uploadType=resumable&part=snippet,status",
            json=metadata,
            headers={
                "Authorization":          f"Bearer {access_token}",
                "Content-Type":           "application/json",
                "X-Upload-Content-Type":   "video/*",
                "X-Upload-Content-Length": str(len(video_bytes)),
            },
            timeout=30,
        )
        session_response.raise_for_status()
        upload_url = session_response.headers["Location"]

        # Upload binary
        upload_response = requests.put(
            upload_url,
            data=video_bytes,
            headers={"Content-Type": "video/*"},
            timeout=600,
        )
        upload_response.raise_for_status()
        video_id = upload_response.json()["id"]

        return {
            "external_post_id": video_id,
            "platform_post_id": f"https://youtube.com/shorts/{video_id}",
        }

    @retry(
        retry=retry_if_exception(_is_retryable),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        reraise=True,
    )
    def _publish_instagram(self, caption: str, video_url: str) -> dict:
        """
        Publish a Reel to Instagram via Meta Graph API v18 (2-step: container + publish).
        1. POST media container.
        2. Poll until status_code == FINISHED (up to 12×10s).
        3. POST media_publish.
        """
        s = self._settings
        account_id = s.instagram_business_account_id
        token = s.instagram_access_token

        # Step 1: Create container
        container_response = requests.post(
            f"{self.INSTAGRAM_GRAPH_URL}/{account_id}/media",
            params={
                "media_type":   "REELS",
                "video_url":    video_url,
                "caption":      caption,
                "access_token": token,
            },
            timeout=30,
        )
        container_response.raise_for_status()
        container_id = container_response.json()["id"]

        # Step 2: Poll until FINISHED
        for _ in range(12):
            time.sleep(10)
            status_response = requests.get(
                f"{self.INSTAGRAM_GRAPH_URL}/{container_id}",
                params={"fields": "status_code", "access_token": token},
                timeout=15,
            )
            status_response.raise_for_status()
            status_code = status_response.json().get("status_code", "")
            if status_code == "FINISHED":
                break
            if status_code == "ERROR":
                raise RuntimeError(f"Instagram container processing failed: {status_code}")

        # Step 3: Publish
        publish_response = requests.post(
            f"{self.INSTAGRAM_GRAPH_URL}/{account_id}/media_publish",
            params={
                "creation_id":  container_id,
                "access_token": token,
            },
            timeout=30,
        )
        publish_response.raise_for_status()
        media_id = publish_response.json()["id"]

        return {
            "external_post_id": media_id,
            "platform_post_id": media_id,
        }

    @retry(
        retry=retry_if_exception(_is_retryable),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        reraise=True,
    )
    def _publish_facebook(self, description: str, video_url: str) -> dict:
        """
        Publish a video to Facebook Page via Meta Graph API v18.
        Uses file_url (URL-based, no binary upload).
        """
        s = self._settings
        response = requests.post(
            f"{self.FACEBOOK_VIDEO_URL}/{s.facebook_page_id}/videos",
            params={
                "file_url":     video_url,
                "description":  description,
                "access_token": s.facebook_access_token,
            },
            timeout=60,
        )
        response.raise_for_status()
        video_id = response.json()["id"]

        return {
            "external_post_id": video_id,
            "platform_post_id": video_id,
        }

    def publish(
        self,
        platform: str,
        post_text: str,
        video_url: str,
    ) -> dict:
        """
        Publish a video to a single platform via direct platform API.

        Args:
            platform:  One of 'instagram', 'facebook', 'youtube'. Not 'tiktok' (manual).
            post_text: Platform-specific copy text.
            video_url: Supabase Storage public URL of the video.

        Returns:
            dict with 'external_post_id' and 'platform_post_id'.

        Raises:
            ValueError:                On unknown or manual platform.
            requests.HTTPError:        On 4xx (fail fast, no retry).
            requests.RequestException: On 5xx/timeout (after 3 attempts).
        """
        if platform in MANUAL_PLATFORMS:
            raise ValueError(f"Platform '{platform}' is manual — do not call publish() for it.")
        logger.info("Publishing to %s: url=%s", platform, video_url[:60],
                    extra={"pipeline_step": "platform_publish", "content_history_id": ""})
        if platform == "youtube":
            return self._publish_youtube(post_text, video_url)
        elif platform == "instagram":
            return self._publish_instagram(post_text, video_url)
        elif platform == "facebook":
            return self._publish_facebook(post_text, video_url)
        else:
            raise ValueError(f"Unknown platform: {platform}")

    def _get_youtube_status(self, video_id: str) -> dict:
        """Check YouTube upload status via Data API v3."""
        access_token = self._refresh_youtube_token()
        response = requests.get(
            self.YOUTUBE_VIDEO_URL,
            params={
                "part":         "status",
                "id":           video_id,
                "access_token": access_token,
            },
            timeout=15,
        )
        response.raise_for_status()
        items = response.json().get("items", [])
        if items and items[0].get("status", {}).get("uploadStatus") == "processed":
            return {"status": "verified"}
        return {"status": "verify_failed"}

    def _get_instagram_status(self, media_id: str) -> dict:
        """Check Instagram media status via Graph API."""
        response = requests.get(
            f"{self.INSTAGRAM_GRAPH_URL}/{media_id}",
            params={
                "fields":       "id,media_type",
                "access_token": self._settings.instagram_access_token,
            },
            timeout=15,
        )
        response.raise_for_status()
        if response.json().get("id"):
            return {"status": "verified"}
        return {"status": "verify_failed"}

    def _get_facebook_status(self, video_id: str) -> dict:
        """Check Facebook video status via Graph API."""
        response = requests.get(
            f"{self.FACEBOOK_GRAPH_URL}/{video_id}",
            params={
                "fields":       "id,status",
                "access_token": self._settings.facebook_access_token,
            },
            timeout=15,
        )
        response.raise_for_status()
        if response.json().get("id"):
            return {"status": "verified"}
        return {"status": "verify_failed"}

    def get_post_status(self, platform: str, external_post_id: str) -> dict:
        """
        Query platform API for post status by platform-native post ID.
        Used by verify_publish_job 30 minutes after publish.
        No retry — verification failure is not retried (just alerts creator).

        Returns:
            dict with 'status': 'verified' or 'verify_failed'
        """
        if platform == "youtube":
            return self._get_youtube_status(external_post_id)
        elif platform == "instagram":
            return self._get_instagram_status(external_post_id)
        elif platform == "facebook":
            return self._get_facebook_status(external_post_id)
        else:
            raise ValueError(f"Unknown platform for status check: {platform}")


def schedule_platform_publishes(
    scheduler,
    content_history_id: str,
    video_url: str,
    approval_time: datetime,
) -> dict[str, datetime]:
    """
    Register DateTrigger APScheduler jobs for AUTO_PLATFORMS only (skips TikTok).

    Peak hours come from settings (audience_timezone + peak_hour_* fields).
    Rule: if approval_time <= today_peak_start → today; else → tomorrow.
    Inclusive lower bound (approval_at_or_before_peak → use today's peak).

    Args:
        scheduler:           The BackgroundScheduler instance from app.state.scheduler.
        content_history_id:  UUID of the content_history row to publish.
        video_url:           Supabase Storage public URL of the video.
        approval_time:       UTC datetime when creator approved. Used for today/tomorrow logic.

    Returns:
        dict mapping platform -> scheduled_at (UTC datetime) for auto platforms only.
    """
    from apscheduler.triggers.date import DateTrigger
    from app.scheduler.jobs.platform_publish import publish_to_platform_job

    settings = get_settings()
    audience_tz = pytz.timezone(settings.audience_timezone)
    approval_local = approval_time.astimezone(audience_tz)

    peak_hours = {
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
            extra={"pipeline_step": "platform_publish", "content_history_id": content_history_id},
        )

    return scheduled_times
