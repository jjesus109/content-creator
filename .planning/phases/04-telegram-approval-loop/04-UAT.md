---
status: testing
phase: 04-telegram-approval-loop
source: [04-01-SUMMARY.md]
started: 2026-02-23T00:00:00Z
updated: 2026-02-23T00:00:00Z
---

## Current Test

number: 2
name: post_copy column on content_history
expected: |
  migrations/0004_approval_events.sql includes:
    ALTER TABLE content_history ADD COLUMN IF NOT EXISTS post_copy text
  The IF NOT EXISTS guard makes the migration idempotent — safe to re-run without error.
awaiting: user response

## Tests

### 1. Migration 0004 file structure
expected: File migrations/0004_approval_events.sql exists and defines: approval_events table with id (uuid PK), created_at (timestamptz), content_history_id (uuid FK to content_history), action CHECK('approved'/'rejected'), cause_code restricted to script_error/visual_error/technical_error/off_topic, CONSTRAINT rejection_requires_cause (action='approved' OR cause_code IS NOT NULL), and two indexes for content_history_id and created_at lookups.
result: pass

### 2. post_copy column on content_history
expected: migrations/0004_approval_events.sql includes ALTER TABLE content_history ADD COLUMN IF NOT EXISTS post_copy text. The IF NOT EXISTS guard makes the migration idempotent — safe to re-run without error.
result: [pending]

### 3. ApprovalService imports cleanly
expected: Running `python -c "from app.services.approval import ApprovalService; print('ok')"` (from /src) prints "ok" with no errors. The module exists at src/app/services/approval.py with ApprovalService class.
result: [pending]

### 4. ApprovalService has all required methods
expected: ApprovalService has these 6 methods: is_already_actioned(content_history_id) → bool, record_approve(content_history_id), record_reject(content_history_id, cause_code), get_today_rejection_count() → int, write_rejection_constraint(cause_code), clear_constraints_for_approved_run(content_history_id). All are synchronous (no async/await).
result: [pending]

### 5. PostCopyService and extract_thumbnail importable
expected: Running `python -c "from app.services.post_copy import PostCopyService, extract_thumbnail; print('ok')"` (from /src) prints "ok" with no errors. Module exists at src/app/services/post_copy.py.
result: [pending]

### 6. cause_code to pattern_type mapping is correct
expected: In src/app/services/approval.py, _CAUSE_TO_PATTERN_TYPE maps: 'script_error' → 'script_class', 'visual_error' → 'topic', 'technical_error' → 'topic', 'off_topic' → 'topic'. Non-matching cause codes fall back to 'topic' via .get(code, 'topic').
result: [pending]

## Summary

total: 6
passed: 1
issues: 0
pending: 5
skipped: 0

## Gaps

[none yet]
