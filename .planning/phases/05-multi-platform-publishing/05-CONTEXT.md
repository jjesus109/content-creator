# Phase 5: Multi-Platform Publishing - Context

**Gathered:** 2026-02-25
**Status:** Ready for planning

<domain>
## Phase Boundary

Schedule and publish the approved video to TikTok, Instagram Reels, Facebook Reels, and YouTube Shorts via Ayrshare — at platform-specific peak hours, with publish verification, and a Telegram fallback if any platform fails. Analytics, metrics harvesting, and storage lifecycle are separate phases.

</domain>

<decisions>
## Implementation Decisions

### Peak hour scheduling
- Each platform publishes at its own platform-specific peak hour (not all simultaneously)
- Default peak windows (research-based, in audience timezone): TikTok 7–9pm, IG 11am–1pm, FB 1–3pm, YT 12–3pm
- Audience timezone is configurable in settings (fixed, but modifiable) — not derived from creator location
- If approval comes in after today's peak window has passed: schedule for tomorrow's peak, never publish off-hours

### Post copy per platform
- Platform-adapted copy — 4 variants generated (TikTok conversational + ~5 hashtags, IG aesthetic + 20-30 hashtags, FB slightly longer, YT SEO title + description)
- Variants generated during video production (before Telegram delivery) — alongside Phase 4 PostCopyService, stored in DB
- All 4 variants shown in the approval Telegram message: stacked in one message with platform labels (e.g., 🎵 TikTok:\n[copy]\n\n📷 Instagram:\n[copy] etc.)

### Telegram confirmation flow
- After Approve: send a separate follow-up message with per-platform scheduled times (e.g., "Scheduled: TikTok 7:00pm, IG 11:00am tomorrow, FB 1:00pm tomorrow, YT 12:00pm tomorrow (US/Eastern)")
- Original approval message (video + copy + buttons) is left unchanged — no edits to it
- After each platform successfully publishes: send one notification per platform as they fire throughout the day
- 30-minute post-publish verification: Claude's discretion on format — only surface failures by default

### Failure handling
- Fallback triggers on ANY platform failure, not just full Ayrshare failure
- Retry policy: 2–3 retries with exponential backoff ONLY for server-side errors (5xx / network timeouts); fail immediately for client errors (4xx, policy violations)
- If Ayrshare is completely unreachable: send fallback immediately — no extended retry window
- Telegram fallback message: Supabase Storage URL (video link, not file upload) + the failed platform's adapted copy text — creator posts manually

### Claude's Discretion
- 30-minute verification message format (show failures only vs. full report)
- Exact retry backoff intervals and max delay
- How to store the 4 copy variants in DB (new columns on content_history vs. separate table)
- Exact scheduling job architecture (one job per platform vs. one job that fires all)

</decisions>

<specifics>
## Specific Ideas

- All 4 platform copy variants visible in the approval message so creator can review before approving
- Fallback is link-based (not file upload) — keeps message lightweight, creator can download from Supabase Storage URL
- Audience timezone is a settings field (like pipeline_hour) — not hardcoded

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 05-multi-platform-publishing*
*Context gathered: 2026-02-25*
