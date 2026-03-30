"""Tests for SCN-03 (anti-repetition) and SCN-04 (rejection feedback)."""
import pytest
from unittest.mock import MagicMock, patch, call
from datetime import datetime, timedelta, timezone


# ── SCN-03: Scene similarity check ──────────────────────────────────────────

def test_is_too_similar_scene_returns_true_when_rows_found(mock_supabase):
    """SCN-03: Returns True when check_scene_similarity finds matching scenes."""
    from app.services.similarity import SimilarityService
    mock_supabase.rpc.return_value.execute.return_value.data = [
        {"id": "uuid-1", "scene_prompt": "Mochi en cocina...", "similarity": 0.82}
    ]
    svc = SimilarityService(supabase=mock_supabase)
    result = svc.is_too_similar_scene(embedding=[0.1] * 1536)
    assert result is True
    mock_supabase.rpc.assert_called_once_with(
        "check_scene_similarity",
        {"query_embedding": [0.1] * 1536, "similarity_threshold": 0.78, "lookback_days": 7},
    )

def test_is_too_similar_scene_returns_false_when_no_rows(mock_supabase):
    """SCN-03: Returns False (unique scene) when no matching scenes found."""
    from app.services.similarity import SimilarityService
    mock_supabase.rpc.return_value.execute.return_value.data = []
    svc = SimilarityService(supabase=mock_supabase)
    result = svc.is_too_similar_scene(embedding=[0.5] * 1536)
    assert result is False

def test_is_too_similar_scene_fails_open_on_exception(mock_supabase):
    """SCN-03: Returns False (fail open) when DB raises exception."""
    from app.services.similarity import SimilarityService
    mock_supabase.rpc.side_effect = Exception("DB connection error")
    svc = SimilarityService(supabase=mock_supabase)
    result = svc.is_too_similar_scene(embedding=[0.1] * 1536)
    assert result is False  # fail open: allow generation if check fails

def test_is_too_similar_scene_uses_7_day_lookback(mock_supabase):
    """SCN-03: is_too_similar_scene uses 7-day lookback (not 90-day like scripts)."""
    from app.services.similarity import SimilarityService, SCENE_LOOKBACK_DAYS
    assert SCENE_LOOKBACK_DAYS == 7  # must be recalibrated value, not inherited 90

def test_scene_similarity_threshold_is_recalibrated(mock_supabase):
    """SCN-03: SCENE_SIMILARITY_THRESHOLD is 0.78, not v1.0's 0.85."""
    from app.services.similarity import SCENE_SIMILARITY_THRESHOLD
    assert SCENE_SIMILARITY_THRESHOLD == 0.78
    # Must be in 75-80% range, not inherited v1.0 value
    assert 0.75 <= SCENE_SIMILARITY_THRESHOLD <= 0.80

def test_is_too_similar_scene_respects_custom_threshold(mock_supabase):
    """SCN-03: custom threshold passed through to RPC call."""
    from app.services.similarity import SimilarityService
    mock_supabase.rpc.return_value.execute.return_value.data = []
    svc = SimilarityService(supabase=mock_supabase)
    svc.is_too_similar_scene(embedding=[0.1] * 1536, threshold=0.75)
    call_args = mock_supabase.rpc.call_args
    assert call_args[0][1]["similarity_threshold"] == 0.75


# ── SCN-04: Rejection feedback storage ──────────────────────────────────────

def test_store_scene_rejection_inserts_with_correct_fields(mock_supabase):
    """SCN-04: store_scene_rejection inserts scene combo with pattern_type='scene'."""
    from unittest.mock import patch
    with patch("app.services.scene_generation.get_supabase", return_value=mock_supabase), \
         patch("app.services.scene_generation.get_settings") as mock_settings, \
         patch("app.services.scene_generation.OpenAI"), \
         patch("builtins.open") as mock_open:
        import json
        mock_settings.return_value.openai_api_key = "test-key"
        mock_open.return_value.__enter__ = lambda s: s
        mock_open.return_value.__exit__ = MagicMock(return_value=False)
        mock_open.return_value.read.return_value = json.dumps([
            {"location": "cocina", "activity": "inspeccionar", "mood": "curious", "weight": 1.0}
        ])
        from app.services.scene_generation import SceneEngine
        engine = SceneEngine.__new__(SceneEngine)
        engine._supabase = mock_supabase
        engine.store_scene_rejection(
            scene_combo={"location": "cocina", "activity": "inspeccionar olla"},
            reason_text="visual_error"
        )

    insert_call = mock_supabase.table.return_value.insert.call_args
    inserted_data = insert_call[0][0]
    assert inserted_data["pattern_type"] == "scene"
    assert inserted_data["scene_combo"] == {"location": "cocina", "activity": "inspeccionar olla"}
    assert inserted_data["reason_text"] == "visual_error"
    assert "expires_at" in inserted_data

def test_store_scene_rejection_expires_in_7_days(mock_supabase):
    """SCN-04: rejection expires_at is approximately 7 days from now."""
    from unittest.mock import patch
    from datetime import datetime, timezone
    import json
    with patch("app.services.scene_generation.get_supabase", return_value=mock_supabase), \
         patch("app.services.scene_generation.get_settings") as mock_settings, \
         patch("app.services.scene_generation.OpenAI"), \
         patch("builtins.open") as mock_open:
        mock_settings.return_value.openai_api_key = "test-key"
        mock_open.return_value.__enter__ = lambda s: s
        mock_open.return_value.__exit__ = MagicMock(return_value=False)
        mock_open.return_value.read.return_value = json.dumps([
            {"location": "cocina", "activity": "inspeccionar", "mood": "curious", "weight": 1.0}
        ])
        from app.services.scene_generation import SceneEngine
        engine = SceneEngine.__new__(SceneEngine)
        engine._supabase = mock_supabase
        before = datetime.now(timezone.utc)
        engine.store_scene_rejection({"location": "cocina", "activity": "x"}, "test")
        after = datetime.now(timezone.utc)

    insert_call = mock_supabase.table.return_value.insert.call_args
    expires_at_str = insert_call[0][0]["expires_at"]
    expires_at = datetime.fromisoformat(expires_at_str)
    expected_min = before + timedelta(days=6, hours=23)
    expected_max = after + timedelta(days=7, hours=1)
    assert expected_min <= expires_at <= expected_max

def test_load_active_scene_rejections_filters_by_pattern_type(mock_supabase):
    """SCN-04: load_active_scene_rejections only loads pattern_type='scene'."""
    from unittest.mock import patch
    import json
    mock_supabase.table.return_value.select.return_value.eq.return_value.gt.return_value.execute.return_value.data = [
        {"scene_combo": {"location": "cocina", "activity": "inspeccionar"}, "reason_text": "visual_error"}
    ]
    with patch("app.services.scene_generation.get_supabase", return_value=mock_supabase), \
         patch("app.services.scene_generation.get_settings") as mock_settings, \
         patch("app.services.scene_generation.OpenAI"), \
         patch("builtins.open") as mock_open:
        mock_settings.return_value.openai_api_key = "test-key"
        mock_open.return_value.__enter__ = lambda s: s
        mock_open.return_value.__exit__ = MagicMock(return_value=False)
        mock_open.return_value.read.return_value = json.dumps([
            {"location": "cocina", "activity": "inspeccionar", "mood": "curious", "weight": 1.0}
        ])
        from app.services.scene_generation import SceneEngine
        engine = SceneEngine.__new__(SceneEngine)
        engine._supabase = mock_supabase
        results = engine.load_active_scene_rejections()

    # Verify the query chain used pattern_type='scene' filter
    eq_call = mock_supabase.table.return_value.select.return_value.eq.call_args
    assert eq_call[0] == ("pattern_type", "scene")


# ── Phase 13: Prompt similarity check ───────────────────────────────────────

def test_is_too_similar_prompt_returns_true_when_rows_found(mock_supabase):
    """SCN-13-05: Returns True when check_prompt_similarity finds matching prompts."""
    from app.services.similarity import SimilarityService
    mock_supabase.rpc.return_value.execute.return_value.data = [
        {"id": "uuid-1", "scene_prompt": "A grey kitten...", "similarity": 0.82}
    ]
    svc = SimilarityService(supabase=mock_supabase)
    result = svc.is_too_similar_prompt(embedding=[0.1] * 1536)
    assert result is True
    mock_supabase.rpc.assert_called_once_with(
        "check_prompt_similarity",
        {"query_embedding": [0.1] * 1536, "similarity_threshold": 0.78, "lookback_days": 7},
    )


def test_is_too_similar_prompt_returns_false_when_no_rows(mock_supabase):
    """SCN-13-05: Returns False (unique prompt) when no matching prompts found."""
    from app.services.similarity import SimilarityService
    mock_supabase.rpc.return_value.execute.return_value.data = []
    svc = SimilarityService(supabase=mock_supabase)
    result = svc.is_too_similar_prompt(embedding=[0.5] * 1536)
    assert result is False


def test_is_too_similar_prompt_fails_open_on_exception(mock_supabase):
    """SCN-13-05: Returns False (fail open) when DB raises exception."""
    from app.services.similarity import SimilarityService
    mock_supabase.rpc.side_effect = Exception("DB connection error")
    svc = SimilarityService(supabase=mock_supabase)
    result = svc.is_too_similar_prompt(embedding=[0.1] * 1536)
    assert result is False


def test_prompt_similarity_threshold_is_0_78():
    """SCN-13-05: PROMPT_SIMILARITY_THRESHOLD is 0.78 (matches scene similarity threshold)."""
    from app.services.similarity import PROMPT_SIMILARITY_THRESHOLD
    assert PROMPT_SIMILARITY_THRESHOLD == 0.78


def test_prompt_similarity_lookback_is_7_days():
    """SCN-13-05: PROMPT_LOOKBACK_DAYS is 7 (matches scene lookback window)."""
    from app.services.similarity import PROMPT_LOOKBACK_DAYS
    assert PROMPT_LOOKBACK_DAYS == 7
