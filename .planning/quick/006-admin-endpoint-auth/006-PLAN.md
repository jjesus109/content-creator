---
phase: quick-006
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - src/app/settings.py
  - src/app/routes/admin.py
autonomous: true
requirements: [SCRTY-01]

must_haves:
  truths:
    - "Request with correct Bearer token returns 202 (trigger-pipeline) or other normal response"
    - "Request with wrong token returns 401"
    - "Request with no Authorization header returns 401"
    - "App startup fails when ADMIN_API_KEY env var is not set (fail-closed, not open)"
  artifacts:
    - path: "src/app/settings.py"
      provides: "admin_api_key field with no default — required env var ADMIN_API_KEY"
    - path: "src/app/routes/admin.py"
      provides: "verify_admin_key dependency applied to all admin router routes"
  key_links:
    - from: "src/app/routes/admin.py"
      to: "src/app/settings.py"
      via: "get_settings() inside verify_admin_key"
      pattern: "get_settings().admin_api_key"
---

<objective>
Protect all admin endpoints with a shared-secret Bearer token so the service can be safely exposed on the public internet via Railway.

Purpose: The /admin router currently has no authentication. Exposing it on Railway's public URL allows anyone to trigger the daily pipeline job. Adding a required Bearer token closes this security hole before the first deployment.

Output: A FastAPI HTTPBearer dependency that validates the Authorization header against ADMIN_API_KEY from env. Applied to every route on the admin router. Fail-closed: if ADMIN_API_KEY is not set, Pydantic raises ValidationError at startup and all requests are rejected.
</objective>

<execution_context>
@./.claude/get-shit-done/workflows/execute-plan.md
@./.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@src/app/settings.py
@src/app/routes/admin.py
@src/app/main.py
</context>

<tasks>

<task type="auto">
  <name>Task 1: Add admin_api_key to Settings</name>
  <files>src/app/settings.py</files>
  <action>
Add a required admin_api_key field to the Settings class with NO default value and NO empty-string fallback. Place it in a new comment section labelled "# Admin API (SCRTY-01)" after the tiktok_refresh_token line and before the audience_timezone line.

Field to add:

    # Admin API (SCRTY-01)
    admin_api_key: str  # Bearer token for /admin/* endpoints — Railway env var ADMIN_API_KEY

The absence of a default value is the security control: Pydantic raises ValidationError at startup if ADMIN_API_KEY is not in the environment. Do NOT add a default of "" or None.
  </action>
  <verify>grep -n "admin_api_key" /Users/jesusalbino/Projects/content-creation/src/app/settings.py</verify>
  <done>settings.py contains admin_api_key: str with no default value and no empty-string fallback</done>
</task>

<task type="auto">
  <name>Task 2: Add Bearer auth dependency to admin router</name>
  <files>src/app/routes/admin.py</files>
  <action>
Add a verify_admin_key dependency to admin.py using FastAPI's built-in HTTPBearer security scheme. Apply it to the APIRouter so every current and future route on the router is protected automatically.

Exact implementation:

1. Add these imports at the top (after existing imports):
   from fastapi import Depends, HTTPException, Security
   from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
   from app.settings import get_settings

2. Define the security scheme and dependency after the imports, before the router definition:

   _bearer = HTTPBearer()

   def verify_admin_key(
       credentials: HTTPAuthorizationCredentials = Security(_bearer),
   ) -> None:
       """Validate the Bearer token against ADMIN_API_KEY from env.
       Raises 401 if missing or wrong. Fail-closed: if ADMIN_API_KEY is
       not set, get_settings() raises ValidationError at startup so this
       line is never reached with an empty key.
       """
       expected = get_settings().admin_api_key
       if credentials.credentials != expected:
           raise HTTPException(status_code=401, detail="Invalid or missing API key.")

3. Add the dependency to the router constructor:
   router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(verify_admin_key)])

Remove the WARNING comment from trigger_pipeline's docstring since the auth gap is now closed. Replace with a note that authentication is via ADMIN_API_KEY Bearer token.

The existing trigger_pipeline handler body (threading.Thread, daemon=True) stays completely unchanged.

Important: Use secrets.compare_digest for the token comparison to prevent timing attacks. Update step 2 to use:

   import secrets
   if not secrets.compare_digest(credentials.credentials, expected):
       raise HTTPException(status_code=401, detail="Invalid or missing API key.")

Add the secrets import to the standard library imports block.
  </action>
  <verify>grep -n "verify_admin_key\|compare_digest\|HTTPBearer\|dependencies=" /Users/jesusalbino/Projects/content-creation/src/app/routes/admin.py</verify>
  <done>admin.py router has dependencies=[Depends(verify_admin_key)], verify_admin_key uses secrets.compare_digest, and the route handler is otherwise unchanged</done>
</task>

</tasks>

<verification>
Manual smoke test (no live Railway needed):

1. Start the app locally with ADMIN_API_KEY set:
   ADMIN_API_KEY=test-secret uvicorn app.main:app --port 8000

2. Request with correct token — expect 202:
   curl -s -o /dev/null -w "%{http_code}" -X POST http://localhost:8000/admin/trigger-pipeline \
     -H "Authorization: Bearer test-secret"

3. Request with wrong token — expect 401:
   curl -s -o /dev/null -w "%{http_code}" -X POST http://localhost:8000/admin/trigger-pipeline \
     -H "Authorization: Bearer wrong"

4. Request with no header — expect 403 (HTTPBearer returns 403 on missing header, 401 on wrong token):
   curl -s -o /dev/null -w "%{http_code}" -X POST http://localhost:8000/admin/trigger-pipeline

5. Missing env var — expect ValidationError at startup (service does not start):
   uvicorn app.main:app --port 8001
   (no ADMIN_API_KEY set — should fail at import/startup, not serve requests)
</verification>

<success_criteria>
- Correct Bearer token: 202 Accepted
- Wrong Bearer token: 401
- Missing Authorization header: 403 (HTTPBearer built-in)
- Missing ADMIN_API_KEY env var: service refuses to start (Pydantic ValidationError)
- Existing route handler (trigger_pipeline thread logic) is unchanged
- No external auth libraries added — only FastAPI built-ins and Python stdlib secrets
</success_criteria>

<output>
After completion, create .planning/quick/006-admin-endpoint-auth/006-SUMMARY.md following the summary template.
</output>
