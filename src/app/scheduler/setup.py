import logging
import pytz
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.executors.pool import ThreadPoolExecutor

from app.settings import get_settings

logger = logging.getLogger(__name__)

TIMEZONE = "America/Mexico_City"


def create_scheduler() -> BackgroundScheduler:
    """
    BackgroundScheduler with persistent Postgres job store on Supabase.
    DATABASE_URL must be postgresql+psycopg2:// via session pooler port 5432.
    APScheduler creates the apscheduler_jobs table automatically on first connect.
    """
    settings = get_settings()

    jobstores = {
        "default": SQLAlchemyJobStore(
            url=settings.database_url,  # MUST be postgresql+psycopg2:// — NOT asyncpg
            tablename="apscheduler_jobs",
        )
    }
    executors = {
        "default": ThreadPoolExecutor(max_workers=4)
    }
    job_defaults = {
        "coalesce": True,           # missed fires collapse to one run (handles DST spring-forward)
        "max_instances": 1,         # never run the same job concurrently
        "misfire_grace_time": 3600, # 1 hour grace — job still fires after downtime
    }

    scheduler = BackgroundScheduler(
        jobstores=jobstores,
        executors=executors,
        job_defaults=job_defaults,
        timezone=pytz.timezone(TIMEZONE),
    )
    logger.info("Scheduler created with SQLAlchemyJobStore on Supabase session pooler.")
    return scheduler
