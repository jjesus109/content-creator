---
phase: quick
plan: 260320-edq
type: execute
wave: 1
depends_on: []
files_modified:
  - src/app/services/kling_circuit_breaker.py
  - tests/test_kling_circuit_breaker.py
  - tests/test_kling_balance.py
autonomous: true
requirements: []
must_haves:
  truths:
    - "check_balance() no longer calls fal_client.get_balance() (attribute does not exist)"
    - "check_balance() queries fal.ai REST API and returns correct bool based on balance"
    - "All balance-related tests pass"
  artifacts:
    - path: "src/app/services/kling_circuit_breaker.py"
      provides: "Fixed check_balance() using requests.get to fal.ai billing API"
    - path: "tests/test_kling_circuit_breaker.py"
      provides: "Updated tests mocking requests.get instead of fal_client.get_balance"
    - path: "tests/test_kling_balance.py"
      provides: "Updated tests mocking requests.get instead of fal_client.get_balance"
  key_links:
    - from: "check_balance()"
      to: "https://fal.ai/v1/billing/balance"
      via: "requests.get with Authorization: Key header"
      pattern: "requests.get.*fal.ai.*billing/balance"
---

<objective>
Fix KlingCircuitBreakerService.check_balance() which fails with "module fal_client has no attribute get_balance".

The fal-client 0.13.1 SDK does not expose a get_balance() function. The fix replaces the non-existent SDK call with a direct REST request to the fal.ai billing API endpoint. The existing fail-open semantics and balance threshold logic remain unchanged.

Purpose: Pipeline is currently logging errors every 60 seconds during video polling — check_balance() is failing on every poll cycle. This breaks the balance guard, which is supposed to halt the pipeline when credits run out.
Output: Fixed check_balance() implementation + updated tests that mock the REST call instead of the non-existent SDK method.
</objective>

<execution_context>
@/Users/jesusalbino/Projects/content-creation/.claude/get-shit-done/workflows/execute-plan.md
@/Users/jesusalbino/Projects/content-creation/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md

Root cause: fal-client==0.13.1 (installed at .venv/lib/python3.12/site-packages/fal_client-0.13.1.dist-info) does not have a get_balance() function. Confirmed by inspecting fal_client module — no balance, credit, or account-related attributes exist.

Fix approach: Replace `fal_client.get_balance()` with a direct REST call:
  GET https://fal.ai/v1/billing/balance
  Authorization: Key <FAL_KEY>
  Response JSON: {"balance": <float>}  (amount in USD)

Auth key retrieval: use `fal_client.auth.fetch_credentials()` which returns AuthCredentials with .token property. This is how the SDK itself reads FAL_KEY — consistent and already validated at startup.

The code already imports `requests` at the top of kling_circuit_breaker.py — no new imports needed.

Tests currently mock `fal_client.get_balance` via `patch.dict("sys.modules", {"fal_client": mock_fal})` and calling `mock_fal.get_balance.return_value = ...`. These tests must be updated to mock `requests.get` with a mock response object that returns the appropriate balance value.
</context>

<tasks>

<task type="auto">
  <name>Task 1: Fix check_balance() to use fal.ai REST API</name>
  <files>src/app/services/kling_circuit_breaker.py</files>
  <action>
Replace the check_balance() method body in KlingCircuitBreakerService (lines 147-193).

The current broken line is:
    balance: float = fal_client.get_balance()

Replace the entire try block inside check_balance() with a REST call. The method signature, docstring, thresholds, logging, and alerts remain unchanged. Only replace how balance is fetched.

New implementation for the try block:

```python
try:
    import fal_client.auth as _fal_auth
    credentials = _fal_auth.fetch_credentials()
    resp = requests.get(
        "https://fal.ai/v1/billing/balance",
        headers={"Authorization": f"Key {credentials}"},
        timeout=10,
    )
    resp.raise_for_status()
    balance: float = float(resp.json()["balance"])

    if balance < BALANCE_HALT_USD:
        ...  # keep existing halt logic unchanged
```

NOTE: `fal_client.auth.fetch_credentials()` returns the raw key string (not an AuthCredentials object) — confirmed from auth.py line 240-254: it returns `auth.token` (a str). So the Authorization header is `f"Key {credentials}"` directly.

The `requests` import already exists at the top of the file (line 16) — do not add a second import.

Keep the entire except block (lines 187-193) unchanged — fail-open behavior is correct.
  </action>
  <verify>
    <automated>cd /Users/jesusalbino/Projects/content-creation && .venv/bin/python3 -c "from app.services.kling_circuit_breaker import KlingCircuitBreakerService; print('import OK')" 2>&1 | grep -v "^$"</automated>
  </verify>
  <done>check_balance() no longer references fal_client.get_balance; imports fal_client.auth and calls requests.get to the billing endpoint; all existing logic (thresholds, alerts, fail-open) intact</done>
</task>

<task type="auto">
  <name>Task 2: Update balance tests to mock requests.get instead of fal_client.get_balance</name>
  <files>tests/test_kling_circuit_breaker.py, tests/test_kling_balance.py</files>
  <action>
The tests that need updating use `patch.dict("sys.modules", {"fal_client": mock_fal})` and set `mock_fal.get_balance.return_value = <value>`. These must be changed to mock the REST call instead.

New test pattern — replace `mock_fal.get_balance.return_value = X` with a `patch("requests.get")` that returns a mock response:

```python
from unittest.mock import MagicMock, patch

mock_resp = MagicMock()
mock_resp.json.return_value = {"balance": 10.0}  # or whatever balance value
mock_resp.raise_for_status.return_value = None

with patch("app.services.kling_circuit_breaker.requests.get", return_value=mock_resp) as mock_get, \
     patch("app.services.kling_circuit_breaker.send_alert_sync") as mock_alert:
    from app.services.kling_circuit_breaker import KlingCircuitBreakerService
    cb = KlingCircuitBreakerService(mock_db)
    result = cb.check_balance()
```

For the exception/fail-open test, use:
```python
with patch("app.services.kling_circuit_breaker.requests.get", side_effect=Exception("Network error")), \
     patch("app.services.kling_circuit_breaker.send_alert_sync") as mock_alert:
```

Files to update:

**tests/test_kling_circuit_breaker.py** — update these 3 tests (around lines 117-167):
- test_check_balance_proceeds_when_above_halt_threshold: balance=10.0
- test_check_balance_halts_when_below_one_dollar: balance=0.50
- test_check_balance_alerts_but_proceeds_when_between_one_and_five: balance=3.00

Remove the `patch.dict("sys.modules", {"fal_client": mock_fal})` wrapping and `mock_fal` setup from these 3 tests. Replace with `patch("app.services.kling_circuit_breaker.requests.get", return_value=mock_resp)`.

**tests/test_kling_balance.py** — update all tests:
- test_check_balance_fail_open_on_exception: use `side_effect=Exception(...)` on requests.get
- test_check_balance_does_not_write_to_db: use mock_resp with balance=50.0

Also remove `sys.modules` patching for fal_client from these tests since the implementation no longer calls fal_client directly in check_balance().

Also add the patch for `app.services.kling_circuit_breaker.fal_client.auth` (the `fal_client.auth.fetch_credentials` call) — mock it to return a string key like "test_key_123" so the Authorization header can be constructed without a real FAL_KEY:

```python
with patch("app.services.kling_circuit_breaker._fal_auth") as mock_auth:
    mock_auth.fetch_credentials.return_value = "test_key_123"
```

Wait — the implementation uses `import fal_client.auth as _fal_auth` inside the try block (local import). To mock this correctly, use `patch("fal_client.auth.fetch_credentials", return_value="test_key_123")` instead.

Simpler: patch `fal_client.auth.fetch_credentials` and `requests.get` together in each test's context manager.
  </action>
  <verify>
    <automated>cd /Users/jesusalbino/Projects/content-creation && .venv/bin/python3 -m pytest tests/test_kling_circuit_breaker.py tests/test_kling_balance.py -x -q 2>&1 | tail -20</automated>
  </verify>
  <done>All tests in test_kling_circuit_breaker.py and test_kling_balance.py pass; no fal_client.get_balance references remain in tests</done>
</task>

</tasks>

<verification>
Run full test suite to confirm no regressions:

```bash
cd /Users/jesusalbino/Projects/content-creation && .venv/bin/python3 -m pytest tests/ -x -q 2>&1 | tail -30
```

Confirm the specific error is gone:
```bash
cd /Users/jesusalbino/Projects/content-creation && .venv/bin/python3 -c "
from unittest.mock import patch, MagicMock
mock_resp = MagicMock()
mock_resp.json.return_value = {'balance': 10.0}
mock_resp.raise_for_status.return_value = None
with patch('requests.get', return_value=mock_resp), \
     patch('fal_client.auth.fetch_credentials', return_value='test_key'):
    from app.services.kling_circuit_breaker import KlingCircuitBreakerService
    from unittest.mock import MagicMock
    db = MagicMock()
    db.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(data={'id':1,'is_open':False,'total_attempts':0,'total_failures':0,'failure_rate':0.0})
    cb = KlingCircuitBreakerService(db)
    result = cb.check_balance()
    print(f'check_balance() returned: {result}')
    assert result is True
    print('PASS — no AttributeError')
"
```
</verification>

<success_criteria>
- check_balance() calls requests.get("https://fal.ai/v1/billing/balance", ...) instead of fal_client.get_balance()
- No "module fal_client has no attribute get_balance" error during video polling
- All tests in test_kling_circuit_breaker.py and test_kling_balance.py pass
- Full test suite passes (no regressions)
- Fail-open behavior preserved: check_balance() returns True on any exception
- Balance thresholds unchanged: halt at $1.00, alert at $5.00
</success_criteria>

<output>
After completion, create `.planning/quick/260320-edq-fix-this-error-klingcb-check-balance-fai/260320-edq-SUMMARY.md`
</output>
