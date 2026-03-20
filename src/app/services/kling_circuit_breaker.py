"""
Kling AI circuit breaker — failure-rate-based, 24-hour rolling window.

SEPARATE from CircuitBreakerService (src/app/services/circuit_breaker.py).
HeyGen CB tracks cost+count; Kling CB tracks failure rate + fal.ai balance.
State persists in kling_circuit_breaker_state DB singleton (migration 0008).

Thresholds (locked in CONTEXT.md):
  - Failure rate > 20% over 24h → open CB, halt pipeline, alert creator
  - Balance < $5 → alert creator, proceed
  - Balance < $1 → halt pipeline
  - Recovery: /resume Telegram command calls reset()
  - Backoff: tenacity exponential 2s → 8s → 32s (applied in KlingService.submit, not here)
  - Midnight reset: reset() called by APScheduler at America/Mexico_City midnight
"""
import logging
from datetime import datetime, timezone

from supabase import Client

from app.services.telegram import send_alert_sync

logger = logging.getLogger(__name__)

TABLE = "kling_circuit_breaker_state"
SINGLETON_ID = 1
FAILURE_THRESHOLD = 0.20     # 20% failure rate threshold (VID-03)
BALANCE_ALERT_USD = 5.0      # Alert creator but proceed
BALANCE_HALT_USD = 1.0       # Block pipeline submission


class KlingCircuitBreakerService:
    """
    Failure-rate-based circuit breaker for Kling AI API calls.
    State persists in Postgres — survives service restarts.
    Implements VID-03.
    """

    def __init__(self, supabase: Client) -> None:
        self.db = supabase

    def get_state(self) -> dict:
        """Read singleton CB state from DB."""
        result = (
            self.db.table(TABLE)
            .select("*")
            .eq("id", SINGLETON_ID)
            .single()
            .execute()
        )
        return result.data

    def is_open(self) -> bool:
        """
        Returns True if CB is open (pipeline should NOT submit to Kling).
        Called by daily_pipeline.py before every Kling submission.
        Fail-open: returns False on any DB error so pipeline can continue.
        """
        try:
            state = self.get_state()
            return bool(state.get("is_open", False))
        except Exception as exc:
            logger.error(
                "KlingCB.is_open() check failed (fail-open): %s", exc,
                extra={"pipeline_step": "kling_cb", "content_history_id": ""},
            )
            return False

    def record_attempt(self, success: bool) -> bool:
        """
        Record a single Kling job attempt (success or failure).
        Updates total_attempts, total_failures, failure_rate in DB.
        If failure_rate exceeds 20% after this attempt, opens the CB.

        Args:
            success: True if Kling responded with a completed video; False on failure.

        Returns:
            True if pipeline should continue, False if CB just opened (or was already open).
        """
        state = self.get_state()

        # Fast path: CB already open
        if state.get("is_open"):
            logger.warning(
                "KlingCB already open — rejecting attempt",
                extra={"pipeline_step": "kling_cb", "content_history_id": ""},
            )
            return False

        new_attempts = state["total_attempts"] + 1
        new_failures = state["total_failures"] + (0 if success else 1)
        failure_rate = new_failures / new_attempts if new_attempts > 0 else 0.0

        logger.info(
            "KlingCB record_attempt: success=%s attempts=%d failures=%d rate=%.2f%%",
            success, new_attempts, new_failures, failure_rate * 100,
            extra={"pipeline_step": "kling_cb", "content_history_id": ""},
        )

        if failure_rate > FAILURE_THRESHOLD:
            logger.error(
                "KlingCB threshold exceeded: failure_rate=%.2f%% > %.0f%%",
                failure_rate * 100, FAILURE_THRESHOLD * 100,
                extra={"pipeline_step": "kling_cb", "content_history_id": ""},
            )
            self._trip(state, new_attempts, new_failures, failure_rate)
            return False

        # Update counts without opening CB
        self.db.table(TABLE).update({
            "total_attempts": new_attempts,
            "total_failures": new_failures,
            "failure_rate": float(failure_rate),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", SINGLETON_ID).execute()

        return True

    def _trip(
        self, state: dict, new_attempts: int, new_failures: int, failure_rate: float
    ) -> None:
        """Open CB and alert creator via Telegram."""
        now = datetime.now(timezone.utc)
        self.db.table(TABLE).update({
            "is_open": True,
            "opened_at": now.isoformat(),
            "total_attempts": new_attempts,
            "total_failures": new_failures,
            "failure_rate": float(failure_rate),
            "updated_at": now.isoformat(),
        }).eq("id", SINGLETON_ID).execute()

        logger.error(
            "KlingCB tripped: failure_rate=%.2f%% (threshold %.0f%%)",
            failure_rate * 100, FAILURE_THRESHOLD * 100,
            extra={"pipeline_step": "kling_cb", "content_history_id": ""},
        )

        send_alert_sync(
            f"ALERTA: Kling AI circuit breaker abierto. "
            f"Tasa de fallos: {failure_rate:.1%} (umbral: {FAILURE_THRESHOLD:.0%}). "
            "Pipeline detenido para evitar gastar creditos. "
            "Escribe /resume para reanudar cuando Kling este disponible."
        )

    def check_balance(self) -> bool:
        """
        fal.ai does not expose a public billing/balance REST API.
        Balance checking is disabled — returns True (fail-open) unconditionally.

        Original intent: halt pipeline at < $1.00, alert at < $5.00.
        Replacement strategy: monitor spend manually via fal.ai dashboard.
        """
        logger.debug(
            "KlingCB.check_balance() called — fal.ai billing API unavailable, "
            "returning True (fail-open). Monitor spend at https://fal.ai/dashboard.",
            extra={"pipeline_step": "kling_cb", "content_history_id": ""},
        )
        return True

    def reset(self) -> None:
        """
        Reset CB state. Called by:
          - /resume Telegram command (creator manually re-opens)
          - APScheduler midnight_reset job (daily cadence, America/Mexico_City)

        Does NOT preserve opened_at history — full reset for fresh 24h window.
        """
        now = datetime.now(timezone.utc)
        self.db.table(TABLE).update({
            "is_open": False,
            "opened_at": None,
            "total_attempts": 0,
            "total_failures": 0,
            "failure_rate": 0.0,
            "last_reset_at": now.isoformat(),
            "updated_at": now.isoformat(),
        }).eq("id", SINGLETON_ID).execute()
        logger.info(
            "KlingCB reset. Fresh 24h window started.",
            extra={"pipeline_step": "kling_cb", "content_history_id": ""},
        )
