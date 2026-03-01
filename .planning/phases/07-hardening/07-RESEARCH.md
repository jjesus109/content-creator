# Phase 7: Hardening - Research

**Researched:** 2026-03-01
**Domain:** Python integration testing, structured JSON logging, APScheduler timeout jobs, Telegram command handlers
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

#### Integration test scope
- Real Anthropic client used — actual script generation runs with live API calls
- HeyGen, Ayrshare, and Telegram mocked — no external video/publish calls
- Pipeline triggered via direct function call to `daily_pipeline_job()` (not via APScheduler)
- One big end-to-end test file covering the full pipeline chain
- Assertions that prove the test passed:
  - A `content_history` DB row exists with expected fields/status
  - The mock Telegram bot received the approval message call
  - A `platform_metrics` or `publish_events` row was created

#### Approval timeout behavior
- 24-hour timer starts from when the approval message was sent (not pipeline start)
- At 24h with no response: send a "last-chance" Telegram message with approve/reject buttons still active — video is still approvable from this message
- If the creator responds to the last-chance message, proceed with normal publish pipeline
- Next generation runs at the next scheduled pipeline hour (next day) — no immediate retry after a skip
- If still no response by the next pipeline run: mark `content_history` row as `approval_timeout` status and proceed with new generation
- Notification sent to creator when timeout triggers (before marking expired)

#### Manual resume flow
- Circuit breaker halts after 3 trips in a day — sends halt alert via Telegram
- Creator resumes via `/resume` Telegram command (typed in the bot chat)
- `/resume` locked to creator ID only — consistent with existing bot security model
- On `/resume`: trigger immediate pipeline retry with no confirmation message
- The halt Telegram alert should include the `/resume` command instructions so creator knows what to do

#### Logging structure
- Library: Python `logging` stdlib with a JSON formatter (no new dependencies)
- Required fields on every log entry: `timestamp`, `level`, `message`, `pipeline_step`, `content_history_id`
- Telegram alerts for errors: only pipeline-critical failures (failures that stop or skip a run) — not every ERROR-level log
- Scope: Retrofit all existing pipeline stages (Phases 1-6 code updated) to emit structured JSON logs throughout

### Claude's Discretion
- JSON log formatter implementation details (pythonjsonlogger or manual dict serialization)
- Exact `pipeline_step` values and naming convention (snake_case strings are fine)
- How to inject `content_history_id` into log context (thread-local, extra dict, or logging adapter)
- Second-timeout window for last-chance approval message (if needed)
- Internal smoke tests for the new Phase 7 code (timeout job, resume handler, logging config)

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within phase scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| INFRA-01 | System runs as persistent worker on Railway with FastAPI health endpoint | E2E test verifies FastAPI + scheduler startup chain |
| INFRA-02 | Supabase schema initialized with all tables | E2E test confirms content_history row with correct fields |
| INFRA-03 | APScheduler triggers daily content generation, survives deploys | E2E test calls daily_pipeline_job() directly and verifies DB writes |
| INFRA-04 | Cost circuit breaker enforces hard daily generation limit | Circuit breaker halt test + /resume handler |
| SCRTY-01 | All API keys in env vars, never hardcoded | Verified by E2E test using env-injected values |
| SCRTY-02 | Bot responds only to creator's configured user ID | /resume handler uses get_creator_filter() pattern |
| SCRP-01 | 140-word max Spanish script generated via GPT-4o | E2E test: real Anthropic call generates script, row saved |
| SCRP-02 | Creator sets weekly mood via Telegram | Covered by E2E mock (mood loaded from DB) |
| SCRP-03 | Anti-repetition pgvector similarity guard | E2E test: embedding written to content_history |
| SCRP-04 | Script auto-summarized if >140 words | E2E test: script word count within target verified |
| VIDP-01 | HeyGen async submit + poll + download | HeyGen mocked in E2E test; mock verifies call was made |
| VIDP-02 | Dark aesthetic enforcement, no repeated background | E2E test: background_url field populated |
| VIDP-03 | Audio post-processing via ffmpeg | Mocked in E2E test (no ffmpeg in CI) |
| VIDP-04 | Video re-hosted to Supabase Storage post-render | E2E test: video_url on content_history row |
| TGAP-01 | Bot delivers video via presigned URL with post copy | E2E test: mock Telegram bot send_photo/send_message called |
| TGAP-02 | Inline Approve/Reject buttons | E2E test: approval keyboard in mock call |
| TGAP-03 | Rejection opens cause menu | Covered by approval timeout test assertions |
| TGAP-04 | Rejection cause stored as constraint for next gen | Approval timeout test: content_history status update |
| PUBL-01 | Approved video published to 4 platforms via Ayrshare | Ayrshare mocked in E2E test |
| PUBL-02 | Publish at peak hours per platform | E2E test: publish_events row created |
| PUBL-03 | Verify post-publish status 30m after scheduled publish | Verify job mock confirmed in E2E test |
| PUBL-04 | Ayrshare fail triggers Telegram manual fallback | Covered by E2E mock assertions |
| ANLX-01 | Harvest views/shares/retention 48h after publish | harvest_metrics mock confirmed in E2E |
| ANLX-02 | Weekly report via Telegram every Sunday | Smoke test: import/contract check |
| ANLX-03 | Virality alert if video exceeds 500% avg performance | Smoke test: import/contract check |
| ANLX-04 | Storage lifecycle hot/warm/cold management | Smoke test: import/contract check |
</phase_requirements>

## Summary

Phase 7 hardens the existing pipeline for autonomous unsupervised operation. Unlike prior phases that added new functionality, this phase introduces no new functional requirements — it verifies all 26 v1 requirements end-to-end and adds the operational guardrails that let the system run for months without supervision.

The four implementation areas are: (1) a single end-to-end integration test that calls `daily_pipeline_job()` directly with a real Anthropic API and mocked HeyGen/Ayrshare/Telegram, asserting DB rows and mock call counts; (2) an approval timeout job scheduled 24 hours after the approval message is sent, with a last-chance Telegram message and `approval_timeout` status written if still no response; (3) a daily halt mechanism in the circuit breaker (3 trips → halt alert + `/resume` command handler) distinct from the existing 7-day escalation; and (4) a structured JSON log formatter using only Python stdlib, with `pipeline_step` and `content_history_id` injected via LoggerAdapter, retrofitted across all pipeline stages.

The most critical implementation risk is the integration test setup: mocking must be applied at the correct module-path level (where names are looked up, not where they are defined), and the real Anthropic API call requires valid credentials in the test environment. The LoggerAdapter approach for injecting `content_history_id` is idiomatic and requires no new libraries. The approval timeout job uses the existing `DateTrigger` pattern already proven in `trigger_immediate_rerun()`. The `/resume` command handler follows the exact same pattern as existing `MessageHandler` + `get_creator_filter()` guards in `mood_flow.py`.

**Primary recommendation:** Implement in four discrete plans — (1) E2E integration test, (2) approval timeout job + last-chance message, (3) daily halt circuit breaker extension + `/resume` handler, (4) JSON logging retrofit — in that order, since the E2E test provides the baseline for catching regressions during the logging retrofit.

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `logging` (stdlib) | 3.12 | Log emission across all pipeline stages | Already used everywhere; no new dependencies per CONTEXT.md |
| `json` (stdlib) | 3.12 | JSON serialization in custom formatter | Avoids `python-json-logger` dependency per CONTEXT.md decision |
| `pytest` | 8.0+ (already in dev deps) | Integration test runner | Already installed in `[dependency-groups].dev` |
| `unittest.mock` (stdlib) | 3.12 | Mock HeyGen, Ayrshare, Telegram in E2E test | No extra install needed; integrates directly with pytest |
| `APScheduler` | 3.11.2 (already installed) | Schedule timeout job + `/resume` pipeline trigger | Already used for all scheduling in the project |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `python-telegram-bot` | 21.x (already installed) | Register `/resume` CommandHandler | Already used for all Telegram interactions |
| `contextvars` (stdlib) | 3.12 | Optional: thread-safe injection of `content_history_id` into log context | If LoggerAdapter approach becomes too verbose across many call sites |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Manual stdlib JSON formatter | `python-json-logger` | CONTEXT.md locks "no new dependencies" — manual formatter is 20 lines, easily maintained |
| LoggerAdapter for `content_history_id` | `contextvars` + Filter | LoggerAdapter is more explicit; contextvars is cleaner for deep call chains but adds invisible magic |
| LoggerAdapter for `content_history_id` | `extra={"content_history_id": ...}` at each callsite | Per-callsite `extra` is verbose; LoggerAdapter sets it once at pipeline entry point |

**Installation:** No new production dependencies. Pytest already in dev group.

## Architecture Patterns

### Recommended Project Structure for Phase 7

```
src/
├── app/
│   ├── logging_config.py          # NEW: JSON formatter + configure_logging()
│   ├── scheduler/
│   │   └── jobs/
│   │       └── approval_timeout.py  # NEW: check_approval_timeout_job()
│   ├── services/
│   │   └── circuit_breaker.py      # MODIFIED: add daily halt after 3 trips
│   ├── telegram/
│   │   ├── app.py                  # MODIFIED: register /resume CommandHandler
│   │   └── handlers/
│   │       └── resume_flow.py      # NEW: handle_resume handler
│   └── main.py                     # MODIFIED: call configure_logging()
tests/
└── test_phase07_e2e.py             # NEW: end-to-end integration test
```

### Pattern 1: Custom JSON Log Formatter (stdlib only)

**What:** A `logging.Formatter` subclass that serializes the LogRecord to a JSON dict with required fields.
**When to use:** Applied once in `configure_logging()` called at app startup in `main.py`.

```python
# Source: Python 3.12 logging module docs + manual implementation
import json
import logging
from datetime import datetime, timezone


class JSONFormatter(logging.Formatter):
    """
    Serializes log records to JSON with required fields:
    timestamp, level, message, pipeline_step, content_history_id.

    Required fields default to empty string if not provided via
    logger.info("msg", extra={"pipeline_step": "...", "content_history_id": "..."})
    or via a PipelineAdapter.
    """

    def format(self, record: logging.LogRecord) -> str:
        record_dict = {
            "timestamp": datetime.fromtimestamp(
                record.created, tz=timezone.utc
            ).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "pipeline_step": getattr(record, "pipeline_step", ""),
            "content_history_id": getattr(record, "content_history_id", ""),
        }
        if record.exc_info:
            record_dict["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(record_dict)
```

### Pattern 2: LoggerAdapter for Pipeline Context Injection

**What:** A `logging.LoggerAdapter` subclass that merges `pipeline_step` and `content_history_id` into every log call without repeating `extra={}` at every site.
**When to use:** Created at the start of `daily_pipeline_job()` and passed through to service calls that accept it.

```python
# Source: Python 3.12 logging.LoggerAdapter docs
import logging


class PipelineLogger(logging.LoggerAdapter):
    """
    Injects pipeline_step and content_history_id into every log record.

    Usage:
        plog = PipelineLogger(logger, {"pipeline_step": "script_gen", "content_history_id": ""})
        plog.info("Script generated.")
        # Updates context: plog.extra["pipeline_step"] = "heygen_submit"
    """

    def process(self, msg, kwargs):
        kwargs.setdefault("extra", {}).update(self.extra)
        return msg, kwargs
```

### Pattern 3: Approval Timeout Job (DateTrigger pattern)

**What:** An APScheduler `DateTrigger` job scheduled 24 hours after approval message delivery. On firing: query the DB, check if `approval_events` row exists. If not: send last-chance Telegram message. If still no response at next pipeline run: mark `approval_timeout`.
**When to use:** Scheduled from `send_approval_message_sync()` or immediately after the approval message is sent.

```python
# Source: APScheduler 3.x DateTrigger docs + existing trigger_immediate_rerun() pattern
from datetime import datetime, timedelta, timezone
from apscheduler.triggers.date import DateTrigger

def schedule_approval_timeout(content_history_id: str, scheduler) -> None:
    """
    Schedule the 24-hour last-chance check job.
    Uses the same DateTrigger pattern as trigger_immediate_rerun().
    replace_existing=True ensures only one timeout job per content_history_id.
    """
    run_at = datetime.now(tz=timezone.utc) + timedelta(hours=24)
    scheduler.add_job(
        check_approval_timeout_job,
        trigger=DateTrigger(run_date=run_at),
        args=[content_history_id],
        id=f"approval_timeout_{content_history_id}",
        name=f"Approval timeout for {content_history_id[:8]}",
        replace_existing=True,
    )
```

### Pattern 4: Daily Halt Circuit Breaker Extension

**What:** Track how many times `daily_pipeline_job()` has been skipped due to CB trips within a single UTC calendar day. On reaching 3, send a halt Telegram alert (with `/resume` instructions) and set a new `daily_halt` flag. `/resume` clears the halt flag and triggers `daily_pipeline_job()` immediately.
**When to use:** Checked at the top of `daily_pipeline_job()` after the existing CB `is_tripped()` check.

The existing `circuit_breaker_state` table has `weekly_trip_count`. For "3 trips in a day" we need either:
- A new `daily_trip_count` column on `circuit_breaker_state` (reset at midnight with the existing `cb_reset_job`), OR
- Counting via a new `daily_halt_at` + `daily_trip_count` pair added to the same table

**Recommendation (Claude's Discretion):** Add `daily_trip_count INTEGER DEFAULT 0` and `daily_halted_at TIMESTAMPTZ` to `circuit_breaker_state` via a migration. Reset `daily_trip_count = 0` and `daily_halted_at = NULL` in `midnight_reset()`. The `/resume` command also clears these fields.

### Pattern 5: `/resume` CommandHandler (existing handler pattern)

**What:** A `CommandHandler` for `/resume` filtered to creator ID only, registered in `build_telegram_app()`. On invocation: clear CB halt, trigger `daily_pipeline_job()` via `trigger_immediate_rerun()`.
**When to use:** Follows the exact same registration pattern as mood flow handlers.

```python
# Source: PTB 21.x CommandHandler docs + existing mood_flow.py registration pattern
from telegram.ext import Application, CommandHandler, filters
from app.services.telegram import get_creator_filter

async def handle_resume(update, context):
    """
    Creator-only command to resume after circuit breaker daily halt.
    Clears daily halt state, triggers immediate pipeline rerun.
    /resume is filtered to creator ID — same as all other handlers.
    """
    # Clear halt state in DB
    ...
    # Trigger immediate rerun (reuse existing trigger_immediate_rerun())
    from app.scheduler.jobs.daily_pipeline import trigger_immediate_rerun
    trigger_immediate_rerun()

def register_resume_handler(app: Application) -> None:
    creator_filter = get_creator_filter()
    app.add_handler(CommandHandler("resume", handle_resume, filters=creator_filter))
```

### Pattern 6: E2E Integration Test with Patching

**What:** A single pytest file that calls `daily_pipeline_job()` synchronously with real Anthropic, mocked HeyGen/Ayrshare/Telegram, and a real test Supabase connection.
**When to use:** This is the single E2E test file for Phase 7.

**Patch targets** (patch where looked up, not where defined):
- `app.scheduler.jobs.daily_pipeline.HeyGenService` — mock `submit()` to return a fake job ID
- `app.services.heygen._process_completed_render` — or mock the entire HeyGen completion flow
- `app.services.telegram.send_alert_sync` — capture calls, assert content
- `app.services.telegram.send_approval_message_sync` — capture calls, assert called
- `app.services.publishing.PublishingService.publish` — mock publish, return fake post ID

```python
# Source: Python 3.12 unittest.mock docs
from unittest.mock import patch, MagicMock
import pytest

@pytest.fixture
def mock_heygen():
    with patch("app.services.heygen.HeyGenService") as mock:
        instance = mock.return_value
        instance.submit.return_value = "fake-heygen-job-id"
        yield instance

def test_full_pipeline_end_to_end(mock_heygen, real_supabase):
    """
    Full pipeline: script_gen -> heygen_submit -> DB write.
    Uses real Anthropic API (env var required).
    """
    from app.scheduler.jobs.daily_pipeline import daily_pipeline_job
    daily_pipeline_job()

    # Assert DB row exists
    result = real_supabase.table("content_history").select("*")...
    assert result.data[0]["video_status"] == "pending_render"
    # Assert Telegram approval message was called
    mock_heygen.submit.assert_called_once()
```

### Anti-Patterns to Avoid

- **Patching at the definition site:** `patch("app.services.heygen.requests.post")` instead of patching `HeyGenService.submit` directly — fragile to internal implementation changes.
- **Module-level `content_history_id` state:** Using a global or class-level variable to track pipeline context instead of a per-invocation LoggerAdapter instance — breaks concurrent runs.
- **Halting on `tripped_at` alone for "3 daily trips":** The existing `tripped_at` is reset at midnight and tracks one trip. "3 trips in a day" requires counting how many times the pipeline was skipped due to tripping, which is a new counter (`daily_trip_count`).
- **JSON logs with `logging.basicConfig(format=...)`:** Using a text `format=` string in `basicConfig` overrides the JSON formatter — must configure handler explicitly, not via `basicConfig`.
- **Scheduling approval timeout from APScheduler thread context:** `schedule_approval_timeout()` must access `_scheduler` via the module-level reference (same pattern as `video_poller._scheduler`), not via `request.app.state`.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Scheduling one-off future jobs | Custom `threading.Timer` or `asyncio.sleep` loops | `APScheduler DateTrigger` | DateTrigger survives restarts, persists in Postgres job store, same pattern already proven in `trigger_immediate_rerun()` |
| JSON serialization of log records | Custom string concatenation | `json.dumps()` in `Formatter.format()` override | Handles escaping, Unicode, special chars correctly |
| Mocking external HTTP calls | Custom fake HTTP server | `unittest.mock.patch` + `MagicMock` | Already used throughout the codebase in existing smoke tests |
| Creator-only command filtering | Custom user ID check inside handler | `get_creator_filter()` from `services/telegram.py` | Already implemented (SCRTY-02), consistent with all handlers |
| Injecting context into log calls | `print()` statements or `logger.info(f"[{id}] ...")` | `logging.LoggerAdapter` | Keeps message clean, fields structured and parseable by Railway log viewer |

**Key insight:** Every new mechanism in Phase 7 mirrors a pattern already established in the codebase. The DateTrigger pattern is in `trigger_immediate_rerun()`. The CommandHandler + creator filter pattern is in `mood_flow.py`. The mock-at-module-path pattern is in existing smoke tests. Phase 7 is consolidation, not invention.

## Common Pitfalls

### Pitfall 1: Patching the Wrong Module Path in E2E Test

**What goes wrong:** `@patch("app.services.heygen.HeyGenService")` patches the class in `services/heygen.py`, but `daily_pipeline_job()` imports it via `from app.services.heygen import HeyGenService, pick_background_url` — a **local import inside the function body**. The patch must target `app.scheduler.jobs.daily_pipeline.HeyGenService`, which is where the name is bound at import time... except it's a local import, so the patch must be applied where it's called during execution.

**Why it happens:** Python's `unittest.mock.patch` replaces the name in the namespace where it's looked up. With lazy imports inside function bodies, the module is imported fresh each call — the patch must be on the source module, not the importer.

**How to avoid:** For the lazy import `from app.services.heygen import HeyGenService` inside `daily_pipeline_job()`, patch `app.services.heygen.HeyGenService` (the source). For top-level imports like `from app.services.telegram import send_alert_sync`, patch `app.services.telegram.send_alert_sync`.

**Warning signs:** Mock was set up but original function still called; mock `call_count == 0` after the test runs.

### Pitfall 2: basicConfig Overriding the JSON Formatter

**What goes wrong:** `logging.basicConfig(format="...", level=logging.INFO)` in `main.py` sets a text formatter on the root logger's StreamHandler. If `configure_logging()` (JSON setup) is called after `basicConfig`, and `basicConfig` already added a handler, `basicConfig` does nothing (it only acts if the root logger has no handlers). If called before, the JSON formatter is applied — then `basicConfig` may add a second text-format handler.

**Why it happens:** `logging.basicConfig()` is idempotent — it only runs if the root logger has no handlers. The order of calls determines which wins.

**How to avoid:** In `main.py`, replace the current `logging.basicConfig(...)` call with `configure_logging()` from `app.logging_config`. The custom `configure_logging()` should remove existing handlers before adding the JSON handler (`logger.handlers.clear()` on the root logger).

**Warning signs:** Logs appear in two formats (one JSON, one text) — indicates two handlers active on root logger.

### Pitfall 3: Daily Trip Count vs Weekly Trip Count Confusion

**What goes wrong:** The existing `circuit_breaker_state.weekly_trip_count` tracks trips in a 7-day rolling window. The Phase 7 "3 trips in a day" requirement needs a per-calendar-day count. Using `weekly_trip_count >= 3` would fire too late (e.g., 3 trips spread over 7 days) or too early (3 small trips in a week from unrelated thresholds).

**Why it happens:** The existing CB was designed for cost escalation, not pipeline-loop prevention.

**How to avoid:** Add `daily_trip_count INTEGER NOT NULL DEFAULT 0` to `circuit_breaker_state` via migration 0007. Reset to 0 in `midnight_reset()`. Increment in `_trip()`. Check `daily_trip_count >= 3` for the daily halt condition, distinct from `weekly_trip_count >= 2` for escalation alerts.

**Warning signs:** CB halts unexpectedly after fewer than 3 daily runs; or halt never fires because the wrong counter is checked.

### Pitfall 4: Approval Timeout Job Not Cancellable on Approval

**What goes wrong:** If the creator approves before 24 hours, the timeout job still fires and sends a spurious "last-chance" message.

**Why it happens:** The timeout job is scheduled at approval-message-send time and fires unconditionally unless cancelled.

**How to avoid:** In `check_approval_timeout_job()`, first check if `approval_events` row exists for `content_history_id`. If it does, log and return immediately — no message sent. The APScheduler job ID (`approval_timeout_{content_history_id}`) also allows explicit cancellation in `handle_approve`: `scheduler.remove_job(f"approval_timeout_{content_history_id}")` — wrap in try/except JobLookupError since the job may have already fired.

**Warning signs:** Creator receives last-chance message even after approving; "Ya procesado" from a double-fire.

### Pitfall 5: content_history `approval_timeout` Status Not in VideoStatus Enum

**What goes wrong:** Writing `"approval_timeout"` directly as a string to `content_history.video_status` works in DB but bypasses the `VideoStatus` enum in `models/video.py`, causing inconsistencies in other pipeline reads.

**Why it happens:** New status values added in Phase 7 without updating the Pydantic model enum.

**How to avoid:** Add `APPROVAL_TIMEOUT = "approval_timeout"` to `VideoStatus` enum in `models/video.py`. Use `VideoStatus.APPROVAL_TIMEOUT.value` when writing to DB.

**Warning signs:** Mypy errors on status comparisons; or pipeline reads that match on VideoStatus enum miss `approval_timeout` rows.

### Pitfall 6: E2E Test Hitting Real HeyGen/Telegram with Incomplete Mocks

**What goes wrong:** `daily_pipeline_job()` has two lazy imports inside its body: `HeyGenService` and `register_video_poller`. If only `HeyGenService` is mocked but `register_video_poller` tries to use a real `_scheduler`, the test crashes.

**Why it happens:** The function body has multiple external dependencies — all must be mocked to reach the DB assertion.

**How to avoid:** Mock all external dependencies before calling `daily_pipeline_job()`:
- `app.services.heygen.HeyGenService` (submit method)
- `app.scheduler.jobs.video_poller.register_video_poller`
- `app.services.telegram.send_alert_sync`
- `app.services.telegram.send_approval_message_sync`

**Warning signs:** Test raises `RuntimeError: FastAPI app not set` (unmocked Telegram path); or `AttributeError: 'NoneType' object has no attribute 'add_job'` (scheduler not set in video_poller module).

### Pitfall 7: `get_settings()` lru_cache in Tests

**What goes wrong:** `get_settings()` is decorated with `@lru_cache`. In test environments where env vars may be missing or different from production, the cached instance from a previous test import may be returned, causing wrong config values or `ValidationError`.

**Why it happens:** `lru_cache` is process-wide and persists across test function calls.

**How to avoid:** In E2E test setup, either set all required env vars before importing `get_settings`, or call `get_settings.cache_clear()` in a fixture teardown. Existing smoke tests sidestep this by never calling `get_settings()` directly.

**Warning signs:** `ValidationError` on first import; or settings values differ from what was set in test env vars.

## Code Examples

Verified patterns from official sources:

### Custom JSON Formatter (stdlib only)

```python
# Source: Python 3.12 logging module docs
# File: src/app/logging_config.py
import json
import logging
from datetime import datetime, timezone


class JSONFormatter(logging.Formatter):
    """
    Formats log records as single-line JSON for Railway log viewer.
    Required fields: timestamp, level, logger, message, pipeline_step, content_history_id.
    Optional: exc_info (only when exception info present).
    """

    def format(self, record: logging.LogRecord) -> str:
        record_dict = {
            "timestamp": datetime.fromtimestamp(
                record.created, tz=timezone.utc
            ).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "pipeline_step": getattr(record, "pipeline_step", ""),
            "content_history_id": getattr(record, "content_history_id", ""),
        }
        if record.exc_info:
            record_dict["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(record_dict, ensure_ascii=False)


def configure_logging(level: int = logging.INFO) -> None:
    """
    Replace root logger handlers with a single JSON StreamHandler.
    Call this once at app startup (main.py lifespan).
    Removes existing handlers to prevent duplicate plain-text output.
    """
    root = logging.getLogger()
    root.handlers.clear()
    handler = logging.StreamHandler()
    handler.setFormatter(JSONFormatter())
    root.addHandler(handler)
    root.setLevel(level)
    # Suppress noisy libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("apscheduler").setLevel(logging.WARNING)
```

### PipelineLogger Adapter

```python
# Source: Python 3.12 logging.LoggerAdapter docs
# File: src/app/logging_config.py (continued)
import logging


class PipelineLogger(logging.LoggerAdapter):
    """
    Wraps a logger to inject pipeline_step and content_history_id
    into every log record without repeating extra={} at every callsite.

    Usage in daily_pipeline_job():
        plog = PipelineLogger(logger, {
            "pipeline_step": "script_gen",
            "content_history_id": "",  # updated after DB write
        })
        plog.info("Pipeline started.")
        plog.extra["pipeline_step"] = "heygen_submit"
        plog.info("HeyGen job submitted: %s", heygen_job_id)
    """

    def process(self, msg, kwargs):
        kwargs.setdefault("extra", {}).update(self.extra)
        return msg, kwargs
```

### Approval Timeout Job

```python
# Source: APScheduler 3.x docs + existing trigger_immediate_rerun() pattern
# File: src/app/scheduler/jobs/approval_timeout.py
import logging
from app.services.database import get_supabase
from app.services.telegram import send_alert_sync
from app.models.video import VideoStatus

logger = logging.getLogger(__name__)


def check_approval_timeout_job(content_history_id: str) -> None:
    """
    Fires 24h after approval message was sent.
    If no approval_events row exists: send last-chance Telegram message.
    The last-chance message reuses the existing approval keyboard.
    """
    supabase = get_supabase()

    # Guard: already actioned — exit silently
    result = supabase.table("approval_events").select("id").eq(
        "content_history_id", content_history_id
    ).limit(1).execute()
    if result.data:
        logger.info(
            "approval_timeout_job: already actioned — skipping.",
            extra={"pipeline_step": "approval_timeout", "content_history_id": content_history_id},
        )
        return

    # Send last-chance message (reuses existing approval keyboard)
    from app.services.telegram import send_approval_message_sync
    video_row = supabase.table("content_history").select("video_url").eq(
        "id", content_history_id
    ).single().execute()
    video_url = video_row.data.get("video_url", "")

    # Notify creator: last chance
    send_alert_sync(
        f"AVISO: Tu video de hoy aun no ha sido aprobado. "
        f"Tienes hasta el proximo pipeline para aprobar o sera omitido."
    )
    # Re-send full approval message with buttons still active
    send_approval_message_sync(content_history_id, video_url)

    logger.info(
        "approval_timeout_job: last-chance message sent.",
        extra={"pipeline_step": "approval_timeout", "content_history_id": content_history_id},
    )
```

### Scheduling the Timeout from the Approval Message Send

```python
# Source: APScheduler 3.x DateTrigger docs
# To be called from send_approval_message() after the bot.send_photo/send_message call

from datetime import datetime, timedelta, timezone
from apscheduler.triggers.date import DateTrigger
from app.scheduler.jobs.video_poller import _scheduler  # module-level scheduler ref


def schedule_approval_timeout(content_history_id: str) -> None:
    run_at = datetime.now(tz=timezone.utc) + timedelta(hours=24)
    _scheduler.add_job(
        check_approval_timeout_job,
        trigger=DateTrigger(run_date=run_at),
        args=[content_history_id],
        id=f"approval_timeout_{content_history_id}",
        name=f"Approval 24h timeout for {content_history_id[:8]}",
        replace_existing=True,
    )
```

### `/resume` CommandHandler Registration

```python
# Source: PTB 21.x CommandHandler docs + mood_flow.py registration pattern
# File: src/app/telegram/handlers/resume_flow.py
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from app.services.telegram import get_creator_filter

logger = logging.getLogger(__name__)


async def handle_resume(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Creator-only /resume command.
    Clears daily halt state in circuit_breaker_state, triggers immediate pipeline rerun.
    No confirmation message sent — pipeline runs immediately per CONTEXT.md decision.
    """
    from app.services.database import get_supabase
    from app.services.circuit_breaker import CircuitBreakerService
    from app.scheduler.jobs.daily_pipeline import trigger_immediate_rerun
    from datetime import datetime, timezone

    supabase = get_supabase()
    # Clear daily halt state
    supabase.table("circuit_breaker_state").update({
        "daily_trip_count": 0,
        "daily_halted_at": None,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", 1).execute()

    trigger_immediate_rerun()
    logger.info(
        "Circuit breaker daily halt cleared via /resume. Pipeline rerun scheduled.",
        extra={"pipeline_step": "manual_resume", "content_history_id": ""},
    )


def register_resume_handler(app: Application) -> None:
    creator_filter = get_creator_filter()
    app.add_handler(CommandHandler("resume", handle_resume, filters=creator_filter))
    logger.info("Resume handler registered.")
```

### E2E Integration Test Skeleton

```python
# Source: Python 3.12 unittest.mock docs + existing test_phase04_smoke.py pattern
# File: tests/test_phase07_e2e.py
import os
import sys
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


@pytest.fixture(autouse=True)
def mock_all_externals():
    """
    Mock all external API calls for the E2E test.
    Real Anthropic API is NOT mocked (locked decision).
    """
    with patch("app.services.heygen.HeyGenService") as mock_heygen_cls, \
         patch("app.scheduler.jobs.video_poller.register_video_poller") as mock_poller, \
         patch("app.services.telegram.send_alert_sync") as mock_alert, \
         patch("app.services.telegram.send_approval_message_sync") as mock_approval:
        mock_heygen = mock_heygen_cls.return_value
        mock_heygen.submit.return_value = "fake-heygen-job-id-e2e"
        yield {
            "heygen": mock_heygen,
            "poller": mock_poller,
            "alert": mock_alert,
            "approval": mock_approval,
        }


def test_daily_pipeline_writes_content_history(mock_all_externals):
    """
    Full pipeline call: generates real script via Anthropic, saves to content_history.
    Asserts: DB row exists with correct fields.
    """
    from app.scheduler.jobs.daily_pipeline import daily_pipeline_job
    from app.services.database import get_supabase

    daily_pipeline_job()

    supabase = get_supabase()
    rows = supabase.table("content_history").select("*").order(
        "created_at", desc=True
    ).limit(1).execute()
    assert rows.data, "content_history row not created"
    row = rows.data[0]
    assert row["heygen_job_id"] == "fake-heygen-job-id-e2e"
    assert row["video_status"] == "pending_render"
    assert row["script_text"]
    mock_all_externals["heygen"].submit.assert_called_once()
```

### Migration: Add daily_trip_count and daily_halted_at

```sql
-- Source: Pattern follows existing migrations/000x_*.sql
-- File: migrations/0007_hardening.sql

-- Extend circuit_breaker_state for daily halt (Phase 7: 3 trips/day → halt)
ALTER TABLE circuit_breaker_state
  ADD COLUMN IF NOT EXISTS daily_trip_count INTEGER NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS daily_halted_at TIMESTAMPTZ;

-- Extend content_history for approval timeout status
-- approval_timeout is a new valid value for video_status
ALTER TABLE content_history
  DROP CONSTRAINT IF EXISTS content_history_video_status_check;

ALTER TABLE content_history
  ADD CONSTRAINT content_history_video_status_check CHECK (
    video_status IN (
      'pending_render',
      'pending_render_retry',
      'rendering',
      'ready',
      'published',
      'approval_timeout'
    )
  );
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `logging.basicConfig(format="%(asctime)s ...")` text logs | JSON formatter with structured fields | Phase 7 retrofit | Railway log viewer can parse fields without regex; log aggregators work out of the box |
| Global `print()` or ad-hoc logger statements | `PipelineLogger` adapter with `pipeline_step` + `content_history_id` | Phase 7 retrofit | Every log entry traceable to a specific pipeline run and content piece |
| No approval timeout (creator can ignore indefinitely) | 24h DateTrigger job with last-chance message | Phase 7 new | Pipeline cannot hang indefinitely on unanswered approvals |
| Manual monitoring for circuit breaker loops | 3-daily-trips halt + `/resume` command | Phase 7 new | Autonomous operation without infinite retry loops |

**Deprecated/outdated in this project after Phase 7:**
- `logging.basicConfig(format="%(asctime)s %(levelname)s %(name)s %(message)s")` in `main.py`: replaced by `configure_logging()` with `JSONFormatter`.

## Open Questions

1. **Where exactly to call `schedule_approval_timeout()`**
   - What we know: The approval message is sent from `send_approval_message()` (async, runs in PTB context) or via `send_approval_message_sync()` (from APScheduler thread).
   - What's unclear: `_scheduler` module-level ref (from `video_poller.py`) is injected at startup — is it accessible from `telegram.py` without a circular import?
   - Recommendation: Add a `set_scheduler` reference in a shared module (or reuse `video_poller._scheduler` via lazy import), same pattern as `trigger_immediate_rerun()` which already does this. Alternatively, schedule the timeout from `_process_completed_render()` in `heygen.py` where the approval message send already happens.

2. **Whether the "next pipeline run" check (approval_timeout status write) is in `daily_pipeline_job()` or in `check_approval_timeout_job()`**
   - What we know: CONTEXT.md says "If still no response by the next pipeline run: mark `content_history` row as `approval_timeout`."
   - What's unclear: This implies `daily_pipeline_job()` checks for un-actioned pending_render rows at startup, not the 24h job.
   - Recommendation: At the top of `daily_pipeline_job()`, query for any `content_history` row with `video_status = 'ready'` (READY = approval message was sent, awaiting response) and no `approval_events` row older than 1 run. Mark as `approval_timeout`. Then proceed with new generation. The 24h job only sends the last-chance message; the status write happens at next-pipeline-run time.

3. **Test environment for real Anthropic API**
   - What we know: E2E test uses real Anthropic (locked decision). Requires `ANTHROPIC_API_KEY` env var.
   - What's unclear: Whether the CI/CD environment (Railway or local) has this credential available for automated test runs.
   - Recommendation: The E2E test should be marked with a pytest mark (`@pytest.mark.e2e`) and skipped if `ANTHROPIC_API_KEY` is not set, to avoid blocking CI on missing credentials. Add `pytest.ini` skip condition or `pytest.importorskip`.

4. **Logger name granularity for `pipeline_step` field**
   - What we know: Required fields include `pipeline_step` on every log entry.
   - What's unclear: Services called from `daily_pipeline_job()` (e.g., `ScriptGenerationService`) have their own module-level `logger = logging.getLogger(__name__)` — these won't have `pipeline_step` unless `PipelineLogger` is passed in or contextvars is used.
   - Recommendation: Use `extra={"pipeline_step": "..."}` on the module-level logger in each service's key methods, defaulting to empty string when not in a pipeline context. Reserve `PipelineLogger` for the job-level orchestration code. This avoids a major refactor of every service's logger construction.

## Sources

### Primary (HIGH confidence)
- Python 3.12 `logging` module docs — LoggerAdapter pattern, Filter, Formatter.format() override
- Python 3.12 `unittest.mock` docs — `patch`, `MagicMock`, patch-where-looked-up rule
- APScheduler 3.11.2 docs — `DateTrigger` constructor, `add_job()` with args, `replace_existing`
- Existing codebase `trigger_immediate_rerun()` in `daily_pipeline.py` — DateTrigger pattern
- Existing codebase `get_creator_filter()` in `services/telegram.py` — creator-only filter pattern
- Existing codebase `mood_flow.py` — CommandHandler registration pattern
- Existing codebase `test_phase04_smoke.py` / `test_phase05_smoke.py` — import/inspect test pattern

### Secondary (MEDIUM confidence)
- `python-json-logger` (nhairs/python-json-logger) Quick Start — verified JsonFormatter API matches stdlib Formatter subclass pattern; decision to NOT use it per CONTEXT.md (no new deps)
- Python 3.12 logging cookbook — LoggerAdapter and contextvars patterns for context injection
- PTB 21.x CommandHandler docs — confirmed `CommandHandler("resume", handler, filters=...)` signature unchanged

### Tertiary (LOW confidence)
- Railway log viewer JSON parsing behavior — assumption that single-line JSON is parseable by Railway without extra tooling; unverified against Railway docs directly

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries already installed; no new dependencies needed
- Architecture: HIGH — all patterns mirror existing, verified code in this codebase
- Pitfalls: HIGH — identified from direct code reading of `daily_pipeline_job()`, approval flow, and test patterns
- E2E test approach: MEDIUM — real Anthropic API + mocked externals is straightforward, but CI credential availability is unverified

**Research date:** 2026-03-01
**Valid until:** 2026-04-01 (stable stdlib + APScheduler 3.x; no fast-moving dependencies involved)
