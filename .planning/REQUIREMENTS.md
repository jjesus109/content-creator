# Requirements: Autonomous Content Machine

**Defined:** 2026-05-20
**Milestone:** v4.0 — Dual-Pipeline Content Machine
**Core Value:** Every piece of content lands in Telegram ready to approve — the creator's only job is to say yes or no.

## v4.0 Requirements

### Infrastructure

- [ ] **INFRA-01**: `content_type` column added to `content_history` table — values `cat` or `history`, used to route approval messages and publish logic
- [ ] **INFRA-02**: `history_topics` table created — columns: category, topic_name, era_period, is_active; seeded with 30+ topics across 6 categories
- [ ] **INFRA-03**: `audio_url`, `long_video_url`, `short_video_url`, `subtitle_url` columns added to `content_history`
- [ ] **INFRA-04**: Supabase Storage buckets `audio-files`, `video-files`, `subtitle-files` created and accessible via service role key
- [ ] **INFRA-05**: History APScheduler job registered — fires every 2 days at 09:00; cat job unchanged (daily); both share Postgres job store

### Script Generation

- [ ] **SCRIPT-01**: GPT-4o generates structured 500–700 word script for Deep History & Education: hook (60–80 words), body (3–4 sections × 100–150 words), call-to-action (40–60 words)
- [ ] **SCRIPT-02**: `CHANNEL_BIBLE` Python constant defines history channel tone — authoritative, accessible, storytelling voice, English only
- [ ] **SCRIPT-03**: Topic pool seeded in `history_topics` table; GPT-4o selects topic from pool for each run
- [ ] **SCRIPT-04**: Topic anti-repetition via pgvector — embeds `topic_title + era_period`, 0.78 cosine threshold, 30-day lookback; retry up to 2 times on similarity hit

### Voice Narration

- [ ] **VOICE-01**: ElevenLabs Flash v2.5 converts script narration text to MP3 audio
- [ ] **VOICE-02**: Channel voice ID stored as `HISTORY_VOICE_ID` Python constant — one voice, locked at config time
- [ ] **VOICE-03**: MP3 stored in Supabase Storage `audio-files/{content_history_id}/narration.mp3`; `audio_url` persisted to `content_history`

### Subtitle Generation

- [ ] **SUB-01**: OpenAI Whisper-1 transcribes ElevenLabs MP3 to SRT with word-level timestamps
- [ ] **SUB-02**: SRT stored in Supabase Storage `subtitle-files/{content_history_id}/subtitles.srt`; `subtitle_url` persisted to `content_history`

### Video Composition

- [ ] **VIDEO-01**: Pexels API fetches royalty-free stock clips keyed to script section topics — 6–8 clips per video
- [ ] **VIDEO-02**: Shotstack long-form template (16:9, 2–5 min) composes: ElevenLabs audio + Pexels clips + Whisper SRT subtitles
- [ ] **VIDEO-03**: Shotstack short-form template (9:16, ≤60s) composes hook-section audio + clips + subtitles from same pipeline run
- [ ] **VIDEO-04**: Long-form MP4 stored in Supabase Storage `video-files/{content_history_id}/long.mp4`; `long_video_url` persisted
- [ ] **VIDEO-05**: Short-form MP4 stored in Supabase Storage `video-files/{content_history_id}/short.mp4`; `short_video_url` persisted

### Publishing

- [ ] **PUB-01**: Telegram approval message for history content shows: content type label, topic title, era, duration, links to both long and short previews
- [ ] **PUB-02**: Single creator approval triggers publish of all applicable formats across all platforms
- [ ] **PUB-03**: YouTube receives long-form (16:9, 2–5 min) with topic title as video title
- [ ] **PUB-04**: Facebook receives long-form (16:9, 2–5 min)
- [ ] **PUB-05**: YouTube Shorts receives short-form (9:16, ≤60s)
- [ ] **PUB-06**: TikTok receives short-form (9:16, ≤60s)
- [ ] **PUB-07**: Instagram Reels receives short-form (9:16, ≤60s)

## Future Requirements

### History Channel Enhancements (v5.0+)

- **HIST-FUT-01**: Background music layer for history videos (ambient, mood-matched)
- **HIST-FUT-02**: Thumbnail generation — static image from video frame + title overlay
- **HIST-FUT-03**: Chapter markers for YouTube long-form (auto-generated from body section timestamps)
- **HIST-FUT-04**: Analytics harvest for history content (views, watch time, RPM tracking)
- **HIST-FUT-05**: Monetization milestone tracker in Telegram (% toward 1K subs / 4K watch hours)

### Cat Pipeline Enhancements (v5.0+)

- **CAT-FUT-01**: Enable scene anti-repetition enforcement (currently log-only, pending calibration)
- **CAT-FUT-02**: Music fallback pool (50-track backup)
- **CAT-FUT-03**: Compliance audit log per publish

## Out of Scope

| Feature | Reason |
|---------|--------|
| Background music for history videos | Narrated voice content is complete without it; deferred to v5.0 |
| Multiple niches / multi-channel | Single niche (Deep History & Education) only in v4.0 |
| AI avatar / on-camera presenter | Stock footage + voice only; no avatar video generation |
| Caption A/B testing | Deferred |
| Per-platform post copy variants | Universal caption policy carries forward |
| Analytics UI / dashboard | Telegram-only interface policy unchanged |
| S3 storage | All media in Supabase Storage — one managed service, no separate credentials |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| INFRA-01 | Phase 14 | Pending |
| INFRA-02 | Phase 14 | Pending |
| INFRA-03 | Phase 14 | Pending |
| INFRA-04 | Phase 14 | Pending |
| INFRA-05 | Phase 14 | Pending |
| SCRIPT-01 | Phase 15 | Pending |
| SCRIPT-02 | Phase 15 | Pending |
| SCRIPT-03 | Phase 15 | Pending |
| SCRIPT-04 | Phase 15 | Pending |
| VOICE-01 | Phase 16 | Pending |
| VOICE-02 | Phase 16 | Pending |
| VOICE-03 | Phase 16 | Pending |
| SUB-01 | Phase 17 | Pending |
| SUB-02 | Phase 17 | Pending |
| VIDEO-01 | Phase 18 | Pending |
| VIDEO-02 | Phase 18 | Pending |
| VIDEO-03 | Phase 18 | Pending |
| VIDEO-04 | Phase 18 | Pending |
| VIDEO-05 | Phase 18 | Pending |
| PUB-01 | Phase 19 | Pending |
| PUB-02 | Phase 19 | Pending |
| PUB-03 | Phase 19 | Pending |
| PUB-04 | Phase 19 | Pending |
| PUB-05 | Phase 19 | Pending |
| PUB-06 | Phase 19 | Pending |
| PUB-07 | Phase 19 | Pending |

**Coverage:**
- v4.0 requirements: 27 total
- Mapped to phases: 27
- Unmapped: 0 ✓

---
*Requirements defined: 2026-05-20*
*Last updated: 2026-05-20 after v4.0 milestone start*
