import logging
import threading

from fastapi import APIRouter

from app.scheduler.jobs.daily_pipeline import daily_pipeline_job

router = APIRouter(prefix="/admin", tags=["admin"])
logger = logging.getLogger(__name__)


@router.post("/trigger-pipeline", status_code=202)
async def trigger_pipeline():
    """
    Manually trigger the daily pipeline job for testing purposes.
    Fires daily_pipeline_job() in a daemon thread so the HTTP response
    returns immediately (202 Accepted) while the job runs in the background.

    daily_pipeline_job is synchronous and designed to run in APScheduler's
    ThreadPoolExecutor — a plain threading.Thread is the correct bridge from
    an async FastAPI handler to a blocking synchronous job (same pattern used
    by APScheduler internally).

    WARNING: This endpoint has no authentication. Do NOT expose it to the public
    internet in production — restrict via Railway's private networking or add a
    shared-secret header if the service is publicly reachable.
    """
    logger.info("Manual pipeline trigger requested via /admin/trigger-pipeline.")
    thread = threading.Thread(target=daily_pipeline_job, daemon=True, name="manual-pipeline-trigger")
    thread.start()
    return {"status": "accepted", "message": "Pipeline job triggered in background."}
