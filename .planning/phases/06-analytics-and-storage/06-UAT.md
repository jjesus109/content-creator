---
status: complete
phase: 06-analytics-and-storage
source: [06-01-SUMMARY.md, 06-02-SUMMARY.md, 06-03-SUMMARY.md, 06-04-SUMMARY.md, 06-05-SUMMARY.md]
started: 2026-02-28T20:45:00Z
updated: 2026-03-01T00:30:00Z
---

## Current Test

[testing complete]

## Tests

### 1. Migration SQL is syntactically valid and contains required tables
expected: Run migrations/0006_analytics.sql against Supabase. Migration completes without errors. platform_metrics table exists (14 cols). content_history gains 5 lifecycle columns (storage_status, storage_tier_set_at, deletion_requested_at, is_viral, is_eternal).
result: pass

### 2. Service imports load without ValidationError
expected: Running `uv run python -c "from app.services.metrics import MetricsService; from app.services.analytics import AnalyticsService; from app.services.storage_lifecycle import StorageLifecycleService; print('OK')"` prints "OK" with no error — even without .env populated.
result: pass

### 3. Virality alert message format
expected: Running `uv run python -c "from app.services.analytics import format_virality_alert; print(format_virality_alert('youtube', '2026-02-28', 12500))"` prints a minimal alert — platform name, video date, view count. No baseline, no percentage.
result: pass

### 4. Sparkline function
expected: Running `uv run python -c "from app.services.analytics import sparkline; print(sparkline([100, 250, 500, 1200]))"` prints 4 Unicode block characters showing an ascending trend (e.g., ▂▄▆█).
result: pass

### 5. Weekly report renders N/A for first-week with no prior data
expected: Running `uv run python -c "from app.services.analytics import format_weekly_report; print(format_weekly_report([], None))"` outputs a weekly report that shows "N/A" where pct_change would appear (no crash, no KeyError).
result: pass

### 6. Storage lifecycle job registered in scheduler registry
expected: Running `uv run python -c "from app.scheduler.registry import register_jobs; import inspect; src = inspect.getsource(register_jobs); print('storage_lifecycle_cron' in src and 'weekly_analytics_report' in src)"` prints "True".
result: pass

### 7. Harvest job scheduled 48h after publish
expected: Running `uv run python -c "from app.scheduler.jobs.platform_publish import publish_to_platform_job; import inspect; src = inspect.getsource(publish_to_platform_job); print('harvest_metrics_job' in src and '48' in src)"` prints "True".
result: pass

### 8. Storage Telegram handlers registered in app.py
expected: Running `uv run python -c "from app.telegram.app import build_telegram_app; import inspect; src = inspect.getsource(build_telegram_app); print('register_storage_handlers' in src)"` prints "True".
result: pass

### 9. 7-day storage warning Telegram message content
expected: Running `uv run python -c "from app.services.storage_lifecycle import StorageLifecycleService; import inspect; src = inspect.getsource(StorageLifecycleService.send_7day_warning); print('stor_eternal' in src and 'stor_warn_ok' in src)"` prints "True" — both button callback prefixes present in the warning message builder.
result: pass

### 10. Deletion confirmation Telegram message content
expected: Running `uv run python -c "from app.services.storage_lifecycle import StorageLifecycleService; import inspect; src = inspect.getsource(StorageLifecycleService.request_deletion_confirmation); print('stor_confirm' in src and 'stor_cancel' in src)"` prints "True" — both button callback prefixes present in the deletion confirmation builder.
result: pass

## Summary

total: 10
passed: 10
issues: 0
pending: 0
skipped: 0

## Gaps

[none yet]
