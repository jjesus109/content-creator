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

    # Load content_history row (includes 4 platform copy columns for PUBL-01)
    row_result = supabase.table("content_history").select(
        "script_text, topic_summary, post_copy, post_copy_tiktok, post_copy_instagram, post_copy_facebook, post_copy_youtube, background_url, created_at"
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

    # Generate and store platform copy variants if missing (PUBL-01)
    # Run this in the thread pool to avoid blocking the async handler
    loop = asyncio.get_event_loop()

    def _generate_and_store_variants():
        variants = PostCopyService().generate_platform_variants(row["script_text"], row["topic_summary"])
        supabase.table("content_history").update({
            "post_copy_tiktok": variants["tiktok"],
            "post_copy_instagram": variants["instagram"],
            "post_copy_facebook": variants["facebook"],
            "post_copy_youtube": variants["youtube"],
        }).eq("id", content_history_id).execute()
        return variants

    # Check if any variant is missing
    has_all_variants = all([
        row.get("post_copy_tiktok"),
        row.get("post_copy_instagram"),
        row.get("post_copy_facebook"),
        row.get("post_copy_youtube"),
    ])
    if not has_all_variants:
        platform_variants = await loop.run_in_executor(None, _generate_and_store_variants)
    else:
        platform_variants = {
            "tiktok": row["post_copy_tiktok"],
            "instagram": row["post_copy_instagram"],
            "facebook": row["post_copy_facebook"],
            "youtube": row["post_copy_youtube"],
        }

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
        f"Mood: {mood_label} | Fondo: {background_short}\n\n"
        f"📱 COPY POR PLATAFORMA:\n"
        f"🎵 TikTok:\n{platform_variants['tiktok']}\n\n"
        f"📷 Instagram:\n{platform_variants['instagram']}\n\n"
        f"🟦 Facebook:\n{platform_variants['facebook']}\n\n"
        f"▶️ YouTube:\n{platform_variants['youtube']}"
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
    After sending the approval message, schedules a 24h timeout job.
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

    # Schedule 24h approval timeout job — lazy import avoids circular import
    from app.scheduler.jobs.approval_timeout import schedule_approval_timeout
    schedule_approval_timeout(content_history_id)
    logger.info("Approval timeout job scheduled for content_history_id=%s", content_history_id[:8])


async def send_publish_confirmation(
    content_history_id: str,
    scheduled_times: dict,
    video_url: str = "",
    tiktok_copy: str = "",
) -> None:
    """
    Send a separate follow-up message after creator approves listing per-platform schedule times.
    scheduled_times: dict mapping platform -> UTC datetime of scheduled publish (auto platforms only).
    TikTok is manual — skip from schedule list, append a manual-posting block instead.
    (CONTEXT.md locked decision: original approval message is not edited — this is a new message.)
    """
    from app.settings import get_settings
    import pytz

    bot = get_telegram_bot()
    settings = get_settings()
    audience_tz = pytz.timezone(settings.audience_timezone)

    PLATFORM_EMOJI = {
        "instagram": "📷 Instagram",
        "facebook":  "🟦 Facebook",
        "youtube":   "▶️ YouTube",
    }

    lines = ["✅ Aprobado. Publicaciones programadas:\n"]
    for platform in ["instagram", "facebook", "youtube"]:
        if platform in scheduled_times:
            sched_utc = scheduled_times[platform]
            sched_local = sched_utc.astimezone(audience_tz)
            label = PLATFORM_EMOJI.get(platform, platform)
            day = "Hoy" if sched_local.date() == sched_local.today().date() else "Mañana"
            lines.append(f"{label}: {day} {sched_local.strftime('%I:%M %p')}")

    lines.append(f"\n(Hora en {settings.audience_timezone})")

    # TikTok manual posting block
    if tiktok_copy:
        lines.append("\n---")
        lines.append("🎵 TikTok — Publicación manual:")
        if video_url:
            lines.append(f"Video: {video_url}")
        copy_preview = tiktok_copy[:300] + ("..." if len(tiktok_copy) > 300 else "")
        lines.append(f"Copy: {copy_preview}")

    message = "\n".join(lines)

    await bot.send_message(chat_id=settings.telegram_creator_id, text=message)
    logger.info("Publish confirmation sent for content_history_id=%s", content_history_id)


def send_publish_confirmation_sync(
    content_history_id: str,
    scheduled_times: dict,
    video_url: str = "",
    tiktok_copy: str = "",
) -> None:
    """Sync wrapper for APScheduler/async approval handler context."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.run_coroutine_threadsafe(
                send_publish_confirmation(content_history_id, scheduled_times, video_url, tiktok_copy), loop
            )
        else:
            loop.run_until_complete(send_publish_confirmation(content_history_id, scheduled_times, video_url, tiktok_copy))
    except RuntimeError:
        asyncio.run(send_publish_confirmation(content_history_id, scheduled_times, video_url, tiktok_copy))


async def send_platform_success(platform: str, content_history_id: str) -> None:
    """Notify creator when a single platform publish succeeds."""
    PLATFORM_EMOJI = {
        "tiktok": "🎵", "instagram": "📷", "facebook": "🟦", "youtube": "▶️"
    }
    emoji = PLATFORM_EMOJI.get(platform, "")
    bot = get_telegram_bot()
    settings = get_settings()
    await bot.send_message(
        chat_id=settings.telegram_creator_id,
        text=f"{emoji} Publicado en {platform.upper()} correctamente.",
    )


def send_platform_success_sync(platform: str, content_history_id: str) -> None:
    """Sync wrapper for APScheduler thread context."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.run_coroutine_threadsafe(send_platform_success(platform, content_history_id), loop)
        else:
            loop.run_until_complete(send_platform_success(platform, content_history_id))
    except RuntimeError:
        asyncio.run(send_platform_success(platform, content_history_id))


async def send_platform_failure(
    platform: str,
    video_url: str,
    post_copy: str,
    error_message: str,
) -> None:
    """
    Send Telegram fallback when Ayrshare publish fails after retries.
    Sends Supabase Storage URL (link-based, not file upload) + platform copy.
    (CONTEXT.md locked decision: fallback is link-based only.)
    """
    bot = get_telegram_bot()
    settings = get_settings()
    message = (
        f"PUBLICACION FALLIDA: {platform.upper()}\n\n"
        f"Video: {video_url}\n\n"
        f"Copy para {platform}:\n{post_copy}\n\n"
        f"Error: {error_message[:200]}\n\n"
        "Por favor publica manualmente."
    )
    await bot.send_message(chat_id=settings.telegram_creator_id, text=message)


def send_platform_failure_sync(
    platform: str,
    video_url: str,
    post_copy: str,
    error_message: str,
) -> None:
    """Sync wrapper for APScheduler thread context."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.run_coroutine_threadsafe(
                send_platform_failure(platform, video_url, post_copy, error_message), loop
            )
        else:
            loop.run_until_complete(send_platform_failure(platform, video_url, post_copy, error_message))
    except RuntimeError:
        asyncio.run(send_platform_failure(platform, video_url, post_copy, error_message))
