import asyncio
import logging
from telegram.ext import Application, ApplicationBuilder
from app.settings import get_settings
from app.telegram.handlers.mood_flow import register_mood_handlers
from app.telegram.handlers.approval_flow import register_approval_handlers
from app.telegram.handlers.storage_confirm import register_storage_handlers

logger = logging.getLogger(__name__)

_application: Application | None = None


def build_telegram_app() -> Application:
    """
    Build PTB Application with polling enabled.
    Phase 2+ requires inbound polling for mood flow callback queries.
    NOTE: No .updater(None) here — that was Phase 1 outbound-only.
    Handlers are added by each feature module (e.g., mood_flow.py).
    """
    settings = get_settings()
    app = ApplicationBuilder().token(settings.telegram_bot_token).build()
    register_mood_handlers(app)
    register_approval_handlers(app)   # Phase 4: approval flow callbacks
    register_storage_handlers(app)    # Phase 6: storage lifecycle callbacks
    return app


async def start_telegram_polling(app: Application) -> None:
    """
    Initialize and start polling. Called from FastAPI lifespan startup.
    Stores reference for job threads to access via asyncio.run_coroutine_threadsafe.
    """
    await app.initialize()
    await app.start()
    await app.updater.start_polling(drop_pending_updates=True)
    logger.info("Telegram polling started.")


async def stop_telegram_polling(app: Application) -> None:
    """Called from FastAPI lifespan shutdown."""
    await app.updater.stop()
    await app.stop()
    await app.shutdown()
    logger.info("Telegram polling stopped.")
