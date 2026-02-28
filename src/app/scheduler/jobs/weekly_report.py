"""
APScheduler job: weekly analytics report sent every Sunday at 9 AM.

Queries platform_metrics for the past 7 days, formats top-5 video report
with per-platform breakdown (YT/IG/TK/FB), sparklines, % change vs prior week,
and top performer by retention_rate. Sends via Telegram.
Uses AnalyticsService.build_weekly_report() for all query + formatting logic.
"""
import logging

from app.services.analytics import AnalyticsService
from app.services.telegram import send_alert_sync

logger = logging.getLogger(__name__)


def weekly_analytics_report_job() -> None:
    """Send weekly analytics report to creator via Telegram."""
    logger.info("Running weekly analytics report job")
    try:
        report_text = AnalyticsService().build_weekly_report()
        send_alert_sync(report_text)
        logger.info("Weekly analytics report sent successfully")
    except Exception as exc:
        logger.error("weekly_analytics_report_job failed: %s", exc, exc_info=True)
        # Do NOT re-raise — APScheduler should continue scheduling future Sunday runs
