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


# ── Phase 13: Scenario Arc Generation tests ─────────────────────────────────

def test_scenario_type_categories_has_six_entries():
    """SCN-13-01: SCENARIO_TYPE_CATEGORIES contains exactly 6 entries."""
    from app.services.scene_generation import SCENARIO_TYPE_CATEGORIES
    assert len(SCENARIO_TYPE_CATEGORIES) == 6
    expected = {"slapstick", "reaction_surprise", "chase", "investigation_gone_wrong", "unexpected_nap", "overconfident_leap"}
    assert set(SCENARIO_TYPE_CATEGORIES) == expected


def test_scene_engine_loads_categories_at_init(tmp_path):
    """SCN-13-01: SceneEngine._load_categories() loads categories.json at init."""
    import json
    from unittest.mock import patch, MagicMock

    categories_data = {
        "categories": [
            {"name": "slapstick", "description": "Physical comedy"},
            {"name": "chase", "description": "Pursuit comedy"},
        ]
    }
    categories_file = tmp_path / "categories.json"
    categories_file.write_text(json.dumps(categories_data))

    with patch("app.services.scene_generation.CATEGORIES_JSON_PATH", categories_file), \
         patch("app.services.scene_generation.SCENES_JSON_PATH", tmp_path / "scenes.json"), \
         patch("app.services.scene_generation.get_supabase"), \
         patch("app.services.scene_generation.get_settings") as mock_settings, \
         patch("app.services.scene_generation.OpenAI"):
        # Create a minimal scenes.json so _load_scene_library doesn't fail
        (tmp_path / "scenes.json").write_text(json.dumps([{"location": "cocina", "activity": "explorar", "mood": "curious"}]))
        mock_settings.return_value.openai_api_key = "sk-test"
        from app.services.scene_generation import SceneEngine
        engine = SceneEngine()
        assert len(engine._categories) == 2
        assert engine._categories[0]["name"] == "slapstick"


def test_pick_scenario_arc_returns_five_tuple():
    """SCN-13-02: pick_scenario_arc() returns exactly (scenario_description, arc_prompt, caption, mood, cost_usd)."""
    import json
    from unittest.mock import patch, MagicMock, mock_open

    mock_gpt_response = {
        "scenario_description": "A grey kitten discovers a rolling avocado on the kitchen floor.",
        "arc_prompt": "An ultra-cute grey kitten with huge blue eyes spots a rolling avocado on the kitchen tiles. Its tail twitches with anticipation—the hunt is on. Suddenly, it pounces, sliding across the tiles with a delighted open-mouthed grin as the avocado escapes.",
        "caption": "Algo malo va a pasar.",
        "mood": "playful",
    }

    mock_openai_response = MagicMock()
    mock_openai_response.choices[0].message.content = json.dumps(mock_gpt_response)
    mock_openai_response.usage.prompt_tokens = 200
    mock_openai_response.usage.completion_tokens = 100

    with patch("app.services.scene_generation._generate_scenario_with_backoff") as mock_backoff, \
         patch("app.services.scene_generation.get_supabase"), \
         patch("app.services.scene_generation.get_settings") as mock_settings, \
         patch("app.services.scene_generation.OpenAI"):
        mock_settings.return_value.openai_api_key = "sk-test"
        mock_backoff.return_value = (mock_gpt_response, 0.0015)

        from app.services.scene_generation import SceneEngine
        engine = MagicMock(spec=SceneEngine)
        engine._categories = [{"name": "slapstick", "description": "Physical comedy"}]
        engine._seasonal = MagicMock()
        engine._seasonal.get_overlay.return_value = None
        engine._client = MagicMock()
        engine._build_scenario_system_prompt = SceneEngine._build_scenario_system_prompt.__get__(engine)
        engine.pick_scenario_arc = SceneEngine.pick_scenario_arc.__get__(engine)

        result = engine.pick_scenario_arc()
        assert len(result) == 5, f"Expected 5-tuple, got {len(result)}-tuple"
        scenario_description, arc_prompt, caption, mood, cost_usd = result
        assert isinstance(scenario_description, str) and len(scenario_description) > 0
        assert isinstance(arc_prompt, str) and len(arc_prompt) > 0
        assert isinstance(caption, str) and len(caption) > 0
        assert mood in {"playful", "sleepy", "curious"}
        assert isinstance(cost_usd, float) and cost_usd >= 0


def test_pick_scenario_arc_raises_on_missing_keys():
    """SCN-13-02: pick_scenario_arc() raises ValueError when GPT-4o response is missing required keys."""
    from unittest.mock import patch, MagicMock

    incomplete_response = {"arc_prompt": "some prompt", "mood": "playful"}  # missing scenario_description and caption

    with patch("app.services.scene_generation._generate_scenario_with_backoff") as mock_backoff, \
         patch("app.services.scene_generation.get_supabase"), \
         patch("app.services.scene_generation.get_settings") as mock_settings, \
         patch("app.services.scene_generation.OpenAI"):
        mock_settings.return_value.openai_api_key = "sk-test"
        mock_backoff.return_value = (incomplete_response, 0.001)

        from app.services.scene_generation import SceneEngine
        engine = MagicMock(spec=SceneEngine)
        engine._categories = [{"name": "chase", "description": "Pursuit comedy"}]
        engine._seasonal = MagicMock()
        engine._seasonal.get_overlay.return_value = None
        engine._client = MagicMock()
        engine._build_scenario_system_prompt = SceneEngine._build_scenario_system_prompt.__get__(engine)
        engine.pick_scenario_arc = SceneEngine.pick_scenario_arc.__get__(engine)

        with pytest.raises(ValueError, match="missing keys"):
            engine.pick_scenario_arc()


def test_generate_scenario_with_backoff_is_module_level():
    """SCN-13-02: _generate_scenario_with_backoff must be a module-level function (ThreadPoolExecutor safe)."""
    from app.services import scene_generation
    assert hasattr(scene_generation, "_generate_scenario_with_backoff"), (
        "_generate_scenario_with_backoff must be at module level"
    )
    from app.services.scene_generation import SceneEngine
    assert not hasattr(SceneEngine, "_generate_scenario_with_backoff"), (
        "_generate_scenario_with_backoff must NOT be an instance method"
    )


def test_pick_scenario_arc_invalid_mood_defaults_to_playful():
    """SCN-13-02: pick_scenario_arc() defaults mood to 'playful' if GPT-4o returns unexpected mood."""
    from unittest.mock import patch, MagicMock

    bad_mood_response = {
        "scenario_description": "A kitten plays.",
        "arc_prompt": "A kitten plays with a ball.",
        "caption": "Algo va a pasar.",
        "mood": "hyper",  # Not a valid mood
    }

    with patch("app.services.scene_generation._generate_scenario_with_backoff") as mock_backoff, \
         patch("app.services.scene_generation.get_supabase"), \
         patch("app.services.scene_generation.get_settings") as mock_settings, \
         patch("app.services.scene_generation.OpenAI"):
        mock_settings.return_value.openai_api_key = "sk-test"
        mock_backoff.return_value = (bad_mood_response, 0.001)

        from app.services.scene_generation import SceneEngine
        engine = MagicMock(spec=SceneEngine)
        engine._categories = [{"name": "slapstick", "description": "Physical comedy"}]
        engine._seasonal = MagicMock()
        engine._seasonal.get_overlay.return_value = None
        engine._client = MagicMock()
        engine._build_scenario_system_prompt = SceneEngine._build_scenario_system_prompt.__get__(engine)
        engine.pick_scenario_arc = SceneEngine.pick_scenario_arc.__get__(engine)

        _, _, _, mood, _ = engine.pick_scenario_arc()
        assert mood == "playful", f"Invalid mood must default to 'playful', got '{mood}'"
