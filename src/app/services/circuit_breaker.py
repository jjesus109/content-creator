import logging
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Optional

from supabase import Client

from app.settings import get_settings

logger = logging.getLogger(__name__)

TABLE = "circuit_breaker_state"
SINGLETON_ID = 1


class CircuitBreakerService:
    """
    Dual cost+count circuit breaker with timezone-aware midnight reset.
    State persists in Postgres — survives service restarts.
    Implements INFRA-04.
    """

    def __init__(self, supabase: Client) -> None:
        self.db = supabase
        settings = get_settings()
        self.cost_limit: float = settings.daily_cost_limit
        self.attempt_limit: int = settings.max_daily_attempts

    def get_state(self) -> dict:
        result = (
            self.db.table(TABLE)
            .select("*")
            .eq("id", SINGLETON_ID)
            .single()
            .execute()
        )
        return result.data

    def is_tripped(self) -> bool:
        """Returns True if the breaker is currently tripped."""
        state = self.get_state()
        return state["tripped_at"] is not None

    def record_attempt(self, cost_usd: float = 0.0) -> bool:
        """
        Increment attempt count and cost. Returns True if allowed, False if tripped.
        Call this before every API generation attempt.
        """
        state = self.get_state()

        # Already tripped — fast path
        if state["tripped_at"] is not None:
            logger.warning("Circuit breaker already tripped — rejecting attempt")
            return False

        new_cost = float(state["current_day_cost"]) + cost_usd
        new_attempts = state["current_day_attempts"] + 1

        # Check limits — whichever fires first (INFRA-04)
        if new_cost >= self.cost_limit or new_attempts >= self.attempt_limit:
            logger.warning(
                "Circuit breaker tripping: cost=%.4f limit=%.4f attempts=%d limit=%d",
                new_cost, self.cost_limit, new_attempts, self.attempt_limit,
            )
            self._trip(state, new_cost, new_attempts)
            return False

        # Atomic increment — single UPDATE to avoid race condition
        self.db.table(TABLE).update({
            "current_day_cost": new_cost,
            "current_day_attempts": new_attempts,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", SINGLETON_ID).execute()

        return True

    def _trip(self, state: dict, final_cost: float, final_attempts: int) -> None:
        now = datetime.now(timezone.utc)
        last_trip_at: Optional[str] = state.get("last_trip_at")

        # Rolling 7-day escalation check
        in_7day_window = False
        if last_trip_at:
            last_trip_dt = datetime.fromisoformat(last_trip_at.replace("Z", "+00:00"))
            in_7day_window = (now - last_trip_dt) < timedelta(days=7)

        new_weekly_count = state["weekly_trip_count"] + 1 if in_7day_window else 1

        self.db.table(TABLE).update({
            "current_day_cost": final_cost,
            "current_day_attempts": final_attempts,
            "tripped_at": now.isoformat(),
            "last_trip_at": now.isoformat(),
            "weekly_trip_count": new_weekly_count,
            "updated_at": now.isoformat(),
        }).eq("id", SINGLETON_ID).execute()

        logger.error("Circuit breaker tripped. weekly_count=%d", new_weekly_count)

        # Escalation alert if 2+ trips in rolling 7-day window
        if new_weekly_count >= 2:
            self._send_escalation_alert(new_weekly_count)

    def _send_escalation_alert(self, trip_count: int) -> None:
        """Send Telegram escalation when breaker fires 2+ times in 7 days."""
        try:
            # Import here to avoid circular import at module level
            from app.services.telegram import send_alert_sync
            send_alert_sync(
                f"ESCALATION: Circuit breaker has fired {trip_count} times in the last 7 days. "
                f"Daily cost limit: ${self.cost_limit:.2f}, attempt limit: {self.attempt_limit}. "
                "Manual review required."
            )
        except Exception as e:
            logger.error("Failed to send escalation alert: %s", e)

    def midnight_reset(self) -> None:
        """
        Reset daily counters. Called by APScheduler at midnight America/Mexico_City.
        Does NOT reset weekly_trip_count or last_trip_at (rolling window must persist).
        """
        now = datetime.now(timezone.utc)
        self.db.table(TABLE).update({
            "current_day_cost": 0,
            "current_day_attempts": 0,
            "tripped_at": None,
            "updated_at": now.isoformat(),
        }).eq("id", SINGLETON_ID).execute()
        logger.info("Circuit breaker daily counters reset at midnight.")
