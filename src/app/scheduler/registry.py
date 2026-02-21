import logging
from apscheduler.schedulers.background import BackgroundScheduler

from app.scheduler.jobs.daily_pipeline import daily_pipeline_job
from app.scheduler.jobs.cb_reset import cb_reset_job
from app.scheduler.jobs.weekly_mood import weekly_mood_prompt_job, weekly_mood_reminder_job
from app.scheduler.jobs.video_poller import set_scheduler
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

    # Inject scheduler into video_poller module — required before any poller job is registered.
    # Module-level reference avoids lambda/closure serialization failures with SQLAlchemyJobStore.
    set_scheduler(scheduler)

    # Daily pipeline trigger at 7 AM Mexico City (INFRA-03, SCRP-01–SCRP-04)
    scheduler.add_job(
        daily_pipeline_job,
        trigger="cron",
        hour=pipeline_hour,
        minute=0,
        timezone=TIMEZONE,
        id="daily_pipeline_trigger",      # stable ID — survives restarts
        name="Daily script generation pipeline",
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

    # Weekly mood prompt — Monday 9 AM Mexico City (SCRP-04)
    scheduler.add_job(
        weekly_mood_prompt_job,
        trigger="cron",
        day_of_week="mon",
        hour=9,
        minute=0,
        timezone=TIMEZONE,
        id="weekly_mood_prompt",
        name="Weekly mood profile prompt",
        replace_existing=True,
    )
    logger.info("Registered job: weekly_mood_prompt at Mon 09:00 %s", TIMEZONE)

    # 4-hour reminder — Monday 1 PM Mexico City (SCRP-04 fallback)
    scheduler.add_job(
        weekly_mood_reminder_job,
        trigger="cron",
        day_of_week="mon",
        hour=13,
        minute=0,
        timezone=TIMEZONE,
        id="weekly_mood_reminder",
        name="Weekly mood profile reminder (4h fallback)",
        replace_existing=True,
    )
    logger.info("Registered job: weekly_mood_reminder at Mon 13:00 %s", TIMEZONE)
