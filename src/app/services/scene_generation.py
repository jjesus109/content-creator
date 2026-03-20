"""
SceneEngine: GPT-4o scene selection, caption generation, and seasonal calendar overlay.

Provides:
  - SceneEngine: loads scenes.json at init, generates scene prompts + Spanish captions
    via a single GPT-4o call. Returns (scene_prompt, caption, mood, cost_usd).
  - SeasonalCalendarService: checks today's date against Mexican holidays + Cat Day
    and returns a themed overlay string for injection into the GPT-4o prompt.

CRITICAL: Uses synchronous OpenAI client — APScheduler ThreadPoolExecutor cannot
manage asyncio event loops. Mirror of EmbeddingService client pattern.
"""
import json
import logging
import random
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from openai import OpenAI
from supabase import Client

from app.services.database import get_supabase
from app.services.kling import CHARACTER_BIBLE
from app.settings import get_settings

logger = logging.getLogger(__name__)

# GPT-4o cost rates (per 1M tokens)
GPT4O_COST_INPUT_PER_MTOK = 2.50
GPT4O_COST_OUTPUT_PER_MTOK = 10.00

# Absolute path to scenes.json (resolved from this file's location)
SCENES_JSON_PATH = Path(__file__).resolve().parents[1] / "data" / "scenes.json"

# Seasonal calendar: (month, day) -> (theme_name, overlay_text)
# overlay_text is in English — injected into the GPT-4o system prompt for better Kling results.
# theme_name keys are kept in Spanish (display/logging only).
SEASONAL_OVERLAYS: dict[tuple[int, int], tuple[str, str]] = {
    (9, 16): (
        "Día de Independencia",
        "Today is Mexico's Independence Day (September 16). "
        "Subtly incorporate Mexican celebration elements into the scene — "
        "for example, a green-white-red flag visible in the background, or colorful lights. "
        "Do not change the cat's activity; only add patriotic festive atmosphere."
    ),
    (11, 1): (
        "Día de Muertos",
        "Today marks the beginning of Día de Muertos (November 1). "
        "Add a subtle visual reference to the tradition — nearby cempasúchil flowers, lit candles, "
        "or an altar in the background. Keep the cat's natural behavior; only the atmosphere changes."
    ),
    (11, 2): (
        "Día de Muertos",
        "Today is the second day of Día de Muertos (November 2). "
        "Add a subtle visual reference to the tradition — nearby cempasúchil flowers, lit candles, "
        "or an altar in the background. Keep the cat's natural behavior; only the atmosphere changes."
    ),
    (11, 20): (
        "Día de la Revolución",
        "Today is Mexico's Revolution Day (November 20). "
        "Add subtle elements of Mexican pride to the environment — flag colors, "
        "tricolor decoration in the background. The cat's behavior does not change."
    ),
    (8, 8): (
        "Día Internacional del Gato",
        "Today is International Cat Day (August 8). "
        "Make the scene especially celebratory for Mochi — perhaps with a special bow, "
        "or showing his best side. The atmosphere can be a little more festive than usual."
    ),
}


class SeasonalCalendarService:
    """
    Checks if today matches a seasonal holiday and returns a themed overlay string.
    Overlay is injected into the GPT-4o prompt as additional context.
    """

    def get_overlay(self, check_date: Optional[date] = None) -> Optional[str]:
        """
        Returns overlay text for the given date (defaults to today in Mexico City time).
        Returns None if no holiday matches.
        """
        if check_date is None:
            import pytz
            mexico_tz = pytz.timezone("America/Mexico_City")
            check_date = datetime.now(tz=mexico_tz).date()

        key = (check_date.month, check_date.day)
        if key in SEASONAL_OVERLAYS:
            theme_name, overlay_text = SEASONAL_OVERLAYS[key]
            logger.info("Seasonal overlay active: %s (%s)", theme_name, check_date.isoformat())
            return overlay_text
        return None


class SceneEngine:
    """
    Generates daily scene prompts via GPT-4o from a curated scene library.

    Single API call returns both:
    - expanded scene prompt (2-3 sentences for Kling generation)
    - 5-8 word Spanish caption ([observation] + [implied personality] formula)

    Scene library (scenes.json) loaded ONCE at init — not per call.
    All OpenAI API calls use the synchronous client (APScheduler ThreadPoolExecutor).
    Cost is returned for circuit breaker tracking.
    """

    def __init__(self, supabase: Client | None = None) -> None:
        self._supabase = supabase or get_supabase()
        settings = get_settings()
        self._client = OpenAI(api_key=settings.openai_api_key)
        self._scene_library = self._load_scene_library()
        self._seasonal = SeasonalCalendarService()
        logger.info(
            "SceneEngine initialized: %d scenes loaded from %s",
            len(self._scene_library),
            SCENES_JSON_PATH,
        )

    def _load_scene_library(self) -> list[dict]:
        """Load scenes.json once at init. Raises FileNotFoundError if missing."""
        with open(SCENES_JSON_PATH, encoding="utf-8") as f:
            library = json.load(f)
        if not library:
            raise ValueError("scenes.json is empty — cannot generate scenes")
        return library

    def _select_combo(self) -> dict:
        """
        Weighted random selection from scene library.
        Uses weight field if present; defaults to 1.0 if absent.
        """
        weights = [entry.get("weight", 1.0) for entry in self._scene_library]
        return random.choices(self._scene_library, weights=weights, k=1)[0]

    def _build_system_prompt(
        self,
        combo: dict,
        rejection_constraints: list[dict] | None = None,
        seasonal_overlay: Optional[str] = None,
    ) -> str:
        """Build the GPT-4o system prompt for scene + caption generation."""
        rejection_text = ""
        if rejection_constraints:
            rejection_lines = ["\nAVOID these scenes (rejected by creator):"]
            for r in rejection_constraints:
                combo_info = r.get("scene_combo") or {}
                reason = r.get("reason_text", "no reason given")
                if combo_info:
                    rejection_lines.append(
                        f"- {combo_info.get('location', '?')} / {combo_info.get('activity', '?')}: {reason}"
                    )
            rejection_text = "\n".join(rejection_lines)

        seasonal_text = ""
        if seasonal_overlay:
            seasonal_text = f"\n\nSPECIAL SEASONAL CONTEXT:\n{seasonal_overlay}"

        return f"""You are a creative director for cat video production.
You are given a scene composition (location + activity + mood). Your task:
1. Expand it into a vivid 2-3 sentence visual prompt in ENGLISH for AI video generation (scene_prompt).
2. Generate a Spanish caption of 5-8 words for the social media post, following the formula: [observation] + [implied personality] (caption).

CHARACTER — Character Bible (include in the prompt):
{CHARACTER_BIBLE}

SELECTED SCENE:
- Location: {combo['location']}
- Activity: {combo['activity']}
- Mood: {combo['mood']}
{seasonal_text}
{rejection_text}

INSTRUCTIONS FOR SCENE PROMPT (scene_prompt):
- 2-3 complete sentences, describing the scene visually for video generation
- Must be in ENGLISH — Kling AI generates better results with English prompts
- Include the name "Mochi" and reference the Character Bible
- Describe the action, environment, lighting, and mood
- Optimized for Kling AI (video generation): specific, visual, cinematic

INSTRUCTIONS FOR CAPTION (caption):
- Exactly 5-8 words in SPANISH
- Formula: [what the cat does/observes] + [implied cat personality]
- Examples: "Mochi descubre los secretos de la cocina", "El gato vigila su territorio con calma"
- NO hashtags, NO emojis

Return ONLY valid JSON with exactly these two keys:
{{"scene_prompt": "...", "caption": "..."}}"""

    def pick_scene(
        self,
        attempt: int = 0,
        rejection_constraints: list[dict] | None = None,
    ) -> tuple[str, str, str, float]:
        """
        Generate a scene prompt and caption for today's video.

        Returns:
            (scene_prompt, caption, mood, cost_usd)
            - scene_prompt: 2-3 sentence Kling-optimized prompt
            - caption: 5-8 word Spanish caption
            - mood: "playful" | "sleepy" | "curious" (from selected combo)
            - cost_usd: GPT-4o API cost for circuit breaker tracking

        attempt: 0 = normal; 1+ = retry with different combo (similarity rejection)
        """
        combo = self._select_combo()
        seasonal_overlay = self._seasonal.get_overlay()

        system_prompt = self._build_system_prompt(
            combo=combo,
            rejection_constraints=rejection_constraints,
            seasonal_overlay=seasonal_overlay,
        )

        logger.info(
            "SceneEngine picking scene (attempt %d): location=%s, activity=%s, mood=%s",
            attempt + 1, combo["location"], combo["activity"], combo["mood"],
        )

        try:
            response = self._client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": system_prompt}],
                response_format={"type": "json_object"},
                temperature=0.85,
                max_tokens=400,
            )
        except Exception as e:
            logger.error("GPT-4o scene generation failed: %s", e)
            raise

        raw_content = response.choices[0].message.content
        try:
            parsed = json.loads(raw_content)
            scene_prompt = parsed["scene_prompt"].strip()
            caption = parsed["caption"].strip()
        except (json.JSONDecodeError, KeyError) as e:
            logger.error("GPT-4o returned invalid JSON for scene: %s | raw: %s", e, raw_content)
            raise ValueError(f"SceneEngine: invalid GPT-4o response structure: {e}") from e

        # Calculate cost
        input_tokens = response.usage.prompt_tokens
        output_tokens = response.usage.completion_tokens
        cost_usd = (
            input_tokens * GPT4O_COST_INPUT_PER_MTOK
            + output_tokens * GPT4O_COST_OUTPUT_PER_MTOK
        ) / 1_000_000

        logger.info(
            "Scene generated: mood=%s, caption='%s', cost=$%.6f",
            combo["mood"], caption, cost_usd,
        )

        return scene_prompt, caption, combo["mood"], cost_usd

    def load_active_scene_rejections(self) -> list[dict]:
        """
        Load active scene rejection constraints (expires_at > now()).
        Returns list of {scene_combo, reason_text}.
        """
        try:
            result = self._supabase.table("rejection_constraints").select(
                "scene_combo, reason_text"
            ).eq("pattern_type", "scene").gt("expires_at", "now()").execute()
            return result.data or []
        except Exception as e:
            logger.error("Failed to load scene rejections: %s — proceeding without", e)
            return []

    def store_scene_rejection(self, scene_combo: dict, reason_text: str) -> None:
        """
        Store a rejected scene combo with 7-day automatic expiry.
        Called when creator rejects a video (from approval_flow).
        """
        expires_at = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
        try:
            self._supabase.table("rejection_constraints").insert({
                "reason_text": reason_text,
                "pattern_type": "scene",
                "scene_combo": scene_combo,
                "expires_at": expires_at,
            }).execute()
            logger.info(
                "Scene rejection stored: %s — expires %s", scene_combo, expires_at
            )
        except Exception as e:
            logger.error("Failed to store scene rejection: %s", e)
