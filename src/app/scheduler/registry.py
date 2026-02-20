import logging
from apscheduler.schedulers.background import BackgroundScheduler

from app.scheduler.jobs.heartbeat import heartbeat_job
from app.scheduler.jobs.cb_reset import cb_reset_job
from app.settings import get_settings

logger = logging.getLogger(__name__)

TIMEZONE = "America/Mexico_City"


def register_jobs(scheduler: BackgroundScheduler) -> None:
    """
    Register all APScheduler jobs.
    ALWAYS use replace_existing=True — prevents duplicate rows on service restart.
    ALWAYS use a stable job id — this is the primary key in the job store.
    """
    settings = get_settings()
    pipeline_hour = settings.pipeline_hour  # default 7

    # Daily heartbeat / pipeline trigger at 7 AM Mexico City (INFRA-03)
    scheduler.add_job(
        heartbeat_job,
        trigger="cron",
        hour=pipeline_hour,
        minute=0,
        timezone=TIMEZONE,
        id="daily_pipeline_trigger",      # stable ID — survives restarts
        name="Daily pipeline trigger (heartbeat)",
        replace_existing=True,             # CRITICAL — never omit
    )
    logger.info("Registered job: daily_pipeline_trigger at %02d:00 %s", pipeline_hour, TIMEZONE)

    # Midnight circuit breaker reset (INFRA-04)
    scheduler.add_job(
        cb_reset_job,
        trigger="cron",
        hour=0,
        minute=0,
        timezone=TIMEZONE,
        id="cb_midnight_reset",
        name="Circuit breaker midnight reset",
        replace_existing=True,
    )
    logger.info("Registered job: cb_midnight_reset at 00:00 %s", TIMEZONE)
