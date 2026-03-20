"""Tests for SCN-02 (seasonal calendar overlays)."""
import pytest
from datetime import date


@pytest.mark.skip(reason="stub — implement SeasonalCalendarService in plan 02 first")
def test_seasonal_injection():
    """SCN-02: seasonal overlay injected for Sep 16, Nov 1-2, Nov 20, Aug 8."""
    pass


@pytest.mark.skip(reason="stub — implement SeasonalCalendarService in plan 02 first")
def test_holiday_dates():
    """SCN-02: correct holidays detected by date."""
    pass


@pytest.mark.skip(reason="stub — implement SeasonalCalendarService in plan 02 first")
def test_non_holiday_returns_none():
    """SCN-02: non-holiday date returns no overlay."""
    pass
