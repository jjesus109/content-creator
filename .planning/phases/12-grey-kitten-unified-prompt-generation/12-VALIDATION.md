---
phase: 12
slug: grey-kitten-unified-prompt-generation
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-21
---

# Phase 12 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `python -m pytest tests/test_smoke.py -x -q` |
| **Full suite command** | `python -m pytest tests/ -x -q` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/test_smoke.py -x -q`
- **After every plan wave:** Run `python -m pytest tests/ -x -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 12-01-01 | 01 | 1 | CHARACTER update | unit | `python -m pytest tests/test_prompt_generation.py::test_grey_kitten_character -x -q` | ❌ W0 | ⬜ pending |
| 12-01-02 | 01 | 1 | PromptGenerationService | unit | `python -m pytest tests/test_prompt_generation.py::test_generate_unified_prompt -x -q` | ❌ W0 | ⬜ pending |
| 12-01-03 | 01 | 1 | Fallback behavior | unit | `python -m pytest tests/test_prompt_generation.py::test_fallback_on_failure -x -q` | ❌ W0 | ⬜ pending |
| 12-02-01 | 02 | 2 | Pipeline integration | integration | `python -m pytest tests/test_smoke.py -x -q` | ✅ | ⬜ pending |
| 12-02-02 | 02 | 2 | DB persistence | unit | `python -m pytest tests/test_prompt_generation.py::test_prompt_persisted_to_db -x -q` | ❌ W0 | ⬜ pending |
| 12-02-03 | 02 | 2 | Telegram notification | unit | `python -m pytest tests/test_prompt_generation.py::test_telegram_notification_includes_prompt -x -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_prompt_generation.py` — stubs for PromptGenerationService, fallback, persistence, and Telegram tests

*Existing infrastructure covers smoke tests and integration base.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Prompt quality review | Unified prompt feels natural (not concatenated) | Subjective creative quality | Generate 3 unified prompts, verify grey kitten character is woven naturally, not appended |
| Telegram notification content | Notification shows unified prompt | Requires live Telegram bot | Trigger pipeline in staging, verify notification contains unified scene prompt |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
