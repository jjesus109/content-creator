---
phase: 13
slug: kitten-scenario-video-generation-hook-climax-conclusion-stories
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-26
---

# Phase 13 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | pytest.ini or pyproject.toml |
| **Quick run command** | `pytest tests/ -x -q --tb=short` |
| **Full suite command** | `pytest tests/ -v` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/ -x -q --tb=short`
- **After every plan wave:** Run `pytest tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 13-01-01 | 01 | 0 | scenario-categories | unit | `pytest tests/test_scenario_engine.py -x -q` | ❌ W0 | ⬜ pending |
| 13-01-02 | 01 | 1 | scenario-generation | unit | `pytest tests/test_scenario_engine.py::test_generate_scenario -x -q` | ❌ W0 | ⬜ pending |
| 13-02-01 | 02 | 1 | prompt-embedding-migration | unit | `pytest tests/test_similarity.py -x -q` | ❌ W0 | ⬜ pending |
| 13-02-02 | 02 | 1 | prompt-embedding-check | unit | `pytest tests/test_similarity.py::test_prompt_similarity -x -q` | ❌ W0 | ⬜ pending |
| 13-03-01 | 03 | 2 | kling-arc-prompt | unit | `pytest tests/test_prompt_generation.py -x -q` | ✅ | ⬜ pending |
| 13-03-02 | 03 | 2 | scene-engine-integration | integration | `pytest tests/test_scene_engine.py -x -q` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_scenario_engine.py` — stubs for scenario generation (categories, GPT-4o call, return signature)
- [ ] `tests/test_similarity.py` — stubs for prompt_embedding similarity check (is_too_similar_prompt)
- [ ] Migration `0012_add_prompt_embedding.py` — ALTER TABLE content_history ADD COLUMN prompt_embedding vector(1536)

*These are created in Wave 0 before main implementation begins.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Multi-beat video narrative quality | arc-quality | Visual inspection required | Generate 3 test videos with hook-climax-conclusion prompts, verify narrative arc is visible |
| Prose arc vs. temporal marker comparison | kling-arc-encoding | Subjective quality assessment | Generate 1 video with prose arc, 1 with explicit timecodes; compare smoothness |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
