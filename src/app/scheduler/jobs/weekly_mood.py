import asyncio
import logging
from app.settings import get_settings
from app.services.mood import MoodService
from app.services.database import get_supabase

logger = logging.getLogger(__name__)


def _get_bot_and_loop():
    """Retrieve PTB bot and event loop from FastAPI app state via telegram service."""
    from app.services.telegram import _fastapi_app
    if _fastapi_app is None:
        raise RuntimeError("FastAPI app not available — weekly mood job ran before lifespan startup")
    bot = _fastapi_app.state.telegram_app.bot
    loop = asyncio.get_event_loop()
    return bot, loop


def weekly_mood_prompt_job() -> None:
    """
    APScheduler job: fires Monday 9 AM Mexico City.
    Sends the 3-step mood selection prompt to the creator.
    """
    settings = get_settings()
    try:
        bot, loop = _get_bot_and_loop()
        from app.telegram.handlers.mood_flow import send_mood_prompt_sync
        send_mood_prompt_sync(bot, settings.telegram_creator_id, loop)
        logger.info("Weekly mood prompt sent to creator (chat_id=%d)", settings.telegram_creator_id)
    except Exception as e:
        logger.error("Failed to send weekly mood prompt: %s", e)


def weekly_mood_reminder_job() -> None:
    """
    APScheduler job: fires Monday 1 PM Mexico City (4 hours after prompt).
    Sends one reminder if creator has not yet responded.
    """
    settings = get_settings()
    try:
        mood_svc = MoodService(get_supabase())
        if mood_svc.has_profile_this_week():
            logger.info("Weekly mood reminder: creator already responded — skipping.")
            return

        bot, loop = _get_bot_and_loop()
        from app.telegram.handlers.mood_flow import send_mood_prompt_sync
        send_mood_prompt_sync(bot, settings.telegram_creator_id, loop)
        logger.info("Weekly mood reminder sent (creator had not responded).")
    except Exception as e:
        logger.error("Failed to send weekly mood reminder: %s", e)
