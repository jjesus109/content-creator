"""Creator-only /resume command handler — clears circuit breaker daily halt and triggers immediate pipeline rerun."""
import logging

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from app.services.telegram import get_creator_filter

logger = logging.getLogger(__name__)


async def handle_resume(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Creator types /resume — clears circuit breaker daily halt and triggers immediate pipeline rerun.

    All DB/service imports are lazy (inside function body) to avoid circular import chain.
    No confirmation message sent to creator (CONTEXT.md locked decision: no confirmation message).
    """
    # Lazy imports to avoid circular import chain at module load time
    from app.services.database import get_supabase
    from app.services.circuit_breaker import CircuitBreakerService
    from app.scheduler.jobs.daily_pipeline import trigger_immediate_rerun

    supabase = get_supabase()
    cb = CircuitBreakerService(supabase)
    cb.clear_daily_halt()
    trigger_immediate_rerun()

    logger.info(
        "Manual resume executed by creator.",
        extra={"pipeline_step": "manual_resume", "content_history_id": ""},
    )


def register_resume_handler(app: Application) -> None:
    """
    Attach the /resume CommandHandler to the PTB Application.
    Filters to creator ID only — consistent with existing bot security model (SCRTY-02).
    Called from build_telegram_app() in src/app/telegram/app.py.
    """
    creator_filter = get_creator_filter()
    app.add_handler(CommandHandler("resume", handle_resume, filters=creator_filter))
    logger.info("Resume handler registered.")
