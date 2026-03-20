"""Tests for SCN-01 (scene selection) and SCN-05 (Spanish caption)."""
import pytest


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


@pytest.mark.skip(reason="stub — implement SceneEngine in plan 02 first")
def test_pick_scene():
    """SCN-01: SceneEngine.pick_scene() returns (scene_prompt, caption, mood, cost)."""
    pass


@pytest.mark.skip(reason="stub — implement SceneEngine in plan 02 first")
def test_gpt4o_selection():
    """SCN-01: GPT-4o receives scene combo from library and returns structured JSON."""
    pass
