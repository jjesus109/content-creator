"""
TDD RED: KlingCircuitBreakerService balance check integration tests.
Phase 09-03 Task 1

Additional balance check scenarios:
  - check_balance() is fail-open (returns True on fal_client exception)
  - check_balance() does NOT write to DB on any path
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from unittest.mock import MagicMock, patch


def _make_supabase(state: dict) -> MagicMock:
    mock_db = MagicMock()
    mock_db.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(data=state)
    mock_db.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()
    return mock_db


def _default_state(**overrides) -> dict:
    base = {
        "id": 1,
        "is_open": False,
        "opened_at": None,
        "total_attempts": 0,
        "total_failures": 0,
        "failure_rate": 0.0,
        "last_reset_at": "2026-03-19T00:00:00+00:00",
        "updated_at": "2026-03-19T00:00:00+00:00",
    }
    base.update(overrides)
    return base


def test_check_balance_fail_open_on_exception():
    """check_balance() returns True (fail-open) when fal_client.get_balance() raises."""
    mock_db = _make_supabase(_default_state())

    mock_fal = MagicMock()
    mock_fal.get_balance.side_effect = Exception("Network error")

    with patch("app.services.kling_circuit_breaker.send_alert_sync") as mock_alert, \
         patch.dict("sys.modules", {"fal_client": mock_fal}):
        from app.services.kling_circuit_breaker import KlingCircuitBreakerService
        cb = KlingCircuitBreakerService(mock_db)
        result = cb.check_balance()

    assert result is True, "check_balance() must fail-open (return True) on exception"
    # On exception, no Telegram alert — fail silently (logged only)
    mock_alert.assert_not_called()


def test_check_balance_does_not_write_to_db():
    """check_balance() never writes to DB — balance check is read-only from fal_client."""
    mock_db = _make_supabase(_default_state())

    mock_fal = MagicMock()
    mock_fal.get_balance.return_value = 50.0  # Healthy balance

    with patch("app.services.kling_circuit_breaker.send_alert_sync"), \
         patch.dict("sys.modules", {"fal_client": mock_fal}):
        from app.services.kling_circuit_breaker import KlingCircuitBreakerService
        cb = KlingCircuitBreakerService(mock_db)
        cb.check_balance()

    # No DB writes should have occurred
    mock_db.table.return_value.update.assert_not_called(), (
        "check_balance() must not write to DB"
    )


def test_kling_cb_uses_separate_table_from_heygen_cb():
    """KlingCB uses 'kling_circuit_breaker_state', NOT 'circuit_breaker_state'."""
    from app.services.kling_circuit_breaker import TABLE
    assert TABLE == "kling_circuit_breaker_state", (
        f"Expected TABLE='kling_circuit_breaker_state', got {TABLE!r}"
    )


def test_kling_cb_constants():
    """FAILURE_THRESHOLD=0.20, BALANCE_HALT_USD=1.0, BALANCE_ALERT_USD=5.0."""
    from app.services.kling_circuit_breaker import (
        FAILURE_THRESHOLD,
        BALANCE_HALT_USD,
        BALANCE_ALERT_USD,
    )
    assert FAILURE_THRESHOLD == 0.20, f"Expected 0.20, got {FAILURE_THRESHOLD}"
    assert BALANCE_HALT_USD == 1.0, f"Expected 1.0, got {BALANCE_HALT_USD}"
    assert BALANCE_ALERT_USD == 5.0, f"Expected 5.0, got {BALANCE_ALERT_USD}"
