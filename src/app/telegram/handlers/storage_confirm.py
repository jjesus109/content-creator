"""
Telegram callback handlers for the storage lifecycle approval flow.

Four CallbackQueryHandlers cover the complete storage decision loop:
  - handle_storage_confirm: Creator confirms deletion — file deleted from Supabase Storage.
  - handle_storage_cancel:  Creator cancels deletion — row reset to warm.
  - handle_storage_eternal: Creator taps "Save forever" — video marked Eternal, never deleted.
  - handle_storage_warn_ok: Creator acknowledges 7-day warning — no action needed.

Design follows the same patterns as approval_flow.py:
  - await query.answer() is always the FIRST async call to prevent Telegram spinner freeze.
  - DB state is read on every invocation — never from context.bot_data (restart-safe).
  - Idempotency checks guard against double-tap and Telegram retry delivery.
  - update.effective_chat.send_message() used for all outbound messages (update.message is
    None in CallbackQuery handlers).
"""
import logging

from telegram import Update
from telegram.ext import Application, CallbackQueryHandler, ContextTypes

from app.services.database import get_supabase

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Callback data prefixes
# Lengths chosen to keep total callback_data under Telegram's 64-byte limit.
# Prefix + 36-char UUID must be <= 64 bytes total.
# ---------------------------------------------------------------------------
PREFIX_STORAGE_CONFIRM = "stor_confirm:"   # 13 chars + 36-char UUID = 49 bytes (under 64-byte limit)
PREFIX_STORAGE_CANCEL  = "stor_cancel:"    # 12 chars + 36-char UUID = 48 bytes (under 64-byte limit)
PREFIX_STORAGE_ETERNAL = "stor_eternal:"   # 13 chars + 36-char UUID = 49 bytes (under 64-byte limit)
PREFIX_STORAGE_WARN_OK = "stor_warn_ok:"   # 13 chars + 36-char UUID = 49 bytes (under 64-byte limit)


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------

async def handle_storage_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Creator tapped 'Confirmar Eliminacion'.

    Flow:
      1. Acknowledge callback (prevents Telegram loading spinner freeze).
      2. Extract content_history_id from callback_data.
      3. Check idempotency — if already deleted, reply and return.
      4. Check is_viral/is_eternal safety guards — exempt videos must never be deleted.
      5. Delete file from Supabase Storage and update storage_status='deleted' in DB.
         DB record (content_history row) is KEPT for analytics.
      6. Confirm deletion to creator.
    """
    query = update.callback_query
    await query.answer()  # REQUIRED FIRST — prevents Telegram loading spinner freeze

    content_history_id = query.data.removeprefix(PREFIX_STORAGE_CONFIRM)

    supabase = get_supabase()

    # Idempotency: check current storage_status
    row_result = supabase.table("content_history").select(
        "storage_status, is_viral, is_eternal"
    ).eq("id", content_history_id).single().execute()
    row = row_result.data

    if not row:
        await update.effective_chat.send_message("Video no encontrado.")
        return

    if row.get("storage_status") == "deleted":
        await update.effective_chat.send_message("Ya eliminado.")
        return

    # Safety guard: viral or eternal videos must never be deleted.
    if row.get("is_viral") or row.get("is_eternal"):
        await update.effective_chat.send_message(
            "Este video esta marcado como exento. No se eliminara."
        )
        return

    # Delete file from Supabase Storage. DB record is KEPT.
    from app.services.storage_lifecycle import StorageLifecycleService
    StorageLifecycleService().delete_from_supabase_storage(content_history_id)

    await update.effective_chat.send_message(
        "Video eliminado del almacenamiento. El registro de analiticas se conserva."
    )
    logger.info("Storage confirmed — deleted: content_history_id=%s", content_history_id[:8])


async def handle_storage_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Creator tapped 'Cancelar'.

    Flow:
      1. Acknowledge callback.
      2. Extract content_history_id.
      3. Reset: deletion_requested_at = NULL, storage_status = 'warm'.
      4. Confirm cancellation to creator.
    """
    query = update.callback_query
    await query.answer()  # REQUIRED FIRST

    content_history_id = query.data.removeprefix(PREFIX_STORAGE_CANCEL)

    supabase = get_supabase()
    supabase.table("content_history").update({
        "deletion_requested_at": None,
        "storage_status": "warm",
    }).eq("id", content_history_id).execute()

    await update.effective_chat.send_message(
        "Eliminacion cancelada. El archivo se conserva."
    )
    logger.info("Storage cancel: content_history_id=%s", content_history_id[:8])


async def handle_storage_eternal(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Creator tapped 'Guardar para siempre'.

    Flow:
      1. Acknowledge callback.
      2. Extract content_history_id.
      3. Check idempotency — if already eternal, reply and return.
      4. Mark video as Eternal: is_eternal=true, storage_status='warm', deletion_requested_at=None.
      5. Confirm to creator — video will never be auto-deleted.
    """
    query = update.callback_query
    await query.answer()  # REQUIRED FIRST

    content_history_id = query.data.removeprefix(PREFIX_STORAGE_ETERNAL)

    supabase = get_supabase()

    # Idempotency: check if already eternal
    row_result = supabase.table("content_history").select("is_eternal").eq(
        "id", content_history_id
    ).single().execute()
    row = row_result.data

    if row and row.get("is_eternal"):
        await update.effective_chat.send_message("Ya marcado como eterno.")
        return

    # Mark video as Eternal — cancels all future deletion.
    supabase.table("content_history").update({
        "is_eternal": True,
        "storage_status": "warm",
        "deletion_requested_at": None,
    }).eq("id", content_history_id).execute()

    await update.effective_chat.send_message(
        "Video marcado como 'Guardar para siempre'. No sera eliminado automaticamente."
    )
    logger.info("Storage eternal: content_history_id=%s", content_history_id[:8])


async def handle_storage_warn_ok(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Creator acknowledged the 7-day pre-deletion warning.

    Flow:
      1. Acknowledge callback.
      2. Reply with acknowledgement message.
      3. No DB update needed — lifecycle job handles 45-day transition separately
         via storage_status='warm' AND deletion_requested_at IS NULL query.
    """
    query = update.callback_query
    await query.answer()  # REQUIRED FIRST

    await update.effective_chat.send_message(
        "Entendido. Te avisaremos de nuevo cuando llegue el momento de confirmar la eliminacion."
    )
    logger.info("Storage warn_ok acknowledged.")


# ---------------------------------------------------------------------------
# Handler registration
# ---------------------------------------------------------------------------

def register_storage_handlers(app: Application) -> None:
    """
    Attach storage lifecycle CallbackQueryHandlers to the PTB Application.

    Called from build_telegram_app() in src/app/telegram/app.py.
    Uses callback_data prefix matching — no ConversationHandler needed.
    """
    app.add_handler(CallbackQueryHandler(handle_storage_confirm, pattern=f"^{PREFIX_STORAGE_CONFIRM}"))
    app.add_handler(CallbackQueryHandler(handle_storage_cancel,  pattern=f"^{PREFIX_STORAGE_CANCEL}"))
    app.add_handler(CallbackQueryHandler(handle_storage_eternal, pattern=f"^{PREFIX_STORAGE_ETERNAL}"))
    app.add_handler(CallbackQueryHandler(handle_storage_warn_ok, pattern=f"^{PREFIX_STORAGE_WARN_OK}"))
    logger.info("Storage lifecycle handlers registered.")
