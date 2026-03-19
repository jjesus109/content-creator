"""
Unit tests for AI content label injection in platform_publish.py.

Covers VID-04: "AI content label applied on all platforms before video is published."
Label: "🤖 Creado con IA" (unicode — exact string, not escaped)
Applied in: _apply_ai_label(post_text, platform) in platform_publish.py

Platforms tested: tiktok, instagram, facebook, youtube
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import pytest
from app.scheduler.jobs.platform_publish import _apply_ai_label, AI_LABEL


class TestApplyAiLabel:
    """Tests for _apply_ai_label(post_text, platform)."""

    # --- TikTok ---

    def test_tiktok_label_prepend(self):
        """TikTok: AI label prepended as first line."""
        result = _apply_ai_label("Mochi duerme en el sol", "tiktok")
        assert result.startswith(AI_LABEL + "\n"), (
            f"Expected label prefix, got: {result!r}"
        )
        assert "Mochi duerme en el sol" in result

    def test_tiktok_empty_post_copy(self):
        """TikTok: empty post_copy returns label only."""
        result = _apply_ai_label("", "tiktok")
        assert result == AI_LABEL

    def test_tiktok_label_exact_string(self):
        """TikTok: label is exactly '🤖 Creado con IA' (not 'AI Generated' or other)."""
        result = _apply_ai_label("Test", "tiktok")
        assert result.startswith("🤖 Creado con IA"), (
            f"Expected '🤖 Creado con IA' prefix, got: {result!r}"
        )

    # --- Instagram ---

    def test_instagram_label_prepend(self):
        """Instagram: AI label prepended to caption."""
        result = _apply_ai_label("Mochi explora la cocina", "instagram")
        assert result.startswith(AI_LABEL + "\n")
        assert "Mochi explora la cocina" in result

    def test_instagram_empty_post_copy(self):
        """Instagram: empty post_copy returns label only."""
        assert _apply_ai_label("", "instagram") == AI_LABEL

    # --- Facebook ---

    def test_facebook_label_prepend(self):
        """Facebook: AI label prepended to caption."""
        result = _apply_ai_label("Mochi mira la ventana", "facebook")
        assert result.startswith(AI_LABEL + "\n")

    # --- YouTube ---

    def test_youtube_label_in_description_not_title(self):
        """YouTube: label in description; title (line 0) is unchanged."""
        post_copy = "Mi titulo del video\nEsta es la descripcion del video."
        result = _apply_ai_label(post_copy, "youtube")

        lines = result.split("\n")
        assert lines[0] == "Mi titulo del video", (
            f"Title line should be unchanged, got: {lines[0]!r}"
        )
        assert AI_LABEL in result, "Label must appear somewhere in result"
        # Label must NOT be in the title line
        assert not lines[0].startswith("🤖"), (
            f"Title must not start with label, got: {lines[0]!r}"
        )

    def test_youtube_label_not_in_title_string(self):
        """YouTube: title (line 0) must not contain any part of the label."""
        post_copy = "El gato curioso\nVe a Mochi explorar."
        result = _apply_ai_label(post_copy, "youtube")
        title_line = result.split("\n", 1)[0]
        assert "🤖" not in title_line, (
            f"Emoji must not appear in title line, got: {title_line!r}"
        )

    def test_youtube_no_description(self):
        """YouTube: single-line post_copy (no description) — label becomes the description."""
        result = _apply_ai_label("Solo el titulo", "youtube")
        assert result.startswith("Solo el titulo\n"), (
            f"Title should be first, got: {result!r}"
        )
        assert AI_LABEL in result

    def test_youtube_empty_post_copy(self):
        """YouTube: empty post_copy — graceful handling."""
        result = _apply_ai_label("", "youtube")
        # Should not crash; label should appear
        assert AI_LABEL in result or result == AI_LABEL or result == "\n" + AI_LABEL

    # --- Cross-platform consistency ---

    def test_label_string_is_consistent_across_platforms(self):
        """All platforms use the same AI_LABEL constant value."""
        for platform in ("tiktok", "instagram", "facebook"):
            result = _apply_ai_label("Test", platform)
            assert AI_LABEL in result, f"Label missing for platform={platform}"

    def test_label_constant_is_unicode_robot_emoji(self):
        """AI_LABEL module constant contains the robot emoji and Spanish text."""
        assert AI_LABEL == "🤖 Creado con IA", (
            f"Label constant changed: {AI_LABEL!r}"
        )
