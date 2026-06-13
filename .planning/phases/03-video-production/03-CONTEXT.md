# Phase 3: Video Production - Context

**Gathered:** 2026-02-20
**Status:** Ready for planning

<domain>
## Phase Boundary

Every generated script becomes a rendered, audio-processed 9:16 avatar video stored at a stable Supabase Storage URL. The HeyGen signed URL is never the canonical reference — re-hosting to stable storage happens immediately on render completion. Video approval and publishing are separate phases.

</domain>

<decisions>
## Implementation Decisions

### HeyGen render configuration
- One fixed avatar ID — single identity, no rotation. Configured as `HEYGEN_AVATAR_ID` in settings.
- Backgrounds use HeyGen built-in scene IDs — pick a curated set of dark/cinematic scenes from their library
- Background rotation rule: no two consecutive videos use the same scene — store last used scene ID in DB, pick any different one for next render. Simple last-used tracking only.
- One fixed voice ID in settings (`HEYGEN_VOICE_ID`) — consistent brand voice, no rotation

### Completion detection
- Pipeline job submits script to HeyGen and exits immediately — does NOT block waiting for render
- Webhook-first: register a FastAPI webhook endpoint that HeyGen calls on completion; cancels the poller when it fires
- Polling as fallback: separate APScheduler job polls HeyGen status every 60 seconds in case webhook never fires
- Timeout: 20 minutes from submission — if not complete by then, retry once (resubmit same script), then alert creator via Telegram and skip the day
- HeyGen job ID stored in `content_history.heygen_job_id` so the poller can track in-flight renders across restarts

### Audio post-processing (ffmpeg)
- Both voice processing AND background music mixed together
- Voice: subtle low-shelf EQ boost for warmth — no compression, no reverb
- Background music: 2-4 ambient tracks stored as public files in Supabase Storage (NOT bundled in repo — keeps Docker image lightweight)
- Track rotation: picks a different track per video from the small pool (rotate or random, Claude decides)
- Music volume: ~20-30% relative to voice — audible but never competes with speech
- ffmpeg downloads the audio track from Supabase Storage URL at processing time, no disk cache needed

### Storage
- Supabase Storage — already in the stack, no new service or credentials required
- Public bucket — permanent, stable public URLs (content will be published anyway)
- File naming: `videos/YYYY-MM-DD.mp4` — human-readable, one video per day
- Schema: add three columns to existing `content_history` table (no new table):
  - `heygen_job_id` — HeyGen render job ID, used by poller and webhook to track completion
  - `video_url` — stable Supabase Storage public URL, set after upload
  - `video_status` — enum: `pending_render` | `rendering` | `processing` | `ready` | `failed`

### Claude's Discretion
- Exact HeyGen API v2 endpoint structure and request body shape (verify against live docs during research)
- ffmpeg filter chain specifics for EQ (frequency, gain, Q values)
- How to handle the case where `videos/YYYY-MM-DD.mp4` already exists (overwrite or append timestamp suffix)
- Poller job schedule timing and whether to use a one-shot job or a recurring job that self-cancels on webhook receipt

</decisions>

<specifics>
## Specific Ideas

- Docker image must stay lightweight — no audio tracks bundled in repo. Store all media assets in Supabase Storage and fetch at runtime.
- Railway cost matters — prefer approaches that minimize compute time and image size.
- The HeyGen signed URL expires — downloading to Supabase Storage must happen before expiry. Poller/webhook should trigger download immediately on render completion signal.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 03-video-production*
*Context gathered: 2026-02-20*
