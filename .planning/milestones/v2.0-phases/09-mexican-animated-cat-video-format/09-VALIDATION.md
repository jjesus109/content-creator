---
phase: 9
slug: mexican-animated-cat-video-format
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-19
---

# Phase 9 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | pytest.ini or pyproject.toml |
| **Quick run command** | `pytest tests/ -x -q --tb=short` |
| **Full suite command** | `pytest tests/ -v --tb=short` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/ -x -q --tb=short`
- **After every plan wave:** Run `pytest tests/ -v --tb=short`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 09-01-01 | 01 | 1 | VID-01 | migration | `pytest tests/test_migrations.py -x -q` | ❌ W0 | ⬜ pending |
| 09-01-02 | 01 | 1 | VID-01 | unit | `pytest tests/test_schema.py -x -q` | ❌ W0 | ⬜ pending |
| 09-02-01 | 02 | 1 | VID-01 | unit | `pytest tests/test_character_bible.py -x -q` | ❌ W0 | ⬜ pending |
| 09-02-02 | 02 | 1 | VID-02 | integration | `pytest tests/test_kling_service.py -x -q` | ❌ W0 | ⬜ pending |
| 09-02-03 | 02 | 1 | VID-02 | unit | `pytest tests/test_video_storage.py -x -q` | ❌ W0 | ⬜ pending |
| 09-03-01 | 03 | 2 | VID-03 | unit | `pytest tests/test_kling_circuit_breaker.py -x -q` | ❌ W0 | ⬜ pending |
| 09-03-02 | 03 | 2 | VID-03 | unit | `pytest tests/test_kling_backoff.py -x -q` | ❌ W0 | ⬜ pending |
| 09-04-01 | 04 | 2 | VID-04 | unit | `pytest tests/test_ai_labels.py -x -q` | ❌ W0 | ⬜ pending |
| 09-04-02 | 04 | 2 | VID-04 | integration | `pytest tests/test_smoke.py -x -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_migrations.py` — stubs for VID-01 DB schema migration
- [ ] `tests/test_schema.py` — stubs for pipeline_runs v2 columns, music_pool, character_bible setting
- [ ] `tests/test_character_bible.py` — stubs for character bible embedding in prompts
- [ ] `tests/test_kling_service.py` — stubs for fal.ai Kling 3.0 job submission and polling
- [ ] `tests/test_video_storage.py` — stubs for Supabase Storage video upload
- [ ] `tests/test_kling_circuit_breaker.py` — stubs for 20% failure threshold tracking
- [ ] `tests/test_kling_backoff.py` — stubs for exponential backoff (2s/8s/32s) and credit check
- [ ] `tests/test_ai_labels.py` — stubs for TikTok/YouTube/Instagram label application
- [ ] `tests/test_smoke.py` — end-to-end smoke test stubs for full pipeline

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Visual cat consistency across 10 videos | VID-02 | Requires human visual inspection — same cat recognized in 8/10 consecutive videos | Run 10-video batch via Kling, review frames side-by-side |
| TikTok C2PA metadata detection | VID-04 | Requires upload to live TikTok platform and label detection verification | Upload test video, confirm AI label appears in TikTok UI |
| Telegram circuit breaker alert delivery | VID-03 | Requires live Telegram bot and simulated Kling failure rate > 20% | Simulate failures in staging, confirm Telegram message received |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
