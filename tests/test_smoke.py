"""
Phase 9 smoke test scaffolds.

These tests verify the structural integrity of Phase 9 components:
- Module imports succeed
- Key functions/constants are exported
- DB migration file exists and contains required keywords
- Settings fields are declared

These are NOT integration tests — they run without network calls or live DB.
Smoke tests gate the phase verification step before human review.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import pytest


class TestVID01KlingServiceSmoke:
    """VID-01: Kling AI 3.0 service structural verification."""

    def test_kling_service_importable(self):
        """KlingService can be imported from app.services.kling."""
        from app.services.kling import KlingService
        assert KlingService is not None

    def test_kling_service_has_submit_method(self):
        """KlingService has submit() method with correct signature."""
        from app.services.kling import KlingService
        import inspect
        sig = inspect.signature(KlingService.submit)
        assert "script_text" in sig.parameters

    def test_fal_key_in_settings(self):
        """Settings declares fal_key field."""
        from app.settings import Settings
        assert "fal_key" in Settings.model_fields

    def test_kling_model_version_in_settings(self):
        """Settings declares kling_model_version field with default."""
        from app.settings import Settings
        field = Settings.model_fields.get("kling_model_version")
        assert field is not None
        assert "kling" in str(field.default).lower()

    def test_migration_0008_exists(self):
        """Migration 0008 file exists."""
        migration_path = os.path.join(
            os.path.dirname(__file__), '..', 'migrations', '0008_v2_schema.sql'
        )
        assert os.path.exists(migration_path), "migrations/0008_v2_schema.sql not found"

    def test_migration_0008_has_kling_job_id(self):
        """Migration 0008 adds kling_job_id column."""
        migration_path = os.path.join(
            os.path.dirname(__file__), '..', 'migrations', '0008_v2_schema.sql'
        )
        content = open(migration_path).read()
        assert "kling_job_id" in content


class TestVID02CharacterBibleSmoke:
    """VID-02: Character Bible structural verification."""

    def test_character_bible_constant_exists(self):
        """CHARACTER_BIBLE constant exported from kling.py."""
        from app.services.kling import CHARACTER_BIBLE
        assert CHARACTER_BIBLE is not None
        assert isinstance(CHARACTER_BIBLE, str)

    def test_character_bible_word_count(self):
        """CHARACTER_BIBLE is 40-50 words."""
        from app.services.kling import CHARACTER_BIBLE
        word_count = len(CHARACTER_BIBLE.split())
        assert 40 <= word_count <= 50, (
            f"CHARACTER_BIBLE has {word_count} words — must be 40-50"
        )

    def test_character_bible_contains_grey_kitten(self):
        """CHARACTER_BIBLE describes a grey kitten (v3.0 character refresh)."""
        from app.services.kling import CHARACTER_BIBLE
        lower = CHARACTER_BIBLE.lower()
        assert "grey kitten" in lower or "gray kitten" in lower, (
            "CHARACTER_BIBLE must describe 'grey kitten' or 'gray kitten' (v3.0 character refresh)"
        )

    def test_character_bible_contains_blue_eyes(self):
        """CHARACTER_BIBLE references the grey kitten's blue eyes (key visual hook)."""
        from app.services.kling import CHARACTER_BIBLE
        lower = CHARACTER_BIBLE.lower()
        assert "blue eyes" in lower, (
            "CHARACTER_BIBLE must reference 'blue eyes' — key visual hook for v3.0 grey kitten"
        )


class TestVID03CircuitBreakerSmoke:
    """VID-03: Kling circuit breaker structural verification."""

    def test_kling_cb_importable(self):
        """KlingCircuitBreakerService can be imported."""
        from app.services.kling_circuit_breaker import KlingCircuitBreakerService
        assert KlingCircuitBreakerService is not None

    def test_kling_cb_threshold_constant(self):
        """FAILURE_THRESHOLD is 0.20 (20%)."""
        from app.services.kling_circuit_breaker import FAILURE_THRESHOLD
        assert FAILURE_THRESHOLD == 0.20, (
            f"Threshold must be 0.20 (20%), got {FAILURE_THRESHOLD}"
        )

    def test_kling_cb_balance_constants(self):
        """Balance thresholds: alert=$5, halt=$1."""
        from app.services.kling_circuit_breaker import BALANCE_ALERT_USD, BALANCE_HALT_USD
        assert BALANCE_ALERT_USD == 5.0
        assert BALANCE_HALT_USD == 1.0

    def test_kling_cb_separate_from_heygen_cb(self):
        """Kling CB uses kling_circuit_breaker_state table (not circuit_breaker_state)."""
        from app.services.kling_circuit_breaker import TABLE
        assert TABLE == "kling_circuit_breaker_state", (
            f"CB must use separate table, got: {TABLE}"
        )

    def test_migration_has_kling_cb_table(self):
        """Migration 0008 creates kling_circuit_breaker_state table."""
        migration_path = os.path.join(
            os.path.dirname(__file__), '..', 'migrations', '0008_v2_schema.sql'
        )
        content = open(migration_path).read()
        assert "kling_circuit_breaker_state" in content


class TestVID04AILabelsSmoke:
    """VID-04: AI content label structural verification."""

    def test_apply_ai_label_importable(self):
        """_apply_ai_label and AI_LABEL exported from platform_publish."""
        from app.scheduler.jobs.platform_publish import _apply_ai_label, AI_LABEL
        assert _apply_ai_label is not None
        assert AI_LABEL == "🤖 Creado con IA"

    def test_ai_label_applied_to_all_platforms(self):
        """All three compliance platforms receive the label."""
        from app.scheduler.jobs.platform_publish import _apply_ai_label, AI_LABEL
        for platform in ("tiktok", "youtube", "instagram"):
            result = _apply_ai_label("Test caption", platform)
            assert AI_LABEL in result, (
                f"AI label missing for platform={platform}: {result!r}"
            )
