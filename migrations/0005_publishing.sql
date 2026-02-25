-- Migration 0005: Publishing schema — Phase 5 (Multi-Platform Publishing)
-- Creates: publish_events table + platform copy columns on content_history

-- Section A: 4 platform copy columns on content_history
-- PostCopyService generates platform-adapted copy for each channel before
-- the Telegram approval message is sent. These columns store the 4 variants
-- so the publish job (Phase 5) can attach the correct caption per platform
-- without regenerating it after approval.
--
-- post_copy_tiktok    — TikTok-adapted copy (hooks, hashtags, 150-char soft limit)
-- post_copy_instagram — Instagram-adapted copy (carousel-style, up to 2200 chars)
-- post_copy_facebook  — Facebook-adapted copy (conversational, link-friendly)
-- post_copy_youtube   — YouTube description-adapted copy (SEO, chapters optional)

ALTER TABLE content_history
    ADD COLUMN IF NOT EXISTS post_copy_tiktok    text,
    ADD COLUMN IF NOT EXISTS post_copy_instagram text,
    ADD COLUMN IF NOT EXISTS post_copy_facebook  text,
    ADD COLUMN IF NOT EXISTS post_copy_youtube   text;

-- Section B: publish_events table
-- Append-only log of publishing outcomes for every platform-post attempt.
-- Verification jobs query this table by content_history_id + platform to
-- confirm that a post is visible 30 minutes after Ayrshare accepted it.
--
-- status values:
--   'published'     — Ayrshare accepted the post (HTTP 200 with postIds)
--   'failed'        — Ayrshare rejected the post or was unreachable
--   'verified'      — 30-minute verification check confirmed post is live
--   'verify_failed' — 30-minute verification check found a problem (post missing or deleted)
--
-- ayrshare_post_id: Ayrshare-internal post ID used by the verify job to
--   call GET /post/{id} on the Ayrshare API to confirm live status.
-- platform_post_id: Platform-native post ID returned by Ayrshare in the
--   postIds response field (e.g. TikTok video ID, Instagram media ID).

CREATE TABLE IF NOT EXISTS publish_events (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at          timestamptz DEFAULT now() NOT NULL,
    content_history_id  uuid NOT NULL REFERENCES content_history(id),
    platform            text NOT NULL CHECK (platform IN ('tiktok', 'instagram', 'facebook', 'youtube')),
    ayrshare_post_id    text,
    platform_post_id    text,
    status              text NOT NULL CHECK (status IN ('published', 'failed', 'verified', 'verify_failed')),
    scheduled_at        timestamptz,
    published_at        timestamptz,
    error_message       text
);

-- Section C: indexes
-- publish_events_content_history_id_idx supports verification job lookup:
--   SELECT * FROM publish_events WHERE content_history_id = $1
-- publish_events_platform_status_idx supports status dashboard queries:
--   SELECT * FROM publish_events WHERE platform = $1 AND status = $2

CREATE INDEX IF NOT EXISTS publish_events_content_history_id_idx
    ON publish_events(content_history_id);

CREATE INDEX IF NOT EXISTS publish_events_platform_status_idx
    ON publish_events(platform, status);
