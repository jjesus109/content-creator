-- Local dev database initialization
-- Runs once when the PostgreSQL container is first created.
-- Sets up the roles and schema that PostgREST expects.

-- Roles expected by the Supabase-compatible JWT tokens in .env.local.example
CREATE ROLE anon          NOLOGIN NOINHERIT;
CREATE ROLE authenticated NOLOGIN NOINHERIT;
CREATE ROLE service_role  NOLOGIN NOINHERIT BYPASSRLS;

-- Extensions schema (mirrors Supabase cloud layout)
CREATE SCHEMA IF NOT EXISTS extensions;
GRANT USAGE ON SCHEMA extensions TO anon, authenticated, service_role;

-- Enable pgvector now so the type is available before migrations run
CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA extensions;

-- Allow service_role full access to public schema (current + future objects)
GRANT USAGE  ON SCHEMA public TO service_role;
GRANT ALL    ON ALL TABLES    IN SCHEMA public TO service_role;
GRANT ALL    ON ALL SEQUENCES IN SCHEMA public TO service_role;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES    TO service_role;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO service_role;
