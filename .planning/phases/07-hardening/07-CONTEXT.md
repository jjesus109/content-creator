# Phase 7: Hardening - Context

**Gathered:** 2026-03-01
**Status:** Ready for planning

<domain>
## Phase Boundary

Harden the existing pipeline for autonomous, unsupervised operation — no new features. Covers: end-to-end integration tests, approval timeout with last-chance flow, manual circuit-breaker resume via Telegram, and structured JSON logging retrofitted across all pipeline stages.

</domain>

<decisions>
## Implementation Decisions

### Integration test scope
- Real Anthropic client used — actual script generation runs with live API calls
- HeyGen, Ayrshare, and Telegram mocked — no external video/publish calls
- Pipeline triggered via direct function call to `daily_pipeline_job()` (not via APScheduler)
- One big end-to-end test file covering the full pipeline chain
- Assertions that prove the test passed:
  - A `content_history` DB row exists with expected fields/status
  - The mock Telegram bot received the approval message call
  - A `platform_metrics` or `publish_events` row was created

### Approval timeout behavior
- 24-hour timer starts from when the approval message was sent (not pipeline start)
- At 24h with no response: send a "last-chance" Telegram message with approve/reject buttons still active — video is still approvable from this message
- If the creator responds to the last-chance message, proceed with normal publish pipeline
- Next generation runs at the next scheduled pipeline hour (next day) — no immediate retry after a skip
- If still no response by the next pipeline run: mark `content_history` row as `approval_timeout` status and proceed with new generation
- Notification sent to creator when timeout triggers (before marking expired)

### Manual resume flow
- Circuit breaker halts after 3 trips in a day — sends halt alert via Telegram
- Creator resumes via `/resume` Telegram command (typed in the bot chat)
- `/resume` locked to creator ID only — consistent with existing bot security model
- On `/resume`: trigger immediate pipeline retry with no confirmation message
- The halt Telegram alert should include the `/resume` command instructions so creator knows what to do

### Logging structure
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

</decisions>

<specifics>
## Specific Ideas

- The `/resume` command should work exactly like existing creator-only commands — same ID check, same handler registration pattern
- The last-chance approval Telegram message should reuse the existing approval keyboard (approve/reject buttons) — not a new UI
- JSON log entries should be observable directly in Railway's log viewer without any extra tooling

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 07-hardening*
*Context gathered: 2026-03-01*
