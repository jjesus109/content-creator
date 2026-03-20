# Roadmap: Autonomous Content Machine

## Milestones

- ✅ **v1.0 Autonomous Content Machine** - Phases 1-8 (shipped 2026-03-02)
- 🚧 **v2.0 Mexican Cat Content Machine** - Phases 9-11 (in progress)

## Phases

<details>
<summary>✅ v1.0 Autonomous Content Machine (Phases 1-8) - SHIPPED 2026-03-02</summary>

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
**Goal**: The system generates a Spanish script daily using the 6-Pillar framework, rejects semantically similar topics, learns from rejection feedback, and takes weekly mood direction from the creator
**Depends on**: Phase 1
**Requirements**: SCRP-01, SCRP-02, SCRP-03, SCRP-04
**Success Criteria** (what must be TRUE):
  1. A generated script is in neutral Spanish, does not exceed the target word count, and follows the Hook + Development + CTA structure
  2. When a proposed topic is more than 85% similar to any script in the history table, the system automatically generates a new angle without creator intervention
  3. When a script exceeds its target word count, it is automatically summarized before being passed downstream
  4. The bot prompts the creator once per week for a mood profile; the creator's response is injected into the next generation as contextual direction
**Plans**: 5 plans

Plans:
- [x] 02-01-PLAN.md — Install anthropic+openai, extend settings, migration 0002, Telegram polling wired into FastAPI lifespan
- [x] 02-02-PLAN.md — Topic generation service with embedding, anti-repetition guard
- [x] 02-03-PLAN.md — Mood flow Telegram handlers (callback queries, weekly prompt, profile persistence)
- [x] 02-04-PLAN.md — Script generation service (6-Pillar prompt, Claude Haiku, word count enforcement)
- [x] 02-05-PLAN.md — Pipeline orchestration and integration

### Phase 3: Video Production
**Goal**: Every approved script becomes a rendered, re-hosted, audio-processed 9:16 avatar video stored at a stable Supabase Storage URL
**Depends on**: Phase 2
**Requirements**: VIDP-01, VIDP-02, VIDP-03, VIDP-04
**Success Criteria** (what must be TRUE):
  1. After script generation, the system submits to HeyGen, polls for completion, and downloads the video before the signed URL expires
  2. The rendered video is in 9:16 1080p dark aesthetic with bokeh background, with background variety enforced across consecutive videos
  3. The video receives dark ambient audio post-processing via ffmpeg before delivery
  4. The video is immediately re-hosted to Supabase Storage upon render completion and the stable URL is the only reference stored in the database
**Plans**: 6 plans

Plans:
- [x] 03-01-PLAN.md — Migration 0003 + HeyGen/audio settings + ffmpeg in Dockerfile
- [x] 03-02-PLAN.md — HeyGenService + VideoStorageService + pick_background_url
- [x] 03-03-PLAN.md — AudioProcessingService (ffmpeg low-shelf EQ + ambient music mix)
- [x] 03-04-PLAN.md — VideoStatus models + POST /webhooks/heygen + video_poller_job
- [x] 03-05-PLAN.md — Integration: _process_completed_render orchestrator + daily_pipeline_job HeyGen submission
- [x] 03-06-PLAN.md — Smoke tests + human verification checkpoint + Railway env var checklist

### Phase 4: Telegram Approval Loop
**Goal**: The creator receives a presigned video URL, post copy, and approve/reject buttons in Telegram every day — one tap approves, structured rejection captures cause and stores it for the next generation
**Depends on**: Phase 3
**Requirements**: TGAP-01, TGAP-02, TGAP-03, TGAP-04
**Success Criteria** (what must be TRUE):
  1. The creator receives a Telegram message with the video, the generated post copy, and inline Approve / Reject with Cause buttons
  2. Tapping Approve triggers the publish pipeline — the pipeline state is read from the database so approval works correctly even after a server restart
  3. Tapping Reject with Cause opens a structured menu — the creator never types free-form rejection text
  4. The selected rejection cause is stored in the database and injected into the next generation iteration as a constraint
**Plans**: 5 plans

Plans:
- [x] 04-01-PLAN.md — Migration 0004 (approval_events table + post_copy column)
- [x] 04-02-PLAN.md — PostCopyService + ApprovalService (DB-backed approval state, idempotency, rejection constraints)
- [x] 04-03-PLAN.md — approval_flow.py handlers + register_approval_handlers
- [x] 04-04-PLAN.md — send_approval_message delivery + trigger_immediate_rerun for rejection retry
- [x] 04-05-PLAN.md — Phase 4 smoke tests + human verification checkpoint

### Phase 5: Multi-Platform Publishing
**Goal**: Approved content is published to all four platforms at peak engagement hours, publication success is verified, and a Telegram fallback fires automatically if publishing fails
**Depends on**: Phase 4
**Requirements**: PUBL-01, PUBL-02, PUBL-03, PUBL-04
**Success Criteria** (what must be TRUE):
  1. The approved video is published to TikTok, Instagram Reels, Facebook Reels, and YouTube Shorts via direct platform APIs
  2. Publication is scheduled at platform-specific peak engagement hours — the creator sees a confirmation of the scheduled time in Telegram
  3. Thirty minutes after the scheduled publish time, the system checks publish status on each platform and logs the result — failures are surfaced to the creator
  4. If any platform publish fails, the system automatically sends the original video file and post copy to the creator's Telegram as a manual posting fallback
**Plans**: 5 plans

Plans:
- [x] 05-01-PLAN.md — Migration 0005 + Settings extension (platform API credentials, peak_hour_*)
- [x] 05-02-PLAN.md — PostCopyService.generate_platform_variants() + send_approval_message update
- [x] 05-03-PLAN.md — PublishingService (per-platform direct API clients + tenacity retry)
- [x] 05-04-PLAN.md — Wire handle_approve to schedule_platform_publishes() + registry.py scheduler injection
- [x] 05-05-PLAN.md — Phase 5 smoke tests + human verification checkpoint

### Phase 6: Analytics and Storage
**Goal**: The system measures every video's performance, alerts the creator to viral breakouts, delivers weekly reports, and automatically manages storage costs through tiered lifecycle rules
**Depends on**: Phase 5
**Requirements**: ANLX-01, ANLX-02, ANLX-03, ANLX-04
**Success Criteria** (what must be TRUE):
  1. Forty-eight hours after each publish, the system harvests views, shares, and retention metrics from each platform and stores them in the database
  2. Every Sunday, the creator receives a Telegram report with the week's growth summary and the top-performing video
  3. When any video exceeds 500% of the rolling average performance, the creator receives an immediate Telegram virality alert
  4. Video files automatically transition through Hot (0-7d), Warm (8-45d), and Cold/Delete (45d+) storage tiers — viral videos are exempt from deletion
**Plans**: 5 plans

Plans:
- [x] 06-01-PLAN.md — Migration 0006 (platform_metrics table + content_history lifecycle columns)
- [x] 06-02-PLAN.md — MetricsService + AnalyticsService (rolling average, virality check, weekly report formatter)
- [x] 06-03-PLAN.md — StorageLifecycleService + storage_confirm Telegram handler
- [x] 06-04-PLAN.md — harvest_metrics_job (48h DateTrigger) + wire into platform_publish_job success block
- [x] 06-05-PLAN.md — weekly_analytics_report_job (Sunday CronTrigger) + storage_lifecycle_job (daily CronTrigger)

### Phase 7: Hardening
**Goal**: The system runs autonomously for months without supervision — every failure mode is handled gracefully, every circuit breaker is verified, and no silent failures can accumulate undetected
**Depends on**: Phase 6
**Requirements**: (all 26 v1 requirements verified end-to-end)
**Success Criteria** (what must be TRUE):
  1. The full pipeline runs end-to-end in integration tests — from APScheduler trigger through script generation, video render, Telegram delivery, approval, publish, and metrics harvest
  2. If a creator does not respond to the approval message within 24 hours, the system auto-skips that run and schedules the next generation normally
  3. When the daily generation circuit breaker fires three times in a day, the system halts, sends a Telegram alert, and requires the creator to manually resume
  4. Structured JSON logging is observable in Railway logs for every pipeline step — every error produces a log entry and a Telegram alert
**Plans**: 4 plans

Plans:
- [x] 07-01-PLAN.md — E2E integration test: daily_pipeline_job() with real Anthropic + mocked services
- [x] 07-02-PLAN.md — Approval timeout: VideoStatus.APPROVAL_TIMEOUT, 24h DateTrigger job, last-chance message
- [x] 07-03-PLAN.md — Daily halt circuit breaker (3 trips/day), migration 0007, /resume CommandHandler
- [ ] 07-04-PLAN.md — JSON logging retrofit: logging_config.py + configure_logging() in main.py

### Phase 8: Milestone Closure
**Goal**: Close all v1 audit gaps — formal verification of Phase 5, test integrity fix, and code hygiene — so audit returns passed
**Depends on**: Phase 7
**Requirements**: PUBL-01, PUBL-02, PUBL-03, PUBL-04 (formal verification closure)
**Success Criteria** (what must be TRUE):
  1. Phase 5 VERIFICATION.md exists and covers PUBL-01 through PUBL-04
  2. E2E test covers render-to-approval delivery flow
  3. Orphaned circuit_breaker.py removed from codebase
**Plans**: 3 plans

Plans:
- [x] 08-01-PLAN.md — Write Phase 5 VERIFICATION.md
- [x] 08-02-PLAN.md — Add E2E test for _process_completed_render()
- [x] 08-03-PLAN.md — Delete orphaned circuit_breaker.py

</details>

---

### 🚧 v2.0 Mexican Cat Content Machine (In Progress)

**Milestone Goal:** Replace the avatar video pipeline with an AI-generated cat video engine — same publishing infrastructure, completely new content strategy. One cute Mexican cat video lands in Telegram every day.

#### Phase 9: Character Bible and Video Generation
**Goal**: The system can generate a recognizable 20-30s cat video via Kling AI 3.0 with a locked character identity — the same cat appears reliably across all videos and all platform compliance labels are applied before any content reaches creators
**Depends on**: Phase 8
**Requirements**: VID-01, VID-02, VID-03, VID-04
**Success Criteria** (what must be TRUE):
  1. The system submits a text-to-video job to Kling AI 3.0 via fal.ai async SDK and receives a 20-30s, 9:16 1080p video stored in Supabase Storage
  2. The Character Bible (40-50 word trait spec) is embedded unchanged in every generation prompt — 8 of 10 consecutive test videos show the same cat recognized by visual inspection
  3. When Kling fails more than 20% of requests, the circuit breaker opens, the pipeline halts, and the creator receives a Telegram alert without any credit waste from retry loops
  4. Every video has AI content labels applied on TikTok, YouTube, and Instagram before the video is surfaced to the creator for approval
**Plans**: 4 plans

Plans:
- [x] 09-01-PLAN.md — DB schema migration 0008 (kling_job_id, kling_circuit_breaker_state, music_pool stub, app_settings) + Settings & VideoStatus extensions
- [x] 09-02-PLAN.md — CHARACTER_BIBLE constant + KlingService + fal.ai video_poller adaptation + daily_pipeline swap
- [x] 09-03-PLAN.md — KlingCircuitBreakerService (20% threshold, balance check, midnight reset) + CB wiring
- [x] 09-04-PLAN.md — _apply_ai_label() in platform_publish.py + test_ai_labels.py + test_smoke.py + human checkpoint

#### Phase 10: Scene Engine and Music Pool
**Goal**: Every daily run produces a scene prompt drawn from a curated library, checked for repetition, enriched with seasonal context when applicable, paired with a mood-matched licensed music track, and expressed in a universal Spanish caption
**Depends on**: Phase 9
**Requirements**: SCN-01, SCN-02, SCN-03, SCN-04, SCN-05, MUS-01, MUS-02, MUS-03
**Success Criteria** (what must be TRUE):
  1. GPT-4o selects a location + activity + mood combination from a library of 40-60 curated entries and produces a scene prompt that drives the Kling generation call
  2. On Sep 16, Nov 1-2, Nov 20, and Aug 8, the scene prompt automatically includes a themed overlay — no manual intervention required
  3. A scene more than 75-80% similar (cosine similarity) to any video in the past 7 days is blocked and a new scene is generated; the threshold is empirically validated against test video pairs
  4. When the creator rejects a video, the rejected scene details are stored and injected as negative context into the next generation prompt automatically
  5. Every video has a universal Spanish caption of 5-8 words following the [observation] + [implied personality] formula — no per-platform variants generated
  6. A music track is selected per video by matching scene mood to BPM range (playful: 110-125, sleepy: 70-80, curious: 90-100) from a pool of 200+ pre-tagged tracks
**Plans**: 5 plans

Plans:
- [x] 10-01-PLAN.md — DB migration 0009 (scene_embedding, check_scene_similarity, music_pool artist column) + Wave 0 test scaffold + music_seed.csv
- [x] 10-02-PLAN.md — scenes.json (40-60 combos) + SceneEngine (GPT-4o scene+caption, single call) + SeasonalCalendarService
- [x] 10-03-PLAN.md — SimilarityService.is_too_similar_scene() (7-day/0.78 threshold) + scene rejection storage/load + feature flag
- [x] 10-04-PLAN.md — MusicMatcher (mood-to-BPM, license flags, expiry filtering) + music pool tests
- [x] 10-05-PLAN.md — Pipeline wiring (SceneEngine+MusicMatcher replace v1.0 script gen) + integration tests + human checkpoint

#### Phase 11: Music License Enforcement at Publish
**Goal**: No video is published to any platform with a music track that is not cleared for that platform — the license matrix is the final gate before cross-platform distribution
**Depends on**: Phase 10
**Requirements**: PUB-01
**Success Criteria** (what must be TRUE):
  1. Before publishing to each platform, the system queries the license matrix for the selected track — if the track is not cleared for a platform, that platform's publish is blocked and the creator is notified via Telegram
  2. A video with a fully licensed track publishes to all four platforms without manual intervention
  3. A video assigned a track with an expired or missing clearance record for at least one platform is blocked from publishing to that platform and a Telegram alert identifies the track and the affected platform
**Plans**: 3 plans

Plans:
- [ ] 11-01-PLAN.md — Migration 0010 (blocked status) + test scaffold (Wave 0) + _check_music_license_cleared() gate wired into publish_to_platform_job()
- [ ] 11-02-PLAN.md — Integration smoke tests (full job call path) + human verification checkpoint
- [ ] 11-03-PLAN.md — Gap closure: migration 0011 (platform_facebook column) + fixture sync + VALID_PLATFORMS + facebook gate tests

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → ... → 8 → 9 → 10 → 11

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Foundation | v1.0 | 3/3 | Complete | 2026-02-20 |
| 2. Script Generation | v1.0 | 5/5 | Complete | 2026-02-20 |
| 3. Video Production | v1.0 | 6/6 | Complete | 2026-02-22 |
| 4. Telegram Approval Loop | v1.0 | 5/5 | Complete | 2026-02-25 |
| 5. Multi-Platform Publishing | v1.0 | 5/5 | Complete | 2026-02-25 |
| 6. Analytics and Storage | v1.0 | 5/5 | Complete | 2026-02-28 |
| 7. Hardening | v1.0 | 3/4 | In Progress | - |
| 8. Milestone Closure | v1.0 | 3/3 | Complete | 2026-03-02 |
| 9. Character Bible and Video Generation | 4/4 | Complete   | 2026-03-19 | - |
| 10. Scene Engine and Music Pool | 5/5 | Complete    | 2026-03-20 | - |
| 11. Music License Enforcement at Publish | 3/3 | Complete    | 2026-03-20 | - |
