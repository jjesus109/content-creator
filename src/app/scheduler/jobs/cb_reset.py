import logging
from app.services.database import get_supabase
from app.services.circuit_breaker import CircuitBreakerService

logger = logging.getLogger(__name__)


def cb_reset_job() -> None:
    """
    Resets circuit breaker daily counters at midnight America/Mexico_City.
    Called by APScheduler — runs in thread pool (sync context).
    Does NOT reset weekly_trip_count — rolling 7-day window persists.
    """
    logger.info("Running circuit breaker midnight reset.")
    supabase = get_supabase()
    cb = CircuitBreakerService(supabase)
    cb.midnight_reset()
    logger.info("Circuit breaker reset complete.")
