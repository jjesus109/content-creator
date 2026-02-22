import asyncio
import hmac
import hashlib
import logging
from fastapi import APIRouter, Request, HTTPException
from app.models.video import HeyGenWebhookPayload, VideoStatus
from app.settings import get_settings

router = APIRouter()
logger = logging.getLogger(__name__)

POLLER_JOB_ID_PREFIX = "video_poller_"


@router.post("/webhooks/heygen")
async def heygen_webhook(request: Request, payload: HeyGenWebhookPayload) -> dict:
    """
    HeyGen POSTs here on avatar_video.success or avatar_video.fail.
    MUST return 200 — HeyGen does not retry on non-200 responses.
    HMAC-SHA256 signature required in 'Signature' header.
    """
    # 1. Validate HMAC-SHA256 signature (timing-safe)
    signature = request.headers.get("Signature", "")
    # Strip "sha256=" prefix if HeyGen sends it (some providers use this format)
    if signature.startswith("sha256="):
        signature = signature[7:]
    body_bytes = await request.body()
    settings = get_settings()
    expected = hmac.new(
        settings.heygen_webhook_secret.encode(),
        body_bytes,
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(signature, expected):
        logger.warning(
            "HeyGen webhook: HMAC mismatch — received_headers=%s signature_present=%s",
            list(request.headers.keys()),
            bool(request.headers.get("Signature")),
        )
        raise HTTPException(status_code=401, detail="Invalid signature")

    video_id = payload.event_data.video_id

    if payload.event_type == "avatar_video.success":
        signed_url = payload.event_data.url
        logger.info("HeyGen webhook: render complete for video_id=%s", video_id)

        # 2. Cancel the polling fallback — webhook fired, poller no longer needed
        try:
            scheduler = request.app.state.scheduler
            scheduler.remove_job(f"{POLLER_JOB_ID_PREFIX}{video_id}")
            logger.info("Cancelled poller job for video_id=%s", video_id)
        except Exception:
            pass  # Poller may already be gone; not an error

        # 3. Offload blocking processing to thread pool — never block async handler
        # _process_completed_render is imported lazily here to avoid circular imports at module level
        from app.services.heygen import _process_completed_render
        loop = asyncio.get_event_loop()
        loop.run_in_executor(None, _process_completed_render, video_id, signed_url)

    elif payload.event_type == "avatar_video.fail":
        error_msg = payload.event_data.msg or "unknown"
        logger.error("HeyGen webhook: render failed for video_id=%s msg=%s", video_id, error_msg)
        from app.services.heygen import _handle_render_failure
        loop = asyncio.get_event_loop()
        loop.run_in_executor(None, _handle_render_failure, video_id, error_msg)

    else:
        logger.info("HeyGen webhook: unhandled event_type=%s", payload.event_type)

    return {"status": "ok"}
