---
phase: quick-009
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - src/app/services/database.py
  - src/app/main.py
autonomous: true
requirements: []
must_haves:
  truths:
    - "Service refuses to start when SUPABASE_KEY is the anon key, with a clear error naming the role"
    - "Service starts normally when SUPABASE_KEY is the service_role key"
    - "A malformed key string (not a valid JWT) produces a clear RuntimeError, not an unhandled exception"
  artifacts:
    - path: "src/app/services/database.py"
      provides: "validate_supabase_key() function that decodes JWT payload and checks role claim"
      exports: ["validate_supabase_key"]
    - path: "src/app/main.py"
      provides: "lifespan calls validate_supabase_key before run_migrations()"
      contains: "validate_supabase_key"
  key_links:
    - from: "src/app/main.py lifespan"
      to: "src/app/services/database.validate_supabase_key"
      via: "direct import and call before run_migrations()"
      pattern: "validate_supabase_key"
---

<objective>
Add startup validation that SUPABASE_KEY is a service_role JWT, not the anon key. If the wrong key is
configured, the service raises a RuntimeError immediately at startup with a clear, actionable message
— before any DB work begins.

Purpose: The anon key triggers RLS 403s deep in the pipeline (Storage upload INSERT). The error
appears far from its cause and gives no hint about credentials. Fail fast at startup instead.
Output: validate_supabase_key() in database.py; one-line call inserted in lifespan before run_migrations().
</objective>

<execution_context>
@./.claude/get-shit-done/workflows/execute-plan.md
@./.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@src/app/services/database.py
@src/app/main.py
@src/app/settings.py
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Add validate_supabase_key() to database.py</name>
  <files>src/app/services/database.py, tests/test_validate_supabase_key.py</files>
  <behavior>
    - Valid service_role JWT: function returns None (no exception)
    - Anon JWT (role="anon"): raises RuntimeError containing "anon key" and "service_role"
    - JWT with unexpected role (e.g. "authenticated"): raises RuntimeError containing that role value
    - Non-JWT string (no dots, random text): raises RuntimeError containing "Could not decode SUPABASE_KEY"
    - JWT with only one dot (malformed, no payload segment): raises RuntimeError containing "Could not decode SUPABASE_KEY"
    - JWT payload with no "role" key: raises RuntimeError containing "Could not decode SUPABASE_KEY"
  </behavior>
  <action>
    Add the following to src/app/services/database.py, after the existing imports and before get_supabase():

    ```python
    import base64
    import json
    import logging

    logger = logging.getLogger(__name__)


    def validate_supabase_key(key: str) -> None:
        """
        Decode the JWT payload section (middle segment) and assert role == 'service_role'.
        No signature verification — we only read the claim.
        Raises RuntimeError with a clear, actionable message if validation fails.
        Called from lifespan before run_migrations() so misconfiguration fails fast.
        """
        try:
            parts = key.split(".")
            if len(parts) != 3:
                raise ValueError("not a three-part JWT")
            payload_b64 = parts[1]
            # JWT base64url uses no padding; add == to satisfy stdlib decoder
            padding = "=" * (4 - len(payload_b64) % 4)
            payload_bytes = base64.urlsafe_b64decode(payload_b64 + padding)
            payload = json.loads(payload_bytes)
            role = payload["role"]
        except Exception as exc:
            raise RuntimeError(
                f"Could not decode SUPABASE_KEY as a JWT — is it set correctly in Railway? "
                f"Error: {exc}"
            ) from exc

        if role != "service_role":
            raise RuntimeError(
                f"SUPABASE_KEY appears to be the anon key (role='{role}'). "
                "Set it to the service_role key in Railway — "
                "the anon key cannot bypass RLS and will cause 403s on every Storage upload."
            )

        logger.info("SUPABASE_KEY validated: service_role JWT confirmed")
    ```

    The function uses only stdlib (base64, json) — no new dependencies.

    For the test file tests/test_validate_supabase_key.py, build minimal valid JWT segments
    using base64.urlsafe_b64encode(json.dumps({...}).encode()).rstrip(b"=").decode() for the
    payload; use "header" and "sig" as the other two segments (content irrelevant, not verified).
    Cover all six behavior cases listed above.
  </action>
  <verify>
    <automated>cd /Users/jesusalbino/Projects/content-creation && python -m pytest tests/test_validate_supabase_key.py -v</automated>
  </verify>
  <done>All six test cases pass. validate_supabase_key is importable from app.services.database.</done>
</task>

<task type="auto">
  <name>Task 2: Call validate_supabase_key in lifespan before run_migrations()</name>
  <files>src/app/main.py</files>
  <action>
    In src/app/main.py:

    1. Add import at the top with the other service imports:
       ```python
       from app.services.database import validate_supabase_key
       from app.settings import get_settings
       ```
       (get_settings may already be imported; only add if not present)

    2. Inside the lifespan function, insert these two lines as the FIRST statements after the
       opening log line and BEFORE the existing `run_migrations()` call:

       ```python
       validate_supabase_key(get_settings().supabase_key)
       ```

    The lifespan body should read (in order):
      logger.info("Starting up content-creation service.")
      validate_supabase_key(get_settings().supabase_key)   # <-- inserted here
      run_migrations()
      ...rest unchanged...

    If validate_supabase_key raises RuntimeError, FastAPI propagates it as an unhandled startup
    exception — the process exits with a non-zero code and Railway logs the full message. This is
    the desired behavior.
  </action>
  <verify>
    <automated>cd /Users/jesusalbino/Projects/content-creation && python -c "
import ast, sys
src = open('src/app/main.py').read()
tree = ast.parse(src)
# confirm import present
imports = [n for n in ast.walk(tree) if isinstance(n, (ast.ImportFrom, ast.Import))]
import_names = [ast.dump(n) for n in imports]
assert any('validate_supabase_key' in s for s in import_names), 'import missing'
# confirm call present
calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call)]
call_names = [ast.dump(n) for n in calls]
assert any('validate_supabase_key' in s for s in call_names), 'call missing'
print('OK: validate_supabase_key imported and called in main.py')
"
    </automated>
  </verify>
  <done>
    lifespan calls validate_supabase_key(get_settings().supabase_key) before run_migrations().
    A wrong key causes the process to abort at startup with a message naming the actual role and
    instructing the operator to set the service_role key in Railway.
  </done>
</task>

</tasks>

<verification>
Run full smoke suite to confirm no regressions:

```
cd /Users/jesusalbino/Projects/content-creation && python -m pytest tests/ -v --tb=short
```

All existing tests must continue to pass. The six new validate_supabase_key tests must pass.
</verification>

<success_criteria>
- validate_supabase_key() exists in src/app/services/database.py, uses only base64 + json (stdlib)
- Anon key raises RuntimeError naming "anon key", "service_role", and "Railway" in the message
- Malformed key raises RuntimeError with "Could not decode SUPABASE_KEY" (never a raw exception)
- Valid service_role key logs "SUPABASE_KEY validated: service_role JWT confirmed" at INFO
- lifespan calls validate_supabase_key before run_migrations() — wrong key aborts before any DB work
- All smoke tests pass (python -m pytest tests/ -v)
</success_criteria>

<output>
After completion, create `.planning/quick/009-supabase-key-validation/009-SUMMARY.md` following
the summary template at @./.claude/get-shit-done/templates/summary.md
</output>
