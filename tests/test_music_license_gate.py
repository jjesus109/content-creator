"""Tests for PUB-01: Music license gate in publish_to_platform_job."""
import pytest
from unittest.mock import MagicMock, patch, call

from app.scheduler.jobs.platform_publish import _check_music_license_cleared


def _make_music_pool_mock(track: dict) -> MagicMock:
    """Return a supabase mock that returns track from music_pool query."""
    mock = MagicMock()
    (mock.table.return_value
         .select.return_value
         .eq.return_value
         .single.return_value
         .execute.return_value.data) = track
    return mock


def _make_content_row(music_track_id="uuid-1") -> dict:
    return {
        "post_copy": "Mochi explora.",
        "post_copy_youtube": "Mochi en la cocina\nExplora con curiosidad",
        "music_track_id": music_track_id,
    }


CLEARED_TRACK = {
    "id": "uuid-1",
    "title": "Siesta Suave",
    "artist": "Lo-Fi Mexico",
    "platform_tiktok": True,
    "platform_youtube": True,
    "platform_instagram": True,
    "platform_facebook": True,
    "license_expires_at": None,
}

UNCLEARED_TRACK = {
    "id": "uuid-2",
    "title": "Siesta Suave",
    "artist": "Lo-Fi Mexico",
    "platform_youtube": False,
    "platform_tiktok": True,
    "platform_instagram": True,
    "platform_facebook": True,
    "license_expires_at": None,
}

EXPIRED_TRACK = {
    "id": "uuid-expired",
    "title": "Expired Song",
    "artist": "Old Artist",
    "platform_youtube": True,
    "platform_tiktok": True,
    "platform_instagram": True,
    "platform_facebook": True,
    "license_expires_at": "2026-01-01T00:00:00Z",
}


def test_license_gate_allows_cleared_track():
    """PUB-01: Cleared track with no expiry returns True (publish proceeds)."""
    mock_supabase = _make_music_pool_mock(CLEARED_TRACK)
    result = _check_music_license_cleared(
        mock_supabase, _make_content_row(), "youtube", "content-id-1"
    )
    assert result is True


def test_license_gate_blocks_uncleared_track():
    """PUB-01: Track not cleared for platform returns False (publish blocked)."""
    mock_supabase = _make_music_pool_mock(UNCLEARED_TRACK)
    with patch("app.scheduler.jobs.platform_publish.send_alert_sync"):
        result = _check_music_license_cleared(
            mock_supabase, _make_content_row(), "youtube", "content-id-1"
        )
    assert result is False


def test_license_gate_blocks_expired_track():
    """PUB-01: Expired license returns False (publish blocked)."""
    mock_supabase = _make_music_pool_mock(EXPIRED_TRACK)
    with patch("app.scheduler.jobs.platform_publish.send_alert_sync"):
        result = _check_music_license_cleared(
            mock_supabase, _make_content_row(), "youtube", "content-id-1"
        )
    assert result is False


def test_license_gate_skips_if_no_track_id():
    """PUB-01: NULL music_track_id -> skip check, return True (fail-open)."""
    mock_supabase = MagicMock()
    result = _check_music_license_cleared(
        mock_supabase, _make_content_row(music_track_id=None), "youtube", "content-id-1"
    )
    assert result is True
    # Must NOT query music_pool
    mock_supabase.table.assert_not_called()


def test_blocked_row_inserted_on_license_fail():
    """PUB-01: On block, publish_events insert with status='blocked' called before send_alert_sync."""
    mock_supabase = _make_music_pool_mock(UNCLEARED_TRACK)
    with patch("app.scheduler.jobs.platform_publish.send_alert_sync") as mock_alert:
        _check_music_license_cleared(
            mock_supabase, _make_content_row(), "youtube", "content-id-1"
        )
    # Verify publish_events insert was called with status='blocked'
    insert_calls = mock_supabase.table.return_value.insert.call_args_list
    assert any(
        call_args[0][0].get("status") == "blocked"
        for call_args in insert_calls
        if call_args[0]
    ), "Expected publish_events insert with status='blocked'"


def test_telegram_alert_format():
    """PUB-01: Alert message contains track title, artist, platform, and fix suggestion."""
    mock_supabase = _make_music_pool_mock(UNCLEARED_TRACK)
    with patch("app.scheduler.jobs.platform_publish.send_alert_sync") as mock_alert:
        _check_music_license_cleared(
            mock_supabase, _make_content_row(), "youtube", "content-id-1"
        )
    assert mock_alert.called, "send_alert_sync must be called on block"
    alert_text = mock_alert.call_args[0][0]
    assert "Siesta Suave" in alert_text, "Alert must include track title"
    assert "Lo-Fi Mexico" in alert_text, "Alert must include artist"
    assert "youtube" in alert_text.lower(), "Alert must include platform"
    assert any(word in alert_text.lower() for word in ("fix", "update", "assign")), \
        "Alert must include a fix suggestion"
