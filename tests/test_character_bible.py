"""
TDD RED: Character Bible validation tests.
Phase 09-02 Task 1
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


def test_character_bible_is_str():
    """CHARACTER_BIBLE must be a plain Python str constant."""
    from app.services.kling import CHARACTER_BIBLE
    assert isinstance(CHARACTER_BIBLE, str), "CHARACTER_BIBLE must be a str"


def test_character_bible_word_count():
    """CHARACTER_BIBLE must be 40–50 words."""
    from app.services.kling import CHARACTER_BIBLE
    words = len(CHARACTER_BIBLE.split())
    assert 40 <= words <= 50, (
        f"CHARACTER_BIBLE word count is {words} — must be between 40 and 50. "
        f"Content: {CHARACTER_BIBLE!r}"
    )


def test_character_bible_not_empty():
    """CHARACTER_BIBLE must not be empty or whitespace."""
    from app.services.kling import CHARACTER_BIBLE
    assert CHARACTER_BIBLE.strip(), "CHARACTER_BIBLE must not be empty"


def test_character_bible_mentions_grey_kitten():
    """CHARACTER_BIBLE must reference the v3.0 grey kitten character identity."""
    from app.services.kling import CHARACTER_BIBLE
    lower = CHARACTER_BIBLE.lower()
    assert "grey" in lower or "gray" in lower, (
        "CHARACTER_BIBLE must mention 'grey' or 'gray' for v3.0 grey kitten visual identity"
    )


def test_character_bible_mentions_key_visual_hooks():
    """CHARACTER_BIBLE must describe the grey kitten's key visual features: blue eyes, pink tongue."""
    from app.services.kling import CHARACTER_BIBLE
    lower = CHARACTER_BIBLE.lower()
    has_eyes = "blue" in lower
    has_tongue = "tongue" in lower or "pink" in lower
    assert has_eyes and has_tongue, (
        f"CHARACTER_BIBLE must mention blue eyes and pink tongue/pink for grey kitten identity. Content: {CHARACTER_BIBLE!r}"
    )
