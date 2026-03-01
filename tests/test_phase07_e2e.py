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
