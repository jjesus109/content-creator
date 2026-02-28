"""
Storage Lifecycle Service — Supabase Storage only. No R2, no boto3.

Architecture (locked from CONTEXT.md):
- Warm (8-45 days): DB label only. storage_status set to 'warm'.
  File stays in Supabase Storage bucket — NO copy, NO R2.
- Cold (45+ days): file deleted from Supabase Storage via
  supabase.storage.from_().remove(). DB record is KEPT for analytics.
- 7-day pre-warning fires at 38 days old (before 45-day deletion).
- "Save forever" button marks video as Eternal and cancels deletion.
"""
import logging
import re
from datetime import datetime, timezone

from app.services.database import get_supabase
from app.services.telegram import get_telegram_bot
from app.settings import get_settings

logger = logging.getLogger(__name__)

# Supabase Storage bucket for videos — must match VideoStorageService from Phase 3.
SUPABASE_VIDEO_BUCKET = "videos"


class StorageLifecycleService:
    """
    Manages video storage lifecycle transitions using Supabase Storage.

    Accepts an optional supabase client in __init__ for testability
    (same pattern as SimilarityService, VideoStorageService).
    """

    def __init__(self, supabase=None):
        self._supabase = supabase

    def _get_supabase(self):
        """Return injected client or singleton."""
        return self._supabase or get_supabase()

    # ------------------------------------------------------------------
    # Warm transition — DB update only, no file copy
    # ------------------------------------------------------------------

    def transition_to_warm(self, content_history_id: str) -> None:
        """
        Mark video as warm in DB. File stays in Supabase Storage bucket — no copy needed.

        Warm tier = DB label only. storage_status set to 'warm'.
        The actual file remains in the same Supabase Storage bucket, untouched.
        """
        supabase = self._get_supabase()
        supabase.table("content_history").update({
            "storage_status": "warm",
            "storage_tier_set_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", content_history_id).execute()
        logger.info("Transitioned to warm (DB only): content_history_id=%s", content_history_id[:8])

    # ------------------------------------------------------------------
    # Cold deletion — delete file from Supabase Storage; keep DB record
    # ------------------------------------------------------------------

    def delete_from_supabase_storage(self, content_history_id: str) -> None:
        """
        Delete video file from Supabase Storage. DB record (content_history row) is preserved for analytics.

        Cold tier = file deletion from Supabase Storage only.
        The content_history row is NEVER deleted — it holds analytics data.
        """
        supabase = self._get_supabase()

        # Fetch the storage path — stored in video_url as a full Supabase Storage public URL.
        # Pattern: "https://<project>.supabase.co/storage/v1/object/public/videos/<path>"
        row_result = supabase.table("content_history").select("video_url").eq(
            "id", content_history_id
        ).single().execute()
        row = row_result.data

        if not row or not row.get("video_url"):
            logger.warning(
                "No video_url found for content_history_id=%s — skipping Supabase deletion",
                content_history_id[:8],
            )
            return

        video_url = row["video_url"]

        # Extract bucket and path from Supabase Storage public URL.
        match = re.search(r"/object/public/([^/]+)/(.+)$", video_url)
        if match:
            bucket = match.group(1)
            storage_path = match.group(2)
        else:
            # Fallback: treat video_url as a direct storage path.
            bucket = SUPABASE_VIDEO_BUCKET
            storage_path = video_url

        try:
            supabase.storage.from_(bucket).remove([storage_path])
            logger.info(
                "Deleted from Supabase Storage: bucket=%s path=%s", bucket, storage_path
            )
        except Exception as exc:
            logger.error(
                "Supabase Storage delete failed for %s: %s", content_history_id[:8], exc
            )
            raise

        # Update DB: mark as deleted. DB record is KEPT — do NOT delete the row.
        supabase.table("content_history").update({
            "storage_status": "deleted",
            "deletion_requested_at": None,
            "storage_tier_set_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", content_history_id).execute()
        logger.info(
            "Marked storage_status=deleted in DB: content_history_id=%s", content_history_id[:8]
        )

    # ------------------------------------------------------------------
    # 7-day pre-warning (fires at 38-44 days old)
    # ------------------------------------------------------------------

    async def send_7day_warning(
        self, content_history_id: str, topic_summary: str, days_old: int
    ) -> None:
        """
        Send 7-day pre-deletion warning. Creator can tap 'Save forever' to mark video as Eternal.

        Fires when video is 38-44 days old (7 days before scheduled 45-day deletion).
        Idempotency: lifecycle job queries only warm videos 38-44 days old with
        deletion_requested_at IS NULL — the job handles deduplication at query level.
        """
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup

        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton(
                "Guardar para siempre",
                callback_data=f"stor_eternal:{content_history_id}",
            ),
            InlineKeyboardButton(
                "OK, entendido",
                callback_data=f"stor_warn_ok:{content_history_id}",
            ),
        ]])

        bot = get_telegram_bot()
        settings = get_settings()
        await bot.send_message(
            chat_id=settings.telegram_creator_id,
            text=(
                f"AVISO: Video sera eliminado en 7 dias\n\n"
                f"Video: {topic_summary[:60]}\n"
                f"Edad: {days_old} dias\n"
                f"Eliminacion programada en: {45 - days_old} dias\n\n"
                "Toca 'Guardar para siempre' para conservar el archivo."
            ),
            reply_markup=keyboard,
        )
        # No DB update needed here — lifecycle job query handles idempotency via:
        # storage_status='warm' AND deletion_requested_at IS NULL AND age BETWEEN 38-44 days.
        logger.info(
            "Sent 7-day pre-deletion warning for content_history_id=%s", content_history_id[:8]
        )

    # ------------------------------------------------------------------
    # 45-day deletion confirmation (actual deletion request)
    # ------------------------------------------------------------------

    async def request_deletion_confirmation(
        self, content_history_id: str, topic_summary: str, days_old: int
    ) -> None:
        """
        Send 45-day deletion confirmation. Creator must confirm before file is deleted.

        Sets storage_status = 'pending_deletion' and records deletion_requested_at.
        If creator does not confirm within 24h, reset_expired_deletion_requests() will
        reset the row back to 'warm' (safe default — do NOT delete without confirmation).
        """
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup

        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton(
                "Confirmar Eliminacion",
                callback_data=f"stor_confirm:{content_history_id}",
            ),
            InlineKeyboardButton(
                "Cancelar",
                callback_data=f"stor_cancel:{content_history_id}",
            ),
        ]])

        bot = get_telegram_bot()
        settings = get_settings()
        await bot.send_message(
            chat_id=settings.telegram_creator_id,
            text=(
                f"ALMACENAMIENTO: Video elegible para eliminacion\n\n"
                f"Video: {topic_summary[:60]}\n"
                f"Edad: {days_old} dias\n\n"
                "Si no confirmas en 24 horas, el archivo NO sera eliminado."
            ),
            reply_markup=keyboard,
        )

        supabase = self._get_supabase()
        supabase.table("content_history").update({
            "deletion_requested_at": datetime.now(timezone.utc).isoformat(),
            "storage_status": "pending_deletion",
        }).eq("id", content_history_id).execute()
        logger.info(
            "Deletion confirmation requested for content_history_id=%s", content_history_id[:8]
        )

    # ------------------------------------------------------------------
    # Expired deletion request reset (safe default: do NOT delete)
    # ------------------------------------------------------------------

    def reset_expired_deletion_requests(self) -> int:
        """
        Reset deletion requests that were not confirmed within 24 hours.

        Finds rows where:
          - storage_status = 'pending_deletion'
          - deletion_requested_at < NOW() - 24h

        Resets them to storage_status = 'warm', deletion_requested_at = NULL.
        Returns the count of rows reset. Safe default: do NOT delete without confirmation.
        """
        from datetime import timedelta

        supabase = self._get_supabase()
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()

        # Fetch expired rows to get count
        expired_rows = supabase.table("content_history").select("id").eq(
            "storage_status", "pending_deletion"
        ).lt("deletion_requested_at", cutoff).execute()

        if not expired_rows.data:
            return 0

        count = len(expired_rows.data)
        expired_ids = [row["id"] for row in expired_rows.data]

        # Reset each expired row
        for content_history_id in expired_ids:
            supabase.table("content_history").update({
                "storage_status": "warm",
                "deletion_requested_at": None,
            }).eq("id", content_history_id).execute()

        logger.info(
            "Reset %d expired deletion requests back to warm storage_status", count
        )
        return count
