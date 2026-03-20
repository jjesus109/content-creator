-- Migration 0009: Phase 10 schema — Scene Engine + Music Pool
-- Adds: scene_embedding on content_history, scene_combo on rejection_constraints,
--       artist column on music_pool, check_scene_similarity function

-- 1. Add scene_embedding column to content_history
--    Stores the 1536-dim embedding of the GPT-4o-expanded scene prompt.
--    Used by check_scene_similarity to block visually repetitive scenes.
--    Decision: stored on content_history (not a separate table) for atomic updates
--    and to avoid join complexity. The existing `embedding` column (script embedding)
--    is preserved unchanged alongside this new scene-specific column.
ALTER TABLE content_history
    ADD COLUMN IF NOT EXISTS scene_embedding extensions.vector(1536);

-- 2. Add scene_prompt and caption columns to content_history
--    scene_prompt: 2-3 sentence Kling-optimized prompt from SceneEngine
--    caption: 5-8 word universal Spanish caption from the same GPT-4o call
ALTER TABLE content_history
    ADD COLUMN IF NOT EXISTS scene_prompt TEXT;

ALTER TABLE content_history
    ADD COLUMN IF NOT EXISTS caption TEXT;

-- 3. Add music_track_id to content_history (FK to music_pool)
ALTER TABLE content_history
    ADD COLUMN IF NOT EXISTS music_track_id UUID REFERENCES music_pool(id);

-- 4. Add artist column to music_pool (missing from Phase 9 stub in 0008)
ALTER TABLE music_pool
    ADD COLUMN IF NOT EXISTS artist TEXT NOT NULL DEFAULT '';

-- 5. Extend rejection_constraints to support scene rejections
--    scene_combo: {"location": "cocina", "activity": "inspeccionar olla"}
--    Drop old pattern_type CHECK; recreate with 'scene' added.
ALTER TABLE rejection_constraints
    ADD COLUMN IF NOT EXISTS scene_combo JSONB;

ALTER TABLE rejection_constraints
    DROP CONSTRAINT IF EXISTS rejection_constraints_pattern_type_check;

ALTER TABLE rejection_constraints
    ADD CONSTRAINT rejection_constraints_pattern_type_check
    CHECK (pattern_type IN ('topic', 'tone', 'script_class', 'scene'));

-- 6. Create check_scene_similarity SQL function
--    Mirrors check_script_similarity but uses scene_embedding column.
--    Default threshold: 0.78 (mid-range of 75-80% research estimate).
--    Default lookback: 7 days (recalibrated from v1.0's 90-day script lookback).
CREATE OR REPLACE FUNCTION check_scene_similarity(
    query_embedding extensions.vector(1536),
    similarity_threshold float DEFAULT 0.78,
    lookback_days int DEFAULT 7
)
RETURNS TABLE(id uuid, scene_prompt text, similarity float)
LANGUAGE sql
AS $$
    SELECT
        ch.id,
        ch.scene_prompt,
        1 - (ch.scene_embedding <=> query_embedding) AS similarity
    FROM content_history ch
    WHERE
        ch.scene_embedding IS NOT NULL
        AND ch.created_at > NOW() - (lookback_days || ' days')::interval
        AND (1 - (ch.scene_embedding <=> query_embedding)) > similarity_threshold
    ORDER BY similarity DESC
    LIMIT 5;
$$;
