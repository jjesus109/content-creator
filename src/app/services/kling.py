"""
Kling AI 3.0 video generation service via fal.ai async SDK.

Provides:
  - CHARACTER_BIBLE: Python constant (40-50 words) defining the Mexican cat character.
    Embedded unchanged in every Kling generation prompt. Stored as code (not config/DB)
    to guarantee consistency across all generations and deployments.
  - KlingService: submits text-to-video jobs to Kling 3.0 via fal.ai sync SDK.
  - _process_completed_render(): shared by poller on completion.
  - _handle_render_failure(): marks failed + alerts creator.

CRITICAL: Use fal_client.submit() (sync), NOT submit_async().
APScheduler ThreadPoolExecutor cannot manage asyncio event loops.
"""
import logging
import requests

import fal_client
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.settings import get_settings
from app.services.database import get_supabase
from app.services.telegram import send_alert_sync

logger = logging.getLogger(__name__)

# Character Bible: 40-50 word constant defining the grey kitten character identity.
# Embedded unchanged as the FIRST part of every Kling generation prompt.
# DO NOT move to config or environment variables — character consistency requires
# prompt consistency. Changes require code review + explicit commit + deployment.
CHARACTER_BIBLE = (
    "A full-body, high-definition 3D render of an ultra-cute, sitting light grey kitten. "
    "The kitten has huge, wide, expressive blue eyes and a cheerful, open-mouthed smile "
    "showing its pink tongue. Its soft fur texture is highly detailed. "
    "Always animated, playful, and irresistibly cute — capturing audience attention "
    "in every frame."
)
# Word count target: 40-50 words. Current: ~46 words. Grey kitten replaces orange tabby Mochi (v3.0).

# Default duration for Kling generations (seconds)
# Nowayds this is the maximum durations can be generated
DEFAULT_KLING_DURATION = 15

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=32),
    retry=retry_if_exception_type(Exception),
    reraise=True,
    before_sleep=lambda retry_state: logger.warning(
        "Kling submit retry attempt %d",
        retry_state.attempt_number,
    ),
)
def _submit_with_backoff(model_id: str, arguments: dict) -> object:
    """
    Submit to fal.ai Kling with exponential backoff: 2s -> 8s -> 32s (3 attempts total).
    Backoff sequence: wait_exponential(multiplier=1, min=2, max=32)
      Attempt 1: immediate
      Retry 1: ~2s wait
      Retry 2: ~8s wait (capped at 32s max)
    Only retries on transient exceptions. reraise=True propagates after exhaustion.
    """
    return fal_client.submit(model_id, arguments=arguments)


class KlingService:
    """
    Thin wrapper around Kling AI 3.0 via fal.ai SDK for text-to-video generation.

    Does NOT write to the database — that is _process_completed_render's responsibility.
    Uses fal_client.submit() (sync) — correct for APScheduler ThreadPoolExecutor context.
    fal_client auto-reads FAL_KEY from environment — no explicit auth token in code.
    """

    def __init__(self) -> None:
        self._settings = get_settings()

    def submit(self, script_text: str) -> str:
        """
        Submit Character Bible + scene prompt to Kling 3.0 via fal.ai.

        Concatenates CHARACTER_BIBLE (unchanged) + script_text into a single prompt.
        This is the locked decision from CONTEXT.md: single text field, no split.

        Args:
            script_text: Scene description from daily_pipeline (Phase 10 will provide
                         structured scene prompt; Phase 9 uses script directly).

        Returns:
            fal.ai request_id string — used as kling_job_id for DB tracking and polling.

        Raises:
            Exception: On fal.ai API failure (logged + re-raised to caller).
        """
        # Concatenate: CHARACTER_BIBLE unchanged + scene prompt
        full_prompt = f"{CHARACTER_BIBLE}\n\n{script_text}"

        logger.info(
            "Submitting Kling job: model=%s duration=20s aspect=9:16 prompt_chars=%d",
            self._settings.kling_model_version,
            len(full_prompt),
            extra={"pipeline_step": "kling_submit", "content_history_id": ""},
        )

        # Use _submit_with_backoff for exponential backoff: 2s -> 8s -> 32s (3 attempts).
        # On transient fal.ai errors, tenacity retries before recording a CB failure.
        # fal_client auto-reads FAL_KEY from environment.
        result = _submit_with_backoff(
            self._settings.kling_model_version,
            arguments={
                "prompt": full_prompt,
                "duration": DEFAULT_KLING_DURATION,   # seconds — locked: 15s
                "resolution": "1080p",    # locked: 1080p
                "aspect_ratio": "9:16",   # locked: vertical video
            },
        )

        job_id: str = result.request_id
        logger.info(
            "Kling job submitted: job_id=%s",
            job_id,
            extra={"pipeline_step": "kling_submit", "content_history_id": ""},
        )
        return job_id


def _process_completed_render(job_id: str, video_url: str) -> None:
    """
    Shared processing function called by video_poller when Kling render is complete.
    Order: download video -> upload to Supabase Storage -> update DB -> send approval message.

    Double-processing guard: only proceeds if video_status is 'kling_pending' or 'kling_pending_retry'.
    Uses conditional UPDATE (.in_ filter) — only one caller wins the status transition.

    NOTE: v2.0 does NOT call AudioProcessingService (no ffmpeg audio mixing for cat videos).
    VideoStorageService receives raw MP4 bytes from fal.ai video URL.
    """
    from app.services.video_storage import VideoStorageService
    from app.models.video import VideoStatus
    from app.services.telegram import send_approval_message_sync

    supabase = get_supabase()

    # Double-processing guard: atomically transition to 'processing'
    result = supabase.table("content_history").update(
        {"video_status": VideoStatus.PROCESSING.value}
    ).eq("kling_job_id", job_id).in_("video_status", [
        VideoStatus.KLING_PENDING.value,
        VideoStatus.KLING_PENDING_RETRY.value,
    ]).execute()

    if not result.data:
        logger.info(
            "_process_completed_render: job_id=%s already processing or done — skipping",
            job_id,
        )
        return

    try:
        logger.info(
            "Processing completed Kling render: job_id=%s video_url=%s",
            job_id, video_url,
            extra={"pipeline_step": "kling_process", "content_history_id": ""},
        )

        # Download MP4 bytes from fal.ai public URL
        resp = requests.get(video_url, timeout=120)
        resp.raise_for_status()
        video_bytes = resp.content

        # Upload to Supabase Storage — stable public URL
        storage_svc = VideoStorageService(supabase)
        stable_url = storage_svc.upload(video_bytes)

        # Update DB: set stable URL and mark ready
        supabase.table("content_history").update({
            "video_url": stable_url,
            "video_status": VideoStatus.READY.value,
        }).eq("kling_job_id", job_id).execute()

        logger.info(
            "Kling video ready: job_id=%s stable_url=%s",
            job_id, stable_url,
            extra={"pipeline_step": "kling_process", "content_history_id": ""},
        )

        # Retrieve content_history_id for approval message
        id_result = supabase.table("content_history").select("id").eq(
            "kling_job_id", job_id
        ).single().execute()
        content_history_id = id_result.data["id"]
        send_approval_message_sync(content_history_id=content_history_id, video_url=stable_url)

    except Exception as exc:
        logger.error(
            "Error processing Kling render job_id=%s: %s",
            job_id, exc,
            extra={"pipeline_step": "kling_process", "content_history_id": ""},
        )
        supabase.table("content_history").update(
            {"video_status": VideoStatus.FAILED.value}
        ).eq("kling_job_id", job_id).execute()
        send_alert_sync(f"Error procesando video Kling {job_id}: {exc}")
        # Do not re-raise — poller/caller does not need exception propagation


def _handle_render_failure(job_id: str, error_msg: str) -> None:
    """Mark video_status=failed and alert creator. Called on Kling render failure."""
    from app.models.video import VideoStatus
    supabase = get_supabase()
    supabase.table("content_history").update(
        {"video_status": VideoStatus.FAILED.value}
    ).eq("kling_job_id", job_id).execute()
    send_alert_sync(
        f"Render Kling fallido para job_id={job_id}: {error_msg}. "
        "Revisa manualmente o acepta saltarte el video de hoy."
    )
    logger.error(
        "Kling render failed: job_id=%s error=%s",
        job_id, error_msg,
        extra={"pipeline_step": "kling_poll", "content_history_id": ""},
    )
