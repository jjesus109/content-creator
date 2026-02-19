# Requirements: Autonomous Content Machine

**Defined:** 2026-02-19
**Core Value:** A hyper-realistic AI avatar video lands in Telegram every day, ready to approve and publish — the creator's only job is to say yes or no.

## v1 Requirements

### Infrastructure

- [ ] **INFRA-01**: System runs as a persistent worker on Railway/Render with FastAPI health endpoint and env-based config
- [ ] **INFRA-02**: Supabase schema initialized with pipeline_runs table, content history table, and pgvector column for embeddings
- [ ] **INFRA-03**: APScheduler with Postgres job store triggers daily content generation and survives deploys without missing jobs
- [ ] **INFRA-04**: Cost circuit breaker enforces a hard daily generation limit to prevent runaway API spend

### Security

- [ ] **SCRTY-01**: All API keys (OpenAI, HeyGen, ElevenLabs, Ayrshare, Telegram) stored as encrypted environment variables — never hardcoded
- [ ] **SCRTY-02**: Telegram bot responds only to the creator's configured user ID, silently ignores all other senders

### Script Generation

- [ ] **SCRP-01**: System generates a 140-word max script in neutral Spanish using GPT-4o, structured as Aggressive Hook (0-3s) + Philosophical Development + Reflective CTA, governed by the 5-Pillar system prompt
- [ ] **SCRP-02**: Creator can set weekly mood profile via Telegram (bot prompts once/week); profile feeds into script generation as contextual direction
- [ ] **SCRP-03**: Anti-repetition guard queries pgvector before generation — if proposed topic exceeds 0.85 cosine similarity to any past script, system generates a new thematic angle automatically
- [ ] **SCRP-04**: Script is automatically summarized by AI if it exceeds 140 words before being submitted to HeyGen

### Video Production

- [ ] **VIDP-01**: System submits script to HeyGen async, polls for completion, and downloads the rendered video before the signed URL expires
- [ ] **VIDP-02**: HeyGen render uses dark aesthetic (high contrast, blacks/grays, 9:16 1080p) with bokeh background; system enforces no repeated background environment in consecutive videos
- [ ] **VIDP-03**: Rendered video receives audio post-processing (dark ambient EQ/atmosphere via ffmpeg) before delivery
- [ ] **VIDP-04**: Completed video is immediately re-hosted to Supabase Storage or S3 after HeyGen render — raw HeyGen URL is never stored as permanent reference

### Telegram Approval

- [ ] **TGAP-01**: Bot delivers daily video to creator via presigned S3/Supabase URL (not file upload) with generated post copy
- [ ] **TGAP-02**: Bot presents inline [Approve] and [Reject with Cause] buttons; approval triggers publish pipeline, rejection suspends the run
- [ ] **TGAP-03**: Rejection opens a structured cause menu: Script Error / Visual Error / Technical Error
- [ ] **TGAP-04**: Rejection cause is stored as negative context and injected into the next generation iteration as a constraint

### Publishing

- [ ] **PUBL-01**: Approved video is published to TikTok, Instagram Reels, Facebook Reels, and YouTube Shorts via a single Ayrshare API call
- [ ] **PUBL-02**: Publish is scheduled at peak engagement hours per platform, not immediately on approval
- [ ] **PUBL-03**: System verifies post-publish status on each platform 30 minutes after scheduled publish time
- [ ] **PUBL-04**: If Ayrshare publish fails, bot automatically sends the original video file and post copy to Telegram for immediate manual posting

### Analytics

- [ ] **ANLX-01**: System harvests views, shares, and retention metrics from each platform 48 hours after publish
- [ ] **ANLX-02**: Every Sunday, bot sends a weekly report to creator: growth summary and top-performing video of the week
- [ ] **ANLX-03**: Bot sends an immediate Telegram alert if any video exceeds 500% of the average performance (virality threshold)
- [ ] **ANLX-04**: Storage lifecycle auto-manages video files: hot (0-7d active), warm (8-45d backup), cold delete (45d+) — videos flagged as Viral or Eternal are exempt from deletion

## v2 Requirements

### Voice

- **VOICE-01**: ElevenLabs voice cloning integration (evaluate after confirming HeyGen native Spanish voice capability in Phase 3 — may be redundant)

### Intelligence

- **INTL-01**: Virality alert automatically extracts format fingerprint of breakout video for next generation cycle (manual process in v1)
- **INTL-02**: Soul Optimization — system tracks which of the 5 Pillars correlates with highest retention and biases future generation accordingly

### Operations

- **OPS-01**: Admin command in Telegram to manually trigger generation on demand (outside daily schedule)
- **OPS-02**: Admin command to mark a video as Eternal/Viral to exempt from storage lifecycle deletion

## Out of Scope

| Feature | Reason |
|---------|--------|
| Multi-user support | Single creator only; no auth/tenancy overhead needed |
| Web or mobile UI | Telegram is the sole interface by design |
| Horizontal/square video formats | 9:16 short-form only |
| Long-form video content | 40-second shorts exclusively |
| Analytics dashboard | All reporting delivered via Telegram bot |
| Auto-approval (no human review) | Creator's editorial voice is non-negotiable; auto-approve removes it |
| Real-time metrics | 48h polling is sufficient; real-time requires paid API tiers |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| INFRA-01 | Phase 1 | Pending |
| INFRA-02 | Phase 1 | Pending |
| INFRA-03 | Phase 1 | Pending |
| INFRA-04 | Phase 1 | Pending |
| SCRTY-01 | Phase 1 | Pending |
| SCRTY-02 | Phase 1 | Pending |
| SCRP-01 | Phase 2 | Pending |
| SCRP-02 | Phase 2 | Pending |
| SCRP-03 | Phase 2 | Pending |
| SCRP-04 | Phase 2 | Pending |
| VIDP-01 | Phase 3 | Pending |
| VIDP-02 | Phase 3 | Pending |
| VIDP-03 | Phase 3 | Pending |
| VIDP-04 | Phase 3 | Pending |
| TGAP-01 | Phase 4 | Pending |
| TGAP-02 | Phase 4 | Pending |
| TGAP-03 | Phase 4 | Pending |
| TGAP-04 | Phase 4 | Pending |
| PUBL-01 | Phase 5 | Pending |
| PUBL-02 | Phase 5 | Pending |
| PUBL-03 | Phase 5 | Pending |
| PUBL-04 | Phase 5 | Pending |
| ANLX-01 | Phase 6 | Pending |
| ANLX-02 | Phase 6 | Pending |
| ANLX-03 | Phase 6 | Pending |
| ANLX-04 | Phase 6 | Pending |

**Coverage:**
- v1 requirements: 26 total
- Mapped to phases: 26
- Unmapped: 0
- Note: Phase 7 (Hardening) verifies all 26 requirements end-to-end; it introduces no new functional requirements

---
*Requirements defined: 2026-02-19*
*Last updated: 2026-02-19 — traceability confirmed after roadmap creation*
