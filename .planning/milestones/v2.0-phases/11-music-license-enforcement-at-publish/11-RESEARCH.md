# Phase 11: Music License Enforcement at Publish - Research

**Researched:** 2026-03-19
**Domain:** Music License Validation Gate in Publishing Pipeline
**Confidence:** HIGH

## Summary

Phase 11 adds a license validation gate to the per-platform publishing pipeline. Before `PublishingService().publish()` is called in `publish_to_platform_job()`, the system queries the `music_pool` table for the track's per-platform clearance flag and license expiry. If the track is not cleared for that platform, or if the license has expired, the job blocks the publish, inserts a `blocked` row into `publish_events`, and sends a Telegram alert to the creator identifying the track and the affected platform.

The gate enforces the already-populated platform flags (`platform_youtube`, `platform_instagram`, `platform_facebook`) and license expiry logic already present in `MusicMatcher`. No new database schema is needed — the music_pool table already has all required columns from Phase 10. TikTok is manual, so no license check is added for it.

**Primary recommendation:** Implement the license gate as an inline check in `publish_to_platform_job()` before `PublishingService().publish()` is called. Reuse the expiry logic from `MusicMatcher.pick_track()` (in-Python comparison: NULL = permanent, ISO string parsed and compared to `datetime.now(timezone.utc)`). Use `send_alert_sync` for Telegram notification following the established pattern. Insert a `blocked` row into `publish_events` with status value requiring schema confirmation.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **Per-platform isolation**: Each platform job checks independently — YouTube blocked does not affect Instagram or Facebook jobs
- **If track not cleared**: Skip that platform's publish, insert a `blocked` row into `publish_events` with reason, send Telegram alert
- **Blocked platform is abandoned for this video** — no re-publish path in Phase 11 (future work)
- **Telegram alert includes**: track title, artist, which platform was blocked, expiry date if applicable (NULL = permanent)
- **Alert suggests fix**: e.g. "Update `platform_youtube = true` in `music_pool` for track '{title}', or assign a different track"
- **Gate placement**: Inside `publish_to_platform_job()`, before the `PublishingService().publish()` call
- **Expiry logic**: Same in-Python check as `MusicMatcher` (NULL = permanent; non-null compared to `datetime.now(timezone.utc)`)
- **TikTok out of scope** — no license check added in Phase 11 (manual posting, no publish() path)
- **music_track_id loading**: Already stored in content_history by Phase 10 pipeline; gate loads it via Supabase select

### Claude's Discretion
- Exact Telegram message wording and formatting for the block alert
- Whether to extract license check into a small helper function or keep inline in `publish_to_platform_job()`
- Whether `publish_events` `blocked` row reuses existing status enum or adds a new status value

### Deferred Ideas (OUT OF SCOPE)
- Re-publish path after license fix — future phase
- TikTok manual posting license warning — not needed
- Compliance audit log per publish (MUS-F02) — tracked in v3.0 requirements
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| PUB-01 | Music license validated against matrix before publishing; publish blocked if track not cleared for target platform. Creator notified via Telegram. | Gate implementation in publish_to_platform_job(), expiry logic from MusicMatcher, platform flags in music_pool schema verified. Telegram pattern established via send_alert_sync. publish_events table already supports status values. |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| supabase-py | >=2.0 | Sync database queries in APScheduler jobs | Already used throughout pipeline for all DB access; sync client required in ThreadPoolExecutor context |
| python-telegram-bot | 21.* | Telegram alert notifications | Established pattern: send_alert_sync used in circuit breaker and error handlers; async wrapper for sync context |
| APScheduler | 3.11.2 | Job scheduling and execution | Existing infrastructure; publish_to_platform_job is registered as DateTrigger job |
| tenacity | >=8.0 | Retry logic | PublishingService._publish_*() methods use @retry decorator already |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytz | >=2024.1 | Timezone handling | Already imported in platform_publish.py for datetime operations |
| python-dotenv | >=1.0 | Environment variable loading | Settings injected via get_settings() — no direct env access needed in job |

**Installation:**
```bash
# All dependencies already in pyproject.toml and runtime environment
# No new packages required for Phase 11
```

**Version verification:** Confirmed against current project pyproject.toml (as of 2026-03-19). All required libraries already present.

## Architecture Patterns

### Existing publish_to_platform_job() Structure
```
publish_to_platform_job(content_history_id, platform, video_url)
  1. Load post_copy from content_history
  2. Apply AI label (_apply_ai_label)
  3. **PHASE 11 GATE INSERTION POINT**: Check music track license here
  4. Call PublishingService().publish()
  5. On success: insert 'published' row, send success notification, schedule verify job
  6. On failure: insert 'failed' row, send fallback notification
```

The license gate replaces step 3 in the above flow: query music_pool for the track's platform clearance and expiry, block if not cleared, send alert, and return early (skipping step 4).

### Recommended Project Structure (no changes needed)
```
src/app/scheduler/jobs/
├── platform_publish.py          # MODIFIED: add license gate before publish()
├── publish_verify.py            # unchanged
└── harvest_metrics.py           # unchanged

src/app/services/
├── music_matcher.py             # REFERENCE: expiry check logic to replicate
├── telegram.py                  # REFERENCE: send_alert_sync pattern
├── publishing.py                # unchanged
└── database.py                  # unchanged
```

### Pattern 1: License Gate Implementation
**What:** Per-platform license validation before publishing, modeled on MusicMatcher expiry logic.
**When to use:** Every platform job that calls PublishingService().publish().
**Example:**
```python
# Source: MusicMatcher.pick_track() in src/app/services/music_matcher.py (lines 84-103)
# Replicate this pattern in publish_to_platform_job():

from datetime import datetime, timezone

# Load music_track_id from content_history (already stored by Phase 10)
row_result = supabase.table("content_history").select(
    "post_copy_tiktok, post_copy_instagram, post_copy_facebook, post_copy_youtube, post_copy, music_track_id"
).eq("id", content_history_id).single().execute()
row = row_result.data
music_track_id = row.get("music_track_id")

# If no track assigned (backward compatibility), skip license check
if not music_track_id:
    logger.info("No music_track_id for content_history_id=%s; skipping license gate", content_history_id)
else:
    # Query music_pool for platform clearance
    track_result = supabase.table("music_pool").select(
        "title, artist, license_expires_at, platform_tiktok, platform_youtube, platform_instagram, platform_facebook"
    ).eq("id", music_track_id).single().execute()
    track = track_result.data

    # Check platform flag
    platform_flag = f"platform_{platform}"
    is_cleared = track.get(platform_flag, False)

    if not is_cleared:
        # Log and block
        logger.warning(
            "Music license gate: %s not cleared for %s (platform=%s)",
            track.get("title"), track.get("artist"), platform
        )
        # Insert blocked row (see Pattern 2)
        # Send alert (see Pattern 3)
        return  # Skip publish_to_platform_job

    # Check expiry
    expires_at = track.get("license_expires_at")
    now_utc = datetime.now(timezone.utc)
    if expires_at is not None:
        try:
            expiry = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
            if expiry <= now_utc:
                logger.warning(
                    "Music license expired for track %s (expired %s)",
                    track.get("title"), expires_at
                )
                # Insert blocked row
                # Send alert
                return  # Skip publish_to_platform_job
        except (ValueError, AttributeError) as e:
            logger.error("Failed to parse license expiry date: %s", e)
            # Continue (fail open — unparseable date is not a blocker)
```

### Pattern 2: Insert Blocked Row into publish_events
**What:** Record that a platform publish was blocked due to license check.
**Example:**
```python
# Source: platform_publish.py insert patterns (lines 122-130, 176-181)
# Replicate for 'blocked' status:

supabase.table("publish_events").insert({
    "content_history_id": content_history_id,
    "platform": platform,
    "status": "blocked",  # NEW status value (see Claude's Discretion below)
    "error_message": f"Music license not cleared for {track.get('title')} on {platform}",
    "scheduled_at": datetime.now(tz=timezone.utc).isoformat(),
}).execute()
```

### Pattern 3: Send Telegram Alert on License Block
**What:** Notify creator via Telegram when a platform publish is blocked due to license issue.
**Example:**
```python
# Source: send_alert_sync() in src/app/services/telegram.py (lines 70-77)
# Reuse send_alert_sync for consistency:

from app.services.telegram import send_alert_sync

track_title = track.get("title")
track_artist = track.get("artist")
expiry_str = track.get("license_expires_at") or "permanent"

alert_message = (
    f"🚫 {platform.upper()} publish blocked\n\n"
    f"Track: '{track_title}' by {track_artist}\n"
    f"License status for {platform}: NOT CLEARED\n"
    f"Expires: {expiry_str}\n\n"
    f"Fix: Update music_pool platform_{platform} = true for this track,\n"
    f"or assign a different licensed track to this video."
)

send_alert_sync(alert_message)
```

### Anti-Patterns to Avoid
- **Querying music_pool in schedule_platform_publishes()**: License check must happen inside the job (where we have platform context), not during scheduling (future platform unknown). Scheduling is "register all 3 platforms", job execution is "check this specific platform".
- **Applying license check to TikTok**: TikTok is manual posting (no publish_to_platform_job call). Do not add a check for platform == "tiktok".
- **Retrying on license block**: If a track is not cleared for a platform, blocking is intentional. Do not use tenacity @retry; return early instead.
- **Silent failure**: Always insert publish_events row and send Telegram alert. Never block without notifying creator.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Async Telegram in sync context | Custom asyncio wrapper | `send_alert_sync()` from telegram.py | Already handles event loop capture, fallback to direct Bot if loop unavailable. Custom implementation risks RuntimeError on Python 3.10+ asyncio issues. |
| Date/time parsing and timezone handling | Custom ISO string parser | `datetime.fromisoformat()` + timezone.utc | Built-in, handles ISO 8601 with Z suffix correctly. MusicMatcher already uses this pattern; consistency matters. |
| Supabase query building | Custom filter logic | Supabase client .select().eq().execute() | Supabase SDK is sync-safe in ThreadPoolExecutor. Custom queries are error-prone; framework handles edge cases (NULL handling, type coercion). |
| Database status enum validation | Custom string checks | Use existing publish_events status enum in schema | Schema constraint CHECK (status IN (...)) validates on insert. Hand-rolling risks inconsistency; schema is source of truth. |

**Key insight:** Publishing pipelines are critical paths where blocking/letting-through decisions cascade downstream. Reusing established patterns (send_alert_sync, datetime parsing, Supabase queries) from MusicMatcher and existing error handlers ensures consistency and avoids edge-case handling bugs.

## Common Pitfalls

### Pitfall 1: Forgetting to Load music_track_id in the SELECT
**What goes wrong:** Assuming music_track_id is always present in the row loaded from content_history. Some legacy rows (before Phase 10) may have NULL music_track_id. Code fails with KeyError or tries to query music_pool with NULL.
**Why it happens:** Easy to copy the existing select() statement without noticing music_track_id isn't fetched. Phase 10 adds the column and populates it; older rows are grandfathered in without re-processing.
**How to avoid:** Always include "music_track_id" in the select() statement. Check `if not music_track_id:` and skip the license gate for backward compatibility (fail-open: publish if no track assigned).
**Warning signs:** Publish job throws KeyError / NoneType error on first run against a database with pre-Phase-10 rows.

### Pitfall 2: Confusing Platform Flag Names
**What goes wrong:** Using wrong flag name (e.g., `platform_tiktok_cleared` instead of `platform_tiktok`). Query executes but returns wrong result.
**Why it happens:** Column names in music_pool are simple boolean flags: `platform_tiktok`, `platform_youtube`, `platform_instagram`, `platform_facebook`. Easy to assume extra prefixes like `_cleared`.
**How to avoid:** Reference MusicMatcher.pick_track() line 63: `platform_flag = f"platform_{target_platform}"`. Copy this pattern verbatim.
**Warning signs:** License check passes but creator says it shouldn't have (or vice versa). Inspect the Telegram alert — it will contain the track info but won't have been blocked correctly.

### Pitfall 3: Expiry Check Off-by-One Errors
**What goes wrong:** Using `>=` instead of `>` when comparing expiry to now. A track that expires at 2026-03-19 23:59:59 UTC is rejected at 2026-03-20 00:00:01 UTC, but using `>=` rejects at exactly expiry time.
**Why it happens:** Boundary conditions are tricky. Easy to flip > and <.
**How to avoid:** Replicate MusicMatcher line 95 exactly: `if expiry > now_utc: valid_candidates.append(track)`. This means: if expiry is in the future, it's valid. If expiry equals now, it's expired (fail-closed).
**Warning signs:** Tracks that expire at midnight are rejected a day early. Test with a track that has license_expires_at = "2026-03-19T00:00:00Z" and current time = 2026-03-18 23:59:59 UTC — should pass. Current time = 2026-03-19 00:00:01 UTC — should fail.

### Pitfall 4: Blocking Without Recording publish_events
**What goes wrong:** Return early from publish_to_platform_job() without inserting a row into publish_events. Creator has no record that the publish was attempted and blocked.
**Why it happens:** Rushing to implement; forget to insert the status='blocked' row before returning.
**How to avoid:** Always follow the pattern: (1) detect block condition, (2) insert publish_events row, (3) send alert, (4) return.
**Warning signs:** Verification job finds no record of the platform publish (verified or failed); creator receives alert but no context in publish_events table.

### Pitfall 5: Telegram Alert Sent But Job Crashes After
**What goes wrong:** Alert sent to creator, but job raises exception after (e.g., Supabase insert fails). Creator is notified but publish_events has no record.
**Why it happens:** Not wrapping the full license gate logic in try/except. If send_alert_sync() succeeds but insert fails, alert is sent with no backing record.
**How to avoid:** Order: (1) validate license, (2) insert publish_events row, (3) send alert, (4) return. If insert fails, don't send alert (let exception bubble). Creator will get job failure log instead.
**Warning signs:** Creator reports getting license block alert with no matching row in publish_events.

### Pitfall 6: Backward Compatibility - Old Rows Without music_track_id
**What goes wrong:** Phase 10 added music_track_id column and populated it for new videos. Old videos in the database have NULL. License gate crashes or silently succeeds.
**Why it happens:** Schema migration adds column with default NULL. Old rows are not backfilled.
**How to avoid:** Check `if not music_track_id: logger.info(...); continue` before querying music_pool. Fail-open: if no track assigned, publish anyway (creator will have gotten music selection at video creation time; gap is tolerable).
**Warning signs:** Legacy videos in database fail to publish after Phase 11 is deployed; new videos work fine.

## Code Examples

Verified patterns from official sources:

### License Gate Insertion Point
```python
# Source: src/app/scheduler/jobs/platform_publish.py (current structure, lines 78-110)
# Integration point: after line 109 (labeled_copy set), before line 112 (PublishingService call)

def publish_to_platform_job(
    content_history_id: str,
    platform: str,
    video_url: str,
) -> None:
    """Publish the approved video to a single platform."""
    supabase = get_supabase()
    settings = get_settings()

    # Load platform-specific copy from content_history
    # PHASE 11: Add music_track_id to the select
    row_result = supabase.table("content_history").select(
        "post_copy_tiktok, post_copy_instagram, post_copy_facebook, post_copy_youtube, post_copy, music_track_id"
    ).eq("id", content_history_id).single().execute()
    row = row_result.data

    copy_key = f"post_copy_{platform}"
    post_copy = row.get(copy_key) or row.get("post_copy", "")

    # AI content label: apply before publish
    try:
        labeled_copy = _apply_ai_label(post_copy, platform)
    except Exception as label_exc:
        logger.error(
            "AI label application failed for platform=%s, falling back to prefix: %s",
            platform, label_exc,
        )
        labeled_copy = f"{AI_LABEL}\n{post_copy}" if post_copy else AI_LABEL

    # ===== PHASE 11: LICENSE GATE INSERTION POINT =====
    # Check music license before publishing
    if not _check_music_license_cleared(supabase, row, platform, content_history_id):
        return  # Block inserted in _check_music_license_cleared()
    # ===== END PHASE 11 GATE =====

    try:
        response = PublishingService().publish(
            platform=platform,
            post_text=labeled_copy,
            video_url=video_url,
        )
        # ... rest of success handling
```

### License Check Helper Function (Claude's Discretion: inline vs. helper)
```python
# Source: Proposed helper function (inline version also valid per CONTEXT.md)
# Use this if extracting to a separate function; otherwise duplicate logic inline

def _check_music_license_cleared(
    supabase: Client,
    content_history_row: dict,
    platform: str,
    content_history_id: str,
) -> bool:
    """
    Check if the music track assigned to this video is cleared for the given platform.

    Returns:
        True if cleared (or no track assigned — fail-open).
        False if blocked; inserts publish_events row and sends Telegram alert.
    """
    from datetime import datetime, timezone
    from app.services.telegram import send_alert_sync

    music_track_id = content_history_row.get("music_track_id")
    if not music_track_id:
        logger.info(
            "No music_track_id assigned for content_history_id=%s; allowing publish",
            content_history_id
        )
        return True

    # Query music_pool for platform clearance and expiry
    try:
        track_result = supabase.table("music_pool").select(
            "title, artist, license_expires_at, platform_tiktok, platform_youtube, platform_instagram, platform_facebook"
        ).eq("id", music_track_id).single().execute()
        track = track_result.data
    except Exception as e:
        logger.error(
            "Failed to query music_pool for track_id=%s: %s",
            music_track_id, e
        )
        # Fail open on DB error — publish anyway
        return True

    # Check platform clearance flag
    platform_flag = f"platform_{platform}"
    is_cleared = track.get(platform_flag, False)

    if not is_cleared:
        error_msg = (
            f"Music license not cleared for platform {platform}: "
            f"'{track.get('title')}' by {track.get('artist')}"
        )
        logger.warning("License gate block: %s", error_msg)

        # Insert blocked row
        supabase.table("publish_events").insert({
            "content_history_id": content_history_id,
            "platform": platform,
            "status": "blocked",
            "error_message": error_msg,
            "scheduled_at": datetime.now(tz=timezone.utc).isoformat(),
        }).execute()

        # Send Telegram alert
        track_title = track.get("title", "Unknown")
        track_artist = track.get("artist", "Unknown")
        alert = (
            f"🚫 {platform.upper()} publish blocked\n\n"
            f"Track: '{track_title}' by {track_artist}\n"
            f"Reason: Not cleared for {platform}\n\n"
            f"Fix: Update music_pool platform_{platform} = true,\n"
            f"or assign a different track to this video."
        )
        send_alert_sync(alert)
        return False

    # Check license expiry
    expires_at = track.get("license_expires_at")
    now_utc = datetime.now(timezone.utc)
    if expires_at is not None:
        try:
            expiry = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
            if expiry <= now_utc:
                error_msg = (
                    f"Music license expired for '{track.get('title')}' "
                    f"(expired {expires_at})"
                )
                logger.warning("License gate block (expired): %s", error_msg)

                # Insert blocked row
                supabase.table("publish_events").insert({
                    "content_history_id": content_history_id,
                    "platform": platform,
                    "status": "blocked",
                    "error_message": error_msg,
                    "scheduled_at": datetime.now(tz=timezone.utc).isoformat(),
                }).execute()

                # Send alert
                alert = (
                    f"🚫 {platform.upper()} publish blocked\n\n"
                    f"Track: '{track.get('title')}' by {track.get('artist')}\n"
                    f"Reason: License expired ({expires_at})\n\n"
                    f"Fix: Assign a different track with active license."
                )
                send_alert_sync(alert)
                return False
        except (ValueError, AttributeError) as e:
            logger.error(
                "Failed to parse license expiry for track '%s': %s",
                track.get("title"), e
            )
            # Fail open — unparseable date is not a blocker
            return True

    # All checks passed — licensed for this platform
    logger.info(
        "Music license cleared for '%s' on %s",
        track.get("title"), platform
    )
    return True
```

### publish_events Row Structure for 'blocked' Status
```python
# Source: src/app/services/publishing.py + migrations/0005_publishing.sql
# Verify status enum before implementing; see schema notes below

# Current schema (0005_publishing.sql, line 45):
# status text NOT NULL CHECK (status IN ('published', 'failed', 'verified', 'verify_failed'))
#
# PHASE 11 DECISION NEEDED (Claude's Discretion):
# Option A: Add 'blocked' to the CHECK constraint in a new migration
# Option B: Reuse 'failed' status with error_message containing "blocked by license"
#
# Recommendation: Option A (add 'blocked' to schema) for clarity in queries.
# If Option B used, always prefix error_message with "BLOCKED: " for discoverability.

# Schema update (if Option A chosen):
# ALTER TABLE publish_events
#     DROP CONSTRAINT publish_events_status_check;
# ALTER TABLE publish_events
#     ADD CONSTRAINT publish_events_status_check
#     CHECK (status IN ('published', 'failed', 'verified', 'verify_failed', 'blocked'));
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Manual license matrix check | Automated license gate in publish job | Phase 11 | Creator no longer manually verifies; system blocks ineligible tracks automatically |
| Track selected without platform context | Track matched at scene selection time; platform validated at publish time | Phase 10 (MusicMatcher) → Phase 11 (gate) | Clear separation: MusicMatcher ensures track exists and has BPM match; license gate ensures platform-specific clearance at publish boundary |
| Single license flag per track | Per-platform boolean flags + nullable expiry | Phase 10 | Platform-specific licensing enables future multi-territorial release strategies |

**Deprecated/outdated:**
- Manual license check in approval flow: Not implemented in v1.0 or v2.0; Phase 11 is first automated check.
- Global track enable/disable: Replaced by per-platform flags in music_pool (platform_tiktok, platform_youtube, platform_instagram, platform_facebook).

## Open Questions

1. **publish_events 'blocked' Status Value**
   - What we know: Schema currently supports ('published', 'failed', 'verified', 'verify_failed'). Phase 11 needs to record license blocks.
   - What's unclear: Should 'blocked' be added as a 5th status (requires schema migration 0010), or reuse 'failed' with a "BLOCKED:" prefix in error_message?
   - Recommendation: Add 'blocked' status via new migration for query clarity. Queries like `SELECT * FROM publish_events WHERE status = 'blocked'` will clearly identify license failures vs. API failures.

2. **Helper Function vs. Inline Implementation**
   - What we know: CONTEXT.md lists this as "Claude's Discretion". Both approaches are valid.
   - What's unclear: Code readability vs. import complexity. Helper function adds ~50 lines to platform_publish.py but improves testability.
   - Recommendation: Keep inline in publish_to_platform_job() for first pass (similar to _apply_ai_label). If the gate logic grows (e.g., adding fallback track selection), extract to helper.

3. **Backward Compatibility: Handling Pre-Phase-10 Rows**
   - What we know: Phase 10 adds music_track_id to content_history and populates it for new videos. Older rows have NULL.
   - What's unclear: Should old videos fail to publish (strict: no license data available), or publish anyway (lenient: music was selected pre-Phase-10)?
   - Recommendation: Publish anyway (fail-open). These videos already approved and scheduled; blocking them creates user friction. Creator can manually unpublish if needed. Log a warning for observability.

## Validation Architecture

> Note: workflow.nyquist_validation not found in .planning/config.json, treating as enabled.

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest >=8.0 |
| Config file | pyproject.toml [tool.pytest.ini_options] |
| Quick run command | `pytest tests/test_music_license_gate.py -x -v` |
| Full suite command | `pytest tests/ -x -v` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| PUB-01 | Track not cleared for platform → publish blocked, Telegram alert sent, publish_events row inserted | unit | `pytest tests/test_music_license_gate.py::test_license_gate_blocks_uncleered_track -xvs` | ❌ Wave 0 |
| PUB-01 | Track cleared with valid license → publish proceeds to PublishingService | unit | `pytest tests/test_music_license_gate.py::test_license_gate_allows_cleared_track -xvs` | ❌ Wave 0 |
| PUB-01 | Track license expired → publish blocked, error_message includes expiry date | unit | `pytest tests/test_music_license_gate.py::test_license_gate_blocks_expired_track -xvs` | ❌ Wave 0 |
| PUB-01 | No music_track_id (legacy row) → publish proceeds (fail-open) | unit | `pytest tests/test_music_license_gate.py::test_license_gate_skips_if_no_track_id -xvs` | ❌ Wave 0 |
| PUB-01 | publish_events table receives 'blocked' status row | unit | `pytest tests/test_music_license_gate.py::test_blocked_row_inserted_on_license_fail -xvs` | ❌ Wave 0 |
| PUB-01 | Telegram alert includes track title, artist, platform, expiry | unit | `pytest tests/test_music_license_gate.py::test_telegram_alert_format -xvs` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/test_music_license_gate.py -x` (5-10 second run)
- **Per wave merge:** `pytest tests/ -x` (full suite, ~20-30 seconds for all unit tests)
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_music_license_gate.py` — License gate logic for all PUB-01 scenarios
- [ ] `tests/conftest.py` — Update SAMPLE_MUSIC_POOL to include license_expires_at field (currently missing, set to NULL)
- [ ] Mock fixture for expired track scenario (add track with license_expires_at = "2026-01-01T00:00:00Z")

## Sources

### Primary (HIGH confidence)
- Phase 10 schema migration (0009_phase10_schema.sql) — music_track_id column, music_pool schema verified
- Phase 5 schema (0005_publishing.sql) — publish_events table structure and status enum documented
- src/app/scheduler/jobs/platform_publish.py — current job structure, integration point confirmed
- src/app/services/music_matcher.py — expiry check logic (lines 84-103) copied for consistency
- src/app/services/telegram.py — send_alert_sync pattern (lines 70-77) verified for APScheduler context
- .planning/phases/11-music-license-enforcement-at-publish/11-CONTEXT.md — locked decisions and code context

### Secondary (MEDIUM confidence)
- pyproject.toml — confirmed all required dependencies already present; no new packages needed
- tests/conftest.py — existing test infrastructure for music_pool mocking provides template for Phase 11 tests

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries already in use; no new packages required
- Architecture: HIGH — integration point clearly defined in existing code; patterns replicable from MusicMatcher and send_alert_sync
- Pitfalls: HIGH — backward compatibility and null-handling risks identified via code inspection
- Schema/database: HIGH — music_pool columns verified in 0009 migration; publish_events structure stable
- Testing: MEDIUM — test framework established; specific test cases for license gate require implementation details

**Research date:** 2026-03-19
**Valid until:** 2026-03-26 (7 days — fast-moving feature, schema decisions pending)

---

*Research for Phase 11 complete. Planner can now create PLAN.md files.*
