"""
Approval state management service for the Telegram approval loop.

All methods are synchronous — called from APScheduler thread context or from
PTB callback handlers via an asyncio bridge (run_in_executor / run_sync).

All approval state is DB-backed by design:
  - approval_events table: immutable record of every approve/reject action
  - rejection_constraints table: active constraints that guide future script generation

This makes the entire approval flow restart-safe. There are NO module-level
counters or in-memory state. Every method reads from or writes to the database.
"""
import logging
from datetime import date, datetime, timedelta, timezone

from supabase import Client

from app.services.database import get_supabase

logger = logging.getLogger(__name__)

# Map from rejection cause_code to the rejection_constraints pattern_type.
# 'script_error' affects script class / structure; all other codes affect topic choice.
_CAUSE_TO_PATTERN_TYPE: dict[str, str] = {
    "script_error": "script_class",
    "visual_error": "topic",
    "technical_error": "topic",
    "off_topic": "topic",
}


class ApprovalService:
    """
    Single source of truth for approval state in the Telegram approval loop.

    Wraps all DB reads and writes for:
      - Idempotency checks (is_already_actioned)
      - Recording approve/reject events (record_approve, record_reject)
      - Daily rejection counts (get_today_rejection_count)
      - Rejection constraint lifecycle (write_rejection_constraint,
        clear_constraints_for_approved_run)

    Accepts an optional supabase Client for testability without a live DB
    (mirrors VideoStorageService and SimilarityService patterns).
    """

    def __init__(self, supabase: Client | None = None) -> None:
        """
        Args:
            supabase: Optional pre-created Supabase Client (for unit tests).
                      If None, get_supabase() is called and cached by lru_cache.
        """
        self._supabase = supabase if supabase is not None else get_supabase()

    # ------------------------------------------------------------------
    # Idempotency guard
    # ------------------------------------------------------------------

    def is_already_actioned(self, content_history_id: str) -> bool:
        """
        Return True if an approval_events row already exists for this content.

        Prevents double-processing when a creator accidentally taps Approve/Reject
        twice, or when a Telegram update is re-delivered after a bot restart.

        Args:
            content_history_id: UUID of the content_history row being evaluated.

        Returns:
            True if an event already exists; False if this is the first action.
        """
        result = (
            self._supabase.table("approval_events")
            .select("id")
            .eq("content_history_id", content_history_id)
            .limit(1)
            .execute()
        )
        return bool(result.data)

    # ------------------------------------------------------------------
    # Recording actions
    # ------------------------------------------------------------------

    def record_approve(self, content_history_id: str) -> None:
        """
        Insert an 'approved' event into approval_events.

        cause_code is intentionally omitted (NULL) — the DB constraint
        allows NULL for approvals; cause_code is only required for rejections.

        Args:
            content_history_id: UUID of the content_history row being approved.
        """
        self._supabase.table("approval_events").insert(
            {
                "content_history_id": content_history_id,
                "action": "approved",
            }
        ).execute()

    def record_reject(self, content_history_id: str, cause_code: str) -> None:
        """
        Insert a 'rejected' event into approval_events.

        Args:
            content_history_id: UUID of the content_history row being rejected.
            cause_code: One of 'script_error', 'visual_error', 'technical_error',
                        'off_topic'. Enforced by DB CHECK constraint.
        """
        self._supabase.table("approval_events").insert(
            {
                "content_history_id": content_history_id,
                "action": "rejected",
                "cause_code": cause_code,
            }
        ).execute()

    # ------------------------------------------------------------------
    # Daily rejection count — DB-backed, restart-safe
    # ------------------------------------------------------------------

    def get_today_rejection_count(self) -> int:
        """
        Count rejection events recorded today (UTC calendar day).

        Reads from the DB on every call — NOT a module-level counter.
        This makes the service restart-safe: the count is correct even
        after a pod restart or re-deployment.

        Returns:
            Number of rejection events with created_at >= today 00:00 UTC
            and created_at < tomorrow 00:00 UTC.
        """
        today = date.today().isoformat()           # e.g. "2026-02-22"
        tomorrow = (date.today() + timedelta(days=1)).isoformat()

        result = (
            self._supabase.table("approval_events")
            .select("id", count="exact")
            .eq("action", "rejected")
            .gte("created_at", today)
            .lt("created_at", tomorrow)
            .execute()
        )
        return result.count or 0

    # ------------------------------------------------------------------
    # Rejection constraint lifecycle
    # ------------------------------------------------------------------

    def write_rejection_constraint(self, cause_code: str) -> None:
        """
        Insert a rejection constraint that guides future script generation.

        The constraint expires after 365 days (effectively permanent for the
        planning horizon) and is read by ScriptGenerationService at script
        generation time to avoid repeating rejected patterns.

        cause_code mapping:
          'script_error'  -> pattern_type 'script_class'
          all others      -> pattern_type 'topic'

        Args:
            cause_code: One of 'script_error', 'visual_error', 'technical_error',
                        'off_topic'.
        """
        pattern_type = _CAUSE_TO_PATTERN_TYPE.get(cause_code, "topic")
        expires_at = (
            datetime.now(tz=timezone.utc) + timedelta(days=365)
        ).isoformat()
        reason_text = f"Rechazado ({cause_code}) — evitar este patron"

        logger.info(
            "Writing rejection constraint: cause_code=%s pattern_type=%s expires_at=%s",
            cause_code,
            pattern_type,
            expires_at,
            extra={"pipeline_step": "approval_check", "content_history_id": ""},
        )

        self._supabase.table("rejection_constraints").insert(
            {
                "pattern_type": pattern_type,
                "reason_text": reason_text,
                "expires_at": expires_at,
            }
        ).execute()

    def clear_constraints_for_approved_run(self, content_history_id: str) -> None:
        """
        Expire all active constraints whose pattern_types match today's rejections.

        When the creator approves a piece of content after one or more same-day
        rejections, it signals that the current run's approach is acceptable.
        Constraints created from today's rejection cause_codes are expired
        immediately so they do not suppress future script generation.

        Note: today's rejections are queried for ANY content, not just
        content_history_id — daily rejections share cause categories across
        the session.

        Args:
            content_history_id: UUID of the approved content_history row.
                                 Used for log context only; not used in queries.
        """
        today = date.today().isoformat()
        tomorrow = (date.today() + timedelta(days=1)).isoformat()

        # 1. Collect all unique cause_codes from today's rejections.
        rejection_result = (
            self._supabase.table("approval_events")
            .select("cause_code")
            .eq("action", "rejected")
            .gte("created_at", today)
            .lt("created_at", tomorrow)
            .execute()
        )

        if not rejection_result.data:
            logger.debug(
                "clear_constraints_for_approved_run: no rejections today for content %s — nothing to clear",
                content_history_id,
            )
            return

        # 2. Map cause_codes to pattern_types.
        cause_codes = {
            row["cause_code"]
            for row in rejection_result.data
            if row.get("cause_code")
        }
        pattern_types = list(
            {_CAUSE_TO_PATTERN_TYPE.get(code, "topic") for code in cause_codes}
        )

        if not pattern_types:
            return

        # 3. Expire matching active constraints.
        now_iso = datetime.now(tz=timezone.utc).isoformat()

        logger.info(
            "clear_constraints_for_approved_run: expiring constraints for pattern_types=%s "
            "(triggered by approval of content %s)",
            pattern_types,
            content_history_id,
        )

        self._supabase.table("rejection_constraints").in_(
            "pattern_type", pattern_types
        ).update({"expires_at": now_iso}).execute()
