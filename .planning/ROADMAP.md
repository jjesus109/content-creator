# Roadmap: Autonomous Content Machine

## Milestones

- ✅ **v1.0 Autonomous Content Machine** — Phases 1-8 (shipped 2026-03-02)
- ✅ **v2.0 Mexican Cat Content Machine** — Phases 9-11 (shipped 2026-03-20)
- ✅ **v3.0 Grey Kitten Character Refresh** — Phases 12-13 (shipped 2026-05-20)
- 🚧 **v4.0 Dual-Pipeline Content Machine** — Phases 14-19 (in progress)

## Phases

<details>
<summary>✅ v1.0 Autonomous Content Machine (Phases 1-8) — SHIPPED 2026-03-02</summary>

- [x] Phase 1: Foundation (3/3 plans) — completed 2026-02-20
- [x] Phase 2: Script Generation (5/5 plans) — completed 2026-02-20
- [x] Phase 3: Video Production (6/6 plans) — completed 2026-02-22
- [x] Phase 4: Telegram Approval Loop (5/5 plans) — completed 2026-02-25
- [x] Phase 5: Multi-Platform Publishing (5/5 plans) — completed 2026-02-25
- [x] Phase 6: Analytics and Storage (5/5 plans) — completed 2026-02-28
- [x] Phase 7: Hardening (3/4 plans) — completed 2026-03-02
- [x] Phase 8: Milestone Closure (3/3 plans) — completed 2026-03-02

Full details: `.planning/milestones/v1.0-ROADMAP.md`

</details>

<details>
<summary>✅ v2.0 Mexican Cat Content Machine (Phases 9-11) — SHIPPED 2026-03-20</summary>

- [x] Phase 9: Character Bible and Video Generation (4/4 plans) — completed 2026-03-19
- [x] Phase 10: Scene Engine and Music Pool (5/5 plans) — completed 2026-03-20
- [x] Phase 11: Music License Enforcement at Publish (3/3 plans) — completed 2026-03-20

Full details: `.planning/milestones/v2.0-ROADMAP.md`

</details>

<details>
<summary>✅ v3.0 Grey Kitten Character Refresh (Phases 12-13) — SHIPPED 2026-05-20</summary>

- [x] Phase 12: Grey Kitten Unified Prompt Generation (3/3 plans) — completed 2026-05-20
- [x] Phase 13: Kitten Scenario Video Generation — Hook Climax Conclusion Stories (4/4 plans) — completed 2026-05-20

</details>

### 🚧 v4.0 Dual-Pipeline Content Machine (In Progress)

**Milestone Goal:** Add Deep History & Education narrated video pipeline alongside the existing cat pipeline — shared infrastructure, separate jobs, unified Telegram approval. Every history video (long-form 16:9 + short 9:16) lands in Telegram ready to approve, the same way cat videos do.

- [ ] **Phase 14: Infrastructure & DB** — Schema and storage foundations for the history pipeline
- [ ] **Phase 15: Script Generation** — GPT-4o history scripts with topic pool and anti-repetition
- [ ] **Phase 16: Voice Narration** — ElevenLabs MP3 generation and storage
- [ ] **Phase 17: Subtitle Generation** — Whisper SRT transcription and storage
- [ ] **Phase 18: Video Composition** — Shotstack dual-format render with Pexels stock footage
- [ ] **Phase 19: Publishing & Telegram** — Format-aware publishing and extended Telegram approval

## Phase Details

### Phase 14: Infrastructure & DB
**Goal**: The database and storage infrastructure supports dual-pipeline content — history rows are first-class citizens alongside cat rows with their own media URL columns, topic pool table, storage buckets, and scheduled job.
**Depends on**: Phase 13
**Requirements**: INFRA-01, INFRA-02, INFRA-03, INFRA-04, INFRA-05
**Success Criteria** (what must be TRUE):
  1. A `content_type` column exists on `content_history`; inserting a row with value `history` succeeds and cat rows default to `cat` without code changes
  2. The `history_topics` table exists and is seeded with 30+ topics across 6 categories; a query for active topics returns results
  3. `audio_url`, `long_video_url`, `short_video_url`, `subtitle_url` columns exist on `content_history` and accept string values
  4. Supabase Storage buckets `audio-files`, `video-files`, `subtitle-files` exist and a file can be uploaded and retrieved via service role key
  5. The history APScheduler job is registered in the Postgres job store and fires every 2 days at 09:00; the cat daily job remains unchanged
**Plans**: TBD
**UI hint**: no

### Phase 15: Script Generation
**Goal**: The system generates a structured, channel-consistent Deep History & Education script for each pipeline run — topic selected from the pool, anti-repetition enforced, and the full script persisted and ready for voice synthesis.
**Depends on**: Phase 14
**Requirements**: SCRIPT-01, SCRIPT-02, SCRIPT-03, SCRIPT-04
**Success Criteria** (what must be TRUE):
  1. A pipeline run produces a 500–700 word script with a distinct hook (60–80 words), 3–4 body sections (100–150 words each), and a call-to-action (40–60 words)
  2. The generated script matches the `CHANNEL_BIBLE` tone — authoritative, accessible, storytelling, English only — verifiable by reading the output
  3. The topic selected for each run comes from the `history_topics` table pool; a topic's category, name, and era are reflected in the script
  4. Running the pipeline twice with a recently used topic results in a different topic being selected (anti-repetition retry fires; no duplicate within 30-day window)
**Plans**: TBD

### Phase 16: Voice Narration
**Goal**: The script narration text is converted to MP3 audio by ElevenLabs using a locked channel voice, and the audio file is durably stored in Supabase Storage with its URL persisted to the database.
**Depends on**: Phase 15
**Requirements**: VOICE-01, VOICE-02, VOICE-03
**Success Criteria** (what must be TRUE):
  1. A pipeline run produces an MP3 file at `audio-files/{content_history_id}/narration.mp3` in Supabase Storage that is playable and covers the full script text
  2. The voice used matches `HISTORY_VOICE_ID` — the same voice is used across all runs (no per-run variation)
  3. The `audio_url` column on the corresponding `content_history` row is populated with the Supabase Storage URL after the run
**Plans**: TBD

### Phase 17: Subtitle Generation
**Goal**: The ElevenLabs MP3 is transcribed by Whisper to an SRT file with word-level timestamps, and the subtitle file is durably stored in Supabase Storage with its URL persisted to the database.
**Depends on**: Phase 16
**Requirements**: SUB-01, SUB-02
**Success Criteria** (what must be TRUE):
  1. A pipeline run produces a valid SRT file at `subtitle-files/{content_history_id}/subtitles.srt` in Supabase Storage; the file contains timestamped subtitle entries that align with the narration audio
  2. The `subtitle_url` column on the corresponding `content_history` row is populated with the Supabase Storage URL after the run
**Plans**: TBD

### Phase 18: Video Composition
**Goal**: The system composes two complete videos per history pipeline run — a 2–5 min 16:9 long-form and a ≤60s 9:16 short — using Pexels stock footage, ElevenLabs audio, and Whisper subtitles via Shotstack; both MP4 files are stored in Supabase Storage with URLs persisted.
**Depends on**: Phase 17
**Requirements**: VIDEO-01, VIDEO-02, VIDEO-03, VIDEO-04, VIDEO-05
**Success Criteria** (what must be TRUE):
  1. A pipeline run fetches 6–8 Pexels stock clips relevant to the script section topics and uses them in the composed video
  2. The long-form MP4 at `video-files/{content_history_id}/long.mp4` is playable, 16:9 aspect ratio, 2–5 minutes, and includes synchronized narration audio and subtitles
  3. The short-form MP4 at `video-files/{content_history_id}/short.mp4` is playable, 9:16 aspect ratio, ≤60 seconds, covers the hook section, and includes synchronized audio and subtitles
  4. Both `long_video_url` and `short_video_url` on the corresponding `content_history` row are populated after the run
**Plans**: TBD
**UI hint**: no

### Phase 19: Publishing & Telegram
**Goal**: The creator receives a single Telegram message per history pipeline run showing content type, topic, and links to both formats; one approval tap publishes long-form to YouTube and Facebook and short-form to YouTube Shorts, TikTok, and Instagram Reels.
**Depends on**: Phase 18
**Requirements**: PUB-01, PUB-02, PUB-03, PUB-04, PUB-05, PUB-06, PUB-07
**Success Criteria** (what must be TRUE):
  1. The Telegram approval message shows: content type label ("History"), topic title, era/period, duration, and accessible links to both the long and short video previews
  2. Tapping Approve triggers publication of all applicable formats; no second approval is required
  3. YouTube receives the long-form 16:9 video (2–5 min) with the topic title as the video title
  4. Facebook receives the long-form 16:9 video (2–5 min)
  5. YouTube Shorts, TikTok, and Instagram Reels each receive the short-form 9:16 video (≤60s)
**Plans**: TBD

## Progress

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Foundation | v1.0 | 3/3 | Complete | 2026-02-20 |
| 2. Script Generation | v1.0 | 5/5 | Complete | 2026-02-20 |
| 3. Video Production | v1.0 | 6/6 | Complete | 2026-02-22 |
| 4. Telegram Approval Loop | v1.0 | 5/5 | Complete | 2026-02-25 |
| 5. Multi-Platform Publishing | v1.0 | 5/5 | Complete | 2026-02-25 |
| 6. Analytics and Storage | v1.0 | 5/5 | Complete | 2026-02-28 |
| 7. Hardening | v1.0 | 3/4 | Complete | 2026-03-02 |
| 8. Milestone Closure | v1.0 | 3/3 | Complete | 2026-03-02 |
| 9. Character Bible and Video Generation | v2.0 | 4/4 | Complete | 2026-03-19 |
| 10. Scene Engine and Music Pool | v2.0 | 5/5 | Complete | 2026-03-20 |
| 11. Music License Enforcement at Publish | v2.0 | 3/3 | Complete | 2026-03-20 |
| 12. Grey Kitten Unified Prompt Generation | v3.0 | 3/3 | Complete | 2026-05-20 |
| 13. Kitten Scenario Video Generation | v3.0 | 4/4 | Complete | 2026-05-20 |
| 14. Infrastructure & DB | v4.0 | 0/TBD | Not started | - |
| 15. Script Generation | v4.0 | 0/TBD | Not started | - |
| 16. Voice Narration | v4.0 | 0/TBD | Not started | - |
| 17. Subtitle Generation | v4.0 | 0/TBD | Not started | - |
| 18. Video Composition | v4.0 | 0/TBD | Not started | - |
| 19. Publishing & Telegram | v4.0 | 0/TBD | Not started | - |
