"""Integration stubs for pipeline wiring (MUS-03, SCN-01 through SCN-05 end-to-end)."""
import pytest


@pytest.mark.skip(reason="stub — implement pipeline wiring in plan 05 first")
def test_scene_engine_replaces_script_generation():
    """Pipeline: SceneEngine.pick_scene() called instead of generate_topic_summary."""
    pass


@pytest.mark.skip(reason="stub — implement pipeline wiring in plan 05 first")
def test_music_matcher_called_after_scene():
    """Pipeline: MusicMatcher.pick_track(mood) called with scene mood."""
    pass


@pytest.mark.skip(reason="stub — implement pipeline wiring in plan 05 first")
def test_caption_saved_to_content_history():
    """Pipeline: caption stored on content_history row after scene generation."""
    pass
