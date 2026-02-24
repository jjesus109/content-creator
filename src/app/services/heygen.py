"""
HeyGen video generation service.

Provides:
  - HeyGenService: submits a script to HeyGen v2 API for avatar video rendering
  - pick_background_url(): selects a background from the pool, enforcing no consecutive repeats

Note: Uses synchronous `requests` (not httpx async) — correct for APScheduler ThreadPoolExecutor context.
"""
import random
import logging

import requests

from app.settings import get_settings
from app.services.database import get_supabase
from app.services.telegram import send_alert_sync

logger = logging.getLogger(__name__)

HEYGEN_GENERATE_URL = "https://api.heygen.com/v2/video/generate"


def pick_background_url(last_used_url: str | None = None) -> str:
    """
    Select a background URL from the configured pool.

    Enforces no-consecutive-repeat: if `last_used_url` is provided and the pool
    has more than one entry, the last-used URL is excluded from the selection.

    Args:
        last_used_url: The URL used in the immediately preceding render, or None.

    Returns:
        A background URL string chosen at random from the available pool.

    Raises:
        ValueError: If the configured pool is empty.
    """
    settings = get_settings()
    pool = [url.strip() for url in settings.heygen_dark_backgrounds.split(",") if url.strip()]

    if not pool:
        raise ValueError(
            "HEYGEN_DARK_BACKGROUNDS is empty — configure at least one background URL."
        )

    # Cannot enforce no-repeat with a single-URL pool
    if len(pool) == 1:
        return pool[0]

    available = [url for url in pool if url != last_used_url]

    # Safety fallback: filtered pool empty (shouldn't happen with len(pool) > 1)
    if not available:
        logger.warning(
            "pick_background_url: filtered pool is empty after excluding last_used_url=%s; "
            "falling back to full pool",
            last_used_url,
        )
        available = pool

    return random.choice(available)


class HeyGenService:
    """
    Thin wrapper around the HeyGen v2 video generation API.

    Responsible only for building and posting the render request.
    Does NOT write to the database or handle webhooks.
    """

    def __init__(self) -> None:
        # Settings loaded lazily via get_settings() — no module-level network call
        self._settings = get_settings()

    def submit(self, script_text: str, background_url: str) -> str:
        """
        Submit a script to HeyGen for avatar video rendering.

        Sends a POST to HEYGEN_GENERATE_URL with the configured avatar, voice,
        portrait dimensions (1080x1920), and the provided background image URL.

        Args:
            script_text:    The Spanish script text to be spoken by the avatar.
            background_url: A Supabase Storage public URL for the background image.

        Returns:
            The HeyGen `video_id` string (used to track render status via webhook/poller).

        Raises:
            requests.HTTPError: If HeyGen returns a non-2xx response.
        """
        settings = self._settings

        payload = {
            "video_inputs": [
                {
                    "character": {
                        "type": "avatar",
                        "avatar_id": settings.heygen_avatar_id,
                        "avatar_style": "normal",
                    },
                    "voice": {
                        "type": "text",
                        "voice_id": settings.heygen_voice_id,
                        "input_text": script_text,
                        "speed": 1.0,
                    },
                    "background": {
                        "type": "image",
                        "url": background_url,
                    },
                }
            ],
            "dimension": {"width": 1080, "height": 1920},  # 9:16 portrait
            "caption": False,
            "callback_url": settings.heygen_webhook_url,
        }

        headers = {
            "x-api-key": settings.heygen_api_key,
            "Content-Type": "application/json",
        }

        logger.info(
            "Submitting HeyGen render: avatar=%s voice=%s background=%s",
            settings.heygen_avatar_id,
            settings.heygen_voice_id,
            background_url,
        )

        response = requests.post(HEYGEN_GENERATE_URL, json=payload, headers=headers, timeout=30)
        response.raise_for_status()

        data = response.json()
        video_id: str = data["data"]["video_id"]

        logger.info("HeyGen render submitted: video_id=%s", video_id)
        return video_id


def _process_completed_render(video_id: str, heygen_signed_url: str) -> None:
    """
    Shared processing function called by webhook handler and poller on render completion.
    Order: download video -> pick music -> ffmpeg EQ+mix -> upload to Supabase -> update DB.

    Double-processing guard: only proceeds if video_status is 'pending_render' or 'rendering'.
    Uses a conditional UPDATE (.eq + filter) — only one caller wins the status transition.
    """
    from app.services.audio_processing import AudioProcessingService
    from app.services.video_storage import VideoStorageService
    from app.models.video import VideoStatus

    supabase = get_supabase()

    # Double-processing guard: atomically transition to 'processing'
    # Only rows with status pending_render or rendering are updated
    # If 0 rows updated, another caller already claimed processing — return early
    result = supabase.table("content_history").update(
        {"video_status": VideoStatus.PROCESSING.value}
    ).eq("heygen_job_id", video_id).in_("video_status", [
        VideoStatus.PENDING_RENDER.value,
        VideoStatus.PENDING_RENDER_RETRY.value,
        VideoStatus.RENDERING.value,
    ]).execute()

    if not result.data:
        logger.info(
            "_process_completed_render: video_id=%s already processing or done — skipping",
            video_id
        )
        return

    try:
        logger.info("Processing completed render: video_id=%s", video_id)

        # ffmpeg: download video + music, apply EQ + mix, return processed bytes
        audio_svc = AudioProcessingService()
        processed_bytes = audio_svc.process_video_audio(video_url=heygen_signed_url)

        # Upload to Supabase Storage — stable public URL (NOT the HeyGen signed URL)
        storage_svc = VideoStorageService(supabase)
        stable_url = storage_svc.upload(processed_bytes)

        # Update DB: set stable URL and mark ready
        supabase.table("content_history").update({
            "video_url": stable_url,
            "video_status": VideoStatus.READY.value,
        }).eq("heygen_job_id", video_id).execute()

        logger.info("Video ready: video_id=%s stable_url=%s", video_id, stable_url)
        # Retrieve the content_history id for the approval message callback_data
        id_result = supabase.table("content_history").select("id").eq("heygen_job_id", video_id).single().execute()
        content_history_id = id_result.data["id"]
        from app.services.telegram import send_approval_message_sync
        send_approval_message_sync(content_history_id=content_history_id, video_url=stable_url)

    except Exception as exc:
        logger.error("Error processing render video_id=%s: %s", video_id, exc)
        supabase.table("content_history").update(
            {"video_status": VideoStatus.FAILED.value}
        ).eq("heygen_job_id", video_id).execute()
        send_alert_sync(f"Error procesando video {video_id}: {exc}")
        # Do not re-raise — caller (executor thread or poller) does not need exception propagation


def _handle_render_failure(video_id: str, error_msg: str) -> None:
    """Mark video_status=failed and alert creator. Called on HeyGen render failure."""
    from app.models.video import VideoStatus
    supabase = get_supabase()
    supabase.table("content_history").update(
        {"video_status": VideoStatus.FAILED.value}
    ).eq("heygen_job_id", video_id).execute()
    send_alert_sync(
        f"Render HeyGen fallido para video_id={video_id}: {error_msg}. "
        "Revisa manualmente o acepta saltarte el video de hoy."
    )
    logger.error("HeyGen render failed: video_id=%s error=%s", video_id, error_msg)
