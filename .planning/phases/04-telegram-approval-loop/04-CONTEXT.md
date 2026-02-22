# Phase 4: Telegram Approval Loop - Context

**Gathered:** 2026-02-22
**Status:** Ready for planning

<domain>
## Phase Boundary

Daily Telegram interaction: the creator receives a video for review, taps Approve or Reject with Cause, and the system acts on that decision. This phase closes the production loop and gates the publish pipeline. Post copy generation, approval state persistence, and rejection feedback injection into future runs are all in scope. Platform scheduling details and multi-platform publish are Phase 5.

</domain>

<decisions>
## Implementation Decisions

### Message design
- Video presented as URL + thumbnail image inline — creator sees a frame before tapping
- Message contains: video URL, generated post copy, and metadata (generation date, mood profile used, script word count, background used)
- Two inline keyboard buttons side by side: ✅ Approve | ❌ Reject with Cause

### Post copy generation
- Language: Spanish (same as the script — no translation)
- Format: Hook line + 2–3 body lines + hashtags
- Generated just before Telegram delivery (Phase 4 responsibility, not Phase 2 pipeline)
- Model: Claude Haiku (same model used for script generation)
- Stored to content_history alongside the video record

### Rejection flow behavior
- Rejection triggers immediate retry (same day) — new script + new video with the constraint injected, new approval message sent
- Daily retry limit: 2 rejections per day (3 total attempts before the run is abandoned)
- Rejection cause categories: Script Error / Visual Error / Technical Error / Off-topic
- Constraint persistence: rejection cause remains active until a run in that category is approved — it does not clear after a single injection

### Approval state & feedback
- After tapping Approve or Reject: a new follow-up message is sent (original message stays unchanged)
- Approval confirmation: "✅ Approved — queued for publish" (Phase 5 will enhance with actual platform schedule times)
- Rejection confirmation: "⚠️ Rejected ([cause]) — new video incoming in ~X minutes"
- Daily retry limit reached notification: "Daily limit reached, next run tomorrow at [time]"
- Approval state stored in a separate `approval_events` table (not extending content_history directly)
- Restart-safe: inline keyboard buttons remain functional after server restart — approval state always read from DB, never in-memory

### Claude's Discretion
- Exact thumbnail generation approach (whether to extract a frame from video or use a cover image)
- Precise retry timing estimate shown in rejection confirmation message
- Schema details for approval_events table beyond the decisions above
- How rejection constraints are surfaced to the script generation prompt (format/injection logic)

</decisions>

<specifics>
## Specific Ideas

- The creator's only job is to say yes or no — the message should make that decision as fast as possible: video link, copy preview, one tap
- Rejection cause categories: Script Error, Visual Error, Technical Error, Off-topic — 4 options, structured menu (no free-form text)
- Approval confirmation shows "queued for publish" now; Phase 5 will replace/enhance this with actual platform scheduled times once Ayrshare scheduling is wired

</specifics>

<deferred>
## Deferred Ideas

- Platform-specific scheduled post times in approval confirmation — Phase 5 (requires Ayrshare scheduling to be built first)

</deferred>

---

*Phase: 04-telegram-approval-loop*
*Context gathered: 2026-02-22*
