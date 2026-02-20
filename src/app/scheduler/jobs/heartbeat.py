import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def heartbeat_job() -> None:
    """
    No-op heartbeat job for APScheduler verification.
    Fires daily at 7 AM America/Mexico_City.
    Writes 'Scheduler heartbeat' log entry — observable in Railway logs.
    """
    now = datetime.now(timezone.utc).isoformat()
    logger.info("Scheduler heartbeat — %s", now)
