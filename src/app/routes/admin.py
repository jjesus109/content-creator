import logging
import secrets
import threading

from fastapi import APIRouter, Depends, HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.scheduler.jobs.daily_pipeline import daily_pipeline_job
from app.settings import get_settings

_bearer = HTTPBearer()


def verify_admin_key(
    credentials: HTTPAuthorizationCredentials = Security(_bearer),
) -> None:
    """Validate the Bearer token against ADMIN_API_KEY from env.
    Raises 401 if missing or wrong. Fail-closed: if ADMIN_API_KEY is
    not set, get_settings() raises ValidationError at startup so this
    line is never reached with an empty key.
    """
    expected = get_settings().admin_api_key
    if not secrets.compare_digest(credentials.credentials, expected):
        raise HTTPException(status_code=401, detail="Invalid or missing API key.")


router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(verify_admin_key)])
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

    Authentication: Bearer token required via ADMIN_API_KEY env var (SCRTY-01).
    """
    logger.info("Manual pipeline trigger requested via /admin/trigger-pipeline.")
    thread = threading.Thread(target=daily_pipeline_job, daemon=True, name="manual-pipeline-trigger")
    thread.start()
    return {"status": "accepted", "message": "Pipeline job triggered in background."}
