"""
TDD RED: video_poller.py and daily_pipeline.py adaptation for Kling/fal.ai.
Phase 09-02 Task 2
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from unittest.mock import MagicMock, patch, call
from datetime import datetime, timezone


def _make_fal_status(status: str, video_url: str = None, error: str = None):
    """Helper: create a mock fal_client.status() response."""
    mock_status = MagicMock()
    mock_status.status = status
    if video_url:
        mock_status.response = {"video": {"url": video_url}}
    elif error:
        mock_status.response = {"error": error}
    else:
        mock_status.response = {}
    return mock_status


def test_video_poller_calls_fal_client_status_not_heygen():
    """video_poller_job calls fal_client.status(), not requests.get(HEYGEN_STATUS_URL)."""
    submitted_at = datetime.now(tz=timezone.utc)
    mock_status = _make_fal_status("in_progress")

    with patch("app.scheduler.jobs.video_poller.fal_client") as mock_fal, \
         patch("app.scheduler.jobs.video_poller.get_settings") as mock_settings, \
         patch("app.scheduler.jobs.video_poller.get_supabase"):
        mock_settings.return_value.kling_model_version = "fal-ai/kling-video/v3/standard/text-to-video"
        mock_fal.status.return_value = mock_status

        from app.scheduler.jobs.video_poller import video_poller_job
        video_poller_job("kling-job-001", submitted_at)

    mock_fal.status.assert_called_once()
    # Verify it did NOT call requests.get with a HeyGen URL


def test_video_poller_on_completed_calls_process_completed_render():
    """On fal.ai status 'completed', calls kling._process_completed_render with video_url."""
    submitted_at = datetime.now(tz=timezone.utc)
    mock_status = _make_fal_status("completed", video_url="https://fal.ai/video/test.mp4")

    with patch("app.scheduler.jobs.video_poller.fal_client") as mock_fal, \
         patch("app.scheduler.jobs.video_poller.get_settings") as mock_settings, \
         patch("app.services.kling._process_completed_render") as mock_process, \
         patch("app.scheduler.jobs.video_poller._cancel_self") as mock_cancel, \
         patch("app.scheduler.jobs.video_poller.get_supabase"):
        mock_settings.return_value.kling_model_version = "fal-ai/kling-video/v3/standard/text-to-video"
        mock_fal.status.return_value = mock_status

        from app.scheduler.jobs.video_poller import video_poller_job
        video_poller_job("kling-job-002", submitted_at)

    mock_process.assert_called_once_with("kling-job-002", "https://fal.ai/video/test.mp4")
    mock_cancel.assert_called_once_with("kling-job-002")


def test_video_poller_on_failed_calls_handle_render_failure():
    """On fal.ai status 'failed', calls kling._handle_render_failure."""
    submitted_at = datetime.now(tz=timezone.utc)
    mock_status = _make_fal_status("failed", error="render_timeout")

    with patch("app.scheduler.jobs.video_poller.fal_client") as mock_fal, \
         patch("app.scheduler.jobs.video_poller.get_settings") as mock_settings, \
         patch("app.services.kling._handle_render_failure") as mock_fail, \
         patch("app.scheduler.jobs.video_poller._cancel_self") as mock_cancel, \
         patch("app.scheduler.jobs.video_poller.get_supabase"):
        mock_settings.return_value.kling_model_version = "fal-ai/kling-video/v3/standard/text-to-video"
        mock_fal.status.return_value = mock_status

        from app.scheduler.jobs.video_poller import video_poller_job
        video_poller_job("kling-job-003", submitted_at)

    mock_fail.assert_called_once()
    call_args = mock_fail.call_args[0]
    assert call_args[0] == "kling-job-003"
    mock_cancel.assert_called_once_with("kling-job-003")


def test_retry_or_fail_uses_kling_job_id_column():
    """_retry_or_fail queries content_history using kling_job_id (not heygen_job_id)."""
    mock_supabase = MagicMock()
    mock_supabase.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(data=None)

    with patch("app.scheduler.jobs.video_poller.get_supabase", return_value=mock_supabase), \
         patch("app.scheduler.jobs.video_poller._cancel_self"):
        from app.scheduler.jobs.video_poller import _retry_or_fail
        _retry_or_fail("kling-job-004")

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

    with patch("app.scheduler.jobs.video_poller.get_supabase", return_value=mock_supabase), \
         patch("app.scheduler.jobs.video_poller._cancel_self"), \
         patch("app.scheduler.jobs.video_poller.register_video_poller"), \
         patch("app.services.kling.KlingService") as MockKling, \
         patch("app.scheduler.jobs.video_poller.KlingService", MockKling):
        mock_kling_instance = MagicMock()
        mock_kling_instance.submit.return_value = "new-kling-job-456"
        MockKling.return_value = mock_kling_instance

        from app.scheduler.jobs.video_poller import _retry_or_fail
        _retry_or_fail("kling-job-005")

    mock_kling_instance.submit.assert_called_once()


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
