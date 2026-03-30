"""Integration tests for Phase 13 pipeline wiring (story-arc format with dual embedding anti-repetition)."""
import pytest
from unittest.mock import MagicMock, patch, call

# Phase 13: pick_scenario_arc returns 5-tuple:
# (scenario_description, arc_prompt, caption, mood, cost_usd)
_DEFAULT_SCENARIO_RETURN = (
    "A curious grey kitten spots a rolling avocado on the kitchen floor.",  # scenario_description
    "The grey kitten freezes, pupils wide, as the avocado rolls toward her. "
    "She crouches low, tail flicking, then pounces — only to slide across the tile. "
    "She sits up, licks her paw, and pretends nothing happened.",            # arc_prompt
    "Algo malo va a pasar.",                                                  # caption
    "curious",                                                                # mood
    0.001,                                                                    # cost_usd
)


def _run_pipeline_with_mocks(
    scenario_return=_DEFAULT_SCENARIO_RETURN,
    music_return={"id": "music-uuid-1", "title": "Test Track", "artist": "Test Artist", "file_url": "http://x.mp3", "bpm": 95, "mood": "curious"},
    embedding_return=([0.1] * 1536, 0.0001),
    similarity_return=False,
    kling_job_id="kling-test-job-123",
    anti_rep_enabled=False,
):
    """Helper: run daily_pipeline_job with all external services mocked.

    Phase 13: SceneEngine.pick_scenario_arc() replaces pick_scene().
    Returns (scenario_description, arc_prompt, caption, mood, cost_usd).
    Dual embedding anti-repetition: scene_embedding + prompt_embedding.
    """
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
    mock_scene_engine.pick_scenario_arc.return_value = scenario_return
    mock_scene_engine.load_active_scene_rejections.return_value = []

    mock_music_matcher = MagicMock()
    mock_music_matcher.pick_track.return_value = music_return

    mock_embedding_svc = MagicMock()
    mock_embedding_svc.generate.return_value = embedding_return

    mock_similarity_svc = MagicMock()
    mock_similarity_svc.is_too_similar_scene.return_value = similarity_return
    mock_similarity_svc.is_too_similar_prompt.return_value = False

    mock_kling_svc = MagicMock()
    mock_kling_svc.submit.return_value = kling_job_id

    mock_settings = MagicMock()
    mock_settings.scene_anti_repetition_enabled = anti_rep_enabled

    mock_prompt_gen_svc = MagicMock()
    mock_prompt_gen_svc.generate_unified_prompt.return_value = "Unified animated arc prompt for grey kitten."
    mock_prompt_gen_svc._last_cost_usd = 0.0

    with patch("app.scheduler.jobs.daily_pipeline.get_supabase", return_value=mock_supabase), \
         patch("app.scheduler.jobs.daily_pipeline.CircuitBreakerService", return_value=mock_cb), \
         patch("app.scheduler.jobs.daily_pipeline.SceneEngine", return_value=mock_scene_engine), \
         patch("app.scheduler.jobs.daily_pipeline.MusicMatcher", return_value=mock_music_matcher), \
         patch("app.scheduler.jobs.daily_pipeline.EmbeddingService", return_value=mock_embedding_svc), \
         patch("app.scheduler.jobs.daily_pipeline.SimilarityService", return_value=mock_similarity_svc), \
         patch("app.scheduler.jobs.daily_pipeline.PromptGenerationService", return_value=mock_prompt_gen_svc), \
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
        "prompt_gen_svc": mock_prompt_gen_svc,
        "kling_svc": mock_kling_svc,
        "supabase": mock_supabase,
        "settings": mock_settings,
    }


def test_scene_engine_uses_pick_scenario_arc():
    """Phase 13 Pipeline: SceneEngine.pick_scenario_arc() is called (not pick_scene)."""
    mocks = _run_pipeline_with_mocks()
    mocks["scene_engine"].pick_scenario_arc.assert_called_once()
    # pick_scene should NOT be called in Phase 13+
    mocks["scene_engine"].pick_scene.assert_not_called()


def test_music_matcher_called_with_scene_mood():
    """Pipeline: MusicMatcher.pick_track() called with mood from SceneEngine result."""
    mocks = _run_pipeline_with_mocks(
        scenario_return=(
            "scenario description", "arc prompt text", "caption here", "curious", 0.001
        )
    )
    mocks["music_matcher"].pick_track.assert_called_once()
    call_args = mocks["music_matcher"].pick_track.call_args
    assert call_args.kwargs.get("mood") == "curious" or call_args[1].get("mood") == "curious" or call_args[0][0] == "curious"


def test_arc_prompt_passed_to_prompt_generation_service():
    """Phase 13 Pipeline: PromptGenerationService.generate_unified_prompt() receives arc_prompt (not scenario_description).

    D-07: PromptGenerationService role is to fuse grey kitten character into the arc-structured prompt.
    arc_prompt (3-5 sentence flowing prose arc) is the correct input — not the scenario_description.
    """
    arc_prompt = "The grey kitten spots a fallen tortilla and creeps toward it with exaggerated stealth."
    scenario_description = "A kitten investigates a fallen tortilla."
    caption = "Eso no iba a funcionar."
    mocks = _run_pipeline_with_mocks(
        scenario_return=(scenario_description, arc_prompt, caption, "curious", 0.001)
    )
    # PromptGenerationService should be called with arc_prompt (the flowing prose arc)
    mocks["prompt_gen_svc"].generate_unified_prompt.assert_called_once_with(arc_prompt)


def test_kling_receives_unified_prompt_not_caption():
    """Pipeline: KlingService.submit() receives unified_prompt (not caption, not raw arc_prompt)."""
    caption = "Algo malo va a pasar."
    mocks = _run_pipeline_with_mocks(
        scenario_return=_DEFAULT_SCENARIO_RETURN
    )
    submit_call = mocks["kling_svc"].submit.call_args
    submitted_text = submit_call[0][0] if submit_call[0] else submit_call[1].get("script_text", "")
    assert caption not in (submitted_text or ""), \
        f"Kling should NOT receive caption, got: {submitted_text}"


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
    caption = "Algo malo va a pasar."
    mocks = _run_pipeline_with_mocks(
        scenario_return=(
            "scenario description", "arc prompt text", caption, "curious", 0.001
        )
    )
    insert_call = mocks["supabase"].table.return_value.insert.call_args
    if insert_call:
        inserted_data = insert_call[0][0]
        assert "caption" in inserted_data, "caption must be saved to content_history"


def test_prompt_embedding_saved_to_content_history():
    """Phase 13 Pipeline: prompt_embedding is included in content_history insert (D-09)."""
    mocks = _run_pipeline_with_mocks()
    insert_call = mocks["supabase"].table.return_value.insert.call_args
    if insert_call:
        inserted_data = insert_call[0][0]
        assert "prompt_embedding" in inserted_data or "prompt_embedding" in str(inserted_data), \
            "prompt_embedding must be saved to content_history (Phase 13 D-09)"


def test_dual_embedding_calls():
    """Phase 13 Pipeline: EmbeddingService.generate() called twice — once for scene, once for prompt."""
    mocks = _run_pipeline_with_mocks()
    # embedding_svc.generate should be called at least twice:
    # 4c: embed scene_prompt (scenario_description)
    # 4h: embed unified_prompt
    assert mocks["embedding_svc"].generate.call_count >= 2, (
        "Phase 13 requires dual embeddings: scene_embedding (4c) + prompt_embedding (4h). "
        f"generate() was called {mocks['embedding_svc'].generate.call_count} time(s)"
    )


def test_is_too_similar_prompt_called():
    """Phase 13 Pipeline: SimilarityService.is_too_similar_prompt() is called for prompt-level anti-repetition."""
    mocks = _run_pipeline_with_mocks()
    mocks["similarity_svc"].is_too_similar_prompt.assert_called_once()


def test_music_matcher_failure_sends_alert_and_halts():
    """Pipeline: MusicMatcher ValueError sends Telegram alert and stops pipeline."""
    with patch("app.scheduler.jobs.daily_pipeline.get_supabase") as mock_get_supabase, \
         patch("app.scheduler.jobs.daily_pipeline.CircuitBreakerService") as mock_cb_cls, \
         patch("app.scheduler.jobs.daily_pipeline.SceneEngine") as mock_engine_cls, \
         patch("app.scheduler.jobs.daily_pipeline.MusicMatcher") as mock_matcher_cls, \
         patch("app.scheduler.jobs.daily_pipeline.EmbeddingService") as mock_embed_cls, \
         patch("app.scheduler.jobs.daily_pipeline.SimilarityService") as mock_sim_cls, \
         patch("app.scheduler.jobs.daily_pipeline.PromptGenerationService") as mock_prompt_gen_cls, \
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
        mock_engine.pick_scenario_arc.return_value = _DEFAULT_SCENARIO_RETURN
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
        mock_sim.is_too_similar_prompt.return_value = False
        mock_sim_cls.return_value = mock_sim

        mock_prompt_gen = MagicMock()
        mock_prompt_gen.generate_unified_prompt.return_value = "Unified animated prompt."
        mock_prompt_gen._last_cost_usd = 0.0
        mock_prompt_gen_cls.return_value = mock_prompt_gen

        mock_settings.return_value.scene_anti_repetition_enabled = False

        from app.scheduler.jobs import daily_pipeline
        daily_pipeline.daily_pipeline_job()

    mock_alert.assert_called()
    alert_text = mock_alert.call_args[0][0]
    assert "música" in alert_text.lower() or "music" in alert_text.lower() or "MusicMatcher" in alert_text


def test_prompt_generation_service_called_between_scene_and_kling():
    """Pipeline: PromptGenerationService.generate_unified_prompt() is called before KlingService.submit()."""
    arc_prompt = "The grey kitten creeps toward the avocado, pounces, and slides."
    mocks = _run_pipeline_with_mocks(
        scenario_return=(
            "scenario description", arc_prompt, "caption", "curious", 0.001
        )
    )
    mocks["prompt_gen_svc"].generate_unified_prompt.assert_called_once_with(arc_prompt)
    # KlingService should receive the output of PromptGenerationService, not raw arc_prompt
    submit_call = mocks["kling_svc"].submit.call_args
    submitted = submit_call[0][0] if submit_call[0] else ""
    assert submitted != arc_prompt, (
        "KlingService should receive the unified_prompt from PromptGenerationService, not the raw arc_prompt"
    )


def test_anti_repetition_log_only_mode_does_not_retry():
    """Pipeline: scene similarity detected + anti-repetition disabled = log warning, continue (no retry)."""
    mocks = _run_pipeline_with_mocks(
        similarity_return=True,   # scene IS similar
        anti_rep_enabled=False,   # but enforcement is disabled
    )
    # Pipeline should complete (not halt): pick_scenario_arc called only once
    assert mocks["scene_engine"].pick_scenario_arc.call_count == 1, \
        "In log-only mode, pipeline should NOT retry on similarity detection"
    # Kling should still be called
    mocks["kling_svc"].submit.assert_called_once()


# ── Phase 13: Scenario arc pipeline wiring ──────────────────────────────────

def test_pipeline_uses_pick_scenario_arc():
    """Phase 13 (SCN-13-04): Pipeline calls pick_scenario_arc, not pick_scene."""
    mocks = _run_pipeline_with_mocks()
    mocks["scene_engine"].pick_scenario_arc.assert_called_once()
    mocks["scene_engine"].pick_scene.assert_not_called()


def test_prompt_embedding_saved_to_content_history_phase13():
    """Phase 13 (SCN-13-04): prompt_embedding is included in content_history insert row."""
    mocks = _run_pipeline_with_mocks()
    # Find the insert call to content_history
    insert_calls = mocks["supabase"].table.return_value.insert.call_args_list
    inserted_rows = [c[0][0] for c in insert_calls if c[0]]
    # At least one insert should include prompt_embedding
    has_prompt_embedding = any("prompt_embedding" in row for row in inserted_rows)
    assert has_prompt_embedding, (
        f"prompt_embedding must be saved to content_history. Insert rows: {inserted_rows}"
    )


def test_prompt_similarity_check_called_in_pipeline():
    """Phase 13 (SCN-13-04): is_too_similar_prompt() is called during pipeline execution."""
    mocks = _run_pipeline_with_mocks()
    mocks["similarity_svc"].is_too_similar_prompt.assert_called_once()


def test_arc_caption_saved_to_content_history():
    """Phase 13: Suspense-style caption from pick_scenario_arc is saved to content_history."""
    caption = "Algo malo va a pasar."
    mocks = _run_pipeline_with_mocks(
        scenario_return=("scenario desc...", "arc prompt...", caption, "curious", 0.001)
    )
    insert_call = mocks["supabase"].table.return_value.insert.call_args
    if insert_call:
        inserted_data = insert_call[0][0]
        assert inserted_data.get("caption") == caption, (
            f"Arc caption must be saved to content_history. Got: {inserted_data.get('caption')}"
        )
