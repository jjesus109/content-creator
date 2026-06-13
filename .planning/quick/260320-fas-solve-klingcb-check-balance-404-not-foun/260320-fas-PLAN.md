---
phase: quick
plan: 260320-fas
type: execute
wave: 1
depends_on: []
files_modified:
  - src/app/services/kling_circuit_breaker.py
  - tests/test_kling_balance.py
autonomous: true
requirements: [VID-03]
must_haves:
  truths:
    - "KlingCB.check_balance() no longer raises or logs 404 errors at runtime"
    - "check_balance() returns True (fail-open, no REST call made)"
    - "All existing balance tests pass"
  artifacts:
    - path: "src/app/services/kling_circuit_breaker.py"
      provides: "check_balance() with REST call removed, no-op implementation"
    - path: "tests/test_kling_balance.py"
      provides: "test confirming no-op path returns True without HTTP call"
  key_links:
    - from: "src/app/services/kling_circuit_breaker.py"
      to: "daily_pipeline.py"
      via: "check_balance() called by video_poller_job"
      pattern: "check_balance"
---

<objective>
Fix KlingCircuitBreakerService.check_balance() which fails with 404 because it calls
`https://fal.ai/v1/billing/balance` — an endpoint that does not exist.

Root cause: fal.ai does not expose a public billing/balance REST API. The SDK
(`fal_client`) uses `https://rest.fal.ai` as its base URL and only exposes
`/storage/*` and `/tokens/` paths — no billing endpoint exists.

Fix: Remove the HTTP REST call entirely. Replace with a no-op that logs a one-time
warning ("fal.ai billing API not available — balance check disabled") and returns
`True` (consistent with the existing fail-open contract documented in the method and
in STATE.md decision [09-03]).

Purpose: Eliminate 404 errors during video polling without changing the fail-open
behaviour contract that downstream callers rely on.
Output: Updated kling_circuit_breaker.py + updated balance tests.
</objective>

<execution_context>
@/Users/jesusalbino/Projects/content-creation/.claude/get-shit-done/workflows/execute-plan.md
@/Users/jesusalbino/Projects/content-creation/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@src/app/services/kling_circuit_breaker.py
@tests/test_kling_balance.py

<interfaces>
<!-- Key decision from STATE.md [09-03]: check_balance() is fail-open — returns True
     on errors to avoid unnecessary pipeline halts. -->

<!-- fal_client SDK fact: no billing/balance endpoint.
     REST base = https://rest.fal.ai
     Exposed paths: /storage/*, /tokens/
     No /billing/*, /account/*, /credits/* paths in SDK source. -->

<!-- Current check_balance() signature (kling_circuit_breaker.py line 148):
     def check_balance(self) -> bool:
         Returns True if balance >= $1.00, False if < $1.00
         Side effect: Telegram alert if balance < $5.00
     After fix: always returns True, no HTTP call, no side effects. -->
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Replace HTTP balance call with documented no-op</name>
  <files>src/app/services/kling_circuit_breaker.py</files>
  <action>
    In check_balance() (line 148), replace the entire try/except body with a
    no-op implementation:

    1. Remove the `import requests` at the top of the file (line 19) — no longer
       needed (verify no other method uses requests before removing).
    2. Replace the try/except block in check_balance() with:

    ```python
    def check_balance(self) -> bool:
        """
        fal.ai does not expose a public billing/balance REST API.
        Balance checking is disabled — returns True (fail-open) unconditionally.

        Original intent: halt pipeline at < $1.00, alert at < $5.00.
        Replacement strategy: monitor spend manually via fal.ai dashboard.
        """
        logger.debug(
            "KlingCB.check_balance() called — fal.ai billing API unavailable, "
            "returning True (fail-open). Monitor spend at https://fal.ai/dashboard.",
            extra={"pipeline_step": "kling_cb", "content_history_id": ""},
        )
        return True
    ```

    Keep BALANCE_ALERT_USD and BALANCE_HALT_USD constants — they are referenced by
    tests (test_kling_balance.py::test_kling_cb_constants) and document intent.

    Do NOT touch any other method (is_open, record_attempt, reset, _trip).
  </action>
  <verify>
    <automated>cd /Users/jesusalbino/Projects/content-creation && python -c "from app.services.kling_circuit_breaker import KlingCircuitBreakerService; print('import ok')"</automated>
  </verify>
  <done>
    check_balance() body contains no requests.get call, no fal_client.auth import,
    no URL reference. Method returns True unconditionally. Module imports cleanly.
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Update balance tests to match no-op implementation</name>
  <files>tests/test_kling_balance.py</files>
  <behavior>
    - test_check_balance_no_op: check_balance() returns True without any HTTP call
    - test_check_balance_no_http: no requests.get is ever called (mock not needed,
      but assert via spy that the method returns True with zero patching)
    - test_check_balance_fail_open_on_exception: still passes (method always returns
      True, exception path is gone but test should be updated to reflect the no-op)
    - test_check_balance_does_not_write_to_db: still passes (no DB writes, no HTTP)
    - test_kling_cb_constants: still passes (constants unchanged)
  </behavior>
  <action>
    Update tests/test_kling_balance.py:

    1. Remove `patch("app.services.kling_circuit_breaker.requests.get", ...)` from
       test_check_balance_fail_open_on_exception and
       test_check_balance_does_not_write_to_db — requests is no longer imported in
       the module. Add a comment: "# No HTTP call expected — fal.ai billing API
       not available; check_balance() is a no-op."

    2. Add test_check_balance_no_op:
    ```python
    def test_check_balance_no_op():
        """check_balance() returns True immediately with no HTTP or DB calls."""
        mock_db = _make_supabase(_default_state())
        from app.services.kling_circuit_breaker import KlingCircuitBreakerService
        cb = KlingCircuitBreakerService(mock_db)
        result = cb.check_balance()
        assert result is True, "check_balance() must return True (no-op, fail-open)"
        mock_db.table.return_value.update.assert_not_called()
    ```

    3. Remove the `patch("fal_client.auth.fetch_credentials", ...)` lines from
       existing tests — fal_client.auth is no longer imported in the module.

    Run tests after each change: `pytest tests/test_kling_balance.py -v`
  </action>
  <verify>
    <automated>cd /Users/jesusalbino/Projects/content-creation && python -m pytest tests/test_kling_balance.py -v 2>&1 | tail -20</automated>
  </verify>
  <done>
    All tests in test_kling_balance.py pass. No patch for requests.get or
    fal_client.auth.fetch_credentials remains. New test_check_balance_no_op passes.
  </done>
</task>

<task type="auto">
  <name>Task 3: Full test suite smoke check</name>
  <files></files>
  <action>
    Run the full test suite to confirm no regressions from removing the `requests`
    import and the balance REST call:

    ```
    python -m pytest tests/ -x --tb=short -q
    ```

    If any test fails due to a missing `requests` mock that expected the old
    behaviour, fix that test file too (update patch target or remove stale mock).
  </action>
  <verify>
    <automated>cd /Users/jesusalbino/Projects/content-creation && python -m pytest tests/ -x --tb=short -q 2>&1 | tail -20</automated>
  </verify>
  <done>
    All tests pass. Zero failures, zero errors related to kling_circuit_breaker
    balance check.
  </done>
</task>

</tasks>

<verification>
1. `python -c "from app.services.kling_circuit_breaker import KlingCircuitBreakerService"` exits 0
2. `grep -n "requests\|fal.ai/v1/billing\|fal_client.auth" src/app/services/kling_circuit_breaker.py` returns no matches
3. `pytest tests/test_kling_balance.py -v` — all pass
4. `pytest tests/ -x -q` — all pass
</verification>

<success_criteria>
- check_balance() contains no HTTP call, returns True unconditionally
- No 404 errors appear in logs during video polling
- All 5 tests in test_kling_balance.py pass
- Full test suite passes (no regressions)
</success_criteria>

<output>
After completion, create `.planning/quick/260320-fas-solve-klingcb-check-balance-404-not-foun/260320-fas-SUMMARY.md`
</output>
