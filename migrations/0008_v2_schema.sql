-- Migration 0008: v2.0 schema — Phase 9 (Character Bible + Kling) + Phase 10 stubs
-- content_history: add kling_job_id column + update video_status CHECK constraint
-- kling_circuit_breaker_state: new table for Kling-specific CB (separate from HeyGen CB)
-- music_pool: Phase 10 stub table for pre-curated music tracks
-- app_settings: generic KV table for character_bible_version and future settings

-- 1. Add kling_job_id to content_history
--    Nullable text: null until KlingService.submit() fires, then stores fal.ai request_id
ALTER TABLE content_history
    ADD COLUMN IF NOT EXISTS kling_job_id TEXT;

-- 2. Update video_status CHECK constraint to include Kling lifecycle values
--    Drop old constraint (created in migration 0003, extended in 0007) and recreate with all values
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
        'approval_timeout',
        'kling_pending',
        'kling_pending_retry'
    ));

-- 3. Create kling_circuit_breaker_state table
--    Singleton row (id=1). Tracks failure rate over 24h rolling window.
--    Separate from circuit_breaker_state (HeyGen, cost+count based).
CREATE TABLE IF NOT EXISTS kling_circuit_breaker_state (
    id                  INTEGER PRIMARY KEY DEFAULT 1,
    is_open             BOOLEAN NOT NULL DEFAULT FALSE,
    opened_at           TIMESTAMPTZ,
    total_attempts      INTEGER NOT NULL DEFAULT 0,
    total_failures      INTEGER NOT NULL DEFAULT 0,
    failure_rate        NUMERIC(5,4) NOT NULL DEFAULT 0.0,
    last_reset_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT kling_cb_singleton CHECK (id = 1)
);

-- Seed singleton row if not exists
INSERT INTO kling_circuit_breaker_state (id)
VALUES (1)
ON CONFLICT (id) DO NOTHING;

-- 4. Create music_pool table (Phase 10 stub)
--    Populated by Phase 10-01. Phase 9 creates the table only.
CREATE TABLE IF NOT EXISTS music_pool (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title               TEXT NOT NULL,
    file_url            TEXT NOT NULL,
    mood                TEXT NOT NULL CHECK (mood IN ('playful', 'sleepy', 'curious', 'neutral')),
    bpm                 INTEGER NOT NULL,
    platform_tiktok     BOOLEAN NOT NULL DEFAULT FALSE,
    platform_youtube    BOOLEAN NOT NULL DEFAULT FALSE,
    platform_instagram  BOOLEAN NOT NULL DEFAULT FALSE,
    license_expires_at  TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 5. Create app_settings table (generic KV store for character_bible_version and future use)
CREATE TABLE IF NOT EXISTS app_settings (
    key         VARCHAR(100) PRIMARY KEY,
    value       TEXT,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Seed character_bible_version (Phase 9 uses v1 — bumping forces re-evaluation of consistency)
INSERT INTO app_settings (key, value)
VALUES ('character_bible_version', '1')
ON CONFLICT (key) DO NOTHING;
