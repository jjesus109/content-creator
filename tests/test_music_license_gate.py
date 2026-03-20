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


# ============================================================
# Integration tests: full publish_to_platform_job() call path
# ============================================================

def _make_integration_supabase_mock(content_row: dict, track: dict) -> MagicMock:
    """
    Mock supporting sequential table() calls in publish_to_platform_job:
      1. content_history: select single -> content_row
      2. music_pool: select single -> track
      3. publish_events: insert -> no-op (on block)
    """
    mock = MagicMock()

    content_result = MagicMock()
    content_result.data = content_row

    track_result = MagicMock()
    track_result.data = track

    def table_side_effect(table_name):
        inner = MagicMock()
        if table_name == "content_history":
            inner.select.return_value.eq.return_value.single.return_value.execute.return_value = content_result
        elif table_name == "music_pool":
            inner.select.return_value.eq.return_value.single.return_value.execute.return_value = track_result
        else:
            # publish_events insert on block
            inner.insert.return_value.execute.return_value = MagicMock()
        return inner

    mock.table.side_effect = table_side_effect
    return mock


def test_publish_to_platform_job_blocked_by_license():
    """PUB-01 integration: publish_to_platform_job returns early when track not cleared for platform."""
    from app.scheduler.jobs.platform_publish import publish_to_platform_job

    content_row = {
        "post_copy": "Mochi explora.",
        "post_copy_youtube": "Mochi en la cocina\nExplora con curiosidad",
        "post_copy_tiktok": None,
        "post_copy_instagram": None,
        "post_copy_facebook": None,
        "music_track_id": "uuid-not-cleared",
    }
    blocked_track = {
        "id": "uuid-not-cleared",
        "title": "Blocked Song",
        "artist": "Blocked Artist",
        "platform_youtube": False,
        "platform_tiktok": True,
        "platform_instagram": True,
        "platform_facebook": True,
        "license_expires_at": None,
    }
    mock_supabase = _make_integration_supabase_mock(content_row, blocked_track)

    with patch("app.scheduler.jobs.platform_publish.get_supabase", return_value=mock_supabase), \
         patch("app.scheduler.jobs.platform_publish.get_settings"), \
         patch("app.scheduler.jobs.platform_publish.PublishingService") as mock_pub_svc, \
         patch("app.scheduler.jobs.platform_publish.send_alert_sync"):
        publish_to_platform_job("content-id-integration", "youtube", "https://video.url")

    # PublishingService().publish must NOT be called
    mock_pub_svc.return_value.publish.assert_not_called()


def test_publish_to_platform_job_proceeds_when_cleared():
    """PUB-01 integration: publish_to_platform_job calls PublishingService when track is cleared."""
    from app.scheduler.jobs.platform_publish import publish_to_platform_job

    content_row = {
        "post_copy": "Mochi explora.",
        "post_copy_youtube": "Mochi en la cocina\nExplora con curiosidad",
        "post_copy_tiktok": None,
        "post_copy_instagram": None,
        "post_copy_facebook": None,
        "music_track_id": "uuid-cleared",
    }
    cleared_track = {
        "id": "uuid-cleared",
        "title": "Cleared Song",
        "artist": "Cleared Artist",
        "platform_youtube": True,
        "platform_tiktok": True,
        "platform_instagram": True,
        "platform_facebook": True,
        "license_expires_at": None,
    }
    mock_supabase = _make_integration_supabase_mock(content_row, cleared_track)

    with patch("app.scheduler.jobs.platform_publish.get_supabase", return_value=mock_supabase), \
         patch("app.scheduler.jobs.platform_publish.get_settings"), \
         patch("app.scheduler.jobs.platform_publish.PublishingService") as mock_pub_svc, \
         patch("app.scheduler.jobs.platform_publish.send_platform_success_sync"), \
         patch("app.scheduler.jobs.platform_publish.send_alert_sync"):
        # Make scheduler not crash on add_job
        import app.scheduler.jobs.platform_publish as pp_module
        pp_module._scheduler = MagicMock()
        mock_pub_svc.return_value.publish.return_value = {
            "external_post_id": "ext-123",
            "platform_post_id": "plat-456",
        }
        publish_to_platform_job("content-id-cleared", "youtube", "https://video.url")

    # PublishingService().publish must be called once
    mock_pub_svc.return_value.publish.assert_called_once()
