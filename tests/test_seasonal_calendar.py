"""Tests for SCN-02 (seasonal calendar overlays)."""
from datetime import date
import pytest
from unittest.mock import patch
from app.services.scene_generation import SeasonalCalendarService


def test_independence_day_overlay():
    """SCN-02: Sep 16 returns Día de Independencia overlay (in English)."""
    svc = SeasonalCalendarService()
    overlay = svc.get_overlay(date(2026, 9, 16))
    assert overlay is not None
    assert "Independence" in overlay or "September" in overlay or "16" in overlay


def test_day_of_dead_overlay_nov1():
    """SCN-02: Nov 1 returns Día de Muertos overlay (in English)."""
    svc = SeasonalCalendarService()
    overlay = svc.get_overlay(date(2026, 11, 1))
    assert overlay is not None
    assert "Muertos" in overlay or "November" in overlay


def test_day_of_dead_overlay_nov2():
    """SCN-02: Nov 2 returns Día de Muertos overlay (in English)."""
    svc = SeasonalCalendarService()
    overlay = svc.get_overlay(date(2026, 11, 2))
    assert overlay is not None
    assert "Muertos" in overlay or "November" in overlay


def test_revolution_day_overlay():
    """SCN-02: Nov 20 returns Día de la Revolución overlay (in English)."""
    svc = SeasonalCalendarService()
    overlay = svc.get_overlay(date(2026, 11, 20))
    assert overlay is not None
    assert "Revolution" in overlay or "November" in overlay


def test_cat_day_overlay():
    """SCN-02: Aug 8 returns Día Internacional del Gato overlay (in English)."""
    svc = SeasonalCalendarService()
    overlay = svc.get_overlay(date(2026, 8, 8))
    assert overlay is not None
    assert "Cat" in overlay or "August" in overlay


def test_non_holiday_returns_none():
    """SCN-02: Non-holiday date returns None (no overlay)."""
    svc = SeasonalCalendarService()
    assert svc.get_overlay(date(2026, 3, 15)) is None
    assert svc.get_overlay(date(2026, 7, 4)) is None
    assert svc.get_overlay(date(2026, 12, 25)) is None
