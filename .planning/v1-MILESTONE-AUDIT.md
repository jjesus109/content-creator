---
milestone: v1
audited: 2026-03-01T15:15:00Z
status: gaps_found
scores:
  requirements: 22/26
  phases: 6/7
  integration: 26/26
  flows: 4/5
gaps:
  requirements:
    - id: "PUBL-01"
      status: "partial"
      phase: "Phase 5"
      claimed_by_plans: ["05-01-PLAN.md", "05-02-PLAN.md", "05-03-PLAN.md", "05-04-PLAN.md", "05-05-PLAN.md"]
      completed_by_plans: ["05-01-SUMMARY.md", "05-02-SUMMARY.md", "05-03-SUMMARY.md", "05-04-SUMMARY.md", "05-05-SUMMARY.md"]
      verification_status: "missing"
      evidence: "Phase 5 has no VERIFICATION.md. UAT document (8/8 tests passing) and all 5 SUMMARY frontmatter list PUBL-01 as completed. Integration checker confirms publishing wiring is intact. Formal verification report was never written."
    - id: "PUBL-02"
      status: "partial"
      phase: "Phase 5"
      claimed_by_plans: ["05-01-PLAN.md", "05-03-PLAN.md", "05-04-PLAN.md"]
      completed_by_plans: ["05-01-SUMMARY.md", "05-03-SUMMARY.md", "05-04-SUMMARY.md", "05-05-SUMMARY.md"]
      verification_status: "missing"
      evidence: "Same as PUBL-01 — no Phase 5 VERIFICATION.md. Peak hour scheduling verified by UAT test 7 and integration checker."
    - id: "PUBL-03"
      status: "partial"
      phase: "Phase 5"
      claimed_by_plans: ["05-03-PLAN.md"]
      completed_by_plans: ["05-03-SUMMARY.md", "05-05-SUMMARY.md"]
      verification_status: "missing"
      evidence: "Same as PUBL-01. verify_publish_job wiring confirmed by integration checker at platform_publish.py."
    - id: "PUBL-04"
      status: "partial"
      phase: "Phase 5"
      claimed_by_plans: ["05-03-PLAN.md"]
      completed_by_plans: ["05-03-SUMMARY.md", "05-05-SUMMARY.md"]
      verification_status: "missing"
      evidence: "Same as PUBL-01. Telegram fallback on publish failure confirmed by integration checker at platform_publish.py except block."
  integration:
    - id: "INT-01"
      severity: "warning"
      description: "Stale duplicate file: src/app/scheduler/jobs/circuit_breaker.py is an unreachable copy of app.services.circuit_breaker. Never imported. Missing Phase 7 methods (is_daily_halted, clear_daily_halt). Editing the wrong file would silently have no effect."
      affected_requirements: ["INFRA-04"]
    - id: "INT-02"
      severity: "warning"
      description: "TikTok OAuth route missing: settings.py comments reference a /auth/tiktok FastAPI route for TikTok token authorization, but no such route is implemented. tiktok_access_token defaults to empty string. TikTok metrics collection (ANLX-01) is non-functional until creator manually populates env var."
      affected_requirements: ["ANLX-01"]
  flows:
    - id: "FLOW-01"
      severity: "warning"
      description: "E2E test assertion broken in tests/test_phase07_e2e.py line 139: mock_all_externals['approval'].assert_called_once() will fail when ANTHROPIC_API_KEY is set. send_approval_message_sync is only called from _process_completed_render() in heygen.py (webhook/poller path), never from daily_pipeline_job() directly. Test assertion is wrong; production wiring is correct."
      affected_requirements: ["TGAP-01"]
tech_debt:
  - phase: "02-script-generation"
    items:
      - "REQUIREMENTS.md still says 'GPT-4o' and '5-Pillar' — implementation uses Claude and 6-Pillar (documented evolution). Staleness only."
      - "Plan frontmatter requirement IDs in 02-02 and 02-03 are mis-mapped (SCRP-02/SCRP-04 swapped). Documentation only, no functional impact."
      - "Similarity threshold 0.85 not empirically calibrated for Spanish philosophical content — flagged in 02-05-SUMMARY.md as open item."
  - phase: "03-video-production"
    items:
      - "hmac.new() deprecated alias in webhooks.py:30 — prefer hmac.HMAC(). Functional in Python 3.12."
      - "_scheduler = None module-level global in video_poller.py — ordering dependency on set_scheduler() call in registry.py. Correctly initialized; risk is only if initialization order changes."
  - phase: "05-multi-platform-publishing"
    items:
      - "Phase 5 VERIFICATION.md never written. UAT (8/8 pass) and SUMMARYs provide coverage evidence but formal verification is absent."
      - "TikTok is MANUAL_PLATFORMS only — creator receives copy in Telegram for manual posting. No TikTok direct API integration. Acceptable for v1 per design."
  - phase: "07-hardening"
    items:
      - "E2E test (test_phase07_e2e.py) has incorrect mock assertion for send_approval_message_sync (assert_called_once will fail with live credentials). Test has never run with real ANTHROPIC_API_KEY per VERIFICATION.md."
      - "JSON logging retrofit (07-04) verified by import check and grep, but Railway log format only confirmable at runtime."
      - "/resume command and 3-trip circuit breaker halt only confirmable at runtime with live Telegram and APScheduler state."
  - phase: "01-foundation"
    items:
      - "Railway deployment and Supabase schema existence require human confirmation (live infra gates, not code gaps). Flagged since Phase 1 verification."
---

# Milestone v1 Audit Report

**Milestone:** Autonomous Content Machine v1
**Audited:** 2026-03-01
**Status:** GAPS FOUND
**Auditor:** Claude (gsd audit-milestone workflow)

---

## Executive Summary

v1 milestone delivery is **functionally complete** in the codebase — all 26 requirements have working code, all cross-phase integration is wired, and 6 of 7 phases have formal VERIFICATION.md reports. However, **Phase 5 (Multi-Platform Publishing) never received a VERIFICATION.md**, creating a formal documentation gap that blocks milestone sign-off per audit rules.

Additionally, the Phase 7 E2E integration test contains a **broken assertion** that will fail when run with live credentials, and the **TikTok metrics collection path** has a functional gap (missing `/auth/tiktok` OAuth route).

These are all closable gaps. The core pipeline is production-ready.

---

## Phase Verification Status

| Phase | VERIFICATION.md | Status | Score |
|-------|----------------|--------|-------|
| 1. Foundation | ✓ Present | human_needed (2 infra gates) | 12/14 |
| 2. Script Generation | ✓ Present | passed | 4/4 |
| 3. Video Production | ✓ Present | passed (re-verified) | 19/19 |
| 4. Telegram Approval Loop | ✓ Present | passed | 10/10 |
| 5. Multi-Platform Publishing | ✗ **MISSING** | **UNVERIFIED** | — |
| 6. Analytics and Storage | ✓ Present | passed | 9/9 |
| 7. Hardening | ✓ Present | passed (re-verified) | 5/5 |

**Phase score: 6/7** — Phase 5 is an unverified phase (blocker).

Note: Phase 5 has a completed UAT document (8/8 tests passing), all 5 plan SUMMARYs with `requirements-completed` listed, and ROADMAP.md marks it Complete (2026-02-25). The missing artifact is only the formal VERIFICATION.md report.

---

## Requirements Coverage (3-Source Cross-Reference)

### Source 1: Phase VERIFICATION.md status
### Source 2: SUMMARY.md `requirements-completed` frontmatter
### Source 3: REQUIREMENTS.md traceability table checkbox

| REQ-ID | VERIFICATION.md | SUMMARY Frontmatter | REQUIREMENTS.md | Final Status |
|--------|----------------|---------------------|-----------------|--------------|
| INFRA-01 | satisfied (Phase 1) | listed (01-01, 01-03) | [x] | **satisfied** |
| INFRA-02 | human_needed infra gate | listed (01-01) | [x] | **satisfied** (live infra only) |
| INFRA-03 | satisfied | listed (01-03, 07-02) | [x] | **satisfied** |
| INFRA-04 | satisfied | listed (01-02, 07-03) | [x] | **satisfied** |
| SCRTY-01 | satisfied | listed (01-01) | [x] | **satisfied** |
| SCRTY-02 | satisfied | listed (01-02, 07-03) | [x] | **satisfied** |
| SCRP-01 | satisfied (Phase 2) | listed (02-04, 02-05, 07-01) | [x] | **satisfied** |
| SCRP-02 | satisfied | listed (02-01, 02-02, 02-05, 07-01) | [x] | **satisfied** |
| SCRP-03 | satisfied | listed (02-04, 02-05, 07-01) | [x] | **satisfied** |
| SCRP-04 | satisfied | listed (02-01, 02-03, 02-05, 07-01) | [x] | **satisfied** |
| VIDP-01 | satisfied (Phase 3) | listed (03-01, 03-02, 07-01) | [x] | **satisfied** |
| VIDP-02 | satisfied | listed (03-01, 03-02, 07-01) | [x] | **satisfied** |
| VIDP-03 | satisfied | listed (03-01, 07-01) | [x] | **satisfied** |
| VIDP-04 | satisfied | listed (03-01, 03-02, 07-01) | [x] | **satisfied** |
| TGAP-01 | satisfied (Phase 4) | listed (04-01, 04-05, 07-01, 07-02) | [x] | **satisfied** |
| TGAP-02 | satisfied | listed (04-05, 07-01, 07-02) | [x] | **satisfied** |
| TGAP-03 | satisfied | listed (04-05, 07-01, 07-02) | [x] | **satisfied** |
| TGAP-04 | satisfied | listed (04-01, 04-05, 07-01, 07-02) | [x] | **satisfied** |
| PUBL-01 | **missing** (Phase 5) | listed (05-01, 05-02, 05-03, 05-04, 05-05) | [x] | **partial** (verification gap) |
| PUBL-02 | **missing** | listed (05-01, 05-03, 05-04, 05-05) | [x] | **partial** |
| PUBL-03 | **missing** | listed (05-03, 05-05) | [x] | **partial** |
| PUBL-04 | **missing** | listed (05-03, 05-05) | [x] | **partial** |
| ANLX-01 | satisfied (Phase 6) | listed (06-01, 06-02, 06-04, 07-01) | [x] | **satisfied** (TikTok OAuth gap — see INT-02) |
| ANLX-02 | satisfied | listed (06-02, 06-05, 07-01) | [x] | **satisfied** |
| ANLX-03 | satisfied | listed (06-02, 06-04, 07-01) | [x] | **satisfied** |
| ANLX-04 | satisfied | listed (06-01, 06-03, 06-05, 07-01) | [x] | **satisfied** |

**Requirements score: 22/26 satisfied, 4/26 partial (all Phase 5)**

**Orphan detection:** No requirements present in traceability table but absent from all VERIFICATION.md files. The 4 PUBL requirements are present in SUMMARY frontmatter but absent from VERIFICATION.md (Phase 5 VERIFICATION.md is missing entirely, not just absent from those requirements).

---

## Cross-Phase Integration Findings

Integration checker verified all 26 cross-phase wiring connections. Results:

### Wired Connections (All 26/26 Requirements)

All five priority integration points from the audit brief are confirmed wired:

1. **Phase 4 → Phase 5:** `handle_approve()` → `schedule_platform_publishes()` WIRED in `approval_flow.py:91-113`. Lazy import + scheduler from `_fastapi_app.state.scheduler`. `scheduled_times` dict passed directly to `send_publish_confirmation_sync`.

2. **Phase 5 → Phase 6:** `platform_publish_job` success block schedules `harvest_metrics_job` via `DateTrigger(now+48h)` WIRED in `platform_publish.py:103-114`.

3. **Phase 7 approval_timeout → Phase 4 delivery:** `check_approval_timeout_job` fetches `video_url` from DB and calls `send_approval_message_sync` WIRED in `approval_timeout.py:91-110`. `schedule_approval_timeout()` called from `telegram.py:208-210` after approval message sent.

4. **Phase 7 `/resume` → Phase 1 circuit breaker → Phase 2 rerun:** `handle_resume()` calls `cb.clear_daily_halt()` then `trigger_immediate_rerun()` WIRED in `resume_flow.py`. Handler registered in `build_telegram_app()` with `get_creator_filter()`.

5. **Phase 4 rejection → Phase 2 constraint:** `write_rejection_constraint()` inserts into `rejection_constraints` table. `load_active_rejection_constraints()` reads it at next pipeline run WIRED via `daily_pipeline.py:66`.

### Issues Found

#### INT-01 — Orphaned Stale File (Warning)

**File:** `src/app/scheduler/jobs/circuit_breaker.py`

A stale duplicate of `app.services.circuit_breaker` that is never imported anywhere. All production code correctly imports from `app.services.circuit_breaker`. The orphan is missing Phase 7 methods: `is_daily_halted()`, `clear_daily_halt()`. Cannot cause a runtime failure (unreachable), but any future edit to the wrong file would silently have no effect.

**Affected:** INFRA-04 (authoritative implementation is correctly wired; orphan poses no live risk)

#### INT-02 — TikTok OAuth Route Missing (Warning)

`settings.py` comments reference a `/auth/tiktok` FastAPI route for TikTok OAuth authorization. No such route exists in the codebase. `tiktok_access_token` defaults to empty string. `MetricsService._fetch_tiktok()` gracefully returns `None` when token is empty. TikTok metrics collection is non-functional until creator manually populates the env var.

**Affected:** ANLX-01 (TikTok metrics non-functional by default; other 3 platforms harvest correctly)

**Note:** TikTok publishing is intentionally manual (`MANUAL_PLATFORMS = {"tiktok"}`). This gap is limited to TikTok *metrics* harvest only — TikTok *publishing* design is correct.

---

## E2E Flow Verification

| Flow | Status | Notes |
|------|--------|-------|
| Daily pipeline (script → render → approval delivery) | COMPLETE | Wired end-to-end via daily_pipeline_job → HeyGen → _process_completed_render → send_approval_message_sync |
| Approval → publish → verify (3 platforms) | COMPLETE | handle_approve → schedule_platform_publishes → publish_to_platform_job → verify_publish_job |
| Rejection → constraint → rerun | COMPLETE | handle_cause → write_rejection_constraint → trigger_immediate_rerun → next daily_pipeline_job reads constraints |
| Analytics harvest → virality alert → storage lifecycle | COMPLETE | harvest_metrics_job → check_and_alert_virality → storage_lifecycle_job → creator Telegram confirmations |
| E2E integration test (test_phase07_e2e.py) | **BROKEN** | Test assertion at line 139 will fail when ANTHROPIC_API_KEY is set (see FLOW-01 gap) |

---

## Tech Debt by Phase

### Phase 2: Script Generation (3 items)
- REQUIREMENTS.md still says "GPT-4o" / "5-Pillar" — implementation evolved to Claude / 6-Pillar (intentional, documented in CONTEXT.md). Documentation staleness only.
- Plan frontmatter requirement IDs mis-mapped in 02-02 and 02-03 (SCRP-02/SCRP-04 swapped). Documentation only, no functional impact.
- Similarity threshold 0.85 not empirically calibrated for Spanish philosophical content. Flagged in 02-05-SUMMARY.md as uncalibrated parameter.

### Phase 3: Video Production (2 items)
- `hmac.new()` deprecated alias in `webhooks.py:30`. Prefer `hmac.HMAC()`. Functional in Python 3.12.
- `_scheduler = None` module-level global in `video_poller.py`. Ordering dependency on `set_scheduler()` in `registry.py`. Correctly initialized; risk exists only if initialization order changes.

### Phase 5: Multi-Platform Publishing (2 items)
- Phase 5 VERIFICATION.md was never written (primary blocker). UAT and SUMMARYs provide coverage evidence.
- TikTok is manual-only by design. No direct API integration needed for v1.

### Phase 7: Hardening (3 items)
- E2E test assertion for `send_approval_message_sync` is incorrect — will fail with live credentials. Fix: either remove the assertion or trigger the render completion path within the test.
- JSON logging format confirmable only at runtime in Railway log viewer (code verified by import checks).
- `/resume` command and 3-trip circuit breaker halt confirmable only at runtime with live Telegram.

### Phase 1: Foundation (1 item)
- Railway deployment health check and Supabase schema existence require live infra confirmation. Flagged since Phase 1 verification (2026-02-19).

**Total: 11 tech debt items across 5 phases**

---

## Summary Table

| Category | Score | Status |
|----------|-------|--------|
| Requirements satisfied | 22/26 | 4 partial (Phase 5 verification gap) |
| Phase verifications complete | 6/7 | Phase 5 VERIFICATION.md missing |
| Integration wiring | 26/26 | All requirements wired |
| E2E flows passing | 4/5 | E2E test assertion broken |
| Orphaned code | 1 stale file | `src/app/scheduler/jobs/circuit_breaker.py` |
| Missing routes | 1 | `/auth/tiktok` OAuth route |
| Tech debt items | 11 | Across 5 phases |

---

## Closure Actions Required

To close all gaps and reach `passed` status:

1. **Write Phase 5 VERIFICATION.md** — Formal verification of PUBL-01 through PUBL-04. All evidence exists (UAT 8/8, SUMMARY frontmatter, integration checker confirms wiring). This is primarily a documentation task.

2. **Fix E2E test assertion** — Remove `mock_all_externals["approval"].assert_called_once()` from `test_phase07_e2e.py:139` or redesign the test to trigger the render completion path.

3. **Delete orphaned file** — Remove `src/app/scheduler/jobs/circuit_breaker.py` (stale, unreachable duplicate).

4. **TikTok OAuth (optional for v1)** — Either implement `/auth/tiktok` route or explicitly document TikTok metric collection as a v2 feature in REQUIREMENTS.md.

---

*Audit completed: 2026-03-01*
*Auditor: Claude (gsd-audit-milestone workflow)*
*Integration checker: gsd-integration-checker agent*
