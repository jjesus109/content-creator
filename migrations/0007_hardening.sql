-- Migration 0007: Hardening — Phase 7
-- circuit_breaker_state additions: daily halt state tracking (3-trips-per-day halt)
-- content_history addition: approval_timeout to video_status CHECK constraint

-- Add daily halt state columns to circuit_breaker_state
ALTER TABLE circuit_breaker_state
    ADD COLUMN IF NOT EXISTS daily_trip_count INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS daily_halted_at  TIMESTAMPTZ;

-- Extend video_status CHECK constraint to include approval_timeout
-- Drop old constraint first (name from migration 0003) then re-add with all values
ALTER TABLE content_history
    DROP CONSTRAINT IF EXISTS content_history_video_status_check;

ALTER TABLE content_history
    ADD CONSTRAINT content_history_video_status_check
    CHECK (video_status IN (
        'pending_render',
        'pending_render_retry',
        'rendering',
        'processing',
        'ready',
        'failed',
        'published',
        'approval_timeout'
    ));
