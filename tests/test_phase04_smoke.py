"""
Phase 4 smoke tests — Telegram Approval Loop

Verifies the complete Phase 4 import chain and surface contracts:
  - Migration 0004 SQL file exists and is syntactically complete
  - ApprovalService exposes all required methods
  - PostCopyService and extract_thumbnail importable with correct signatures
  - send_approval_message_sync exists in services/telegram.py
  - trigger_immediate_rerun exists in scheduler/jobs/daily_pipeline.py
  - approval_flow handler imports and callback prefix constants correct
  - callback_data byte lengths within Telegram's 64-byte limit
  - register_approval_handlers called in build_telegram_app

No live DB or API calls — all checks use import/inspect only.
"""
import os
import sys

# Ensure src is on the path for all tests
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


# ---------------------------------------------------------------------------
# Check 1 — migration file exists and is complete
# ---------------------------------------------------------------------------

def test_migration_0004_exists():
    path = os.path.join(os.path.dirname(__file__), "..", "migrations", "0004_approval_events.sql")
    assert os.path.exists(path), "migrations/0004_approval_events.sql not found"
    content = open(path).read()
    assert "approval_events" in content
    assert "post_copy" in content
    assert "rejection_requires_cause" in content


# ---------------------------------------------------------------------------
# Check 2 — ApprovalService import and method surface
# ---------------------------------------------------------------------------

def test_approval_service_methods():
    import inspect
    from app.services.approval import ApprovalService
    for method in ["is_already_actioned", "record_approve", "record_reject",
                   "get_today_rejection_count", "write_rejection_constraint",
                   "clear_constraints_for_approved_run"]:
        assert method in ApprovalService.__dict__, f"Missing method: {method}"


# ---------------------------------------------------------------------------
# Check 3 — PostCopyService import
# ---------------------------------------------------------------------------

def test_post_copy_service_importable():
    import inspect
    from app.services.post_copy import PostCopyService, extract_thumbnail
    assert callable(PostCopyService)
    assert callable(extract_thumbnail)
    sig = inspect.signature(extract_thumbnail)
    assert "video_url" in sig.parameters


def test_extract_thumbnail_ffmpeg_flags():
    """Asserts extract_thumbnail uses temp-file approach and ffmpeg 7.x safe flags."""
    import inspect
    from app.services.post_copy import extract_thumbnail
    src = inspect.getsource(extract_thumbnail)
    assert "NamedTemporaryFile" in src, "Must use temp file (not pipe:0)"
    assert "pipe:0" not in src, "pipe:0 causes partial-file EOF — must be removed"
    assert "yuvj420p" in src, "Must set pix_fmt yuvj420p for ffmpeg 7.x mjpeg"
    assert "unofficial" in src, "Must include -strict unofficial for mjpeg encoder"


# ---------------------------------------------------------------------------
# Check 4 — send_approval_message_sync in services/telegram.py
# ---------------------------------------------------------------------------

def test_send_approval_message_sync_exists():
    import inspect
    from app.services.telegram import send_approval_message_sync
    sig = inspect.signature(send_approval_message_sync)
    assert "content_history_id" in sig.parameters
    assert "video_url" in sig.parameters


# ---------------------------------------------------------------------------
# Check 5 — trigger_immediate_rerun in daily_pipeline.py
# ---------------------------------------------------------------------------

def test_trigger_immediate_rerun_exists():
    from app.scheduler.jobs.daily_pipeline import trigger_immediate_rerun
    assert callable(trigger_immediate_rerun)


# ---------------------------------------------------------------------------
# Check 6 — approval_flow handler imports and prefix constants
# ---------------------------------------------------------------------------

def test_approval_flow_imports():
    from app.telegram.handlers.approval_flow import (
        register_approval_handlers, PREFIX_APPROVE, PREFIX_REJECT, PREFIX_CAUSE,
        handle_approve, handle_reject, handle_cause
    )
    assert PREFIX_APPROVE == "appr_approve:"
    assert PREFIX_REJECT  == "appr_reject:"
    assert PREFIX_CAUSE   == "appr_cause:"
    # No collision with Phase 2 mood_flow prefixes
    mood_prefixes = ["mood_pool:", "mood_tone:", "mood_duration:"]
    for mp in mood_prefixes:
        assert not PREFIX_APPROVE.startswith(mp[:4])
        assert not PREFIX_REJECT.startswith(mp[:4])
        assert not PREFIX_CAUSE.startswith(mp[:4])


# ---------------------------------------------------------------------------
# Check 7 — callback_data byte limit for technical_error (longest cause code)
# ---------------------------------------------------------------------------

def test_callback_data_byte_limit():
    import uuid
    # Longest possible callback_data: appr_cause: + UUID + : + technical_error
    test_id = str(uuid.uuid4())  # 36 chars
    longest = f"appr_cause:{test_id}:technical_error"
    assert len(longest.encode("utf-8")) <= 64, (
        f"callback_data too long: {len(longest.encode('utf-8'))} bytes: {longest}"
    )


# ---------------------------------------------------------------------------
# Check 8 — register_approval_handlers registered in build_telegram_app
# ---------------------------------------------------------------------------

def test_register_approval_handlers_called_in_build():
    import inspect
    from app.telegram import app as tg_app_module
    source = inspect.getsource(tg_app_module.build_telegram_app)
    assert "register_approval_handlers" in source, (
        "register_approval_handlers not called in build_telegram_app()"
    )
