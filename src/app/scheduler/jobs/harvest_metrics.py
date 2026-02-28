"""
APScheduler job: harvest platform metrics 48 hours after a successful publish.

Triggered automatically by platform_publish_job using a DateTrigger (run_date = now + 48h).
All args are str — required for SQLAlchemyJobStore pickling (same constraint as all Phase 5/6 jobs).

Workflow:
  1. Call MetricsService().fetch_and_store() to pull API metrics and persist the row.
  2. Call AnalyticsService().check_and_alert_virality() to detect viral spike and send alert.
  3. Log result and return silently — never raises (APScheduler logs uncaught exceptions as errors
     but the job is already finished at that point).
"""
import logging

from app.services.analytics import AnalyticsService
from app.services.database import get_supabase
from app.services.metrics import MetricsService

logger = logging.getLogger(__name__)


def harvest_metrics_job(
    content_history_id: str,
    platform: str,
    external_post_id: str,
) -> None:
    """
    Harvest platform metrics and run virality check for a published video.

    Args are picklable (str only) — required for SQLAlchemyJobStore serialization.
    Scheduled 48h after a successful publish by platform_publish_job.
    """
    try:
        logger.info(
            "Harvesting %s metrics for content_history_id=%s",
            platform,
            content_history_id[:8],
        )

        # Step 1: Fetch metrics from platform API and persist to platform_metrics table
        metrics = MetricsService().fetch_and_store(
            content_history_id, platform, external_post_id
        )

        if metrics is None:
            logger.warning(
                "Metrics fetch returned None for %s %s",
                platform,
                content_history_id[:8],
            )
            return

        current_views = metrics.get("views") or 0

        # Step 2: Fetch topic_summary and video_date from content_history for virality alert
        supabase = get_supabase()
        ch_result = (
            supabase.table("content_history")
            .select("topic_summary, created_at")
            .eq("id", content_history_id)
            .single()
            .execute()
        )
        ch_data = ch_result.data or {}
        topic_summary = ch_data.get("topic_summary", "")
        # video_date: use date portion of created_at (e.g. "2026-02-28")
        created_at = ch_data.get("created_at", "")
        video_date = created_at[:10] if created_at else ""

        # Step 3: Run virality check — fires Telegram alert and marks Eternal if threshold exceeded
        AnalyticsService().check_and_alert_virality(
            content_history_id,
            platform,
            current_views,
            topic_summary,
            video_date,
        )

        logger.info(
            "harvest_metrics_job complete: %s content_history_id=%s views=%s",
            platform,
            content_history_id[:8],
            current_views,
        )

    except Exception as exc:
        logger.error(
            "harvest_metrics_job failed: %s",
            exc,
            exc_info=True,
        )
