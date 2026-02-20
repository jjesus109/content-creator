import asyncio
import logging
from functools import lru_cache

from telegram import Bot
from telegram.ext import ApplicationBuilder, filters

from app.settings import get_settings

logger = logging.getLogger(__name__)


@lru_cache
def get_telegram_bot() -> Bot:
    """
    Returns the Telegram Bot instance.
    Uses updater(None) — no polling. Phase 1 is outbound-only.
    Phase 4 will add inbound message handlers on top of this bot.
    """
    settings = get_settings()
    app = (
        ApplicationBuilder()
        .token(settings.telegram_bot_token)
        .updater(None)  # SCRTY-02: disable polling — FastAPI owns the event loop
        .build()
    )
    return app.bot


def get_creator_filter():
    """
    Returns the Telegram filter that silently drops messages from non-creator users.
    Apply this filter to ALL inbound message handlers (SCRTY-02).
    Messages NOT matching this filter produce no response — silent discard.
    Usage: MessageHandler(filters.TEXT & get_creator_filter(), handler_fn)
    """
    settings = get_settings()
    return filters.User(user_id=settings.telegram_creator_id)


async def send_alert(message: str) -> None:
    """
    Send a text alert to the creator's Telegram chat.
    Used by: circuit breaker escalation, future pipeline error handlers.
    """
    settings = get_settings()
    bot = get_telegram_bot()
    try:
        await bot.send_message(
            chat_id=settings.telegram_creator_id,
            text=message,
        )
        logger.info("Telegram alert sent to creator.")
    except Exception as e:
        logger.error("Failed to send Telegram alert: %s", e)


def send_alert_sync(message: str) -> None:
    """
    Synchronous wrapper for send_alert().
    Required because APScheduler thread pool jobs cannot use async directly.
    Creates a new event loop if none is running.
    """
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Schedule as a task on the existing loop (FastAPI's loop)
            asyncio.run_coroutine_threadsafe(send_alert(message), loop)
        else:
            loop.run_until_complete(send_alert(message))
    except RuntimeError:
        asyncio.run(send_alert(message))
