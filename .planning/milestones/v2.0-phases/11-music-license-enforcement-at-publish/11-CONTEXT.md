# Phase 11: Music License Enforcement at Publish - Context

**Gathered:** 2026-03-19
**Status:** Ready for planning

<domain>
## Phase Boundary

Add a per-platform license validation gate inside `publish_to_platform_job()` that runs before calling `PublishingService().publish()`. Gate reads `music_track_id` from `content_history`, queries `music_pool` for the platform clearance flag + license expiry, and blocks publish with a Telegram alert if not cleared. TikTok is out of scope (manual posting, no publish() path). Music in the pool is AI-generated but per-platform rules still apply via the flags already in `music_pool`.

</domain>

<decisions>
## Implementation Decisions

### Blocking behavior
- **Per-platform isolation**: each platform job (`publish_to_platform_job()`) checks independently — YouTube blocked does not affect Instagram or Facebook jobs
- If a track is not cleared for a platform: skip that platform's publish, insert a `blocked` row into `publish_events` (with reason), send Telegram alert
- Blocked platform is **abandoned for this video** — no re-publish path in Phase 11 (future work)

### Telegram alert on block
- Alert includes: track title, artist, which platform was blocked, expiry date if applicable (null = permanent — note that it has permanent clearance but platform flag is False)
- Alert suggests fix: e.g. "Update `platform_youtube = true` in `music_pool` for track '{title}', or assign a different track"
- Uses existing `send_alert_sync` / Telegram alert pattern (same as MusicMatcher ValueError alerts)

### TikTok
- **Out of scope** — TikTok is manual posting; no license check added in Phase 11
- All music is AI-generated; platform-specific clearance flags in `music_pool` still govern which platforms a track may appear on

### Gate placement
- Gate lives inside `publish_to_platform_job()`, before the `PublishingService().publish()` call
- Job loads `music_track_id` from `content_history` (already stored by Phase 10 pipeline)
- Queries `music_pool` for: `platform_{platform}` flag + `license_expires_at` for that track
- Expiry logic: same in-Python check as `MusicMatcher` (NULL = permanent; non-null compared to `datetime.now(timezone.utc)`)

### Claude's Discretion
- Exact Telegram message wording and formatting for the block alert
- Whether to extract license check into a small helper function or keep inline in `publish_to_platform_job()`
- Whether `publish_events` `blocked` row reuses existing status enum or adds a new status value

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements
- `.planning/REQUIREMENTS.md` — PUB-01 acceptance criteria (the license gate requirement)
- `.planning/STATE.md` — Accumulated v2.0 decisions and completed phase context

### Existing codebase (read before modifying)
- `src/app/scheduler/jobs/platform_publish.py` — `publish_to_platform_job()`: where the license gate is inserted; currently loads post_copy and calls PublishingService().publish()
- `src/app/services/music_matcher.py` — `MusicMatcher.pick_track()`: expiry check logic to replicate (in-Python, not DB filter); `VALID_PLATFORMS` constant; platform flag naming convention (`platform_tiktok`, `platform_youtube`, `platform_instagram`)
- `src/app/services/publishing.py` — `PublishingService.publish()` and `schedule_platform_publishes()`: understand what publish_to_platform_job() calls and what platforms it covers
- `src/app/services/telegram.py` — `send_alert_sync` / Telegram notification pattern to reuse for block alerts

### DB schema
- `music_pool` table columns: `id`, `title`, `artist`, `platform_tiktok`, `platform_youtube`, `platform_instagram`, `license_expires_at` — gate queries these

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `send_alert_sync` (`src/app/services/telegram.py`): reuse for block alert — existing pattern for pipeline errors/alerts
- License expiry check in `MusicMatcher.pick_track()` (`src/app/services/music_matcher.py`): copy the in-Python expiry comparison logic (NULL = permanent, ISO string parsed + compared to now_utc)
- `publish_events` table: already used for `published` / `failed` rows — add `blocked` status row with `error_message` containing the reason

### Established Patterns
- APScheduler jobs are sync (ThreadPoolExecutor) — any new DB query must use sync Supabase client (already established)
- Telegram alerts on error: `send_alert_sync(message)` called before returning / raising (Phase 9 + 10 pattern)
- `content_history_id` is always available inside `publish_to_platform_job()` — use it to load `music_track_id` via Supabase select

### Integration Points
- `publish_to_platform_job()` line after loading post_copy (row already fetched from `content_history`) — add `music_track_id` to the select and insert license check before `PublishingService().publish()`
- `publish_events` table: insert `blocked` row (mirrors `failed` row structure) when license check fails

</code_context>

<specifics>
## Specific Ideas

- Music in the pool is AI-generated — but per-platform license rules still apply via the boolean flags in `music_pool`; the gate enforces those flags regardless of music origin
- If `music_track_id` is None (old pipeline rows without a track assigned), gate should skip the check and allow publish (fail-open for backward compatibility)
- Block alert example wording: "🚫 YouTube publish blocked — track '{title}' by {artist} is not cleared for YouTube. Fix: set platform_youtube = true in music_pool, or update the track assignment for this video."

</specifics>

<deferred>
## Deferred Ideas

- Re-publish path after license fix — future phase
- TikTok manual posting license warning — not needed (AI-generated music, manual flow)
- Compliance audit log per publish (MUS-F02) — tracked in v3.0 requirements

</deferred>

---

*Phase: 11-music-license-enforcement-at-publish*
*Context gathered: 2026-03-19*
