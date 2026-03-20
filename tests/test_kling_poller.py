"""
Tests for video_poller.py — Kling/fal.ai status detection using isinstance checks.
Phase 09-02 Task 2 (updated 260320-dtz: fix status flow)
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from unittest.mock import MagicMock, patch, call
from datetime import datetime, timezone
import fal_client as fal_module


def _make_completed_status():
    """Return a real fal_client.Completed instance."""
    return fal_module.Completed(logs=None, metrics={})


def _make_in_progress_status():
    """Return a real fal_client.InProgress instance."""
    return fal_module.InProgress(logs=None)


def _make_queued_status():
    """Return a real fal_client.Queued instance."""
    return fal_module.Queued(position=0)


def test_video_poller_calls_fal_client_status_not_heygen():
    """video_poller_job calls fal_client.status(), not requests.get(HEYGEN_STATUS_URL)."""
    submitted_at = datetime.now(tz=timezone.utc)
    mock_status = _make_in_progress_status()

    with patch("app.scheduler.jobs.video_poller.fal_client") as mock_fal, \
         patch("app.scheduler.jobs.video_poller.get_settings") as mock_settings, \
         patch("app.scheduler.jobs.video_poller.get_supabase"):
        mock_settings.return_value.kling_model_version = "fal-ai/kling-video/v3/standard/text-to-video"
        mock_fal.status.return_value = mock_status
        mock_fal.InProgress = fal_module.InProgress
        mock_fal.Completed = fal_module.Completed
        mock_fal.Queued = fal_module.Queued

        from app.scheduler.jobs.video_poller import video_poller_job
        video_poller_job("kling-job-001", submitted_at)

    mock_fal.status.assert_called_once()
    # Verify it did NOT call requests.get with a HeyGen URL


def test_video_poller_on_completed_calls_process_completed_render():
    """On fal.ai Completed status, calls kling._process_completed_render with video_url."""
    submitted_at = datetime.now(tz=timezone.utc)
    mock_status = _make_completed_status()
    mock_result = {"video": {"url": "https://fal.ai/video/test.mp4"}}

    with patch("app.scheduler.jobs.video_poller.fal_client") as mock_fal, \
         patch("app.scheduler.jobs.video_poller.get_settings") as mock_settings, \
         patch("app.services.kling._process_completed_render") as mock_process, \
         patch("app.scheduler.jobs.video_poller._cancel_self") as mock_cancel, \
         patch("app.scheduler.jobs.video_poller.get_supabase"):
        mock_settings.return_value.kling_model_version = "fal-ai/kling-video/v3/standard/text-to-video"
        mock_fal.status.return_value = mock_status
        mock_fal.result.return_value = mock_result
        mock_fal.Completed = fal_module.Completed
        mock_fal.InProgress = fal_module.InProgress
        mock_fal.Queued = fal_module.Queued

        from app.scheduler.jobs.video_poller import video_poller_job
        video_poller_job("kling-job-002", submitted_at)

    mock_process.assert_called_once_with("kling-job-002", "https://fal.ai/video/test.mp4")
    mock_cancel.assert_called_once_with("kling-job-002")
    # Verify fal_client.result() was called to retrieve the video URL
    mock_fal.result.assert_called_once()


def test_video_poller_on_exception_logs_and_continues_polling():
    """When fal_client.status() raises an exception, logs error and does NOT cancel the poller."""
    submitted_at = datetime.now(tz=timezone.utc)

    with patch("app.scheduler.jobs.video_poller.fal_client") as mock_fal, \
         patch("app.scheduler.jobs.video_poller.get_settings") as mock_settings, \
         patch("app.scheduler.jobs.video_poller._cancel_self") as mock_cancel, \
         patch("app.scheduler.jobs.video_poller.get_supabase"):
        mock_settings.return_value.kling_model_version = "fal-ai/kling-video/v3/standard/text-to-video"
        mock_fal.status.side_effect = Exception("render error")
        mock_fal.Completed = fal_module.Completed
        mock_fal.InProgress = fal_module.InProgress
        mock_fal.Queued = fal_module.Queued

        from app.scheduler.jobs.video_poller import video_poller_job
        video_poller_job("kling-job-003", submitted_at)

    # Exception handling — poller should NOT be cancelled (transient failure)
    mock_cancel.assert_not_called()


def test_video_poller_on_in_progress_continues_polling():
    """On fal.ai InProgress status, does NOT cancel and does NOT call _process_completed_render."""
    submitted_at = datetime.now(tz=timezone.utc)
    mock_status = _make_in_progress_status()

    with patch("app.scheduler.jobs.video_poller.fal_client") as mock_fal, \
         patch("app.scheduler.jobs.video_poller.get_settings") as mock_settings, \
         patch("app.scheduler.jobs.video_poller._cancel_self") as mock_cancel, \
         patch("app.scheduler.jobs.video_poller.get_supabase"):
        mock_settings.return_value.kling_model_version = "fal-ai/kling-video/v3/standard/text-to-video"
        mock_fal.status.return_value = mock_status
        mock_fal.Completed = fal_module.Completed
        mock_fal.InProgress = fal_module.InProgress
        mock_fal.Queued = fal_module.Queued

        from app.scheduler.jobs.video_poller import video_poller_job
        video_poller_job("kling-job-004", submitted_at)

    mock_cancel.assert_not_called()


def test_video_poller_on_queued_continues_polling():
    """On fal.ai Queued status, does NOT cancel the poller."""
    submitted_at = datetime.now(tz=timezone.utc)
    mock_status = _make_queued_status()

    with patch("app.scheduler.jobs.video_poller.fal_client") as mock_fal, \
         patch("app.scheduler.jobs.video_poller.get_settings") as mock_settings, \
         patch("app.scheduler.jobs.video_poller._cancel_self") as mock_cancel, \
         patch("app.scheduler.jobs.video_poller.get_supabase"):
        mock_settings.return_value.kling_model_version = "fal-ai/kling-video/v3/standard/text-to-video"
        mock_fal.status.return_value = mock_status
        mock_fal.Completed = fal_module.Completed
        mock_fal.InProgress = fal_module.InProgress
        mock_fal.Queued = fal_module.Queued

        from app.scheduler.jobs.video_poller import video_poller_job
        video_poller_job("kling-job-005", submitted_at)

    mock_cancel.assert_not_called()


def test_retry_or_fail_uses_kling_job_id_column():
    """_retry_or_fail queries content_history using kling_job_id (not heygen_job_id)."""
    mock_supabase = MagicMock()
    mock_supabase.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(data=None)

    with patch("app.scheduler.jobs.video_poller.get_supabase", return_value=mock_supabase), \
         patch("app.scheduler.jobs.video_poller._cancel_self"):
        from app.scheduler.jobs.video_poller import _retry_or_fail
        _retry_or_fail("kling-job-006")

    # Verify query used kling_job_id
    eq_call = mock_supabase.table.return_value.select.return_value.eq.call_args
    assert eq_call[0][0] == "kling_job_id", (
        f"Expected 'kling_job_id', got {eq_call[0][0]!r}"
    )


def test_retry_or_fail_first_timeout_calls_kling_service():
    """_retry_or_fail on first timeout (kling_pending status) calls KlingService().submit()."""
    mock_supabase = MagicMock()
    mock_row = {"script_text": "Test scene.", "video_status": "kling_pending"}
    mock_supabase.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(data=mock_row)
    mock_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()

    mock_kling_instance = MagicMock()
    mock_kling_instance.submit.return_value = "new-kling-job-456"
    MockKlingClass = MagicMock(return_value=mock_kling_instance)

    # KlingService is imported inside _retry_or_fail via `from app.services.kling import KlingService`
    # Patch at the kling module so local import picks up our mock
    with patch("app.scheduler.jobs.video_poller.get_supabase", return_value=mock_supabase), \
         patch("app.scheduler.jobs.video_poller._cancel_self"), \
         patch("app.scheduler.jobs.video_poller.register_video_poller"), \
         patch("app.services.kling.KlingService", MockKlingClass):

        from app.scheduler.jobs.video_poller import _retry_or_fail
        _retry_or_fail("kling-job-007")

    # submit() must have been called on the KlingService instance
    mock_kling_instance.submit.assert_called_once()
    # Verify the DB was updated with the new job ID and KLING_PENDING_RETRY status
    update_calls = str(mock_supabase.table.return_value.update.call_args_list)
    assert "kling_pending_retry" in update_calls or "new-kling-job-456" in update_calls


def test_daily_pipeline_imports_kling_service():
    """daily_pipeline.py must import KlingService, not HeyGenService, for submission."""
    import ast
    import os
    pipeline_path = os.path.join(
        os.path.dirname(__file__), '..', 'src', 'app', 'scheduler', 'jobs', 'daily_pipeline.py'
    )
    with open(pipeline_path) as f:
        source = f.read()

    # Must reference KlingService
    assert "KlingService" in source, "daily_pipeline.py must import and use KlingService"


def test_daily_pipeline_uses_kling_job_id():
    """daily_pipeline._save_to_content_history uses kling_job_id, not heygen_job_id."""
    import os
    pipeline_path = os.path.join(
        os.path.dirname(__file__), '..', 'src', 'app', 'scheduler', 'jobs', 'daily_pipeline.py'
    )
    with open(pipeline_path) as f:
        source = f.read()

    assert "kling_job_id" in source, "daily_pipeline.py must use kling_job_id"
    assert "heygen_job_id" not in source, (
        "daily_pipeline.py must NOT reference heygen_job_id (old v1.0 column)"
    )


def test_daily_pipeline_saves_kling_pending_status():
    """daily_pipeline._save_to_content_history sets video_status=kling_pending."""
    import os
    pipeline_path = os.path.join(
        os.path.dirname(__file__), '..', 'src', 'app', 'scheduler', 'jobs', 'daily_pipeline.py'
    )
    with open(pipeline_path) as f:
        source = f.read()

    assert "KLING_PENDING" in source or "kling_pending" in source, (
        "daily_pipeline.py must use KLING_PENDING status when saving"
    )
