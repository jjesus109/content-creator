-- Migration 0010: Phase 11 — Music License Enforcement at Publish
-- Adds 'blocked' status to publish_events for license gate blocks.
--
-- Supabase does not support ALTER CONSTRAINT directly; drop and recreate.
ALTER TABLE publish_events
    DROP CONSTRAINT IF EXISTS publish_events_status_check;

ALTER TABLE publish_events
    ADD CONSTRAINT publish_events_status_check
    CHECK (status IN ('published', 'failed', 'verified', 'verify_failed', 'blocked'));
