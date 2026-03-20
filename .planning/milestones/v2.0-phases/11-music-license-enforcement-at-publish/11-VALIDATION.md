---
phase: 11
slug: music-license-enforcement-at-publish
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-19
---

# Phase 11 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | pyproject.toml |
| **Quick run command** | `pytest tests/test_music_license_gate.py -x -q` |
| **Full suite command** | `pytest tests/ -x -q` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_music_license_gate.py -x -q`
- **After every plan wave:** Run `pytest tests/ -x -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 11-01-01 | 01 | 1 | PUB-01 | unit | `pytest tests/test_music_license_gate.py::test_license_check_cleared -xq` | ❌ W0 | ⬜ pending |
| 11-01-02 | 01 | 1 | PUB-01 | unit | `pytest tests/test_music_license_gate.py::test_license_check_not_cleared -xq` | ❌ W0 | ⬜ pending |
| 11-01-03 | 01 | 1 | PUB-01 | unit | `pytest tests/test_music_license_gate.py::test_license_check_expired -xq` | ❌ W0 | ⬜ pending |
| 11-01-04 | 01 | 1 | PUB-01 | unit | `pytest tests/test_music_license_gate.py::test_license_check_null_track -xq` | ❌ W0 | ⬜ pending |
| 11-01-05 | 01 | 1 | PUB-01 | unit | `pytest tests/test_music_license_gate.py::test_telegram_alert_on_block -xq` | ❌ W0 | ⬜ pending |
| 11-02-01 | 02 | 2 | PUB-01 | integration | `pytest tests/test_music_license_gate.py -xq` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_music_license_gate.py` — stubs for PUB-01 (6 test scenarios: cleared, blocked, expired, null-track, telegram-alert, full integration)
- [ ] `tests/conftest.py` — verify SAMPLE_MUSIC_POOL fixture includes `license_expires_at`, `platform_youtube`, `platform_instagram`, `platform_facebook` fields

*Existing pytest infrastructure covers the framework — only test file stubs need creation.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Human verification checkpoint after integration tests | PUB-01 | End-to-end pipeline validation requires live Supabase + Telegram | Run pipeline with a test video; verify blocked alert arrives in Telegram with track name and platform |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
