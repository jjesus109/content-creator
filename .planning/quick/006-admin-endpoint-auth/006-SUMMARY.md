---
phase: quick-006
plan: 01
subsystem: admin-auth
tags: [security, fastapi, auth, bearer-token]
dependency_graph:
  requires: [quick-005]
  provides: [SCRTY-01-admin-auth]
  affects: [src/app/routes/admin.py, src/app/settings.py]
tech_stack:
  added: []
  patterns: [HTTPBearer, secrets.compare_digest, Pydantic required field, router-level dependency]
key_files:
  created: []
  modified:
    - src/app/settings.py
    - src/app/routes/admin.py
decisions:
  - "admin_api_key has no default — Pydantic ValidationError at startup is the fail-closed mechanism; no runtime empty-key guard needed"
  - "secrets.compare_digest used for timing-safe comparison — prevents token oracle via response timing"
  - "Dependency applied at router constructor level (not per-route) — all current and future admin routes are automatically protected"
  - "HTTPBearer returns 403 on missing Authorization header (built-in) and 401 on wrong token (explicit raise)"
metrics:
  duration: "4 min"
  completed: "2026-03-15"
  tasks_completed: 2
  files_modified: 2
---

# Quick Task 006: Admin Endpoint Auth Summary

**One-liner:** Bearer token auth via HTTPBearer + secrets.compare_digest protecting all /admin/* routes, with fail-closed ADMIN_API_KEY required env var.

## What Was Built

Protected the `/admin` router with a shared-secret Bearer token scheme using only FastAPI built-ins and Python stdlib. The service now refuses to start if `ADMIN_API_KEY` is not set in the environment, and every request to any admin route must include a valid `Authorization: Bearer <token>` header.

## Tasks Completed

| Task | Name | Commit | Files Modified |
|------|------|--------|----------------|
| 1 | Add admin_api_key to Settings | b1cc4ee | src/app/settings.py |
| 2 | Add Bearer auth dependency to admin router | 18241cd | src/app/routes/admin.py |

## Security Properties

- **Correct Bearer token:** 202 Accepted (trigger-pipeline normal response)
- **Wrong Bearer token:** 401 Unauthorized (`Invalid or missing API key.`)
- **Missing Authorization header:** 403 Forbidden (HTTPBearer built-in)
- **Missing ADMIN_API_KEY env var:** service refuses to start (Pydantic ValidationError at startup)
- **Timing attack:** `secrets.compare_digest` prevents response-time token oracle
- **Scope:** All routes on `router = APIRouter(prefix="/admin")` — current and future

## Key Implementation Details

`verify_admin_key` is a FastAPI dependency defined before the router and applied via `dependencies=[Depends(verify_admin_key)]` on the `APIRouter` constructor. This means any new route added to the admin router is automatically protected without per-route annotation.

The `admin_api_key: str` field in `Settings` carries no default value — this is the entire fail-closed mechanism. Pydantic raises `ValidationError` during `Settings()` instantiation if the env var is absent, which propagates as a startup crash before Railway serves any traffic.

The `trigger_pipeline` handler body (threading.Thread, daemon=True pattern) is completely unchanged.

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check

- [x] `src/app/settings.py` contains `admin_api_key: str` with no default
- [x] `src/app/routes/admin.py` contains `verify_admin_key`, `compare_digest`, `HTTPBearer`, `dependencies=`
- [x] Commit b1cc4ee exists (Task 1)
- [x] Commit 18241cd exists (Task 2)
