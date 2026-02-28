# Phase 6: Analytics and Storage - Context

**Gathered:** 2026-02-28
**Status:** Ready for planning

<domain>
## Phase Boundary

Measure video performance via direct platform APIs, surface insights to the creator via Telegram (weekly reports + virality alerts), and manage Supabase Storage costs through automated lifecycle transitions with creator-controlled deletion safety.

</domain>

<decisions>
## Implementation Decisions

### Weekly report (Sunday)
- Show both raw totals AND % change vs prior week
- Per-platform breakdown (TikTok, Instagram, Facebook, YouTube) — not aggregate-only
- Top performer of the week = highest retention rate
- First week (no prior data): show N/A for all % change columns

### Virality alerts
- Baseline requirement: at least 2 published videos with metrics before alerts can fire
- Alert fires every 48h harvest cycle while a video stays above 500% of rolling average (not just once per video)
- Alert message = minimal flag: short message with video date and view count — no deep breakdown
- Viral videos are auto-marked as Eternal — exempt from deletion without creator action

### Storage tier transitions
- Hot (0-7 days): active, no action
- Warm (8-45 days): DB metadata only — label tracked in DB, file stays in same Supabase Storage bucket
- Cold (45+ days): file deleted from Supabase Storage; DB record (content_history row) is KEPT for analytics history
- 7-day warning: Telegram alert fires 7 days before scheduled deletion
- Warning includes inline "Save forever" button — tapping marks the video Eternal and cancels the deletion job
- Viral/Eternal videos are exempt from all tier transitions and deletion

### Metrics harvest (direct platform APIs)
- Harvest from each platform's native API directly — NOT via Ayrshare analytics
  - TikTok API
  - Instagram Graph API (Meta)
  - Facebook Graph API (Meta)
  - YouTube Data API
- Target metrics per platform: views + retention rate + shares + all additional metrics each platform exposes
- If a platform doesn't return a specific metric (e.g., retention): mark that platform as 'partial harvest' in DB, store null for missing fields
- Harvest retry: if a platform API is down or rate-limited, retry once after 1 hour, then log failure
- Telegram alert: fires only if ALL 4 platforms fail to harvest (partial failures stay silent)

### Claude's Discretion
- Exact DB schema for platform_metrics table (columns, indexes)
- Ayrshare post_id mapping to platform-native IDs (needed to query each platform's API)
- Rolling average calculation window (e.g., trailing 30 videos vs all-time)
- Weekly report message formatting and emoji use

</decisions>

<specifics>
## Specific Ideas

- "Save forever" inline button on deletion warning = Telegram callback query, consistent with existing approval flow button pattern
- The DB record must survive file deletion — analytics value compounds over time even for deleted videos

</specifics>

<deferred>
## Deferred Ideas

- **Replace Ayrshare publishing with direct platform APIs** — User wants to remove Ayrshare entirely, including the publishing mechanism from Phase 5. This requires a Phase 5 rework and should be inserted as Phase 5.1 (or a revision of Phase 5) before Phase 6 executes. Note: Phase 6 analytics already assumes direct platform API access, so the platform API integration work will partially overlap.

</deferred>

---

*Phase: 06-analytics-and-storage*
*Context gathered: 2026-02-28*
