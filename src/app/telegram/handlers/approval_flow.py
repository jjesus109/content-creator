"""
Telegram callback handlers for the creator approval flow.

Three CallbackQueryHandlers cover the complete approval loop:
  - handle_approve: Records approval, clears constraints, confirms to creator.
  - handle_reject:  Opens a 4-button cause selection menu.
  - handle_cause:   Records rejection with cause, writes constraint, triggers re-run.

All state is read from DB on every invocation — never from context.bot_data.
This makes the flow restart-safe after pod restarts or re-deployments.

Design notes:
  - await query.answer() is always the FIRST async call in every handler to prevent
    the Telegram loading spinner from freezing on the creator's device.
  - update.effective_chat.send_message() is used for all outbound messages because
    update.message is None in CallbackQuery handlers.
  - ApprovalService is instantiated inside each handler body (lazy/local import) to
    prevent circular imports at module load time — same pattern as mood_flow.py:144.
  - The original approval message with its Approve/Reject buttons is NOT edited;
    only new messages are sent (user decision: original message stays unchanged).
"""
import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, ContextTypes

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Callback data prefixes
# Lengths chosen to keep total callback_data under Telegram's 64-byte limit.
# ---------------------------------------------------------------------------
PREFIX_APPROVE = "appr_approve:"   # 13 chars + 36-char UUID = 49 bytes  (OK)
PREFIX_REJECT  = "appr_reject:"    # 12 chars + 36-char UUID = 48 bytes  (OK)
PREFIX_CAUSE   = "appr_cause:"     # 11 chars + 36-char UUID + ":" + cause_code
                                   # longest: 11+36+1+15 = 63 bytes (technical_error) — just under limit

# ---------------------------------------------------------------------------
# Cause options — display labels paired with DB-stored cause_codes
# ---------------------------------------------------------------------------
CAUSE_OPTIONS = [
    ("Script Error",    "script_error"),
    ("Visual Error",    "visual_error"),
    ("Technical Error", "technical_error"),
    ("Off-topic",       "off_topic"),
]


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------

async def handle_approve(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Creator tapped Approve.

    Flow:
      1. Acknowledge callback (prevents Telegram loading spinner freeze).
      2. Check idempotency — silently skip if already actioned.
      3. Record approval event in DB.
      4. Clear same-day rejection constraints (if any existed).
      5. Confirm to creator via new message.
    """
    query = update.callback_query
    await query.answer()  # REQUIRED FIRST — prevents Telegram loading spinner freeze

    content_history_id = query.data[len(PREFIX_APPROVE):]

    # Cancel the 24h approval timeout job — non-fatal if already fired or not found
    from app.scheduler.jobs.approval_timeout import _scheduler as _approval_timeout_scheduler
    try:
        if _approval_timeout_scheduler is not None:
            _approval_timeout_scheduler.remove_job(f"approval_timeout_{content_history_id}")
            logger.info("Approval timeout job cancelled for %s", content_history_id[:8])
    except Exception:
        pass  # Job may have already fired or ID not found — non-fatal

    # Local import — prevents circular import at module load time
    from app.services.approval import ApprovalService
    approval_svc = ApprovalService()

    if approval_svc.is_already_actioned(content_history_id):
        await update.effective_chat.send_message("Ya procesado.")
        return

    approval_svc.record_approve(content_history_id)
    approval_svc.clear_constraints_for_approved_run(content_history_id)

    # Schedule platform publish jobs (PUBL-01, PUBL-02)
    # Retrieve video_url and scheduler from app state
    from app.services.publishing import schedule_platform_publishes
    from app.services.telegram import send_publish_confirmation_sync
    from app.services.database import get_supabase
    from datetime import datetime, timezone as tz_module

    supabase = get_supabase()
    video_row = supabase.table("content_history").select(
        "video_url, post_copy_tiktok"
    ).eq("id", content_history_id).single().execute()
    video_url = video_row.data.get("video_url", "")
    tiktok_copy = video_row.data.get("post_copy_tiktok", "") or ""

    # Get scheduler from FastAPI app state (same pattern as registry.py)
    from app.services.telegram import _fastapi_app
    scheduler = _fastapi_app.state.scheduler

    approval_time = datetime.now(tz=tz_module.utc)
    scheduled_times = schedule_platform_publishes(
        scheduler=scheduler,
        content_history_id=content_history_id,
        video_url=video_url,
        approval_time=approval_time,
    )

    # Confirmation message: separate message (CONTEXT.md: original approval message stays unchanged)
    send_publish_confirmation_sync(content_history_id, scheduled_times, video_url=video_url, tiktok_copy=tiktok_copy)

    logger.info("Approved and publish jobs scheduled: content_history_id=%s", content_history_id)


async def handle_reject(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Creator tapped Reject with Cause.

    Flow:
      1. Acknowledge callback.
      2. Build a 4-button cause selection keyboard (each button on its own row).
      3. Send the cause menu as a new message.

    No idempotency check here — showing the cause menu is always safe.
    The actual rejection is recorded only in handle_cause.
    """
    query = update.callback_query
    await query.answer()  # REQUIRED FIRST

    content_history_id = query.data[len(PREFIX_REJECT):]

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(label, callback_data=f"{PREFIX_CAUSE}{content_history_id}:{code}")]
        for label, code in CAUSE_OPTIONS
    ])

    await update.effective_chat.send_message(
        "Selecciona la causa del rechazo:",
        reply_markup=keyboard,
    )
    logger.info("Rejection cause menu sent: content_history_id=%s", content_history_id)


async def handle_cause(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Creator selected a rejection cause.

    Flow:
      1. Acknowledge callback.
      2. Parse content_history_id and cause_code from callback_data.
         rsplit(":", 1) is used — UUIDs contain hyphens but no colons, so
         rsplit correctly splits only on the separator injected by handle_reject.
      3. Check idempotency.
      4. Record rejection event in DB.
      5. Write rejection constraint for future script generation.
      6. Check daily rejection count:
           - If >= 2: notify creator that next video arrives tomorrow.
           - Otherwise: notify creator of ~15-minute rerun, then trigger it.
    """
    query = update.callback_query
    await query.answer()  # REQUIRED FIRST

    # Parse callback_data: PREFIX_CAUSE + UUID + ":" + cause_code
    payload = query.data[len(PREFIX_CAUSE):]
    content_history_id, cause_code = payload.rsplit(":", 1)

    # Local import — prevents circular import at module load time
    from app.services.approval import ApprovalService
    approval_svc = ApprovalService()

    if approval_svc.is_already_actioned(content_history_id):
        await update.effective_chat.send_message("Ya procesado.")
        return

    approval_svc.record_reject(content_history_id, cause_code)
    approval_svc.write_rejection_constraint(cause_code)

    rejection_count = approval_svc.get_today_rejection_count()

    if rejection_count >= 2:
        # Daily limit reached — use dynamic pipeline_hour from settings (not hardcoded)
        from app.settings import get_settings
        settings = get_settings()
        await update.effective_chat.send_message(
            f"Limite diario alcanzado. El proximo video llega manana a las {settings.pipeline_hour:02d}:00."
        )
        logger.info("Rejected (%s): content_history_id=%s", cause_code, content_history_id)
        return

    # Daily limit not yet reached — confirm rerun
    await update.effective_chat.send_message(
        f"⚠️ Rechazado ({cause_code}) — nuevo video en camino en ~15 minutos"
    )

    # Trigger immediate pipeline rerun — function defined in plan 04-04
    from app.scheduler.jobs.daily_pipeline import trigger_immediate_rerun
    trigger_immediate_rerun()

    logger.info("Rejected (%s): content_history_id=%s", cause_code, content_history_id)


# ---------------------------------------------------------------------------
# Handler registration
# ---------------------------------------------------------------------------

def register_approval_handlers(app: Application) -> None:
    """
    Attach approval flow CallbackQueryHandlers to the PTB Application.

    Called from build_telegram_app() in src/app/telegram/app.py.
    Uses callback_data prefix matching — no ConversationHandler needed.
    """
    app.add_handler(CallbackQueryHandler(handle_approve, pattern=f"^{PREFIX_APPROVE}"))
    app.add_handler(CallbackQueryHandler(handle_reject,  pattern=f"^{PREFIX_REJECT}"))
    app.add_handler(CallbackQueryHandler(handle_cause,   pattern=f"^{PREFIX_CAUSE}"))
    logger.info("Approval flow handlers registered.")
