-- Migration 0006: Analytics and Storage — Phase 6
-- platform_metrics: per-platform per-video metrics row inserted by 48h harvest job
-- content_history additions: storage_status, deletion flags, viral/eternal flags
-- Architecture: warm tier = DB label only (file stays in Supabase Storage bucket)
--               cold tier = file deleted from Supabase Storage; DB record KEPT

CREATE TABLE IF NOT EXISTS platform_metrics (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at          timestamptz DEFAULT now() NOT NULL,
    harvested_at        timestamptz NOT NULL,
    content_history_id  uuid NOT NULL REFERENCES content_history(id),
    platform            text NOT NULL CHECK (platform IN ('youtube', 'instagram', 'tiktok', 'facebook')),
    external_post_id    text,
    views               integer,
    likes               integer,
    shares              integer,
    comments            integer,
    reach               integer,
    saves               integer,
    retention_rate      float,
    virality_alerted_at timestamptz
);

CREATE INDEX IF NOT EXISTS platform_metrics_content_history_idx
    ON platform_metrics(content_history_id);

CREATE INDEX IF NOT EXISTS platform_metrics_platform_harvested_idx
    ON platform_metrics(platform, harvested_at);

ALTER TABLE content_history
    ADD COLUMN IF NOT EXISTS storage_status       text DEFAULT 'hot'
        CHECK (storage_status IN ('hot', 'warm', 'pending_deletion', 'deleted', 'exempt')),
    ADD COLUMN IF NOT EXISTS storage_tier_set_at  timestamptz,
    ADD COLUMN IF NOT EXISTS deletion_requested_at timestamptz,
    ADD COLUMN IF NOT EXISTS is_viral             boolean DEFAULT false,
    ADD COLUMN IF NOT EXISTS is_eternal           boolean DEFAULT false;
