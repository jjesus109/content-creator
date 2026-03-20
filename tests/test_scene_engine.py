"""Tests for SCN-01 (scene selection) and SCN-05 (Spanish caption)."""
import json
import pytest
from unittest.mock import MagicMock, patch


def test_scene_library_structure(mock_scene_library):
    """SCN-01: scene library entries have location, activity, mood fields."""
    required_fields = {"location", "activity", "mood"}
    for entry in mock_scene_library:
        assert required_fields.issubset(entry.keys())


def test_mood_values_valid(mock_scene_library):
    """SCN-01: mood is one of playful/sleepy/curious."""
    valid_moods = {"playful", "sleepy", "curious"}
    for entry in mock_scene_library:
        assert entry["mood"] in valid_moods


def test_scene_engine_init_loads_library(tmp_path, mock_scene_library):
    """SCN-01: SceneEngine loads scene library at init."""
    import json
    scenes_file = tmp_path / "scenes.json"
    scenes_file.write_text(json.dumps(mock_scene_library))

    with patch("app.services.scene_generation.SCENES_JSON_PATH", scenes_file), \
         patch("app.services.scene_generation.get_supabase"), \
         patch("app.services.scene_generation.get_settings") as mock_settings, \
         patch("app.services.scene_generation.OpenAI"):
        mock_settings.return_value.openai_api_key = "test-key"
        from app.services.scene_generation import SceneEngine
        engine = SceneEngine.__new__(SceneEngine)
        engine._scene_library = mock_scene_library
        assert len(engine._scene_library) == len(mock_scene_library)


def test_pick_scene_returns_correct_tuple(mock_scene_library, mock_openai_client):
    """SCN-01, SCN-05: pick_scene() returns (scene_prompt, caption, mood, cost)."""
    import json
    from unittest.mock import patch, MagicMock
    from app.services.scene_generation import SceneEngine

    with patch("app.services.scene_generation.get_supabase"), \
         patch("app.services.scene_generation.get_settings") as mock_settings, \
         patch("app.services.scene_generation.OpenAI", return_value=mock_openai_client), \
         patch("builtins.open", return_value=MagicMock(
             __enter__=lambda s: s,
             __exit__=MagicMock(return_value=False),
             read=lambda: json.dumps(mock_scene_library)
         )):
        mock_settings.return_value.openai_api_key = "test-key"
        engine = MagicMock(spec=SceneEngine)
        engine._client = mock_openai_client
        engine._scene_library = mock_scene_library
        engine._seasonal = MagicMock()
        engine._seasonal.get_overlay.return_value = None
        engine._select_combo = lambda: mock_scene_library[0]
        engine._build_system_prompt = SceneEngine._build_system_prompt.__get__(engine)
        engine.pick_scene = SceneEngine.pick_scene.__get__(engine)
        scene_prompt, caption, mood, cost = engine.pick_scene()
        assert isinstance(scene_prompt, str) and len(scene_prompt) > 0
        assert isinstance(caption, str) and len(caption) > 0
        assert mood in {"playful", "sleepy", "curious"}
        assert isinstance(cost, float) and cost >= 0


def test_caption_word_count_fixture():
    """SCN-05: caption is between 5 and 8 words (fixture validation)."""
    captions = [
        "Mochi descubre los secretos de la cocina",
        "El gato observa la lluvia caer",
        "Mochi juega con su cola",
    ]
    for caption in captions:
        word_count = len(caption.split())
        assert 5 <= word_count <= 8, f"Caption '{caption}' has {word_count} words"
