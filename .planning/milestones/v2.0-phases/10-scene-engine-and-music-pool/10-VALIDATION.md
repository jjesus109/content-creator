---
phase: 10
slug: scene-engine-and-music-pool
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-19
---

# Phase 10 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | pyproject.toml |
| **Quick run command** | `uv run pytest tests/ -x -q --tb=short` |
| **Full suite command** | `uv run pytest tests/ -v --tb=short` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/ -x -q --tb=short`
- **After every plan wave:** Run `uv run pytest tests/ -v --tb=short`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 10-01-01 | 01 | 1 | MUS-01 | unit | `uv run pytest tests/test_music_pool.py -x -q` | ❌ W0 | ⬜ pending |
| 10-01-02 | 01 | 1 | MUS-01 | unit | `uv run pytest tests/test_music_pool.py::test_seed_data -x -q` | ❌ W0 | ⬜ pending |
| 10-02-01 | 02 | 1 | SCN-01 | unit | `uv run pytest tests/test_scene_engine.py -x -q` | ❌ W0 | ⬜ pending |
| 10-02-02 | 02 | 1 | SCN-01 | unit | `uv run pytest tests/test_scene_engine.py::test_gpt4o_selection -x -q` | ❌ W0 | ⬜ pending |
| 10-03-01 | 03 | 1 | SCN-02 | unit | `uv run pytest tests/test_seasonal_calendar.py -x -q` | ❌ W0 | ⬜ pending |
| 10-03-02 | 03 | 1 | SCN-02 | unit | `uv run pytest tests/test_seasonal_calendar.py::test_holiday_dates -x -q` | ❌ W0 | ⬜ pending |
| 10-04-01 | 04 | 2 | SCN-03 | unit | `uv run pytest tests/test_anti_repetition.py -x -q` | ❌ W0 | ⬜ pending |
| 10-04-02 | 04 | 2 | SCN-04 | unit | `uv run pytest tests/test_anti_repetition.py::test_rejection_feedback -x -q` | ❌ W0 | ⬜ pending |
| 10-05-01 | 05 | 2 | MUS-02 | unit | `uv run pytest tests/test_music_matcher.py -x -q` | ❌ W0 | ⬜ pending |
| 10-05-02 | 05 | 2 | SCN-05 | unit | `uv run pytest tests/test_caption_generator.py -x -q` | ❌ W0 | ⬜ pending |
| 10-05-03 | 05 | 2 | MUS-03 | integration | `uv run pytest tests/test_pipeline_wiring.py -x -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_music_pool.py` — stubs for MUS-01
- [ ] `tests/test_scene_engine.py` — stubs for SCN-01
- [ ] `tests/test_seasonal_calendar.py` — stubs for SCN-02
- [ ] `tests/test_anti_repetition.py` — stubs for SCN-03, SCN-04
- [ ] `tests/test_music_matcher.py` — stubs for MUS-02
- [ ] `tests/test_caption_generator.py` — stubs for SCN-05
- [ ] `tests/test_pipeline_wiring.py` — integration stubs for MUS-03

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Cosine similarity threshold calibration | SCN-03 | Requires running 20-30 real scene prompt pairs to validate 75-80% threshold empirically | Run dry-run script with test pairs; check blocked/allowed distribution matches expected behavior |
| Music pool license clearance | MUS-01 | License validity for TikTok/YouTube/Instagram cannot be automated — requires legal review | Verify each track's platform clearance flags in music_pool table match actual license agreements |
| Spanish caption tone/quality | SCN-05 | NLP quality is subjective; formula compliance is automated but natural sound is manual | Review 10 generated captions against [observation]+[implied personality] formula; confirm 5-8 word count |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
