"""
Tests for validate_supabase_key() in app.services.database.
Covers all six behavior cases described in quick task 009.
"""
import base64
import json
import pytest


def _make_jwt(payload: dict) -> str:
    """
    Build a minimal fake JWT string: header.payload.sig
    Content of header and sig don't matter — validate_supabase_key only decodes the payload segment.
    """
    payload_bytes = json.dumps(payload).encode()
    payload_b64 = base64.urlsafe_b64encode(payload_bytes).rstrip(b"=").decode()
    return f"header.{payload_b64}.sig"


def test_valid_service_role_jwt_returns_none():
    """Valid service_role JWT must return None (no exception)."""
    from app.services.database import validate_supabase_key

    key = _make_jwt({"role": "service_role", "iss": "supabase"})
    result = validate_supabase_key(key)
    assert result is None


def test_anon_jwt_raises_runtime_error():
    """Anon JWT (role='anon') must raise RuntimeError mentioning 'anon key' and 'service_role'."""
    from app.services.database import validate_supabase_key

    key = _make_jwt({"role": "anon", "iss": "supabase"})
    with pytest.raises(RuntimeError) as exc_info:
        validate_supabase_key(key)
    msg = str(exc_info.value)
    assert "anon key" in msg
    assert "service_role" in msg


def test_unexpected_role_raises_runtime_error_with_role_value():
    """JWT with role='authenticated' must raise RuntimeError containing that role value."""
    from app.services.database import validate_supabase_key

    key = _make_jwt({"role": "authenticated", "iss": "supabase"})
    with pytest.raises(RuntimeError) as exc_info:
        validate_supabase_key(key)
    msg = str(exc_info.value)
    assert "authenticated" in msg


def test_non_jwt_string_raises_runtime_error():
    """A non-JWT string (no dots) must raise RuntimeError containing 'Could not decode SUPABASE_KEY'."""
    from app.services.database import validate_supabase_key

    with pytest.raises(RuntimeError) as exc_info:
        validate_supabase_key("notajwtstring")
    assert "Could not decode SUPABASE_KEY" in str(exc_info.value)


def test_malformed_jwt_one_dot_raises_runtime_error():
    """JWT with only one dot (two parts) must raise RuntimeError with 'Could not decode SUPABASE_KEY'."""
    from app.services.database import validate_supabase_key

    with pytest.raises(RuntimeError) as exc_info:
        validate_supabase_key("header.payload")  # only one dot → two parts, not three
    assert "Could not decode SUPABASE_KEY" in str(exc_info.value)


def test_jwt_payload_missing_role_raises_runtime_error():
    """JWT payload with no 'role' key must raise RuntimeError with 'Could not decode SUPABASE_KEY'."""
    from app.services.database import validate_supabase_key

    key = _make_jwt({"iss": "supabase"})  # no 'role' key
    with pytest.raises(RuntimeError) as exc_info:
        validate_supabase_key(key)
    assert "Could not decode SUPABASE_KEY" in str(exc_info.value)
