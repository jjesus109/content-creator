-- Migration 0011: Phase 11 Gap Closure — Add platform_facebook to music_pool
-- Root cause: migration 0008 created music_pool with only 3 platform flags
-- (platform_tiktok, platform_youtube, platform_instagram). Phase 11 code
-- references platform_facebook at publish time. This migration adds the
-- missing column so the license gate can correctly evaluate facebook clearance.
--
-- DEFAULT FALSE: existing tracks are NOT facebook-cleared until explicitly updated.
-- IF NOT EXISTS: safe to run multiple times (idempotent).

ALTER TABLE music_pool
    ADD COLUMN IF NOT EXISTS platform_facebook BOOLEAN NOT NULL DEFAULT FALSE;
