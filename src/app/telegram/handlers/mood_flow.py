import asyncio
import logging
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, ContextTypes

logger = logging.getLogger(__name__)

# State machine keys stored in context.bot_data["mood_state"][chat_id]
STATE_POOL = "pool"
STATE_TONE = "tone"
STATE_DONE = "done"

# Callback data prefixes — uniquely identify mood flow callbacks
PREFIX_POOL = "mood_pool:"
PREFIX_TONE = "mood_tone:"
PREFIX_DURATION = "mood_duration:"

POOLS = [
    ("Preguntas existenciales", "existential"),
    ("Sabiduria practica", "practical_wisdom"),
    ("Naturaleza humana", "human_nature"),
    ("Paradojas modernas", "modern_paradoxes"),
    ("Filosofia oriental", "eastern"),
    ("La vida creativa", "creative_life"),
]

TONES = [
    ("Contemplativo", "contemplative"),
    ("Provocativo", "provocative"),
    ("Esperanzador", "hopeful"),
    ("Crudo", "raw"),
]

DURATIONS = [
    ("Corto (30s / ~70 palabras)", "short"),
    ("Medio (60s / ~140 palabras)", "medium"),
    ("Largo (90s / ~200 palabras)", "long"),
]


async def send_pool_prompt(bot: Bot, chat_id: int) -> None:
    """
    Sends the first step of the mood flow (pool selection).
    Called from APScheduler thread via asyncio.run_coroutine_threadsafe.
    """
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(label, callback_data=f"{PREFIX_POOL}{val}")]
        for label, val in POOLS
    ])
    await bot.send_message(
        chat_id=chat_id,
        text=(
            "Es lunes — momento de configurar el contenido de esta semana.\n\n"
            "*Paso 1 de 3:* Selecciona el area tematica:"
        ),
        reply_markup=keyboard,
        parse_mode="Markdown",
    )


def send_mood_prompt_sync(bot: Bot, chat_id: int, loop: asyncio.AbstractEventLoop) -> None:
    """
    Sync wrapper for send_pool_prompt — used by APScheduler weekly job.
    Follows the same run_coroutine_threadsafe pattern as Phase 1 send_alert_sync.
    """
    asyncio.run_coroutine_threadsafe(
        send_pool_prompt(bot, chat_id), loop
    ).result(timeout=15)


async def handle_pool(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Step 1: Creator selects thematic pool."""
    query = update.callback_query
    await query.answer()  # REQUIRED — prevents Telegram loading spinner forever

    pool_value = query.data[len(PREFIX_POOL):]

    # Initialize state dict for this user
    if "mood_state" not in context.bot_data:
        context.bot_data["mood_state"] = {}
    context.bot_data["mood_state"][query.from_user.id] = {"pool": pool_value}

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(label, callback_data=f"{PREFIX_TONE}{val}")]
        for label, val in TONES
    ])
    await query.edit_message_text(
        text=(
            f"Pool: *{pool_value}* guardado.\n\n"
            "*Paso 2 de 3:* Selecciona el tono emocional de la semana:"
        ),
        reply_markup=keyboard,
        parse_mode="Markdown",
    )


async def handle_tone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Step 2: Creator selects emotional tone."""
    query = update.callback_query
    await query.answer()

    tone_value = query.data[len(PREFIX_TONE):]
    user_id = query.from_user.id

    # Retrieve existing state (pool already set)
    state = context.bot_data.get("mood_state", {}).get(user_id, {})
    state["tone"] = tone_value
    if "mood_state" not in context.bot_data:
        context.bot_data["mood_state"] = {}
    context.bot_data["mood_state"][user_id] = state

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(label, callback_data=f"{PREFIX_DURATION}{val}")]
        for label, val in DURATIONS
    ])
    await query.edit_message_text(
        text=(
            f"Tono: *{tone_value}* guardado.\n\n"
            "*Paso 3 de 3:* Selecciona la duracion objetivo del video:"
        ),
        reply_markup=keyboard,
        parse_mode="Markdown",
    )


async def handle_duration(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Step 3 (final): Creator selects duration — saves to DB."""
    query = update.callback_query
    await query.answer()

    duration_value = query.data[len(PREFIX_DURATION):]
    user_id = query.from_user.id

    state = context.bot_data.get("mood_state", {}).get(user_id, {})
    state["duration"] = duration_value

    mood = {
        "pool": state.get("pool", "existential"),
        "tone": state.get("tone", "contemplative"),
        "duration": duration_value,
    }

    # Persist to DB — local import avoids circular dependency
    from app.services.mood import MoodService
    try:
        MoodService().save_mood_profile(mood)
        confirmation = (
            f"Perfecto. Esta semana:\n"
            f"- Area: *{mood['pool']}*\n"
            f"- Tono: *{mood['tone']}*\n"
            f"- Duracion: *{mood['duration']}*\n\n"
            "Lo tengo en cuenta para el guion de manana."
        )
    except Exception as e:
        logger.error("Failed to save mood profile: %s", e)
        confirmation = "Hubo un error guardando tu seleccion. Usare los valores por defecto esta semana."

    # Clean up state
    if "mood_state" in context.bot_data and user_id in context.bot_data["mood_state"]:
        del context.bot_data["mood_state"][user_id]

    await query.edit_message_text(text=confirmation, parse_mode="Markdown")


def register_mood_handlers(app: Application) -> None:
    """
    Attach mood flow CallbackQueryHandlers to the PTB Application.
    Called from build_telegram_app() in src/app/telegram/app.py.
    Uses callback_data prefix matching — no ConversationHandler needed.
    """
    app.add_handler(CallbackQueryHandler(handle_pool, pattern=f"^{PREFIX_POOL}"))
    app.add_handler(CallbackQueryHandler(handle_tone, pattern=f"^{PREFIX_TONE}"))
    app.add_handler(CallbackQueryHandler(handle_duration, pattern=f"^{PREFIX_DURATION}"))
    logger.info("Mood flow handlers registered.")
