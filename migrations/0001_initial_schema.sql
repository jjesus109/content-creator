-- Migration 0001: Initial schema
-- Tables: pipeline_runs, content_history, mood_profiles, circuit_breaker_state
-- pgvector extension + HNSW index on content_history.embedding

CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA extensions;

CREATE TABLE IF NOT EXISTS pipeline_runs (
    id            uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    created_at    timestamptz DEFAULT now() NOT NULL,
    status        text NOT NULL CHECK (status IN ('running','completed','failed','rejected')),
    mood_profile  text,
    error_message text,
    cost_usd      numeric(10,6) DEFAULT 0
);

CREATE TABLE IF NOT EXISTS content_history (
    id               uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    created_at       timestamptz DEFAULT now() NOT NULL,
    pipeline_run_id  uuid REFERENCES pipeline_runs(id),
    script_text      text NOT NULL,
    topic_summary    text,
    embedding        extensions.vector(1536),
    rejection_reason text,
    published_at     timestamptz
);

CREATE INDEX IF NOT EXISTS content_history_embedding_hnsw
    ON content_history
    USING hnsw (embedding extensions.vector_cosine_ops);

CREATE TABLE IF NOT EXISTS mood_profiles (
    id           uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    created_at   timestamptz DEFAULT now() NOT NULL,
    week_start   date NOT NULL UNIQUE,
    profile_text text NOT NULL
);

CREATE TABLE IF NOT EXISTS circuit_breaker_state (
    id                   int PRIMARY KEY DEFAULT 1,
    current_day_cost     numeric(10,6) DEFAULT 0,
    current_day_attempts int DEFAULT 0,
    tripped_at           timestamptz,
    last_trip_at         timestamptz,
    weekly_trip_count    int DEFAULT 0,
    week_start           date DEFAULT CURRENT_DATE,
    updated_at           timestamptz DEFAULT now()
);

INSERT INTO circuit_breaker_state (id) VALUES (1) ON CONFLICT DO NOTHING;
