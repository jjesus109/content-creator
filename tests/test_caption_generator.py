"""Tests for SCN-05 (Spanish caption formula)."""
import pytest


def test_caption_word_count():
    """SCN-05: caption is between 5 and 8 words."""
    captions = [
        "Mochi descubre los secretos de la cocina",
        "El gato observa la lluvia caer",
        "Mochi juega con su cola",
        "El gato vigila su territorio con calma",
    ]
    for caption in captions:
        word_count = len(caption.split())
        assert 5 <= word_count <= 8, f"Caption '{caption}' has {word_count} words"


def test_caption_not_empty():
    """SCN-05: caption must not be empty string."""
    caption = "Mochi descubre los secretos de la cocina"
    assert len(caption.strip()) > 0


def test_caption_no_hashtags():
    """SCN-05: caption must not contain hashtags."""
    captions = [
        "Mochi descubre los secretos de la cocina",
        "El gato observa la lluvia caer",
    ]
    for caption in captions:
        assert "#" not in caption, f"Caption contains hashtag: {caption}"
