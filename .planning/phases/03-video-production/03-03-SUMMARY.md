---
phase: 03-video-production
plan: "03"
subsystem: infra
tags: [ffmpeg, audio-processing, ambient-music, eq, subprocess, supabase, heygen]

# Dependency graph
requires:
  - phase: 03-01
    provides: heygen_ambient_music_urls Settings field and ffmpeg binary in Docker runtime stage

provides:
  - AudioProcessingService with process_video_audio() and pick_music_track()
  - ffmpeg filter chain: voice low-shelf EQ (180Hz/+3dB/Q=0.7) + amix at 25% ambient music
  - Fragmented MP4 output via frag_keyframe+empty_moov for valid piped stdout output
  - Guaranteed temp file cleanup via try/finally

affects:
  - 03-06-orchestration (calls AudioProcessingService.process_video_audio() after HeyGen render completes)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - ffmpeg subprocess.run with pipe:0 stdin for video and temp file for music (two-pipe workaround)
    - try/finally ensures temp file os.unlink even on ffmpeg failure or timeout
    - frag_keyframe+empty_moov movflags required for all piped MP4 output
    - music track randomly selected from comma-separated URL pool in settings

key-files:
  created:
    - src/app/services/audio_processing.py
  modified: []

key-decisions:
  - "Music written to temp file because ffmpeg cannot read two stdin pipes simultaneously"
  - "music_volume default of 0.25 (25%) — center of 20-30% research range; audible but subservient to voice"
  - "pick_music_track() raises ValueError on empty pool — fail-fast preferable to silent silence"
  - "frag_keyframe+empty_moov required for pipe:1 output — fragmented MP4 header written progressively, no seek needed"

patterns-established:
  - "ffmpeg piped I/O pattern: video bytes via stdin, music via temp file, processed MP4 bytes via stdout"
  - "AudioProcessingService reads settings internally in __init__ — callers pass no credentials"

requirements-completed: [VIDP-03]

# Metrics
duration: 1min
completed: 2026-02-21
---

# Phase 3 Plan 03: Audio Processing Summary

**ffmpeg filter chain service mixing voice low-shelf EQ (180Hz/+3dB/Q=0.7) with ambient music at 25% volume via subprocess piping, returning fragmented MP4 bytes for Supabase upload**

## Performance

- **Duration:** 1 min
- **Started:** 2026-02-21T06:39:07Z
- **Completed:** 2026-02-21T06:40:26Z
- **Tasks:** 1
- **Files modified:** 1

## Accomplishments

- Created `AudioProcessingService` with the full ffmpeg pipeline: video download, music download + temp file write, filter_complex with voice EQ and amix, fragmented MP4 piped output
- `pick_music_track()` randomly selects from the `heygen_ambient_music_urls` comma-separated pool with fail-fast ValueError on empty pool
- `process_video_audio(video_url, music_volume=0.25)` implements the complete pipeline with `try/finally` guaranteeing temp file cleanup

## Task Commits

Each task was committed atomically:

1. **Task 1: AudioProcessingService — ffmpeg voice EQ + ambient music mix** - `4f2d822` (feat)

## Files Created/Modified

- `src/app/services/audio_processing.py` — AudioProcessingService class with pick_music_track() and process_video_audio(); ffmpeg filter_complex with equalizer and amix; frag_keyframe+empty_moov for piped MP4; try/finally temp file cleanup

## Decisions Made

- Music bytes written to a temp file (not a second pipe) because ffmpeg subprocess cannot read two stdin streams simultaneously — one input must come from the filesystem
- Default `music_volume=0.25` (25%) selected as the center of the 20-30% research range — audible ambient presence without competing with speech
- `pick_music_track()` raises `ValueError` on empty URL pool — a silent failure would be harder to debug and produce a video with no ambient music
- `frag_keyframe+empty_moov` movflags are required without exception for `pipe:1` output — without them ffmpeg cannot seek backward to finalize the moov atom and the output MP4 is corrupt

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

Local dev environment lacked `pydantic_settings` in the system Python, so verification used the project's `.venv` interpreter instead. No code changes required — the import path and module structure are correct.

## User Setup Required

None - no new external services. `HEYGEN_AMBIENT_MUSIC_URLS` was already required from Plan 03-01.

## Next Phase Readiness

- `AudioProcessingService` is ready to be called from the orchestration layer (Plan 03-06)
- The service imports cleanly from `app.services.audio_processing`
- ffmpeg binary availability is a runtime requirement (installed in Dockerfile final stage per Plan 03-01)

## Self-Check: PASSED

- FOUND: src/app/services/audio_processing.py
- FOUND commit 4f2d822: feat(03-03): implement AudioProcessingService with ffmpeg EQ + ambient music mix
- frag_keyframe present in ffmpeg command
- os.unlink present in finally block

---
*Phase: 03-video-production*
*Completed: 2026-02-21*
