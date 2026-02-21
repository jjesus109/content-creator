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
