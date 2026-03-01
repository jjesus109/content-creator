---
plan: 07-04
phase: 07-hardening
status: complete
completed: 2026-03-01
duration: ~15 min
commits:
  - de88ad0: feat(07-04): create JSONFormatter/PipelineLogger module + replace basicConfig in main.py
  - ab21715: feat(07-04): retrofit pipeline_step/content_history_id structured logs across all pipeline stages
---

# Plan 07-04 Summary: Structured JSON Logging Retrofit

## What Was Built

Retrofitted structured JSON logging across the entire pipeline.

### Task 1: logging_config.py + main.py

**`src/app/logging_config.py`** (new file) — exports three symbols:
- `JSONFormatter` — subclass of `logging.Formatter`; `format()` returns a JSON string with `timestamp` (ISO UTC), `level`, `logger`, `message`, `pipeline_step`, `content_history_id`, and `exc_info` when present.
- `PipelineLogger` — subclass of `logging.LoggerAdapter`; `process()` merges `self.extra` into every log call's `extra={}` dict. Used in `daily_pipeline_job` to carry `pipeline_step` and `content_history_id` through the orchestrator.
- `configure_logging(level=INFO)` — clears root handlers, attaches `StreamHandler(JSONFormatter())`, suppresses `httpx`, `apscheduler`, and `telegram` loggers to WARNING.

**`src/app/main.py`** — removed `logging.basicConfig(...)` block (3 lines), replaced with `configure_logging()`. Every log line from the service now emits single-line JSON to Railway's log viewer.

### Task 2: pipeline_step/content_history_id retrofit

**`src/app/scheduler/jobs/daily_pipeline.py`** — rewrote to use `PipelineLogger`:
- `plog = PipelineLogger(logger, {"pipeline_step": "pipeline_start", "content_history_id": ""})` at function start.
- `plog.extra["pipeline_step"]` updated at transitions: `script_gen`, `pipeline_halt_check`, `heygen_submit`, `pipeline_complete`.
- After DB write, `plog.extra["content_history_id"] = new_id or ""` so all completion/error logs include the row ID.
- `_save_to_content_history()` return type changed from `None` to `str | None` — returns inserted row's `id`.

**All 11 pipeline service files** — `extra={"pipeline_step": "...", "content_history_id": ""}` added to:
- All `logger.error()` and `logger.warning()` calls (every failure is now traceable)
- Main milestone `logger.info()` calls (start, complete, submit, upload)

Files retrofitted: `script_generation.py`, `heygen.py`, `audio_processing.py`, `video_storage.py`, `approval.py`, `publishing.py`, `analytics.py`, `metrics.py`, `storage_lifecycle.py`, `circuit_breaker.py`.

## Verification

- `python3 -c "from app.logging_config import JSONFormatter, PipelineLogger, configure_logging"` — imports OK
- `grep basicConfig src/app/main.py` — empty (removed)
- `uv run pytest tests/test_phase04_smoke.py tests/test_phase05_smoke.py -v` — **21/21 passed**

## Key Files

### Created
- `src/app/logging_config.py` — JSONFormatter, PipelineLogger, configure_logging

### Modified
- `src/app/main.py` — configure_logging() replaces basicConfig
- `src/app/scheduler/jobs/daily_pipeline.py` — PipelineLogger orchestration, _save_to_content_history returns ID
- `src/app/services/script_generation.py` — error/warning extra added
- `src/app/services/heygen.py` — submit/process/failure milestones annotated
- `src/app/services/audio_processing.py` — ffmpeg start/complete/error annotated
- `src/app/services/video_storage.py` — upload milestone annotated
- `src/app/services/approval.py` — constraint write annotated
- `src/app/services/publishing.py` — publish/schedule milestones annotated
- `src/app/services/analytics.py` — virality alert annotated
- `src/app/services/metrics.py` — all 11 warning/error calls annotated
- `src/app/services/storage_lifecycle.py` — all lifecycle transitions annotated
- `src/app/services/circuit_breaker.py` — trip/halt/reset calls annotated

## Self-Check: PASSED

All must-haves from plan frontmatter met:
- ✓ logging_config.py exists with JSONFormatter, PipelineLogger, configure_logging exported
- ✓ main.py replaced logging.basicConfig with configure_logging()
- ✓ All pipeline stage services have pipeline_step on key error/warning log calls
- ✓ daily_pipeline_job uses PipelineLogger with content_history_id updated after DB write
- ✓ All smoke tests pass — logging retrofit did not break any existing contracts
