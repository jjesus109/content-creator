"""
TDD RED: KlingCircuitBreakerService unit tests.
Phase 09-03 Task 1

Tests 7 behaviors:
  1. record_attempt(success=True) increments total_attempts, rate below threshold, returns True
  2. After 2 failures and 8 total attempts (25% > 20%), returns False and sets is_open=True
  3. record_attempt when is_open=True immediately returns False without incrementing counts
  4. check_balance() — proceed when >= $1.00; halt when < $1.00; alert when < $5.00 but >= $1.00
  5. reset() — clears is_open, zeroes counters, updates last_reset_at
  6. _trip() sends alert with "circuit breaker", failure_rate percentage, "/resume"
  7. is_open() reads from DB (survives restart — not in-memory)
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from unittest.mock import MagicMock, patch, call


def _make_supabase(state: dict) -> MagicMock:
    """Helper: mock Supabase client returning the given state dict."""
    mock_db = MagicMock()
    mock_db.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(data=state)
    mock_db.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()
    return mock_db


def _default_state(**overrides) -> dict:
    """Returns a default CB state dict, optionally overriding fields."""
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


# --- Test 1: Successful attempt increments total_attempts, returns True ---

def test_record_attempt_success_returns_true():
    """record_attempt(success=True) increments total_attempts, failure_rate stays below threshold, returns True."""
    state = _default_state(total_attempts=5, total_failures=0, failure_rate=0.0)
    mock_db = _make_supabase(state)

    with patch("app.services.kling_circuit_breaker.send_alert_sync"):
        from app.services.kling_circuit_breaker import KlingCircuitBreakerService
        cb = KlingCircuitBreakerService(mock_db)
        result = cb.record_attempt(success=True)

    assert result is True, "record_attempt(success=True) must return True when below threshold"

    # Verify DB was updated with incremented total_attempts
    update_call = mock_db.table.return_value.update.call_args
    updated_data = update_call[0][0]
    assert updated_data["total_attempts"] == 6, f"Expected total_attempts=6, got {updated_data['total_attempts']}"
    assert updated_data.get("is_open") is None or updated_data.get("is_open") is False, (
        "is_open must not be set to True in normal update"
    )


# --- Test 2: 25% failure rate exceeds 20% threshold → CB opens ---

def test_record_attempt_failure_opens_circuit_breaker_at_threshold():
    """After 2 failures and 8 total attempts (25% failure rate > 20%), opens CB, returns False."""
    # State: 7 attempts, 1 failure so far = 14.3% (below threshold)
    # This record_attempt will make it 8 attempts, 2 failures = 25% > 20%
    state = _default_state(total_attempts=7, total_failures=1, failure_rate=0.143)
    mock_db = _make_supabase(state)

    with patch("app.services.kling_circuit_breaker.send_alert_sync") as mock_alert:
        from app.services.kling_circuit_breaker import KlingCircuitBreakerService
        cb = KlingCircuitBreakerService(mock_db)
        result = cb.record_attempt(success=False)

    assert result is False, "record_attempt returning False when threshold exceeded"

    # Verify DB was updated with is_open=True
    update_call = mock_db.table.return_value.update.call_args
    updated_data = update_call[0][0]
    assert updated_data.get("is_open") is True, f"Expected is_open=True, got {updated_data.get('is_open')}"
    assert updated_data["total_failures"] == 2
    assert updated_data["total_attempts"] == 8

    # Verify alert was sent
    mock_alert.assert_called_once()


# --- Test 3: Fast path — CB already open, returns False without incrementing ---

def test_record_attempt_when_open_returns_false_without_increment():
    """record_attempt when is_open=True immediately returns False without incrementing counts."""
    state = _default_state(is_open=True, total_attempts=8, total_failures=3, failure_rate=0.375)
    mock_db = _make_supabase(state)

    with patch("app.services.kling_circuit_breaker.send_alert_sync"):
        from app.services.kling_circuit_breaker import KlingCircuitBreakerService
        cb = KlingCircuitBreakerService(mock_db)
        result = cb.record_attempt(success=False)

    assert result is False, "CB open: record_attempt must return False immediately"

    # DB update must NOT have been called (no counter increment)
    mock_db.table.return_value.update.assert_not_called(), (
        "CB open: DB update must NOT be called when fast-pathing"
    )


# --- Test 4: check_balance() thresholds ---

def test_check_balance_proceeds_when_above_halt_threshold():
    """check_balance() returns True when balance >= $1.00."""
    mock_db = _make_supabase(_default_state())

    mock_fal = MagicMock()
    mock_fal.get_balance.return_value = 10.0  # $10 — well above all thresholds

    with patch("app.services.kling_circuit_breaker.send_alert_sync") as mock_alert, \
         patch.dict("sys.modules", {"fal_client": mock_fal}):
        from app.services.kling_circuit_breaker import KlingCircuitBreakerService
        cb = KlingCircuitBreakerService(mock_db)
        result = cb.check_balance()

    assert result is True, "Balance $10.00 should proceed (>= $1 halt threshold)"
    mock_alert.assert_not_called(), "No alert for healthy balance"


def test_check_balance_halts_when_below_one_dollar():
    """check_balance() returns False (halt pipeline) when balance < $1.00."""
    mock_db = _make_supabase(_default_state())

    mock_fal = MagicMock()
    mock_fal.get_balance.return_value = 0.50  # $0.50 — below $1 halt threshold

    with patch("app.services.kling_circuit_breaker.send_alert_sync") as mock_alert, \
         patch.dict("sys.modules", {"fal_client": mock_fal}):
        from app.services.kling_circuit_breaker import KlingCircuitBreakerService
        cb = KlingCircuitBreakerService(mock_db)
        result = cb.check_balance()

    assert result is False, "Balance $0.50 should halt (< $1 threshold)"
    mock_alert.assert_called_once()
    alert_msg = mock_alert.call_args[0][0]
    assert "0.50" in alert_msg or "bajo" in alert_msg.lower() or "criticamente" in alert_msg.lower()


def test_check_balance_alerts_but_proceeds_when_between_one_and_five():
    """check_balance() returns True but sends alert when $1.00 <= balance < $5.00."""
    mock_db = _make_supabase(_default_state())

    mock_fal = MagicMock()
    mock_fal.get_balance.return_value = 3.00  # $3.00 — alert zone but not halt

    with patch("app.services.kling_circuit_breaker.send_alert_sync") as mock_alert, \
         patch.dict("sys.modules", {"fal_client": mock_fal}):
        from app.services.kling_circuit_breaker import KlingCircuitBreakerService
        cb = KlingCircuitBreakerService(mock_db)
        result = cb.check_balance()

    assert result is True, "Balance $3.00 should proceed (>= $1 halt threshold)"
    mock_alert.assert_called_once(), "Should alert when balance < $5.00"


# --- Test 5: reset() clears all CB state ---

def test_reset_clears_state():
    """reset() sets is_open=False, zeroes counters, updates last_reset_at."""
    state = _default_state(is_open=True, total_attempts=8, total_failures=3, failure_rate=0.375)
    mock_db = _make_supabase(state)

    with patch("app.services.kling_circuit_breaker.send_alert_sync"):
        from app.services.kling_circuit_breaker import KlingCircuitBreakerService
        cb = KlingCircuitBreakerService(mock_db)
        cb.reset()

    update_call = mock_db.table.return_value.update.call_args
    updated_data = update_call[0][0]
    assert updated_data["is_open"] is False, "reset() must set is_open=False"
    assert updated_data["total_attempts"] == 0, "reset() must zero total_attempts"
    assert updated_data["total_failures"] == 0, "reset() must zero total_failures"
    assert updated_data["failure_rate"] == 0.0, "reset() must zero failure_rate"
    assert "last_reset_at" in updated_data, "reset() must update last_reset_at"
    assert updated_data.get("opened_at") is None, "reset() must clear opened_at"


# --- Test 6: _trip() sends alert containing "circuit breaker", failure rate, "/resume" ---

def test_trip_sends_alert_with_required_content():
    """_trip() sends alert containing 'circuit breaker', failure_rate %, and '/resume'."""
    state = _default_state(total_attempts=7, total_failures=1, failure_rate=0.143)
    mock_db = _make_supabase(state)

    with patch("app.services.kling_circuit_breaker.send_alert_sync") as mock_alert:
        from app.services.kling_circuit_breaker import KlingCircuitBreakerService
        cb = KlingCircuitBreakerService(mock_db)
        # Trigger _trip via record_attempt exceeding threshold
        cb.record_attempt(success=False)  # 8 attempts, 2 failures = 25%

    mock_alert.assert_called_once()
    alert_msg = mock_alert.call_args[0][0].lower()
    assert "circuit breaker" in alert_msg, f"Alert must mention 'circuit breaker', got: {alert_msg!r}"
    assert "/resume" in alert_msg, f"Alert must include '/resume' instruction, got: {alert_msg!r}"
    # Check failure rate percentage is mentioned (e.g., "25%" or "0.25")
    original_msg = mock_alert.call_args[0][0]
    has_rate = any(x in original_msg for x in ["25%", "25.0%", "0.25", "25,0"])
    assert has_rate, f"Alert must mention failure rate percentage, got: {original_msg!r}"


# --- Test 7: is_open() reads from DB (not in-memory) ---

def test_is_open_reads_from_db():
    """is_open() reads DB state each call — not cached in-memory (survives restart)."""
    # First call: CB closed
    state_closed = _default_state(is_open=False)
    # Second call: CB open (simulate state change between calls)
    state_open = _default_state(is_open=True)

    mock_db = MagicMock()
    mock_db.table.return_value.select.return_value.eq.return_value.single.return_value.execute.side_effect = [
        MagicMock(data=state_closed),
        MagicMock(data=state_open),
    ]

    with patch("app.services.kling_circuit_breaker.send_alert_sync"):
        from app.services.kling_circuit_breaker import KlingCircuitBreakerService
        cb = KlingCircuitBreakerService(mock_db)

        result1 = cb.is_open()
        result2 = cb.is_open()

    assert result1 is False, "First call: CB should be closed"
    assert result2 is True, "Second call: CB should be open (DB changed between calls)"
    # Verify DB was queried twice (not cached)
    assert mock_db.table.return_value.select.return_value.eq.return_value.single.return_value.execute.call_count == 2
