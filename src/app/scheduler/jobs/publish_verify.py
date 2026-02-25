"""
APScheduler job: verify publish status 30 minutes after a platform publish.

Fired automatically by publish_to_platform_job() 30 minutes after a successful
Ayrshare response. Queries Ayrshare GET /post/{id} to confirm the post is live.

On success (status == "completed" or "success"): silently log only (user decision:
  only surface failures by default — no Telegram message on success).
On failure: update publish_events.status to 'verify_failed', send Telegram alert.
"""
import logging

from app.services.database import get_supabase
from app.services.publishing import PublishingService
from app.services.telegram import send_alert_sync

logger = logging.getLogger(__name__)

SUCCESS_STATUSES = {"completed", "success", "active"}


def verify_publish_job(
    content_history_id: str,
    platform: str,
    ayrshare_post_id: str,
) -> None:
    """
    Verify that a platform post is live 30 minutes after publishing.

    Args are picklable (str only) — required for SQLAlchemyJobStore.
    """
    supabase = get_supabase()

    try:
        response = PublishingService().get_post_status(ayrshare_post_id)
        status = response.get("status", "").lower()
        logger.info(
            "Verification %s for content_history_id=%s: status=%s",
            platform, content_history_id[:8], status,
        )

        if status in SUCCESS_STATUSES:
            # Silent success — log only (user decision: no Telegram message on success)
            supabase.table("publish_events").update(
                {"status": "verified"}
            ).eq("content_history_id", content_history_id).eq("platform", platform).eq("status", "published").execute()
            logger.info("Verification PASSED: %s content_history_id=%s", platform, content_history_id[:8])
        else:
            # Unexpected status — surface to creator
            _handle_verify_failure(supabase, content_history_id, platform, f"unexpected status: {status}")

    except Exception as exc:
        error_str = str(exc)[:300]
        logger.error("Verify job error for %s content_history_id=%s: %s", platform, content_history_id[:8], error_str)
        _handle_verify_failure(supabase, content_history_id, platform, error_str)


def _handle_verify_failure(supabase, content_history_id: str, platform: str, reason: str) -> None:
    """Update DB and send Telegram alert on verification failure."""
    supabase.table("publish_events").update(
        {"status": "verify_failed", "error_message": reason[:500]}
    ).eq("content_history_id", content_history_id).eq("platform", platform).eq("status", "published").execute()

    send_alert_sync(
        f"Verificacion fallida: {platform.upper()}\n"
        f"Razon: {reason}\n"
        f"ID: {content_history_id[:8]}\n"
        "El post podria no estar visible. Revisa manualmente."
    )
    logger.error("Verification FAILED: %s content_history_id=%s reason=%s", platform, content_history_id[:8], reason)
