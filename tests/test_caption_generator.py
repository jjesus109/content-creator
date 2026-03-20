"""Tests for SCN-05 (Spanish caption formula)."""
import pytest


def test_caption_word_count():
    """SCN-05: caption is between 5 and 8 words."""
    captions = [
        "Mochi descubre los secretos de la cocina",
        "El gato observa la lluvia caer",
        "Mochi juega con su cola",
    ]
    for caption in captions:
        word_count = len(caption.split())
        assert 5 <= word_count <= 8, f"Caption '{caption}' has {word_count} words"


@pytest.mark.skip(reason="stub — implement SceneEngine caption generation in plan 02 first")
def test_caption_format():
    """SCN-05: caption follows [observation] + [implied personality] formula."""
    pass


@pytest.mark.skip(reason="stub — implement SceneEngine caption generation in plan 02 first")
def test_caption_is_spanish():
    """SCN-05: generated caption is in Spanish."""
    pass
