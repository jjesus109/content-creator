-- Phase 3: Video Production columns on content_history
-- heygen_job_id: returned by POST /v2/video/generate; used by poller and webhook to track render
-- video_url: stable Supabase Storage public URL (NEVER the HeyGen signed URL)
-- video_status: lifecycle state; constrained to six valid values including retry sentinel
-- background_url: the dark background image URL used for this render (for consecutive-repeat prevention)

ALTER TABLE content_history
  ADD COLUMN IF NOT EXISTS heygen_job_id    text,
  ADD COLUMN IF NOT EXISTS video_url        text,
  ADD COLUMN IF NOT EXISTS video_status     text
    CHECK (video_status IN (
      'pending_render',
      'pending_render_retry',
      'rendering',
      'processing',
      'ready',
      'failed'
    )),
  ADD COLUMN IF NOT EXISTS background_url   text;
