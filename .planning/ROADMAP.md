# Roadmap: Autonomous Content Machine

## Overview

Seven phases build the pipeline in strict dependency order: the daily video cannot be published without approval, approval cannot happen without a video, a video cannot be rendered without a script, and nothing runs without a foundation. Phases 1-5 deliver the live content loop. Phase 6 adds the analytics and storage intelligence that compounds value over time. Phase 7 hardens the system for autonomous, unsupervised operation across months.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Foundation** - Persistent service, Supabase schema, secrets management, and security baseline running on Railway (completed 2026-02-20)
- [x] **Phase 2: Script Generation** - Daily scripts generated with 5-Pillar framework, anti-repetition guard, mood profiles, and rejection feedback loop (completed 2026-02-20)
- [ ] **Phase 3: Video Production** - HeyGen avatar video rendered, re-hosted to S3, audio post-processed, background variety enforced
- [ ] **Phase 4: Telegram Approval Loop** - Creator receives daily video via Telegram with approve/reject inline keyboard and structured rejection flow
- [ ] **Phase 5: Multi-Platform Publishing** - Approved video scheduled and published to TikTok, IG Reels, FB Reels, and YT Shorts via Ayrshare with publish verification
- [ ] **Phase 6: Analytics and Storage** - 48-hour metrics harvest, virality alerts, Sunday weekly reports, and tiered storage lifecycle management
- [ ] **Phase 7: Hardening** - End-to-end integration tests, timeout handling, circuit breakers verified, and system cleared for unattended autonomous operation

## Phase Details

### Phase 1: Foundation
**Goal**: A persistent, secure service runs on Railway with all infrastructure in place — the rest of the pipeline can be built on top of it
**Depends on**: Nothing (first phase)
**Requirements**: INFRA-01, INFRA-02, INFRA-03, INFRA-04, SCRTY-01, SCRTY-02
**Success Criteria** (what must be TRUE):
  1. The FastAPI service is deployed on Railway, survives a restart, and returns 200 from its health endpoint with no manual intervention
  2. The Supabase schema exists with pipeline_runs, content_history, and mood_profiles tables plus pgvector extension enabled and HNSW index created
  3. APScheduler with Postgres job store triggers a no-op test job at a scheduled time and continues firing correctly after a service restart
  4. The cost circuit breaker halts generation and sends a Telegram alert when the daily generation limit is hit
  5. The Telegram bot silently ignores a message from any user ID other than the configured creator ID and responds normally to the correct ID
**Plans**: 3 plans

Plans:
- [x] 01-01-PLAN.md — Project scaffold (pyproject.toml, Dockerfile, railway.toml) + Pydantic settings/models + Supabase schema SQL
- [x] 01-02-PLAN.md — CircuitBreakerService (dual cost+count, midnight reset, escalation) + Telegram outbound-only service
- [x] 01-03-PLAN.md — FastAPI app with lifespan + APScheduler (heartbeat + cb_reset jobs) + deep health endpoint

### Phase 2: Script Generation
**Goal**: The system generates a Spanish script daily using the 6-Pillar framework, rejects semantically similar topics, learns from rejection feedback, and takes weekly mood direction (pool, tone, duration) from the creator
**Depends on**: Phase 1
**Requirements**: SCRP-01, SCRP-02, SCRP-03, SCRP-04
**Success Criteria** (what must be TRUE):
  1. A generated script is in neutral Spanish, does not exceed the target word count (70, 140, or 200 words based on creator's duration selection), and follows the Hook + Development + CTA structure governed by the 6-Pillar prompt
  2. When a proposed topic is more than 85% similar to any script in the history table, the system automatically generates a new angle without creator intervention
  3. When a script exceeds its target word count, it is automatically summarized before being passed downstream — the creator never sees an over-length script
  4. The bot prompts the creator once per week via Telegram for a mood profile (thematic pool + tone + duration); the creator's response is injected into the next generation as contextual direction
**Plans**: 5 plans

Plans:
- [x] 02-01-PLAN.md — Install anthropic+openai, extend settings, migration 0002 (similarity function + rejection_constraints), Telegram polling Application wired into FastAPI lifespan
- [x] 02-02-PLAN.md — Topic generation service with embedding, anti-repetition guard via check_script_similarity
- [x] 02-03-PLAN.md — Mood flow Telegram handlers (callback queries, weekly prompt, profile persistence)
- [x] 02-04-PLAN.md — Script generation service (6-Pillar prompt, Claude Haiku, word count enforcement)
- [x] 02-05-PLAN.md — Pipeline orchestration and integration (checkpoint approved 2026-02-20)

### Phase 3: Video Production
**Goal**: Every approved script becomes a rendered, re-hosted, audio-processed 9:16 avatar video stored at a stable Supabase Storage URL — the HeyGen signed URL is never the canonical reference
**Depends on**: Phase 2
**Requirements**: VIDP-01, VIDP-02, VIDP-03, VIDP-04
**Success Criteria** (what must be TRUE):
  1. After script generation, the system submits to HeyGen, polls for completion (with exponential backoff fallback if webhook fails), and downloads the video before the HeyGen signed URL expires
  2. The rendered video is in 9:16 1080p dark aesthetic with bokeh background, and the system prevents the same background environment from appearing in two consecutive videos
  3. The video receives dark ambient audio post-processing via ffmpeg before delivery — the raw HeyGen audio is not what the creator hears
  4. The video is immediately re-hosted to Supabase Storage upon render completion and the stable self-hosted URL is the only reference stored in the database
**Plans**: 6 plans

Plans:
- [ ] 03-01-PLAN.md — Migration 0003 (heygen_job_id, video_url, video_status, background_url) + HeyGen/audio settings + ffmpeg in Dockerfile
- [ ] 03-02-PLAN.md — HeyGenService (submit to v2 API, portrait dimensions, background URL) + VideoStorageService (Supabase Storage upsert) + pick_background_url
- [ ] 03-03-PLAN.md — AudioProcessingService (ffmpeg low-shelf EQ + ambient music mix, subprocess pipe with frag_keyframe+empty_moov)
- [ ] 03-04-PLAN.md — VideoStatus models + POST /webhooks/heygen (HMAC validation, executor offload, poller cancel) + video_poller_job (60s interval, 20-min timeout, self-cancel)
- [ ] 03-05-PLAN.md — Integration: _process_completed_render orchestrator + daily_pipeline_job HeyGen submission + webhook router wired into main.py
- [ ] 03-06-PLAN.md — Smoke tests (import chain, route registration, migration, ffmpeg) + human verification checkpoint + Railway env var checklist

### Phase 4: Telegram Approval Loop
**Goal**: The creator receives a presigned video URL, post copy, and approve/reject buttons in Telegram every day — one tap approves, structured rejection captures cause and stores it for the next generation
**Depends on**: Phase 3
**Requirements**: TGAP-01, TGAP-02, TGAP-03, TGAP-04
**Success Criteria** (what must be TRUE):
  1. The creator receives a Telegram message with the video (as a presigned URL, not a file upload), the generated post copy, and inline Approve / Reject with Cause buttons
  2. Tapping Approve triggers the publish pipeline — the pipeline state is read from the database so approval works correctly even after a server restart between video delivery and creator response
  3. Tapping Reject with Cause opens a structured menu (Script Error / Visual Error / Technical Error) — the creator never types free-form rejection text
  4. The selected rejection cause is stored in the database and injected into the next generation iteration as a constraint — the system does not repeat the same class of error
**Plans**: TBD

### Phase 5: Multi-Platform Publishing
**Goal**: Approved content is published to all four platforms at peak engagement hours, publication success is verified, and a Telegram fallback fires automatically if Ayrshare fails
**Depends on**: Phase 4
**Requirements**: PUBL-01, PUBL-02, PUBL-03, PUBL-04
**Success Criteria** (what must be TRUE):
  1. A single Ayrshare API call publishes the approved video to TikTok, Instagram Reels, Facebook Reels, and YouTube Shorts simultaneously with the generated post copy
  2. Publication is scheduled at platform-specific peak engagement hours, not immediately on approval — the creator sees a confirmation of the scheduled time in Telegram
  3. Thirty minutes after the scheduled publish time, the system checks publish status on each platform and logs the result — failures are surfaced to the creator
  4. If Ayrshare publish fails, the system automatically sends the original video file and post copy to the creator's Telegram as a manual posting fallback
**Plans**: TBD

### Phase 6: Analytics and Storage
**Goal**: The system measures every video's performance, alerts the creator to viral breakouts, delivers weekly reports, and automatically manages storage costs through tiered lifecycle rules
**Depends on**: Phase 5
**Requirements**: ANLX-01, ANLX-02, ANLX-03, ANLX-04
**Success Criteria** (what must be TRUE):
  1. Forty-eight hours after each publish, the system harvests views, shares, and retention metrics from each platform and stores them in the database against the video record
  2. Every Sunday, the creator receives a Telegram report with the week's growth summary and the top-performing video
  3. When any video exceeds 500% of the rolling average performance, the creator receives an immediate Telegram virality alert
  4. Video files automatically transition through Hot (0-7d), Warm (8-45d), and Cold/Delete (45d+) storage tiers — videos flagged as Viral or Eternal are exempt from deletion
**Plans**: TBD

### Phase 7: Hardening
**Goal**: The system runs autonomously for months without supervision — every failure mode is handled gracefully, every circuit breaker is verified, and no silent failures can accumulate undetected
**Depends on**: Phase 6
**Requirements**: (all 26 v1 requirements verified end-to-end)
**Success Criteria** (what must be TRUE):
  1. The full pipeline runs end-to-end in integration tests — from APScheduler trigger through script generation, video render, Telegram delivery, approval, publish, and metrics harvest
  2. If a creator does not respond to the approval message within 24 hours, the system auto-skips that run, logs it, and schedules the next generation normally — no run hangs indefinitely
  3. When the daily generation circuit breaker fires three times in a day, the system halts, sends a Telegram alert, and requires the creator to manually resume — it does not loop
  4. Structured JSON logging is observable in Railway logs for every pipeline step — no silent failures; every error produces a log entry and a Telegram alert to the creator
**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5 → 6 → 7

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Foundation | 3/3 | Complete   | 2026-02-20 |
| 2. Script Generation | 5/5 | Complete | 2026-02-20 |
| 3. Video Production | 5/6 | In Progress|  |
| 4. Telegram Approval Loop | 0/TBD | Not started | - |
| 5. Multi-Platform Publishing | 0/TBD | Not started | - |
| 6. Analytics and Storage | 0/TBD | Not started | - |
| 7. Hardening | 0/TBD | Not started | - |
