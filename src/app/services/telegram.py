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
    Falls back to a direct Bot instance if the FastAPI app isn't initialized yet
    (e.g. APScheduler jobs firing before lifespan completes, or manual test runs).
    """
    settings = get_settings()
    try:
        bot = get_telegram_bot()
    except RuntimeError:
        bot = Bot(token=settings.telegram_bot_token)
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


async def send_approval_message(content_history_id: str, video_url: str) -> None:
    """
    Send the approval Telegram message to the creator after a video reaches READY status.

    Loads the content_history row, generates post_copy if missing, extracts a thumbnail,
    builds a caption with metadata (date, word count, mood profile, background filename),
    and sends a photo (or text fallback) with Approve / Reject inline buttons.

    Called via send_approval_message_sync() from _process_completed_render() in heygen.py.
    """
    from app.services.post_copy import PostCopyService, extract_thumbnail
    from app.services.database import get_supabase
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup

    bot = get_telegram_bot()
    settings = get_settings()
    supabase = get_supabase()

    # Load content_history row
    row_result = supabase.table("content_history").select(
        "script_text, topic_summary, post_copy, background_url, created_at"
    ).eq("id", content_history_id).single().execute()
    row = row_result.data

    # Query mood_profiles for the latest profile text
    mood_result = supabase.table("mood_profiles").select("profile_text").order("created_at", desc=True).limit(1).execute()
    if mood_result.data:
        mood_label = mood_result.data[0]["profile_text"][:40]
    else:
        mood_label = "—"

    # Generate post_copy if missing and persist it
    post_copy = row.get("post_copy")
    if not post_copy:
        post_copy = PostCopyService().generate(row["script_text"], row["topic_summary"])
        supabase.table("content_history").update({"post_copy": post_copy}).eq("id", content_history_id).execute()

    # Extract thumbnail — fallback to None on failure
    thumbnail_bio = None
    try:
        thumbnail_bio = extract_thumbnail(video_url)
    except Exception as exc:
        logger.error("Thumbnail extraction failed for content_history_id=%s: %s", content_history_id, exc)

    # Build caption metadata fields
    generation_date = row["created_at"][:10]
    word_count = len(row["script_text"].split())
    background_short = row["background_url"].split("/")[-1] if row.get("background_url") else "—"

    caption = (
        f"{post_copy}\n\n"
        f"---\n"
        f"Video: {video_url}\n"
        f"Fecha: {generation_date} | Palabras: {word_count}\n"
        f"Mood: {mood_label} | Fondo: {background_short}"
    )
    if len(caption) > 1024:
        caption = caption[:1021] + "..."

    # Inline approval keyboard
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Aprobar",              callback_data=f"appr_approve:{content_history_id}"),
        InlineKeyboardButton("❌ Rechazar con Causa",   callback_data=f"appr_reject:{content_history_id}"),
    ]])

    # Send photo or text fallback
    if thumbnail_bio is not None:
        await bot.send_photo(
            chat_id=settings.telegram_creator_id,
            photo=thumbnail_bio,
            caption=caption,
            reply_markup=keyboard,
        )
    else:
        await bot.send_message(
            chat_id=settings.telegram_creator_id,
            text=caption,
            reply_markup=keyboard,
        )

    logger.info("Approval message sent for content_history_id=%s", content_history_id)


def send_approval_message_sync(content_history_id: str, video_url: str) -> None:
    """
    Sync wrapper for APScheduler thread pool / executor context.
    Same pattern as send_alert_sync(). Called from _process_completed_render().
    """
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.run_coroutine_threadsafe(
                send_approval_message(content_history_id, video_url), loop
            )
        else:
            loop.run_until_complete(send_approval_message(content_history_id, video_url))
    except RuntimeError:
        asyncio.run(send_approval_message(content_history_id, video_url))
