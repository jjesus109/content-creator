"""
TDD RED: KlingService unit tests.
Phase 09-02 Task 1
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from unittest.mock import MagicMock, patch


def test_kling_service_submit_calls_fal_client():
    """KlingService.submit() calls fal_client.submit with the locked model ID."""
    mock_result = MagicMock()
    mock_result.request_id = "test-job-123"

    with patch("app.services.kling.fal_client") as mock_fal, \
         patch("app.services.kling.get_settings") as mock_settings:
        mock_settings.return_value.kling_model_version = "fal-ai/kling-video/v3/standard/text-to-video"
        mock_fal.submit.return_value = mock_result

        from app.services.kling import KlingService
        svc = KlingService()
        job_id = svc.submit("A cat playing with yarn in a kitchen.")

    assert job_id == "test-job-123"
    mock_fal.submit.assert_called_once()
    call_args = mock_fal.submit.call_args
    assert call_args[0][0] == "fal-ai/kling-video/v3/standard/text-to-video"


def test_kling_service_submit_returns_request_id():
    """KlingService.submit() returns result.request_id."""
    mock_result = MagicMock()
    mock_result.request_id = "fal-job-abc123"

    with patch("app.services.kling.fal_client") as mock_fal, \
         patch("app.services.kling.get_settings") as mock_settings:
        mock_settings.return_value.kling_model_version = "fal-ai/kling-video/v3/standard/text-to-video"
        mock_fal.submit.return_value = mock_result

        from app.services.kling import KlingService
        svc = KlingService()
        result = svc.submit("Test scene.")

    assert result == "fal-job-abc123"


def test_kling_prompt_includes_character_bible_unchanged():
    """Prompt sent to fal.ai is CHARACTER_BIBLE + newline + script_text, bible first and unchanged."""
    from app.services.kling import CHARACTER_BIBLE

    mock_result = MagicMock()
    mock_result.request_id = "job-xyz"

    with patch("app.services.kling.fal_client") as mock_fal, \
         patch("app.services.kling.get_settings") as mock_settings:
        mock_settings.return_value.kling_model_version = "fal-ai/kling-video/v3/standard/text-to-video"
        mock_fal.submit.return_value = mock_result

        from app.services.kling import KlingService
        svc = KlingService()
        scene_text = "Mochi investigates a fallen serape."
        svc.submit(scene_text)

    call_kwargs = mock_fal.submit.call_args[1]
    prompt = call_kwargs["arguments"]["prompt"]
    assert prompt.startswith(CHARACTER_BIBLE), (
        "Prompt must start with CHARACTER_BIBLE unchanged"
    )
    assert scene_text in prompt, "Prompt must include the scene text"
    assert f"{CHARACTER_BIBLE}\n\n{scene_text}" == prompt


def test_kling_fal_arguments_locked_spec():
    """fal.ai arguments must include duration=20, resolution='1080p', aspect_ratio='9:16'."""
    mock_result = MagicMock()
    mock_result.request_id = "job-spec-test"

    with patch("app.services.kling.fal_client") as mock_fal, \
         patch("app.services.kling.get_settings") as mock_settings:
        mock_settings.return_value.kling_model_version = "fal-ai/kling-video/v3/standard/text-to-video"
        mock_fal.submit.return_value = mock_result

        from app.services.kling import KlingService
        svc = KlingService()
        svc.submit("Test scene.")

    call_kwargs = mock_fal.submit.call_args[1]
    args = call_kwargs["arguments"]
    assert args["duration"] == 20, f"Expected duration=20, got {args['duration']}"
    assert args["resolution"] == "1080p", f"Expected resolution='1080p', got {args['resolution']}"
    assert args["aspect_ratio"] == "9:16", f"Expected aspect_ratio='9:16', got {args['aspect_ratio']}"


def test_process_completed_render_uses_kling_job_id():
    """_process_completed_render uses kling_job_id column (not heygen_job_id) for DB lookups."""
    mock_supabase = MagicMock()
    # Simulate no existing row for double-processing guard (returns empty data — skip)
    mock_update_chain = MagicMock()
    mock_update_chain.execute.return_value = MagicMock(data=[])
    mock_supabase.table.return_value.update.return_value.eq.return_value.in_.return_value = mock_update_chain

    with patch("app.services.kling.get_supabase", return_value=mock_supabase):
        from app.services.kling import _process_completed_render
        _process_completed_render("kling-job-001", "https://example.com/video.mp4")

    # Verify the DB update used kling_job_id not heygen_job_id
    table_calls = mock_supabase.table.call_args_list
    assert any("content_history" in str(c) for c in table_calls)
    update_call = mock_supabase.table.return_value.update.return_value.eq.call_args
    assert update_call[0][0] == "kling_job_id", (
        f"DB filter must use 'kling_job_id', got {update_call[0][0]!r}"
    )


def test_process_completed_render_double_processing_guard():
    """_process_completed_render only proceeds if status is kling_pending or kling_pending_retry."""
    mock_supabase = MagicMock()

    # Simulate row already claimed (returns empty data — another caller won)
    mock_update_chain = MagicMock()
    mock_update_chain.execute.return_value = MagicMock(data=[])
    mock_supabase.table.return_value.update.return_value.eq.return_value.in_.return_value = mock_update_chain

    with patch("app.services.kling.get_supabase", return_value=mock_supabase), \
         patch("app.services.kling.requests") as mock_requests:

        from app.services.kling import _process_completed_render
        _process_completed_render("kling-job-002", "https://example.com/video.mp4")

    # requests.get must NOT be called — skipped early due to empty result
    mock_requests.get.assert_not_called()

    # Verify in_ was called with kling_pending and kling_pending_retry
    in_call = mock_supabase.table.return_value.update.return_value.eq.return_value.in_.call_args
    statuses = in_call[0][1]
    assert "kling_pending" in statuses
    assert "kling_pending_retry" in statuses


def test_handle_render_failure_sets_failed_and_alerts():
    """_handle_render_failure sets video_status=FAILED and calls send_alert_sync."""
    mock_supabase = MagicMock()
    mock_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()

    with patch("app.services.kling.get_supabase", return_value=mock_supabase), \
         patch("app.services.kling.send_alert_sync") as mock_alert:

        from app.services.kling import _handle_render_failure
        _handle_render_failure("kling-job-fail", "render timed out")

    # DB should be updated with failed status
    mock_supabase.table.return_value.update.assert_called_once()
    update_args = mock_supabase.table.return_value.update.call_args[0][0]
    assert update_args["video_status"] == "failed"

    # Alert must be sent
    mock_alert.assert_called_once()
    alert_msg = mock_alert.call_args[0][0]
    assert "kling-job-fail" in alert_msg
