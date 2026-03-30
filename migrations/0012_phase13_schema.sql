-- Migration 0012: Phase 13 schema — Kitten Scenario Video Generation
-- Adds: prompt_embedding column to content_history for visual/stylistic anti-repetition (D-09, D-10)
-- Tracks the Kling-prompt-level embedding separately from scene_embedding (scenario-level).
-- Both embeddings together catch semantic (story type) AND stylistic (Kling prompt) repetition.

-- Add prompt_embedding column to content_history
--   vector(1536): text-embedding-3-small dimension, matches scene_embedding column type
--   IF NOT EXISTS: idempotent, safe to apply multiple times to Supabase
ALTER TABLE content_history
    ADD COLUMN IF NOT EXISTS prompt_embedding extensions.vector(1536);

-- Create check_prompt_similarity SQL function
--   Mirrors check_scene_similarity but queries prompt_embedding column.
--   Default threshold: 0.78 (same as scene similarity — empirically validated pre-Phase 10)
--   Default lookback: 7 days (same window as scene similarity)
CREATE OR REPLACE FUNCTION check_prompt_similarity(
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
        1 - (ch.prompt_embedding <=> query_embedding) AS similarity
    FROM content_history ch
    WHERE
        ch.prompt_embedding IS NOT NULL
        AND ch.created_at > NOW() - (lookback_days || ' days')::interval
        AND (1 - (ch.prompt_embedding <=> query_embedding)) > similarity_threshold
    ORDER BY similarity DESC
    LIMIT 5;
$$;
