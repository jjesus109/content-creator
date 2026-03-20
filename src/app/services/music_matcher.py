import logging
import random
from datetime import datetime, timezone
from supabase import Client

from app.services.database import get_supabase

logger = logging.getLogger(__name__)

# BPM ranges per mood — locked decision from CONTEXT.md
# Do NOT read from config: these are stable content-strategy constants
MOOD_BPM_MAP: dict[str, dict[str, int]] = {
    "playful": {"min": 110, "max": 125},
    "sleepy":  {"min": 70,  "max": 80},
    "curious": {"min": 90,  "max": 100},
}

VALID_PLATFORMS = {"tiktok", "youtube", "instagram"}


class MusicMatcher:
    """
    Selects a music track from the music_pool table by matching scene mood to BPM range.

    Selection criteria:
    1. mood matches the scene mood (playful/sleepy/curious)
    2. BPM is within the mood's configured range
    3. Platform license flag is True for the target platform
    4. License is not expired (license_expires_at IS NULL or > now())

    Track is randomly selected from all matching candidates (not first-match).
    Raises ValueError if no cleared tracks found for the given mood+platform.
    """

    def __init__(self, supabase: Client | None = None) -> None:
        self._supabase = supabase or get_supabase()

    def pick_track(self, mood: str, target_platform: str = "tiktok") -> dict:
        """
        Select a music track matching mood and BPM range, cleared for target platform.

        Args:
            mood: "playful" | "sleepy" | "curious"
            target_platform: "tiktok" | "youtube" | "instagram"

        Returns:
            dict with keys: id, title, artist, file_url, bpm, mood

        Raises:
            ValueError: if mood is invalid, platform is invalid, or no cleared tracks found
        """
        if mood not in MOOD_BPM_MAP:
            raise ValueError(
                f"MusicMatcher: invalid mood '{mood}'. Must be one of: {list(MOOD_BPM_MAP.keys())}"
            )
        if target_platform not in VALID_PLATFORMS:
            raise ValueError(
                f"MusicMatcher: invalid platform '{target_platform}'. Must be one of: {sorted(VALID_PLATFORMS)}"
            )

        bpm_range = MOOD_BPM_MAP[mood]
        platform_flag = f"platform_{target_platform}"

        try:
            result = (
                self._supabase.table("music_pool")
                .select("id, title, artist, file_url, bpm, mood")
                .eq("mood", mood)
                .gte("bpm", bpm_range["min"])
                .lte("bpm", bpm_range["max"])
                .eq(platform_flag, True)
                .execute()
            )
        except Exception as e:
            logger.error(
                "MusicMatcher: DB query failed for mood=%s platform=%s: %s",
                mood, target_platform, e,
            )
            raise

        candidates = result.data or []

        # Filter out expired licenses (license_expires_at is not None and is in the past)
        # Supabase returns license_expires_at as ISO string or None
        now_utc = datetime.now(timezone.utc)
        valid_candidates = []
        for track in candidates:
            expires_at = track.get("license_expires_at")
            if expires_at is None:
                valid_candidates.append(track)
            else:
                try:
                    expiry = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
                    if expiry > now_utc:
                        valid_candidates.append(track)
                    else:
                        logger.warning(
                            "MusicMatcher: skipping expired track '%s' (expired %s)",
                            track.get("title"), expires_at,
                        )
                except (ValueError, AttributeError):
                    valid_candidates.append(track)  # unparseable date: include (fail open)

        if not valid_candidates:
            msg = (
                f"MusicMatcher: no cleared tracks found for mood='{mood}', "
                f"platform='{target_platform}', bpm={bpm_range['min']}-{bpm_range['max']}. "
                f"Add tracks to music_pool or check platform license flags."
            )
            logger.error(msg)
            raise ValueError(msg)

        selected = random.choice(valid_candidates)
        logger.info(
            "MusicMatcher: selected '%s' by %s (bpm=%d, mood=%s, platform=%s)",
            selected.get("title"), selected.get("artist"), selected.get("bpm", 0),
            mood, target_platform,
        )
        return selected
