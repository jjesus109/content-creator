# Phase 13: Kitten Scenario Video Generation - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions captured in CONTEXT.md — this log preserves the Q&A.

**Date:** 2026-03-26
**Phase:** 13-kitten-scenario-video-generation-hook-climax-conclusion-stories
**Mode:** discuss
**Areas analyzed:** Scenario library, Arc encoding, Service architecture, Funny vs cute balance, Anti-repetition, Caption changes, Database/storage

## Questions & Answers

### Scenario Library
| Question | Answer |
|----------|--------|
| Where do Phase 13's funny/arc scenarios come from? | GPT-4o generates scenarios (no library file) |
| GPT-4o generates scenarios — what guardrails, if any? | Semi-guided: scenario type categories |

### Arc Encoding
| Question | Answer |
|----------|--------|
| How should hook→climax→conclusion be encoded in the Kling prompt? | Implied arc in prose (user note: use best approach per Kling documentation) |

### Service Architecture
| Question | Answer |
|----------|--------|
| Where does the story arc generation logic live? | Modify SceneEngine (extend, don't replace) |
| Should Phase 13 replace the current pipeline or run alongside it? | Replace current pipeline (no feature flag) |

### Funny vs Cute Balance
| Question | Answer |
|----------|--------|
| What scenario type categories define 'funny' for Phase 13? | Mix of types defined by Claude (researcher defines final category list) |
| Should funny scenarios still use the Mexican cultural/domestic setting? | Yes, domestic Mexican setting |

### Anti-Repetition
| Question | Answer |
|----------|--------|
| What gets embedded for anti-repetition in story arc videos? | Both: scenario embedding + prompt embedding (two embeddings per content_history row) |

### Caption Changes
| Question | Answer |
|----------|--------|
| Should the Spanish caption formula change for story arc videos? | Arc-aware caption (replaces current observation + personality formula) |
| What's the arc-aware caption style? | Tease/hook — teases the story without revealing outcome (e.g., "Algo malo va a pasar.") |

### Database / Storage
| Question | Answer |
|----------|--------|
| Database schema for Phase 13 — what changes are needed? | Reuse existing columns only; no new scenario_arcs table; one new prompt_embedding column via migration |

## No Corrections Made

All answers were direct user selections — no scope creep redirects needed.
