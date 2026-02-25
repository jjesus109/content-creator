"""
Phase 5 smoke tests — Multi-Platform Publishing

Verifies the complete Phase 5 import chain and surface contracts:
  - PublishingService imports with correct methods and retry decorator
  - schedule_platform_publishes() importable with correct signature
  - Peak hour logic uses inclusive lower bound (today if approval <= peak)
  - PLATFORM_PEAK_HOURS constant has all 4 platforms with correct defaults
  - publish_to_platform_job and set_scheduler importable
  - verify_publish_job and SUCCESS_STATUSES importable
  - Telegram helpers send_publish_confirmation_sync, send_platform_success_sync,
    send_platform_failure_sync importable and callable
  - handle_approve wired to schedule_platform_publishes() + send_publish_confirmation_sync
  - registry.py injects scheduler into platform_publish at startup
  - Settings has all publishing fields (ayrshare_api_key + per-platform peaks)
  - PostCopyService.generate_platform_variants() importable with correct signature

No live DB or API calls — all checks use import/inspect only.
"""
import os
import sys

# Ensure src is on the path for all tests
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


# ---------------------------------------------------------------------------
# Check 1 — PublishingService imports and methods exist
# ---------------------------------------------------------------------------

def test_publishing_service_import():
    from app.services.publishing import PublishingService
    svc = object.__new__(PublishingService)
    assert hasattr(svc, "publish")
    assert hasattr(svc, "get_post_status")
    assert hasattr(svc, "_post")


# ---------------------------------------------------------------------------
# Check 2 — _post has tenacity retry decorator
# ---------------------------------------------------------------------------

def test_publishing_service_retry_decorator():
    import inspect
    from app.services.publishing import PublishingService
    src = inspect.getsource(PublishingService._post)
    assert "stop_after_attempt" in src or "retry" in src


# ---------------------------------------------------------------------------
# Check 3 — schedule_platform_publishes is importable with correct signature
# ---------------------------------------------------------------------------

def test_schedule_platform_publishes_import():
    from app.services.publishing import schedule_platform_publishes
    import inspect
    sig = inspect.signature(schedule_platform_publishes)
    params = list(sig.parameters.keys())
    assert "scheduler" in params
    assert "content_history_id" in params
    assert "video_url" in params
    assert "approval_time" in params


# ---------------------------------------------------------------------------
# Check 4 — Peak hour logic (today vs tomorrow, inclusive lower bound)
# ---------------------------------------------------------------------------

def test_peak_hour_today_vs_tomorrow():
    """schedule_platform_publishes correctly uses today's peak if approval is at or before peak."""
    import inspect
    from app.services.publishing import schedule_platform_publishes
    src = inspect.getsource(schedule_platform_publishes)
    # Confirm inclusive lower bound: approval_local <= today_peak_start -> today
    assert "approval_local <= today_peak_start" in src
    # Confirm timedelta(days=1) used for tomorrow
    assert "timedelta(days=1)" in src


# ---------------------------------------------------------------------------
# Check 5 — PLATFORM_PEAK_HOURS has all 4 platforms
# ---------------------------------------------------------------------------

def test_platform_peak_hours_constant():
    from app.services.publishing import PLATFORM_PEAK_HOURS
    assert set(PLATFORM_PEAK_HOURS.keys()) == {"tiktok", "instagram", "facebook", "youtube"}
    assert PLATFORM_PEAK_HOURS["tiktok"] == 19
    assert PLATFORM_PEAK_HOURS["instagram"] == 11
    assert PLATFORM_PEAK_HOURS["facebook"] == 13
    assert PLATFORM_PEAK_HOURS["youtube"] == 12


# ---------------------------------------------------------------------------
# Check 6 — platform_publish job imports and set_scheduler exists
# ---------------------------------------------------------------------------

def test_platform_publish_job_import():
    from app.scheduler.jobs.platform_publish import publish_to_platform_job, set_scheduler
    import inspect
    sig = inspect.signature(publish_to_platform_job)
    params = list(sig.parameters.keys())
    assert "content_history_id" in params
    assert "platform" in params
    assert "video_url" in params


# ---------------------------------------------------------------------------
# Check 7 — verify_publish_job imports and SUCCESS_STATUSES defined
# ---------------------------------------------------------------------------

def test_verify_publish_job_import():
    from app.scheduler.jobs.publish_verify import verify_publish_job, SUCCESS_STATUSES
    import inspect
    sig = inspect.signature(verify_publish_job)
    params = list(sig.parameters.keys())
    assert "content_history_id" in params
    assert "platform" in params
    assert "ayrshare_post_id" in params
    assert "completed" in SUCCESS_STATUSES


# ---------------------------------------------------------------------------
# Check 8 — Telegram helpers exist
# ---------------------------------------------------------------------------

def test_telegram_publish_helpers():
    from app.services.telegram import (
        send_publish_confirmation_sync,
        send_platform_success_sync,
        send_platform_failure_sync,
    )
    import inspect
    # Confirm all 3 are callable sync functions
    assert callable(send_publish_confirmation_sync)
    assert callable(send_platform_success_sync)
    assert callable(send_platform_failure_sync)


# ---------------------------------------------------------------------------
# Check 9 — approval_flow handle_approve is wired to schedule_platform_publishes
# ---------------------------------------------------------------------------

def test_approval_flow_wired_to_publishing():
    import inspect
    from app.telegram.handlers.approval_flow import handle_approve
    src = inspect.getsource(handle_approve)
    assert "schedule_platform_publishes" in src
    assert "send_publish_confirmation_sync" in src
    assert "video_url" in src


# ---------------------------------------------------------------------------
# Check 10 — registry.py injects scheduler into platform_publish
# ---------------------------------------------------------------------------

def test_registry_injects_platform_publish_scheduler():
    import inspect
    from app.scheduler import registry
    src = inspect.getsource(registry.register_jobs)
    assert "platform_publish" in src or "set_publish_scheduler" in src


# ---------------------------------------------------------------------------
# Check 11 — Settings has new publishing fields
# ---------------------------------------------------------------------------

def test_settings_has_publishing_fields():
    from app.settings import Settings
    fields = Settings.model_fields
    assert "ayrshare_api_key" in fields
    assert "audience_timezone" in fields
    assert "peak_hour_tiktok" in fields
    assert "peak_hour_instagram" in fields
    assert "peak_hour_facebook" in fields
    assert "peak_hour_youtube" in fields


# ---------------------------------------------------------------------------
# Check 12 — PostCopyService has generate_platform_variants
# ---------------------------------------------------------------------------

def test_post_copy_service_has_platform_variants():
    from app.services.post_copy import PostCopyService
    assert hasattr(PostCopyService, "generate_platform_variants")
    import inspect
    sig = inspect.signature(PostCopyService.generate_platform_variants)
    params = list(sig.parameters.keys())
    assert "script_text" in params
    assert "topic_summary" in params
