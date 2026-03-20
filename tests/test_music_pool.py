"""Tests for MUS-01 (music pool population) and MUS-03 (platform license filters)."""
import pytest


def test_music_pool_table_schema(mock_music_pool):
    """MUS-01: music pool entries have required fields."""
    required_fields = {"id", "title", "artist", "file_url", "mood", "bpm",
                       "platform_tiktok", "platform_youtube", "platform_instagram"}
    for track in mock_music_pool:
        assert required_fields.issubset(track.keys()), f"Track missing fields: {track}"


def test_mood_values_are_valid(mock_music_pool):
    """MUS-01: mood must be one of playful/sleepy/curious/neutral."""
    valid_moods = {"playful", "sleepy", "curious", "neutral"}
    for track in mock_music_pool:
        assert track["mood"] in valid_moods


def test_bpm_in_expected_range(mock_music_pool):
    """MUS-01: BPM values are reasonable (40-200)."""
    for track in mock_music_pool:
        assert 40 <= track["bpm"] <= 200, f"BPM out of range: {track['bpm']}"


def test_platform_license_flags_are_boolean(mock_music_pool):
    """MUS-03: platform license flags are boolean."""
    for track in mock_music_pool:
        assert isinstance(track["platform_tiktok"], bool)
        assert isinstance(track["platform_youtube"], bool)
        assert isinstance(track["platform_instagram"], bool)


def test_platform_flags_can_differ_per_platform(mock_music_pool):
    """MUS-03: a track can be cleared for some platforms but not others."""
    # uuid-2 in fixture: tiktok=True, youtube=True, instagram=False
    # uuid-3 in fixture: tiktok=False, youtube=True, instagram=True
    tiktok_blocked = [t for t in mock_music_pool if not t["platform_tiktok"]]
    assert len(tiktok_blocked) > 0, "Fixture should have at least one TikTok-blocked track"


@pytest.mark.skip(reason="requires real DB — run after 0009 migration applied to Supabase")
def test_seed_data():
    """MUS-01: music_pool table has 200+ tracks after seed migration."""
    pass


@pytest.mark.skip(reason="requires real DB — run after 0009 migration applied to Supabase")
def test_load_music_pool():
    """MUS-01: music_pool table loads successfully from DB."""
    pass


@pytest.mark.skip(reason="requires real DB — run after 0009 migration applied to Supabase")
def test_platform_license_filters():
    """MUS-03: tracks with platform_tiktok=False are not returned for TikTok queries."""
    pass
