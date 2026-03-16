import json
import logging
from datetime import date, timedelta
from supabase import Client
from app.services.database import get_supabase

logger = logging.getLogger(__name__)

# 6 thematic pools — rotation order for no-response fallback
POOLS = [
    "existential",
    "practical_wisdom",
    "human_nature",
    "modern_paradoxes",
    "eastern",
    "creative_life",
]

# Defaults when creator does not respond (CONTEXT.md: Contemplative + rotate pool + Medium)
DEFAULT_TONE = "contemplative"
DEFAULT_DURATION = "medium"

# Target word counts by duration (CONTEXT.md locked decision)
DURATION_WORD_COUNTS = {
    "short": 40,    # 30s — TikTok hook-only
    "medium": 80,  # 60s — all-platform safe (default)
    "long": 120,    # 90s — YT Shorts max
}


class MoodService:
    """
    Reads and writes mood_profiles.
    profile_text column stores JSON: {"pool": str, "tone": str, "duration": str}
    """

    def __init__(self, supabase: Client | None = None) -> None:
        self._supabase = supabase or get_supabase()

    def get_current_week_mood(self) -> dict:
        """
        Returns mood profile for the current ISO week.
        Falls back to defaults if no profile exists for this week.

        Returns dict with keys: pool, tone, duration, target_words
        """
        week_start = self._get_week_start()
        try:
            result = self._supabase.table("mood_profiles").select("profile_text").eq(
                "week_start", week_start.isoformat()
            ).limit(1).execute()

            if result.data:
                profile = json.loads(result.data[0]["profile_text"])
                profile["target_words"] = DURATION_WORD_COUNTS.get(
                    profile.get("duration", "medium"), 140
                )
                logger.info("Loaded mood profile for week %s: %s", week_start, profile)
                return profile
        except Exception as e:
            logger.error("Failed to load mood profile: %s — using defaults", e)

        # Default fallback — no profile this week
        default_pool = self._get_default_pool_rotation()
        mood = {
            "pool": default_pool,
            "tone": DEFAULT_TONE,
            "duration": DEFAULT_DURATION,
            "target_words": DURATION_WORD_COUNTS[DEFAULT_DURATION],
        }
        logger.info("No mood profile for week %s — using defaults: %s", week_start, mood)
        return mood

    def save_mood_profile(self, mood: dict) -> None:
        """
        Upsert mood profile for the current week.
        mood must have keys: pool, tone, duration
        """
        week_start = self._get_week_start()
        profile_json = json.dumps({
            "pool": mood["pool"],
            "tone": mood["tone"],
            "duration": mood["duration"],
        })
        try:
            self._supabase.table("mood_profiles").upsert(
                {"week_start": week_start.isoformat(), "profile_text": profile_json},
                on_conflict="week_start",
            ).execute()
            logger.info("Mood profile saved for week %s: %s", week_start, mood)
        except Exception as e:
            logger.error("Failed to save mood profile: %s", e)
            raise

    def has_profile_this_week(self) -> bool:
        """Used by reminder job to decide whether to send the 4-hour reminder."""
        week_start = self._get_week_start()
        try:
            result = self._supabase.table("mood_profiles").select("id").eq(
                "week_start", week_start.isoformat()
            ).limit(1).execute()
            return len(result.data) > 0
        except Exception:
            return False

    def _get_week_start(self) -> date:
        """Returns the Monday of the current ISO week."""
        today = date.today()
        return today - timedelta(days=today.weekday())  # weekday(): Mon=0, Sun=6

    def _get_default_pool_rotation(self) -> str:
        """
        Rotate through pools in order when no mood profile is set.
        Uses week number modulo pool count for deterministic rotation.
        """
        week_number = date.today().isocalendar()[1]
        return POOLS[week_number % len(POOLS)]
