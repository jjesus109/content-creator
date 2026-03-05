---
quick_task: "003"
subsystem: "heygen-video-production"
tags: ["heygen", "api", "payload", "settings", "dry-run"]
tech_stack:
  modified: ["pydantic-settings", "requests"]
  patterns: ["settings-driven config", "verified-payload-pattern"]
key_files:
  modified:
    - src/app/settings.py
    - src/app/services/heygen.py
  created:
    - scripts/dry_run_heygen_submit.py
decisions:
  - "background_url retained in submit() signature for caller compatibility; excluded from v2 payload"
  - "dimension values are strings '1920'/'1080' per verified API — HeyGen v2 requires string not int"
  - "caption=True enables automatic captions on rendered video"
metrics:
  duration: "~8 min"
  completed: "2026-03-05"
  tasks: 3
  files: 3
---

# Quick Task 003: HeyGen API Payload Update — Summary

**One-liner:** Aligned HeyGenService.submit() to verified v2 payload structure with string dimensions, character iv_model and gesture_prompt; added heygen_gesture_prompt to Settings; created real-API dry-run submit CLI.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Add heygen_gesture_prompt to Settings | ba5a451 | src/app/settings.py |
| 2 | Rewrite HeyGenService.submit() payload to verified v2 structure | 846cd1a | src/app/services/heygen.py |
| 3 | Create dry_run_heygen_submit.py | 739f48d | scripts/dry_run_heygen_submit.py |

## Changes Made

### src/app/settings.py

Added one new required field in the HeyGen section (after heygen_ambient_music_urls):

```python
heygen_gesture_prompt: str  # Avatar gesture instruction sent as character.prompt in v2 API
```

No default value — Pydantic raises ValidationError at startup if HEYGEN_GESTURE_PROMPT env var absent. Follows the "all 7 HeyGen fields required" project decision from Phase 03-01 (now 8 required fields).

### src/app/services/heygen.py

Rewrote the payload dict inside HeyGenService.submit() to match verified v2 structure:

| Field | Old value | New value |
|-------|-----------|-----------|
| caption | False | True |
| dimension.width | 1080 (int) | "1920" (str) |
| dimension.height | 1920 (int) | "1080" (str) |
| character.scale | absent | 1 |
| character.talking_style | absent | "stable" |
| character.use_avatar_iv_model | absent | True |
| character.prompt | absent | settings.heygen_gesture_prompt |
| voice.speed | 1.0 (float) | "1" (str) |
| voice.pitch | absent | "0" (str) |
| voice.duration | absent | "1" (str) |
| background block | present | removed |
| title | absent | "Daily video" |

background_url parameter retained in method signature for caller compatibility (daily_pipeline_job.py passes it); comment added explaining it is unused in v2 payload. logger.info updated to log gesture_prompt[:40].

### scripts/dry_run_heygen_submit.py

New CLI script that submits a real render job to the live HeyGen v2 API and prints the video_id. Does not wait for completion. Handles requests.HTTPError with response body output. Uses argparse with --script flag (default: short Spanish test phrase).

## Verification

All three automated checks pass:

```
Task 1 OK  — heygen_gesture_prompt in Settings source
Task 2 OK  — use_avatar_iv_model, "1920", talking_style, heygen_gesture_prompt, caption True all present
Task 3 OK  — HeyGenService, video_id, HTTPError, argparse present; ast.parse() passes
```

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check: PASSED

- src/app/settings.py: FOUND, contains heygen_gesture_prompt
- src/app/services/heygen.py: FOUND, payload verified
- scripts/dry_run_heygen_submit.py: FOUND, syntax valid
- Commits: ba5a451, 846cd1a, 739f48d all present in git log
