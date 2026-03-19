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


def test_character_bible_mentions_orange_tabby():
    """CHARACTER_BIBLE must reference the orange tabby cat identity."""
    from app.services.kling import CHARACTER_BIBLE
    lower = CHARACTER_BIBLE.lower()
    assert "orange" in lower or "tabby" in lower, (
        "CHARACTER_BIBLE must mention 'orange' or 'tabby' for visual identity"
    )


def test_character_bible_mentions_mexican_setting():
    """CHARACTER_BIBLE must contain Mexican cultural markers."""
    from app.services.kling import CHARACTER_BIBLE
    lower = CHARACTER_BIBLE.lower()
    has_setting = any(kw in lower for kw in ["mexican", "mexico", "serape", "pottery", "adobe"])
    assert has_setting, "CHARACTER_BIBLE must reference Mexican setting/culture"
