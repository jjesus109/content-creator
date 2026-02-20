-- Migration 0002: Script generation support
-- Creates: check_script_similarity function + rejection_constraints table

-- Section A: check_script_similarity SQL function
-- Uses pgvector <=> operator (cosine DISTANCE, not similarity).
-- similarity = 1 - distance. Filter is WHERE (1 - distance) > threshold.
CREATE OR REPLACE FUNCTION check_script_similarity(
    query_embedding extensions.vector(1536),
    similarity_threshold float DEFAULT 0.85,
    lookback_days int DEFAULT 90
)
RETURNS TABLE(id uuid, topic_summary text, similarity float)
LANGUAGE sql
AS $$
    SELECT
        ch.id,
        ch.topic_summary,
        1 - (ch.embedding <=> query_embedding) AS similarity
    FROM content_history ch
    WHERE
        ch.embedding IS NOT NULL
        AND ch.created_at > NOW() - (lookback_days || ' days')::interval
        AND (1 - (ch.embedding <=> query_embedding)) > similarity_threshold
    ORDER BY similarity DESC
    LIMIT 5;
$$;

-- Section B: rejection_constraints table
-- Phase 2 reads it; Phase 4 writes to it.
-- Created now so pipeline queries return empty result safely.
CREATE TABLE IF NOT EXISTS rejection_constraints (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    reason_text  text NOT NULL,
    pattern_type text NOT NULL CHECK (pattern_type IN ('topic', 'tone', 'script_class')),
    expires_at   timestamptz NOT NULL,
    created_at   timestamptz DEFAULT now()
);
