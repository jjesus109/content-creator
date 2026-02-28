"""
APScheduler job: daily storage lifecycle cron.

Runs every day at 2 AM to manage video storage tiers:
  - hot -> warm: videos older than 7 days (DB label only, file stays in Supabase Storage)
  - 7-day pre-warning: videos aged 38-44 days (Telegram alert with "Save forever" button)
  - warm -> pending_deletion: videos older than 45 days (send creator confirmation message)
  - Reset expired deletion requests (>24h timeout with no confirmation)

Videos flagged is_viral=true or is_eternal=true are ALWAYS skipped (exempt).
Actual file deletion only happens when creator confirms via stor_confirm: Telegram handler.
NO R2, NO boto3, NO file copy operations in this job.
"""
import asyncio
import logging
from datetime import datetime, timedelta, timezone

from app.services.database import get_supabase
from app.services.storage_lifecycle import StorageLifecycleService

logger = logging.getLogger(__name__)

HOT_TO_WARM_DAYS = 7
WARN_DAYS = 38          # Send 7-day pre-warning at 38 days old
WARM_TO_DELETE_DAYS = 45
DELETION_TIMEOUT_HOURS = 24


def storage_lifecycle_job() -> None:
    """Run storage tier transitions and send Telegram alerts to creator."""
    logger.info("Running storage lifecycle job")
    try:
        supabase = get_supabase()
        service = StorageLifecycleService(supabase)
        now = datetime.now(tz=timezone.utc)

        # Step 1: Reset timed-out deletion requests (safe default: do NOT delete)
        reset_count = service.reset_expired_deletion_requests()
        if reset_count:
            logger.info("Reset %d expired deletion requests", reset_count)

        # Step 2: Hot -> Warm (videos older than 7 days)
        # Warm = DB label only. File stays in Supabase Storage bucket. No file copy.
        hot_cutoff = (now - timedelta(days=HOT_TO_WARM_DAYS)).isoformat()
        hot_rows = supabase.table("content_history").select(
            "id, topic_summary"
        ).eq("storage_status", "hot").lte(
            "created_at", hot_cutoff
        ).eq("is_viral", False).eq("is_eternal", False).execute().data or []

        for row in hot_rows:
            try:
                service.transition_to_warm(row["id"])
                logger.info("Transitioned to warm (DB label only): content_history_id=%s", row["id"][:8])
            except Exception as exc:
                logger.error("Hot->warm failed for %s: %s", row["id"][:8], exc)
                # Continue with other rows — partial failure is acceptable

        # Step 3: 7-day pre-warning (videos aged 38-44 days, still warm, no deletion request yet)
        # Fires once: only for videos that are 'warm' with no deletion_requested_at set.
        # At 45+ days they move to pending_deletion, so 38-44 days is the exact warning window.
        #
        # asyncio.run() bridge: This job runs in APScheduler's ThreadPoolExecutor (no event loop).
        # send_7day_warning is async (calls bot.send_message). asyncio.run() creates a fresh
        # event loop per call — correct here because the thread has no existing loop.
        # Contrast: send_alert_sync uses run_coroutine_threadsafe when a loop already exists
        # (FastAPI's main thread). Different contexts require different async bridges.
        warn_cutoff_start = (now - timedelta(days=WARM_TO_DELETE_DAYS)).isoformat()  # older than 45d excluded
        warn_cutoff_end   = (now - timedelta(days=WARN_DAYS)).isoformat()             # must be 38+ days old
        warn_rows = supabase.table("content_history").select(
            "id, topic_summary, created_at"
        ).eq("storage_status", "warm").lte(
            "created_at", warn_cutoff_end
        ).gt(
            "created_at", warn_cutoff_start
        ).is_("deletion_requested_at", None).eq(
            "is_viral", False
        ).eq("is_eternal", False).execute().data or []

        for row in warn_rows:
            try:
                days_old = (now - datetime.fromisoformat(row["created_at"].replace("Z", "+00:00"))).days
                asyncio.run(service.send_7day_warning(
                    row["id"], row.get("topic_summary", "Video"), days_old
                ))
                logger.info("Sent 7-day pre-warning for content_history_id=%s", row["id"][:8])
            except Exception as exc:
                logger.error("7-day warning failed for %s: %s", row["id"][:8], exc)

        # Step 4: Warm -> Pending Deletion (videos older than 45 days, no prior request)
        warm_cutoff = (now - timedelta(days=WARM_TO_DELETE_DAYS)).isoformat()
        warm_rows = supabase.table("content_history").select(
            "id, topic_summary, created_at"
        ).eq("storage_status", "warm").lte(
            "created_at", warm_cutoff
        ).is_("deletion_requested_at", None).eq("is_viral", False).eq("is_eternal", False).execute().data or []

        for row in warm_rows:
            try:
                days_old = (now - datetime.fromisoformat(row["created_at"].replace("Z", "+00:00"))).days
                asyncio.run(service.request_deletion_confirmation(
                    row["id"], row.get("topic_summary", "Video"), days_old
                ))
                logger.info("Sent deletion confirmation for content_history_id=%s", row["id"][:8])
            except Exception as exc:
                logger.error("Warm->pending_deletion failed for %s: %s", row["id"][:8], exc)

        logger.info("Storage lifecycle job complete")
    except Exception as exc:
        logger.error("storage_lifecycle_job failed: %s", exc, exc_info=True)
