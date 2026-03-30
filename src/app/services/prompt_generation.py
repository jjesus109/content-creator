"""
PromptGenerationService: GPT-4o unified scene prompt generation for grey kitten character.

Takes a raw scene_prompt from SceneEngine and generates a unified, animated-style
prompt that naturally weaves the grey kitten character into the scene.

Fallback: if GPT-4o fails after retries, returns CHARACTER_BIBLE + "\n\n" + scene_prompt
(preserves pipeline continuity without interruption).

CRITICAL: Uses synchronous OpenAI client — APScheduler ThreadPoolExecutor cannot
manage asyncio event loops.
"""
import logging
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from openai import OpenAI
from app.settings import get_settings
from app.services.kling import CHARACTER_BIBLE

logger = logging.getLogger(__name__)

# GPT-4o cost rates (per 1M tokens) — same constants as scene_generation.py
GPT4O_COST_INPUT_PER_MTOK = 2.50
GPT4O_COST_OUTPUT_PER_MTOK = 10.00

# System prompt for unified prompt generation.
# Goal: animated/ultra-cute style, not photorealistic or technical "3D render" framing.
# The grey kitten's key visual hooks must appear naturally in the output.
_SYSTEM_PROMPT = """You are a creative director for short-form cat video content (TikTok, Instagram Reels).

Your job: take a story-arc scene description (with hook → climax → conclusion narrative structure) and enhance it into a vivid, animated-style Kling AI video generation prompt that naturally features an ultra-cute grey kitten throughout every beat of the arc.

CHARACTER — Grey kitten visual identity (weave naturally into EACH narrative beat, do NOT just prepend once):
{character_bible}

RAW SCENE ARC (hook → climax → conclusion):
{scene_prompt}

RULES:
- Output a single flowing paragraph (3-5 sentences) — no JSON, no keys, just the prompt text
- Style: animated, ultra-cute, vibrant, attention-grabbing — NOT photorealistic, NOT live-action
- PRESERVE the narrative arc structure: hook → climax → conclusion pacing and emotional beats must remain clear
- The kitten should be present and central to EACH narrative beat — weave huge blue eyes, open-mouthed smile, pink tongue, and soft light grey fur naturally throughout the arc, showing how the kitten's personality drives the story
- Use flowing prose with action progression (linking words: "immediately," "suddenly," "continuing," "pause") — DO NOT use explicit time markers like "In the first 3 seconds..." or "At second 5..."
- Preserve the scene's domestic Mexican setting, props, and mood intent
- Optimized for Kling AI 3.0 multi-shot video generation: specific, visual, cinematic, narrative-coherent
- Output in ENGLISH only
- Do NOT use the word "Mochi" — the character is unnamed

Return ONLY the unified prompt text. No explanation, no formatting, no quotes."""


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=16),
    retry=retry_if_exception_type(Exception),
    reraise=True,
    before_sleep=lambda retry_state: logger.warning(
        "PromptGenerationService GPT-4o retry attempt %d",
        retry_state.attempt_number,
    ),
)
def _call_gpt4o_with_backoff(client: OpenAI, filled_prompt: str) -> tuple[str, float]:
    """
    Call GPT-4o with exponential backoff: 2s -> 8s -> 16s (3 attempts total).
    Returns (unified_prompt_text, cost_usd).
    Module-level function (not instance method) required for tenacity decorator
    compatibility in APScheduler ThreadPoolExecutor context.
    """
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": filled_prompt}],
        temperature=0.9,
        max_tokens=300,
    )
    text = response.choices[0].message.content.strip()
    if not text:
        raise ValueError("GPT-4o returned empty unified prompt")

    input_tokens = response.usage.prompt_tokens
    output_tokens = response.usage.completion_tokens
    cost_usd = (
        input_tokens * GPT4O_COST_INPUT_PER_MTOK
        + output_tokens * GPT4O_COST_OUTPUT_PER_MTOK
    ) / 1_000_000

    return text, cost_usd


class PromptGenerationService:
    """
    Generates a unified animated-style Kling prompt by fusing the grey kitten
    character naturally into a raw scene description via GPT-4o.

    Falls back to CHARACTER_BIBLE + scene_prompt concatenation on GPT-4o failure.
    Never raises — always returns a usable prompt string.
    """

    def __init__(self) -> None:
        settings = get_settings()
        self._client = OpenAI(api_key=settings.openai_api_key)
        self._last_cost_usd: float = 0.0

    def generate_unified_prompt(self, scene_prompt: str) -> str:
        """
        Generate a unified animated-style Kling prompt from a raw scene description.

        Args:
            scene_prompt: Raw 2-3 sentence scene description from SceneEngine.pick_scene().

        Returns:
            Unified prompt string ready for KlingService.submit().
            On GPT-4o failure: returns CHARACTER_BIBLE + "\\n\\n" + scene_prompt.
        """
        filled = _SYSTEM_PROMPT.format(
            character_bible=CHARACTER_BIBLE,
            scene_prompt=scene_prompt,
        )

        try:
            unified_prompt, cost_usd = _call_gpt4o_with_backoff(self._client, filled)
            self._last_cost_usd = cost_usd
            logger.info(
                "PromptGenerationService: unified prompt generated (cost=$%.6f, chars=%d)",
                cost_usd,
                len(unified_prompt),
            )
            return unified_prompt
        except Exception as exc:
            self._last_cost_usd = 0.0
            logger.warning(
                "PromptGenerationService: GPT-4o failed after retries (%s) — "
                "falling back to CHARACTER_BIBLE concatenation",
                exc,
            )
            return f"{CHARACTER_BIBLE}\n\n{scene_prompt}"
