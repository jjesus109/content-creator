"""
TDD RED: Grey Kitten CHARACTER_BIBLE validation tests.
Phase 12-01 Task 1

Tests that CHARACTER_BIBLE describes the new grey kitten (not orange tabby Mochi).
Written before implementation — must FAIL against existing orange tabby constant.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


def test_character_bible_grey_kitten():
    """CHARACTER_BIBLE must describe a grey kitten."""
    from app.services.kling import CHARACTER_BIBLE
    assert "grey kitten" in CHARACTER_BIBLE.lower(), (
        f"CHARACTER_BIBLE must contain 'grey kitten', got: {CHARACTER_BIBLE!r}"
    )


def test_character_bible_blue_eyes():
    """CHARACTER_BIBLE must mention blue eyes."""
    from app.services.kling import CHARACTER_BIBLE
    assert "blue eyes" in CHARACTER_BIBLE.lower(), (
        f"CHARACTER_BIBLE must contain 'blue eyes', got: {CHARACTER_BIBLE!r}"
    )


def test_character_bible_pink_tongue():
    """CHARACTER_BIBLE must mention pink tongue."""
    from app.services.kling import CHARACTER_BIBLE
    assert "pink tongue" in CHARACTER_BIBLE.lower(), (
        f"CHARACTER_BIBLE must contain 'pink tongue', got: {CHARACTER_BIBLE!r}"
    )


def test_character_bible_word_count_grey():
    """CHARACTER_BIBLE must be 40-50 words (retained from Phase 09-02)."""
    from app.services.kling import CHARACTER_BIBLE
    words = len(CHARACTER_BIBLE.split())
    assert 40 <= words <= 50, (
        f"CHARACTER_BIBLE word count is {words} — must be between 40 and 50. "
        f"Content: {CHARACTER_BIBLE!r}"
    )


def test_character_bible_no_orange_tabby():
    """CHARACTER_BIBLE must NOT reference orange tabby identity."""
    from app.services.kling import CHARACTER_BIBLE
    lower = CHARACTER_BIBLE.lower()
    assert "orange" not in lower, "CHARACTER_BIBLE must not contain 'orange'"
    assert "tabby" not in lower, "CHARACTER_BIBLE must not contain 'tabby'"


def test_character_bible_no_mochi():
    """CHARACTER_BIBLE must NOT use the name Mochi."""
    from app.services.kling import CHARACTER_BIBLE
    assert "mochi" not in CHARACTER_BIBLE.lower(), (
        "CHARACTER_BIBLE must not contain 'Mochi' — character is unnamed"
    )


def test_character_bible_no_mexican_household():
    """CHARACTER_BIBLE must NOT reference Mexican household setting."""
    from app.services.kling import CHARACTER_BIBLE
    lower = CHARACTER_BIBLE.lower()
    assert "mexican" not in lower, "CHARACTER_BIBLE must not contain 'mexican'"
