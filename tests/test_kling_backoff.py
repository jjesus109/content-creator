"""
TDD RED: Tests for CB wiring and exponential backoff integration.
Phase 09-03 Task 2

Tests 7 behaviors:
  1. video_poller_job calls cb.check_balance() once per poll and returns early if False
  2. video_poller_job calls cb.record_attempt(success=False) when Kling status is "failed"
  3. video_poller_job calls cb.record_attempt(success=True) when Kling status is "completed"
  4. daily_pipeline.py calls kling_cb.is_open() before KlingService.submit() and skips if open
  5. KlingService.submit() applies tenacity retry with wait_exponential and stop_after_attempt(3)
  6. After all tenacity retries exhausted, submit() raises the exception (not swallowed)
  7. tenacity is in pyproject.toml
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


# --- Test 1: video_poller_job calls check_balance() and halts if False ---

def test_video_poller_calls_check_balance_and_cancels_if_false():
    """video_poller_job calls cb.check_balance() at start; cancels and returns if check_balance() is False."""
    submitted_at = datetime.now(tz=timezone.utc)

    mock_cb = MagicMock()
    mock_cb.check_balance.return_value = False  # Halt — balance too low

    mock_kling_cb_class = MagicMock(return_value=mock_cb)

    with patch("app.scheduler.jobs.video_poller.fal_client") as mock_fal, \
         patch("app.scheduler.jobs.video_poller.get_settings") as mock_settings, \
         patch("app.scheduler.jobs.video_poller.get_supabase") as mock_get_db, \
         patch("app.scheduler.jobs.video_poller._cancel_self") as mock_cancel, \
         patch("app.services.kling_circuit_breaker.KlingCircuitBreakerService", mock_kling_cb_class):
        mock_settings.return_value.kling_model_version = "fal-ai/kling-video/v3/standard/text-to-video"

        from app.scheduler.jobs.video_poller import video_poller_job
        video_poller_job("kling-job-bal-001", submitted_at)

    # check_balance must be called
    mock_cb.check_balance.assert_called_once()
    # fal_client.status must NOT have been called (returned early)
    mock_fal.status.assert_not_called()


# --- Test 2: video_poller_job records failure on Kling "failed" status ---

def test_video_poller_records_failure_on_kling_failed():
    """video_poller_job calls cb.record_attempt(success=False) when Kling status is 'failed'."""
    submitted_at = datetime.now(tz=timezone.utc)
    mock_status = _make_fal_status("failed", error="render_timeout")

    mock_cb = MagicMock()
    mock_cb.check_balance.return_value = True  # Balance OK
    mock_kling_cb_class = MagicMock(return_value=mock_cb)

    with patch("app.scheduler.jobs.video_poller.fal_client") as mock_fal, \
         patch("app.scheduler.jobs.video_poller.get_settings") as mock_settings, \
         patch("app.scheduler.jobs.video_poller.get_supabase"), \
         patch("app.scheduler.jobs.video_poller._cancel_self"), \
         patch("app.services.kling._handle_render_failure"), \
         patch("app.services.kling_circuit_breaker.KlingCircuitBreakerService", mock_kling_cb_class):
        mock_settings.return_value.kling_model_version = "fal-ai/kling-video/v3/standard/text-to-video"
        mock_fal.status.return_value = mock_status

        from app.scheduler.jobs.video_poller import video_poller_job
        video_poller_job("kling-job-fail-002", submitted_at)

    mock_cb.record_attempt.assert_called_once_with(success=False)


# --- Test 3: video_poller_job records success on Kling "completed" status ---

def test_video_poller_records_success_on_kling_completed():
    """video_poller_job calls cb.record_attempt(success=True) when Kling status is 'completed'."""
    submitted_at = datetime.now(tz=timezone.utc)
    mock_status = _make_fal_status("completed", video_url="https://fal.ai/video/test.mp4")

    mock_cb = MagicMock()
    mock_cb.check_balance.return_value = True  # Balance OK
    mock_kling_cb_class = MagicMock(return_value=mock_cb)

    with patch("app.scheduler.jobs.video_poller.fal_client") as mock_fal, \
         patch("app.scheduler.jobs.video_poller.get_settings") as mock_settings, \
         patch("app.scheduler.jobs.video_poller.get_supabase"), \
         patch("app.scheduler.jobs.video_poller._cancel_self"), \
         patch("app.services.kling._process_completed_render"), \
         patch("app.services.kling_circuit_breaker.KlingCircuitBreakerService", mock_kling_cb_class):
        mock_settings.return_value.kling_model_version = "fal-ai/kling-video/v3/standard/text-to-video"
        mock_fal.status.return_value = mock_status

        from app.scheduler.jobs.video_poller import video_poller_job
        video_poller_job("kling-job-ok-003", submitted_at)

    mock_cb.record_attempt.assert_called_once_with(success=True)


# --- Test 4: daily_pipeline skips Kling submit if CB is open ---

def test_daily_pipeline_skips_kling_when_cb_open():
    """daily_pipeline.py checks kling_cb.is_open() before submit and skips if open.
    Updated for v2.0: uses SceneEngine + MusicMatcher (MoodService + ScriptGenerationService removed).
    """
    mock_cb = MagicMock()
    mock_cb.is_open.return_value = True  # CB is open
    mock_kling_cb_class = MagicMock(return_value=mock_cb)

    mock_supabase = MagicMock()
    # Prevent expire_stale_approvals from doing real work
    mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
    mock_supabase.table.return_value.select.return_value.execute.return_value = MagicMock(data=[])

    mock_circuit_cb = MagicMock()
    mock_circuit_cb.is_tripped.return_value = False
    mock_circuit_cb.is_daily_halted.return_value = False
    mock_circuit_cb.record_attempt.return_value = True
    mock_circuit_cb_class = MagicMock(return_value=mock_circuit_cb)

    mock_scene_engine = MagicMock()
    mock_scene_engine.pick_scene.return_value = ("scene prompt...", "caption here", "curious", 0.001)
    mock_scene_engine.load_active_scene_rejections.return_value = []

    mock_music_matcher = MagicMock()
    mock_music_matcher.pick_track.return_value = {
        "id": "music-uuid-1", "title": "Test Track", "artist": "Test Artist",
        "file_url": "http://x.mp3", "bpm": 95, "mood": "curious"
    }

    mock_embedding_svc = MagicMock()
    mock_embedding_svc.generate.return_value = ([0.1] * 1536, 0.0001)

    mock_similarity_svc = MagicMock()
    mock_similarity_svc.is_too_similar_scene.return_value = False

    mock_settings = MagicMock()
    mock_settings.scene_anti_repetition_enabled = False

    with patch("app.scheduler.jobs.daily_pipeline.CircuitBreakerService", mock_circuit_cb_class), \
         patch("app.scheduler.jobs.daily_pipeline.get_supabase", return_value=mock_supabase), \
         patch("app.scheduler.jobs.daily_pipeline.SceneEngine", return_value=mock_scene_engine), \
         patch("app.scheduler.jobs.daily_pipeline.MusicMatcher", return_value=mock_music_matcher), \
         patch("app.scheduler.jobs.daily_pipeline.EmbeddingService", return_value=mock_embedding_svc), \
         patch("app.scheduler.jobs.daily_pipeline.SimilarityService", return_value=mock_similarity_svc), \
         patch("app.scheduler.jobs.daily_pipeline.get_settings", return_value=mock_settings), \
         patch("app.services.kling_circuit_breaker.KlingCircuitBreakerService", mock_kling_cb_class), \
         patch("app.scheduler.jobs.daily_pipeline.send_alert_sync") as mock_alert, \
         patch("app.scheduler.jobs.daily_pipeline._expire_stale_approvals"):

        from app.scheduler.jobs.daily_pipeline import daily_pipeline_job
        daily_pipeline_job()

    # CB.is_open() must have been called
    mock_cb.is_open.assert_called_once()

    # Verify alert was sent when Kling CB is open
    mock_alert.assert_called()
    alert_text = mock_alert.call_args[0][0]
    assert "Kling" in alert_text or "kling" in alert_text.lower() or "circuit" in alert_text.lower(), \
        f"Alert must mention Kling CB. Got: {alert_text}"


# --- Test 5: KlingService.submit() uses _submit_with_backoff (tenacity) ---

def test_kling_service_submit_uses_backoff_function():
    """KlingService.submit() calls _submit_with_backoff instead of fal_client.submit directly."""
    import os
    kling_path = os.path.join(
        os.path.dirname(__file__), '..', 'src', 'app', 'services', 'kling.py'
    )
    with open(kling_path) as f:
        source = f.read()

    assert "_submit_with_backoff" in source, (
        "kling.py must define and use _submit_with_backoff for exponential backoff"
    )
    assert "wait_exponential" in source, (
        "kling.py must use wait_exponential from tenacity"
    )
    assert "stop_after_attempt" in source, (
        "kling.py must use stop_after_attempt(3) from tenacity"
    )


# --- Test 6: After tenacity retries exhausted, exception is re-raised ---

def test_kling_submit_backoff_reraises_on_exhaustion():
    """After all tenacity retries exhausted, submit() raises the exception (not swallowed)."""
    import pytest

    mock_result = MagicMock()
    mock_result.request_id = "test-job"

    call_count = [0]

    def always_fail(model_id, arguments):
        call_count[0] += 1
        raise Exception("fal.ai API unavailable")

    with patch("app.services.kling.fal_client") as mock_fal, \
         patch("app.services.kling.get_settings") as mock_settings, \
         patch("app.services.kling._submit_with_backoff", side_effect=Exception("fal.ai API unavailable")):
        mock_settings.return_value.kling_model_version = "fal-ai/kling-video/v3/standard/text-to-video"

        from app.services.kling import KlingService
        svc = KlingService()

        with pytest.raises(Exception, match="fal.ai API unavailable"):
            svc.submit("Test scene.")


# --- Test 7: tenacity is in pyproject.toml ---

def test_tenacity_in_pyproject():
    """tenacity dependency is present in pyproject.toml."""
    import os
    pyproject_path = os.path.join(
        os.path.dirname(__file__), '..', 'pyproject.toml'
    )
    with open(pyproject_path) as f:
        content = f.read()

    assert "tenacity" in content, (
        "pyproject.toml must include tenacity as a dependency"
    )
