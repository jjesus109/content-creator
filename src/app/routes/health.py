import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request

from app.services.database import get_supabase

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/health")
async def health_check(request: Request):
    """
    Deep health probe for Railway restart policy.
    Checks: (1) Supabase reachability via lightweight query, (2) APScheduler running state.
    Returns 200 if both healthy, 503 with diagnostic detail if either is not.
    Railway restarts the service on non-200 responses (restartPolicyType = ON_FAILURE).
    """
    checks: dict = {}

    # --- Database check ---
    try:
        supabase = get_supabase()
        supabase.table("pipeline_runs").select("id").limit(1).execute()
        checks["database"] = "ok"
    except Exception as exc:
        logger.error("Health check DB failure: %s", exc)
        checks["database"] = f"error: {exc}"

    # --- Scheduler check ---
    scheduler = getattr(request.app.state, "scheduler", None)
    if scheduler is not None and scheduler.running:
        checks["scheduler"] = "running"
        checks["scheduled_jobs"] = len(scheduler.get_jobs())
    else:
        checks["scheduler"] = "stopped"
        logger.error("Health check: scheduler is not running.")

    # Determine overall health
    all_ok = (
        checks["database"] == "ok"
        and checks["scheduler"] == "running"
    )

    if not all_ok:
        raise HTTPException(status_code=503, detail=checks)

    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "checks": checks,
    }
