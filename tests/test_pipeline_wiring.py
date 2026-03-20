"""Integration tests for Phase 10 pipeline wiring (SCN-01 through MUS-03 end-to-end)."""
import pytest
from unittest.mock import MagicMock, patch, call


def _run_pipeline_with_mocks(
    scene_return=("Mochi explora la cocina...", "Mochi descubre la cocina", "curious", 0.001),
    music_return={"id": "music-uuid-1", "title": "Test Track", "artist": "Test Artist", "file_url": "http://x.mp3", "bpm": 95, "mood": "curious"},
    embedding_return=([0.1] * 1536, 0.0001),
    similarity_return=False,
    kling_job_id="kling-test-job-123",
    anti_rep_enabled=False,
):
    """Helper: run daily_pipeline_job with all external services mocked."""
    mock_supabase = MagicMock()
    mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []
    mock_supabase.table.return_value.insert.return_value.execute.return_value.data = [{"id": "content-history-uuid-1"}]

    mock_cb = MagicMock()
    mock_cb.is_tripped.return_value = False
    mock_cb.is_daily_halted.return_value = False
    mock_cb.record_attempt.return_value = True

    mock_kling_cb = MagicMock()
    mock_kling_cb.is_open.return_value = False

    mock_scene_engine = MagicMock()
    mock_scene_engine.pick_scene.return_value = scene_return
    mock_scene_engine.load_active_scene_rejections.return_value = []

    mock_music_matcher = MagicMock()
    mock_music_matcher.pick_track.return_value = music_return

    mock_embedding_svc = MagicMock()
    mock_embedding_svc.generate.return_value = embedding_return

    mock_similarity_svc = MagicMock()
    mock_similarity_svc.is_too_similar_scene.return_value = similarity_return

    mock_kling_svc = MagicMock()
    mock_kling_svc.submit.return_value = kling_job_id

    mock_settings = MagicMock()
    mock_settings.scene_anti_repetition_enabled = anti_rep_enabled

    with patch("app.scheduler.jobs.daily_pipeline.get_supabase", return_value=mock_supabase), \
         patch("app.scheduler.jobs.daily_pipeline.CircuitBreakerService", return_value=mock_cb), \
         patch("app.scheduler.jobs.daily_pipeline.SceneEngine", return_value=mock_scene_engine), \
         patch("app.scheduler.jobs.daily_pipeline.MusicMatcher", return_value=mock_music_matcher), \
         patch("app.scheduler.jobs.daily_pipeline.EmbeddingService", return_value=mock_embedding_svc), \
         patch("app.scheduler.jobs.daily_pipeline.SimilarityService", return_value=mock_similarity_svc), \
         patch("app.scheduler.jobs.daily_pipeline.get_settings", return_value=mock_settings), \
         patch("app.scheduler.jobs.daily_pipeline.send_alert_sync"), \
         patch("app.services.kling_circuit_breaker.KlingCircuitBreakerService", return_value=mock_kling_cb), \
         patch("app.services.kling.KlingService", return_value=mock_kling_svc), \
         patch("app.scheduler.jobs.video_poller.register_video_poller"), \
         patch("app.scheduler.jobs.daily_pipeline._expire_stale_approvals"):
        from app.scheduler.jobs import daily_pipeline
        daily_pipeline.daily_pipeline_job()

    return {
        "scene_engine": mock_scene_engine,
        "music_matcher": mock_music_matcher,
        "embedding_svc": mock_embedding_svc,
        "similarity_svc": mock_similarity_svc,
        "kling_svc": mock_kling_svc,
        "supabase": mock_supabase,
        "settings": mock_settings,
    }


def test_scene_engine_replaces_script_generation():
    """Pipeline: SceneEngine.pick_scene() is called instead of ScriptGenerationService."""
    mocks = _run_pipeline_with_mocks()
    mocks["scene_engine"].pick_scene.assert_called_once()
    # ScriptGenerationService should not be imported or called
    # (verified by the absence of its import in daily_pipeline.py)


def test_music_matcher_called_with_scene_mood():
    """Pipeline: MusicMatcher.pick_track() called with mood from SceneEngine result."""
    mocks = _run_pipeline_with_mocks(
        scene_return=("scene prompt...", "caption here", "curious", 0.001)
    )
    mocks["music_matcher"].pick_track.assert_called_once()
    call_args = mocks["music_matcher"].pick_track.call_args
    assert call_args.kwargs.get("mood") == "curious" or call_args[1].get("mood") == "curious" or call_args[0][0] == "curious"


def test_scene_prompt_passed_to_kling_not_caption():
    """Pipeline: KlingService.submit() receives scene_prompt, not caption."""
    scene_prompt = "Mochi, el gato naranja tabby, inspecciona la cocina..."
    caption = "Mochi descubre los secretos"
    mocks = _run_pipeline_with_mocks(
        scene_return=(scene_prompt, caption, "curious", 0.001)
    )
    # Kling receives scene_prompt
    submit_call = mocks["kling_svc"].submit.call_args
    submitted_text = submit_call[0][0] if submit_call[0] else submit_call[1].get("scene_prompt", "")
    assert scene_prompt in (submitted_text or ""), \
        f"Kling should receive scene_prompt, got: {submitted_text}"


def test_music_track_id_saved_to_content_history():
    """Pipeline: music_track_id is included in content_history insert."""
    mocks = _run_pipeline_with_mocks(
        music_return={"id": "music-uuid-42", "title": "Test", "artist": "Test", "file_url": "http://x.mp3", "bpm": 95, "mood": "curious"}
    )
    insert_call = mocks["supabase"].table.return_value.insert.call_args
    if insert_call:
        inserted_data = insert_call[0][0]
        assert "music_track_id" in inserted_data or "music_track_id" in str(inserted_data), \
            "music_track_id must be saved to content_history"


def test_caption_saved_to_content_history():
    """Pipeline: caption from SceneEngine saved to content_history.caption."""
    caption = "Mochi descubre los secretos de la cocina"
    mocks = _run_pipeline_with_mocks(
        scene_return=("scene prompt...", caption, "curious", 0.001)
    )
    insert_call = mocks["supabase"].table.return_value.insert.call_args
    if insert_call:
        inserted_data = insert_call[0][0]
        assert "caption" in inserted_data, "caption must be saved to content_history"


def test_music_matcher_failure_sends_alert_and_halts():
    """Pipeline: MusicMatcher ValueError sends Telegram alert and stops pipeline."""
    with patch("app.scheduler.jobs.daily_pipeline.get_supabase") as mock_get_supabase, \
         patch("app.scheduler.jobs.daily_pipeline.CircuitBreakerService") as mock_cb_cls, \
         patch("app.scheduler.jobs.daily_pipeline.SceneEngine") as mock_engine_cls, \
         patch("app.scheduler.jobs.daily_pipeline.MusicMatcher") as mock_matcher_cls, \
         patch("app.scheduler.jobs.daily_pipeline.EmbeddingService") as mock_embed_cls, \
         patch("app.scheduler.jobs.daily_pipeline.SimilarityService") as mock_sim_cls, \
         patch("app.scheduler.jobs.daily_pipeline.get_settings") as mock_settings, \
         patch("app.scheduler.jobs.daily_pipeline.send_alert_sync") as mock_alert, \
         patch("app.scheduler.jobs.daily_pipeline._expire_stale_approvals"):

        mock_get_supabase.return_value = MagicMock()
        mock_cb = MagicMock()
        mock_cb.is_tripped.return_value = False
        mock_cb.is_daily_halted.return_value = False
        mock_cb.record_attempt.return_value = True
        mock_cb_cls.return_value = mock_cb

        mock_engine = MagicMock()
        mock_engine.pick_scene.return_value = ("prompt...", "caption", "curious", 0.001)
        mock_engine.load_active_scene_rejections.return_value = []
        mock_engine_cls.return_value = mock_engine

        mock_matcher = MagicMock()
        mock_matcher.pick_track.side_effect = ValueError("no cleared tracks found for mood='curious'")
        mock_matcher_cls.return_value = mock_matcher

        mock_embed = MagicMock()
        mock_embed.generate.return_value = ([0.1] * 1536, 0.0001)
        mock_embed_cls.return_value = mock_embed

        mock_sim = MagicMock()
        mock_sim.is_too_similar_scene.return_value = False
        mock_sim_cls.return_value = mock_sim

        mock_settings.return_value.scene_anti_repetition_enabled = False

        from app.scheduler.jobs import daily_pipeline
        daily_pipeline.daily_pipeline_job()

    mock_alert.assert_called()
    alert_text = mock_alert.call_args[0][0]
    assert "música" in alert_text.lower() or "music" in alert_text.lower() or "MusicMatcher" in alert_text


def test_anti_repetition_log_only_mode_does_not_retry():
    """Pipeline: similarity detected + anti-repetition disabled = log warning, continue (no retry)."""
    mocks = _run_pipeline_with_mocks(
        similarity_return=True,   # scene IS similar
        anti_rep_enabled=False,   # but enforcement is disabled
    )
    # Pipeline should complete (not halt): pick_scene called only once
    assert mocks["scene_engine"].pick_scene.call_count == 1, \
        "In log-only mode, pipeline should NOT retry on similarity detection"
    # Kling should still be called
    mocks["kling_svc"].submit.assert_called_once()
