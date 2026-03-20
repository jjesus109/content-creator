"""Tests for MUS-02 (mood-to-BPM track matching) and MUS-03 (license filtering)."""
import pytest
from unittest.mock import MagicMock, patch
from app.services.music_matcher import MusicMatcher, MOOD_BPM_MAP


def _make_supabase_mock(tracks: list[dict]) -> MagicMock:
    """Create a Supabase mock that returns given tracks from the query chain."""
    mock = MagicMock()
    (mock.table.return_value
         .select.return_value
         .eq.return_value
         .gte.return_value
         .lte.return_value
         .eq.return_value
         .execute.return_value.data) = tracks
    return mock


def test_mood_bpm_map_playful():
    """MUS-02: playful BPM range is 110-125."""
    assert MOOD_BPM_MAP["playful"] == {"min": 110, "max": 125}


def test_mood_bpm_map_sleepy():
    """MUS-02: sleepy BPM range is 70-80."""
    assert MOOD_BPM_MAP["sleepy"] == {"min": 70, "max": 80}


def test_mood_bpm_map_curious():
    """MUS-02: curious BPM range is 90-100."""
    assert MOOD_BPM_MAP["curious"] == {"min": 90, "max": 100}


def test_pick_track_returns_dict_with_required_keys(mock_music_pool):
    """MUS-02: pick_track returns dict with id, title, artist, file_url, bpm."""
    playful_tracks = [t for t in mock_music_pool if t["mood"] == "playful"]
    mock_supabase = _make_supabase_mock(playful_tracks)
    matcher = MusicMatcher(supabase=mock_supabase)
    result = matcher.pick_track(mood="playful", target_platform="tiktok")
    assert "id" in result
    assert "title" in result
    assert "file_url" in result
    assert "bpm" in result


def test_pick_track_random_from_candidates(mock_music_pool):
    """MUS-02: pick_track randomly selects from all candidates (not first-match)."""
    # With 3 playful tracks, selection is non-deterministic
    tracks = [
        {"id": f"uuid-{i}", "title": f"Track {i}", "artist": "Test", "file_url": "http://x.mp3",
         "bpm": 115, "mood": "playful", "license_expires_at": None}
        for i in range(3)
    ]
    mock_supabase = _make_supabase_mock(tracks)
    matcher = MusicMatcher(supabase=mock_supabase)
    results = {matcher.pick_track("playful", "tiktok")["id"] for _ in range(20)}
    assert len(results) > 1, "random.choice should select different tracks across 20 calls"


def test_pick_track_raises_on_empty_pool():
    """MUS-02: raises ValueError when no cleared tracks found."""
    mock_supabase = _make_supabase_mock([])
    matcher = MusicMatcher(supabase=mock_supabase)
    with pytest.raises(ValueError, match="no cleared tracks found"):
        matcher.pick_track(mood="sleepy", target_platform="tiktok")


def test_pick_track_raises_on_invalid_mood():
    """MUS-02: raises ValueError for unknown mood."""
    matcher = MusicMatcher(supabase=MagicMock())
    with pytest.raises(ValueError, match="invalid mood"):
        matcher.pick_track(mood="angry", target_platform="tiktok")


def test_pick_track_raises_on_invalid_platform():
    """MUS-03: raises ValueError for unknown platform."""
    matcher = MusicMatcher(supabase=MagicMock())
    with pytest.raises(ValueError, match="invalid platform"):
        matcher.pick_track(mood="playful", target_platform="snapchat")


def test_pick_track_excludes_expired_licenses():
    """MUS-03: tracks with expired license_expires_at are excluded."""
    from datetime import datetime, timedelta, timezone
    past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    tracks = [
        {"id": "expired-1", "title": "Expired Track", "artist": "Test", "file_url": "http://x.mp3",
         "bpm": 115, "mood": "playful", "license_expires_at": past},
    ]
    mock_supabase = _make_supabase_mock(tracks)
    matcher = MusicMatcher(supabase=mock_supabase)
    with pytest.raises(ValueError, match="no cleared tracks found"):
        matcher.pick_track(mood="playful", target_platform="tiktok")


def test_pick_track_includes_null_expiry():
    """MUS-03: tracks with license_expires_at=None (permanent) are always included."""
    tracks = [
        {"id": "perm-1", "title": "Permanent Track", "artist": "Test", "file_url": "http://x.mp3",
         "bpm": 75, "mood": "sleepy", "license_expires_at": None},
    ]
    mock_supabase = _make_supabase_mock(tracks)
    matcher = MusicMatcher(supabase=mock_supabase)
    result = matcher.pick_track(mood="sleepy", target_platform="tiktok")
    assert result["id"] == "perm-1"


def test_pick_track_includes_future_expiry():
    """MUS-03: tracks with future license_expires_at are included."""
    from datetime import datetime, timedelta, timezone
    future = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
    tracks = [
        {"id": "future-1", "title": "Future Track", "artist": "Test", "file_url": "http://x.mp3",
         "bpm": 95, "mood": "curious", "license_expires_at": future},
    ]
    mock_supabase = _make_supabase_mock(tracks)
    matcher = MusicMatcher(supabase=mock_supabase)
    result = matcher.pick_track(mood="curious", target_platform="youtube")
    assert result["id"] == "future-1"
