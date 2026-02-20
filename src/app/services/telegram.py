import asyncio
import logging
from telegram import Bot
from telegram.ext import filters
from app.settings import get_settings

logger = logging.getLogger(__name__)

# _fastapi_app holds the FastAPI app reference set during lifespan startup.
# Used by APScheduler thread pool jobs to access app.state.telegram_app.
_fastapi_app = None


def set_fastapi_app(fastapi_app) -> None:
    """Called from main.py lifespan after telegram app is built."""
    global _fastapi_app
    _fastapi_app = fastapi_app


def get_telegram_bot() -> Bot:
    """
    Returns the Bot from the running PTB Application.
    Requires lifespan to have set _fastapi_app (called by set_fastapi_app in main.py).
    """
    if _fastapi_app is None:
        raise RuntimeError("FastAPI app not set — call set_fastapi_app() first")
    return _fastapi_app.state.telegram_app.bot


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
        await bot.send_message(chat_id=settings.telegram_creator_id, text=message)
        logger.info("Telegram alert sent to creator.")
    except Exception as e:
        logger.error("Failed to send Telegram alert: %s", e)


def send_alert_sync(message: str) -> None:
    """Sync wrapper for APScheduler thread pool jobs — same pattern as Phase 1."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.run_coroutine_threadsafe(send_alert(message), loop)
        else:
            loop.run_until_complete(send_alert(message))
    except RuntimeError:
        asyncio.run(send_alert(message))
