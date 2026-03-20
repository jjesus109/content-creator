"""Tests for SCN-03 (anti-repetition) and SCN-04 (rejection feedback)."""
import pytest


@pytest.mark.skip(reason="stub — implement SimilarityService.is_too_similar_scene() in plan 03 first")
def test_check_scene_similarity():
    """SCN-03: scene >threshold% similar to past 7 days is blocked."""
    pass


@pytest.mark.skip(reason="stub — implement SimilarityService.is_too_similar_scene() in plan 03 first")
def test_below_threshold_passes():
    """SCN-03: scene below threshold is allowed."""
    pass


@pytest.mark.skip(reason="stub — implement SceneEngine rejection methods in plan 03 first")
def test_rejection_feedback():
    """SCN-04: rejected scene combo stored with 7-day expiry."""
    pass


@pytest.mark.skip(reason="stub — implement SceneEngine rejection methods in plan 03 first")
def test_load_active_scene_rejections():
    """SCN-04: active scene rejections loaded and injected as negative context."""
    pass
