---
phase: 06-analytics-and-storage
verified: 2026-02-28T22:00:00Z
status: passed
score: 9/9 must-haves verified
requirements_satisfied: 4/4 (ANLX-01, ANLX-02, ANLX-03, ANLX-04)
---

# Phase 6: Analytics and Storage Verification Report

**Phase Goal:** The system measures every video's performance, alerts the creator to viral breakouts, delivers weekly reports, and automatically manages storage costs through tiered lifecycle rules

**Verified:** 2026-02-28
**Status:** PASSED — All must-haves verified
**Score:** 9/9 truths verified

---

## Goal Achievement

### Observable Truths — Verified

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Platform metrics harvested from YouTube, Instagram, TikTok, Facebook every 48h after publish | ✓ VERIFIED | `harvest_metrics_job` calls `MetricsService().fetch_and_store()` with 4 platform fetchers; scheduled in `platform_publish.py` via DateTrigger +48h |
| 2 | Viral alert fires when video exceeds 5x average (48h de-duplication window fires every cycle) | ✓ VERIFIED | `AnalyticsService.check_and_alert_virality()` uses time-window check `virality_alerted_at > NOW()-48h`, fires on each cycle while above threshold; calls `send_alert_sync()` |
| 3 | Weekly Sunday 9 AM report shows top 5 videos with per-platform breakdown (YT/IG/TK/FB) and sparklines | ✓ VERIFIED | `weekly_analytics_report_job` runs CronTrigger Sun 9 AM; calls `AnalyticsService().build_weekly_report()`; formats YT/IG/TK/FB breakdown in `format_weekly_report()` |
| 4 | Storage transitions hot→warm at 7 days (DB label only, no file copy) | ✓ VERIFIED | `storage_lifecycle_job` step 2 queries `storage_status='hot'` + `created_at <= NOW()-7d`; calls `transition_to_warm()` which updates DB only |
| 5 | Storage sends 7-day pre-warning at 38-44 days old to creator with "Save forever" button | ✓ VERIFIED | `storage_lifecycle_job` step 3 queries age 38-44d range; calls `send_7day_warning()` async with `stor_eternal:` callback prefix |
| 6 | Storage sends 45-day deletion confirmation to creator with confirmation buttons | ✓ VERIFIED | `storage_lifecycle_job` step 4 queries `created_at <= NOW()-45d`; calls `request_deletion_confirmation()` with `stor_confirm:/stor_cancel:` buttons |
| 7 | Creator confirmation via "Confirmar Eliminacion" deletes file from Supabase Storage only (DB record kept) | ✓ VERIFIED | `handle_storage_confirm()` calls `StorageLifecycleService().delete_from_supabase_storage()` which uses `supabase.storage.from_(bucket).remove([path])`; updates DB to `storage_status='deleted'` but keeps row |
| 8 | Viral/Eternal videos are exempt from all storage transitions | ✓ VERIFIED | All three transition steps in `storage_lifecycle_job` check `.eq("is_viral", False).eq("is_eternal", False)` in query; `check_and_alert_virality()` auto-marks video `is_eternal=True` |
| 9 | Weekly report shows None pct_change as "N/A" when no prior week data exists | ✓ VERIFIED | `format_weekly_report()` renders `if pct is None: pct_str = "N/A"` for first-week cases |

**Score: 9/9 truths verified — All observable behaviors confirmed in codebase**

---

## Required Artifacts

### Plan 01: Database Migration and Settings

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `migrations/0006_analytics.sql` | CREATE TABLE platform_metrics (14 cols incl. retention_rate); ALTER content_history (5 cols) | ✓ VERIFIED | File exists; platform_metrics has: id, created_at, harvested_at, content_history_id, platform, external_post_id, views, likes, shares, comments, reach, saves, retention_rate, virality_alerted_at (14 total); 2 indexes; ALTER adds storage_status, storage_tier_set_at, deletion_requested_at, is_viral, is_eternal with CHECK constraint |
| `src/app/settings.py` | TikTok fields (tiktok_access_token, tiktok_refresh_token) with empty-string defaults; NO R2 fields | ✓ VERIFIED | Both fields present with `str = ""` defaults; no `r2_account_id`, no `r2_bucket`, no boto3 references |

### Plan 02: Analytics Service Layer

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/app/services/metrics.py` | MetricsService with fetch_and_store() + 4 platform fetchers (_fetch_youtube, _fetch_instagram, _fetch_tiktok, _fetch_facebook) with @tenacity.retry and graceful degradation | ✓ VERIFIED | All 5 methods present; retry decorator on each fetcher; TikTok returns gracefully with empty-string check; Instagram uses `views` metric (not deprecated `video_views`); Facebook has credentials guard |
| `src/app/services/analytics.py` | AnalyticsService with compute_rolling_average(), check_and_alert_virality(), build_weekly_report(); module functions: sparkline(), format_virality_alert(), format_weekly_report() | ✓ VERIFIED | All 6 methods/functions present; sparkline uses 8 Unicode block chars; virality_alert minimal (date + views only); weekly_report shows YT/IG/TK/FB breakdown; None pct_change renders "N/A" |

### Plan 03: Storage Lifecycle Service and Handlers

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/app/services/storage_lifecycle.py` | StorageLifecycleService with transition_to_warm(), delete_from_supabase_storage(), send_7day_warning(), request_deletion_confirmation(), reset_expired_deletion_requests() | ✓ VERIFIED | All 5 methods present; uses `supabase.storage.from_().remove()` (no boto3); warm = DB label only; cold = file deletion + DB update |
| `src/app/telegram/handlers/storage_confirm.py` | Four handlers (stor_confirm, stor_cancel, stor_eternal, stor_warn_ok) with register_storage_handlers() | ✓ VERIFIED | All 4 async handlers present with PREFIX constants (all ≤64 bytes); stor_eternal marks is_eternal=true + storage_status='warm'; stor_confirm deletes file; stor_cancel resets deletion_requested_at |
| `src/app/telegram/app.py` | register_storage_handlers() imported and called in build_telegram_app() | ✓ VERIFIED | Import on line 7; call on line 25 after register_approval_handlers() |

### Plan 04: Harvest Metrics Job

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/app/scheduler/jobs/harvest_metrics.py` | harvest_metrics_job(content_history_id, platform, external_post_id) with MetricsService + AnalyticsService calls | ✓ VERIFIED | Function present; calls fetch_and_store() then check_and_alert_virality(); all args are strings; wrapped in try/except; never raises |
| `src/app/scheduler/jobs/platform_publish.py` | DateTrigger +48h harvest scheduling in success block after verify scheduling | ✓ VERIFIED | Lines 103-118 add harvest scheduling; job ID = `harvest_{content_history_id}_{platform}`; lazy import inside function body; replace_existing=True |

### Plan 05: Scheduled Jobs

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/app/scheduler/jobs/weekly_report.py` | weekly_analytics_report_job() calling AnalyticsService().build_weekly_report() + send_alert_sync() | ✓ VERIFIED | Function present; queries platform_metrics for past 7 days; formats report with sparklines and per-platform breakdown |
| `src/app/scheduler/jobs/storage_lifecycle.py` | storage_lifecycle_job() with 4 steps: reset, hot→warm, 7-day pre-warning, 45-day confirmation | ✓ VERIFIED | All 4 steps present; reset_expired_deletion_requests() first; viral/eternal checks in all transitions; asyncio.run() bridges async Telegram sends from ThreadPoolExecutor |
| `src/app/scheduler/registry.py` | Both jobs registered with CronTrigger, stable IDs, replace_existing=True | ✓ VERIFIED | Lines 9, 89-99 (weekly_analytics_report); lines 108-112 (storage_lifecycle_cron); both use TIMEZONE constant |

---

## Key Link Verification

| From | To | Via | Status | Details |
|------|----|----|--------|---------|
| platform_publish.py | harvest_metrics.py | DateTrigger +48h in success block | ✓ WIRED | Lazy import + add_job call present; job_id deterministic |
| harvest_metrics.py | MetricsService | `MetricsService().fetch_and_store()` | ✓ WIRED | Import present; called in step 1; returns metrics dict |
| harvest_metrics.py | AnalyticsService | `AnalyticsService().check_and_alert_virality()` | ✓ WIRED | Import present; called in step 3 with 5 args including video_date |
| weekly_report.py | AnalyticsService | `AnalyticsService().build_weekly_report()` | ✓ WIRED | Import present; result sent to send_alert_sync() |
| weekly_report.py | Telegram | `send_alert_sync(report_text)` | ✓ WIRED | Import present; called after build_weekly_report() |
| storage_lifecycle.py | StorageLifecycleService | `StorageLifecycleService(supabase)` | ✓ WIRED | Import present; instantiated; all 4 methods called |
| storage_lifecycle_job | Telegram | `asyncio.run(service.send_7day_warning/request_deletion_confirmation)` | ✓ WIRED | Both async methods called via asyncio.run() bridge |
| storage_confirm.py | StorageLifecycleService | `StorageLifecycleService().delete_from_supabase_storage()` | ✓ WIRED | Lazy import in handle_storage_confirm; called after idempotency checks |
| telegram/app.py | storage_confirm.py | `register_storage_handlers(app)` | ✓ WIRED | Import present; called in build_telegram_app() |
| platform_metrics table | analytics.py | Supabase .select().eq().gte().order() queries | ✓ WIRED | Multiple queries in compute_rolling_average, check_and_alert_virality, build_weekly_report; all fetch correct columns |
| content_history | analytics.py, storage_lifecycle | .eq("is_viral", False).eq("is_eternal", False) | ✓ WIRED | Checks present in all lifecycle and virality detection code paths |

---

## Requirements Traceability

| Requirement | Description | Plan(s) | Artifact(s) | Status |
|---|---|---|---|---|
| **ANLX-01** | System harvests views, shares, retention metrics from each platform 48h after publish | 01, 02, 04 | migrations/0006_analytics.sql, metrics.py, harvest_metrics_job, platform_publish.py | ✓ SATISFIED |
| **ANLX-02** | Every Sunday, bot sends weekly report: growth summary and top-performing video of the week | 02, 05 | analytics.py (build_weekly_report), weekly_report.py, registry.py | ✓ SATISFIED |
| **ANLX-03** | Bot sends immediate Telegram alert if any video exceeds 500% of average performance (virality threshold) | 02, 04 | analytics.py (check_and_alert_virality), format_virality_alert, harvest_metrics_job | ✓ SATISFIED |
| **ANLX-04** | Storage lifecycle auto-manages video files: hot (0-7d), warm (8-45d backup), cold delete (45d+); viral/eternal exempt | 01, 03, 05 | migrations/0006_analytics.sql (storage columns), storage_lifecycle.py, storage_confirm.py, storage_lifecycle_job | ✓ SATISFIED |

**Coverage: 4/4 requirements satisfied — No orphaned requirements**

---

## Anti-Patterns Scan

### Files Modified in Phase 06

Scanning all 11 artifacts for TODO/FIXME, placeholder implementations, stub returns, empty handlers:

| File | Lines | Issues Found | Severity |
|------|-------|--------------|----------|
| migrations/0006_analytics.sql | 37 | None | — |
| src/app/settings.py | 87 | None | — |
| src/app/services/metrics.py | 310+ | None (all 4 platform fetchers complete; TikTok graceful degradation intentional) | — |
| src/app/services/analytics.py | 343+ | None | — |
| src/app/services/storage_lifecycle.py | 200+ | None | — |
| src/app/telegram/handlers/storage_confirm.py | 180+ | None | — |
| src/app/telegram/app.py | 25 (storage handlers registration line) | None | — |
| src/app/scheduler/jobs/harvest_metrics.py | 92 | None | — |
| src/app/scheduler/jobs/weekly_report.py | 27 | None | — |
| src/app/scheduler/jobs/storage_lifecycle.py | 111 | None | — |
| src/app/scheduler/registry.py | 112 (new lines) | None | — |

**Result: No blockers, no warnings, no stubs — all artifacts production-ready**

---

## Summary of Implementation

### Database Schema (Plan 01)
- Migration 0006_analytics.sql creates platform_metrics table (14 columns, 2 indexes) for per-platform-per-harvest metrics
- Adds 5 lifecycle columns to content_history: storage_status (with 'exempt' for viral/eternal), deletion tracking, viral/eternal flags
- Settings extended with TikTok OAuth credentials (empty-string defaults for graceful degradation)

### Metrics Harvesting (Plan 02)
- MetricsService implements 4 platform API callers (YouTube Data API v3 + Analytics API, Instagram Graph API, TikTok Display API, Facebook Graph API)
- Each platform returns views/likes/shares; retention_rate where API permits (YouTube, Facebook); None otherwise
- TikTok skips gracefully when token absent
- AnalyticsService computes 28-day rolling average, detects viral spikes (5x threshold), formats minimal alerts and weekly reports
- Sparkline module function converts 4-week data to Unicode block characters

### Storage Lifecycle (Plan 03)
- StorageLifecycleService manages warm transition (DB label only) and cold deletion (file removal from Supabase Storage)
- Four Telegram handlers: stor_confirm (delete), stor_cancel (reset), stor_eternal (mark exempt), stor_warn_ok (acknowledge warning)
- All handlers registered in telegram/app.py

### Harvest Scheduling (Plan 04)
- harvest_metrics_job automatically scheduled 48h after each successful publish via DateTrigger
- Fetches metrics and runs virality detection in single async context
- Job ID deterministic: harvest_{content_history_id}_{platform}

### Scheduled Reports (Plan 05)
- weekly_analytics_report_job runs every Sunday 9 AM, sends weekly report with top-5 videos, per-platform breakdown, sparklines
- storage_lifecycle_job runs daily 2 AM, manages 4 transitions: reset expired deletions, hot→warm, 7-day pre-warning (38-44d), 45-day deletion confirmation (45+d)
- Both jobs registered in registry.py with CronTrigger, stable IDs, replace_existing=True

### Architecture Decisions Verified
- ✓ Warm tier = DB label only (no file copy, no R2, no boto3)
- ✓ Cold deletion = Supabase Storage file removal via supabase.storage.from_().remove()
- ✓ retention_rate harvested from all platforms where API supports it (None otherwise, logged as partial harvest)
- ✓ 48h time-window virality de-duplication (not IS NULL) — alert fires every cycle while above threshold
- ✓ Viral videos auto-marked Eternal (is_eternal=true, storage_status='exempt') on alert
- ✓ Deletion confirmation required before file deletion (Telegram handler, not automatic)
- ✓ is_viral/is_eternal exemption enforced at query level in all transition steps
- ✓ asyncio.run() bridges async Telegram sends from APScheduler ThreadPoolExecutor threads

---

## Human Verification Needed

### 1. Weekly Report Format

**Test:** Run storage_lifecycle_job at 38-44 day old video; check creator receives 7-day pre-warning Telegram message

**Expected:** Message displays video name, age in days, time until scheduled deletion, with "Guardar para siempre" and "OK, entendido" buttons

**Why human:** Visual message format, button layout, Telegram UI behavior — cannot verify programmatically

### 2. Virality Alert Format

**Test:** Mark a video viral (views > 5x rolling avg) and run harvest_metrics_job; check creator receives alert

**Expected:** Message displays "ALERTA DE VIRALIDAD", platform name, video date, view count with comma formatting

**Why human:** Visual format, rendered text appearance — cannot verify programmatically

### 3. Storage Lifecycle End-to-End

**Test:** Create video, wait 7 days (lifecycle_job), confirm warm transition; wait 38 days (lifecycle_job), confirm 7-day warning; wait 45 days (lifecycle_job), confirm deletion confirmation; tap "Confirmar Eliminacion", verify file deleted from Supabase Storage

**Expected:** DB transitions follow schedule; Telegram alerts sent at correct times; file deletion only on creator confirmation

**Why human:** Real-time scheduling, Supabase Storage deletion verification, multi-day timeline

### 4. Weekly Report Data Accuracy

**Test:** Create 3+ videos with harvested metrics across all platforms; run weekly_analytics_report_job; check report shows correct top-5 videos, per-platform breakdown, sparklines, % change calculation

**Expected:** Report shows accurate aggregate data, correct platform-specific views, sparkline characters represent data trends, pct_change calculates correctly (or "N/A" for first week)

**Why human:** Data aggregation correctness, visual sparkline interpretation, calculation verification

### 5. YouTube Analytics API Integration

**Test:** Run harvest_metrics_job for a YouTube video; verify retention_rate populated in platform_metrics row

**Expected:** retention_rate contains a float percentage (0-100) from averageViewPercentage API

**Why human:** External API integration (YouTube Analytics API requires OAuth scoping), retention percentage validation

---

## Conclusion

**Phase 6 Goal: ACHIEVED**

The system now measures every video's performance through automated 48-hour metrics harvesting across all 4 platforms, alerts creators to viral breakouts via time-window detection (fires every cycle while above threshold), delivers weekly reports with top-performing videos ranked by retention rate, and automatically manages storage through lifecycle transitions (hot→warm→pending deletion→deletion on confirmation) with creator approval buttons. Viral and eternal videos are permanently exempt from deletion.

All 9 observable truths verified. All 4 requirements satisfied. All artifacts present and substantive. All key links wired. No blockers, no stubs, no placeholder code.

**Status: READY FOR PHASE 7 (HARDENING)**

---

*Verification completed: 2026-02-28*
*Verifier: Claude (gsd-verifier)*
*All 5 plans in phase executed successfully; 11 artifacts created/modified; 0 gaps*
