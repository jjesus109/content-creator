"""
Phase 7 end-to-end integration test.

Tests the full pipeline chain by calling daily_pipeline_job() directly
(no APScheduler needed). Key design decisions:

- Real Anthropic API: actual script generation runs with live credentials.
  ANTHROPIC_API_KEY must be set in the environment; test is skipped if absent.
- Mocked externals: HeyGen, video poller, and Telegram are mocked so no
  real HTTP calls leave the process during test runs.
- Real Supabase connection: the test writes a real content_history row and
  reads it back to confirm the full DB write path works end-to-end.

Patch targets follow the "patch where looked up" rule (Python mock docs):
- HeyGenService is imported lazily inside daily_pipeline_job() body via
  `from app.services.heygen import HeyGenService` — patch the source module.
- register_video_poller is also a lazy import in the function body — same rule.
- send_alert_sync and send_approval_message_sync are module-level imports in
  daily_pipeline.py — patch at the definition module (app.services.telegram).

See RESEARCH.md Pitfall 1 for detailed explanation of lazy import patch targets.
See RESEARCH.md Pitfall 6 for full list of required mocks to avoid APScheduler errors.
See RESEARCH.md Pitfall 7 for get_settings() lru_cache teardown requirement.
"""
import os
import sys

# Ensure src is on the path for all imports (same pattern as test_phase05_smoke.py)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest
from unittest.mock import patch, MagicMock

# Mark all tests in this module as e2e
pytestmark = pytest.mark.e2e


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def clear_lru_cache():
    """
    Clear get_settings() lru_cache after each test.
    Prevents stale cached Settings instances leaking between tests.
    (Pitfall 7: lru_cache is process-wide and persists across test calls.)
    """
    yield
    from app.settings import get_settings
    get_settings.cache_clear()


@pytest.fixture
def mock_all_externals():
    """
    Mock all external API calls for the E2E pipeline test.

    Mocked:
    - app.services.heygen.HeyGenService — submit() returns fake job ID
    - app.scheduler.jobs.video_poller.register_video_poller — no-op
    - app.services.telegram.send_alert_sync — capture calls
    - app.services.telegram.send_approval_message_sync — capture calls

    NOT mocked (locked decision from CONTEXT.md):
    - Anthropic API — real script generation must run

    Yields a dict of mocks keyed by short name for assertion access.
    """
    with patch("app.services.heygen.HeyGenService") as mock_heygen_cls, \
         patch("app.scheduler.jobs.video_poller.register_video_poller") as mock_poller, \
         patch("app.services.telegram.send_alert_sync") as mock_alert, \
         patch("app.services.telegram.send_approval_message_sync") as mock_approval:

        # Configure the HeyGen service instance mock
        mock_heygen_instance = mock_heygen_cls.return_value
        mock_heygen_instance.submit.return_value = "fake-heygen-job-id-e2e"

        yield {
            "heygen": mock_heygen_instance,
            "poller": mock_poller,
            "alert": mock_alert,
            "approval": mock_approval,
        }


# ---------------------------------------------------------------------------
# End-to-end test
# ---------------------------------------------------------------------------

@pytest.mark.skipif(
    not os.getenv("ANTHROPIC_API_KEY"),
    reason="ANTHROPIC_API_KEY not set — E2E skipped"
)
def test_daily_pipeline_writes_content_history(mock_all_externals):
    """
    Full pipeline integration test.

    Calls daily_pipeline_job() with:
    - Real Anthropic API (actual script generation)
    - Mocked HeyGen (fake job ID returned)
    - Mocked video poller (no APScheduler scheduler needed)
    - Mocked Telegram (no real bot calls)

    Asserts:
    - content_history row created with heygen_job_id == "fake-heygen-job-id-e2e"
    - video_status == "pending_render"
    - script_text is non-empty
    - HeyGen submit was called exactly once
    - send_approval_message_sync was called exactly once (Telegram delivery happened)
    """
    # Import inside test body to avoid module-level import before sys.path is set
    from app.scheduler.jobs.daily_pipeline import daily_pipeline_job
    from app.services.database import get_supabase

    # Run the full pipeline
    daily_pipeline_job()

    # Read back the most recently created content_history row
    supabase = get_supabase()
    rows = supabase.table("content_history").select("*").order(
        "created_at", desc=True
    ).limit(1).execute()

    assert rows.data, "Expected a content_history row to be created, but none found"
    row = rows.data[0]

    # Core assertions — pipeline wrote expected fields
    assert row["heygen_job_id"] == "fake-heygen-job-id-e2e", (
        f"Expected heygen_job_id='fake-heygen-job-id-e2e', got {row.get('heygen_job_id')!r}"
    )
    assert row["video_status"] == "pending_render", (
        f"Expected video_status='pending_render', got {row.get('video_status')!r}"
    )
    assert row["script_text"], "Expected non-empty script_text in content_history row"

    # Mock invocation assertions — externals were called exactly once
    mock_all_externals["heygen"].submit.assert_called_once()
    mock_all_externals["approval"].assert_called_once()


# ---------------------------------------------------------------------------
# Render completion fixture and test (FLOW-01 gap closure)
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_render_completion_externals():
    """
    Mock the three callables _process_completed_render() uses via lazy import.

    Patch targets follow the "patch where looked up" rule — all three are
    lazy-imported inside the function body, so patch at the source module:
    - app.services.audio_processing.AudioProcessingService
    - app.services.video_storage.VideoStorageService
    - app.services.telegram.send_approval_message_sync

    Yields a dict keyed by short name for assertion access.
    """
    with patch("app.services.audio_processing.AudioProcessingService") as mock_audio_cls, \
         patch("app.services.video_storage.VideoStorageService") as mock_storage_cls, \
         patch("app.services.telegram.send_approval_message_sync") as mock_approval:

        # Configure return values for the service instances
        mock_audio_cls.return_value.process_video_audio.return_value = b"fake-video-bytes"
        mock_storage_cls.return_value.upload.return_value = "https://storage.supabase.co/fake.mp4"

        yield {
            "audio": mock_audio_cls.return_value,
            "storage": mock_storage_cls.return_value,
            "approval": mock_approval,
        }


@pytest.mark.skipif(
    not os.getenv("SUPABASE_URL") or not os.getenv("SUPABASE_KEY"),
    reason="SUPABASE_URL/SUPABASE_KEY not set — render completion test skipped"
)
def test_render_completion_sends_approval_message(mock_render_completion_externals):
    """
    Verify that _process_completed_render() calls send_approval_message_sync exactly once.

    Targets the render-completion code path (FLOW-01 gap closure):
    _process_completed_render(video_id, heygen_signed_url)
      -> send_approval_message_sync(content_history_id=..., video_url=...)

    Uses a real Supabase connection to insert a content_history row with
    video_status='pending_render', calls _process_completed_render() directly,
    asserts the approval message was sent with the correct content_history_id,
    then cleans up the inserted row.
    """
    from app.services.heygen import _process_completed_render
    from app.services.database import get_supabase

    supabase = get_supabase()

    # Insert a content_history row in pending_render state for the double-processing guard to pass
    insert_result = supabase.table("content_history").insert({
        "heygen_job_id": "test-render-job-e2e",
        "video_status": "pending_render",
        "script_text": "Test script for render completion E2E",
        "topic_summary": "test topic",
    }).execute()

    assert insert_result.data, "Failed to insert test content_history row"
    content_history_id = insert_result.data[0]["id"]

    try:
        _process_completed_render(
            video_id="test-render-job-e2e",
            heygen_signed_url="https://fake-heygen-signed.url/video.mp4",
        )

        # Assert approval message was sent exactly once
        mock_render_completion_externals["approval"].assert_called_once()

        # Assert the correct content_history_id was passed as a keyword argument
        call_kwargs = mock_render_completion_externals["approval"].call_args
        assert call_kwargs.kwargs["content_history_id"] == content_history_id, (
            f"Expected content_history_id={content_history_id!r}, "
            f"got {call_kwargs.kwargs.get('content_history_id')!r}"
        )
    finally:
        # Clean up the inserted row regardless of test outcome
        supabase.table("content_history").delete().eq("id", content_history_id).execute()
