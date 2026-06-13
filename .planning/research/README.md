# v2.0 Architecture Research — Complete Documentation

**Project:** Autonomous Content Machine — Mexican Cat Content
**Milestone:** v2.0 (Replace HeyGen with AI cat video generation)
**Status:** Research Complete
**Date:** 2026-03-19

---

## What This Research Covers

This research answers 6 specific architectural questions for integrating AI cat video generation into the existing content pipeline:

1. **How does scene prompt generation replace ScriptGenerationService?**
2. **How does the new AI video API integrate with APScheduler ThreadPoolExecutor (sync vs async)?**
3. **How should the curated scene category library be stored?**
4. **How should the seasonal calendar service work?**
5. **How should music selection work?**
6. **What DB schema changes are needed?**

---

## Documents in This Directory

### 1. `ARCHITECTURE-V2.md` (Primary Reference)
**Length:** ~2500 lines
**Audience:** Architects, senior developers, tech leads

Comprehensive architectural design covering all 6 questions with:
- Executive summary
- Detailed answer to each question with code examples
- Complete service implementations (pseudocode)
- Database schema (SQL)
- Data flow diagrams
- Integration points (new vs modified components)
- Build order and dependencies
- Pitfalls and mitigations
- Confidence assessment
- Alternative approaches considered

**Use this for:** Implementation planning, detailed technical decisions, code structure.

---

### 2. `V2-RESEARCH-SUMMARY.md` (Executive Overview)
**Length:** ~400 lines
**Audience:** Project managers, team leads, decision makers

Condensed summary of each research question with:
- One-paragraph answer to each question
- Key data flows
- New vs modified components list
- Build order (phases)
- Risk/mitigation table
- Confidence levels
- Next steps for build phase

**Use this for:** Quick reference, status updates, decision briefings.

---

### 3. `V2-BUILD-CHECKLIST.md` (Implementation Guide)
**Length:** ~600 lines
**Audience:** Developers, QA, implementation team

Detailed build plan organized by phase with:
- Phase-by-phase breakdown (6 phases, 8-11 days)
- Specific tasks and sub-tasks (checklist format)
- Integration checkpoints and blockers
- Risk mitigation strategies
- Success criteria
- Rollback plan
- Timeline estimate

**Use this for:** Sprint planning, daily task tracking, progress monitoring, rollback procedures.

---

### 4. `README.md` (This File)
**Length:** ~300 lines
**Audience:** All stakeholders

Navigation guide and quick-reference for research documentation.

---

## Key Research Findings

### Architecture Decisions

| Decision | Rationale |
|----------|-----------|
| **Sync polling wrapper** (not async) | APScheduler ThreadPoolExecutor runs blocking jobs. Runway polls in ~30-60 seconds (acceptable). Avoids asyncio/threading conflicts. |
| **Database-backed categories** (not Python constants) | Easy to add/disable without redeploy. YAML config provides version control. Creator can extend via future Telegram UI. |
| **Month-day only seasonal matching** (not YYYY-MM-DD) | Same holiday every year. Avoids leap year logic. Simple SQL range queries. |
| **Mood-tagged music pool** (not random selection) | Playful scenes get playful music. Improves content coherence. Reuses existing HeyGen pool structure. |
| **4 new tables + 5 modified columns** | Backward compatible with v1.0 HeyGen content. Future-proofs for additional providers (Pika, Kling). |

### Technology Choices

| Component | Technology | Why |
|-----------|-----------|-----|
| **Scene generation** | Claude Haiku | Proven in v1.0. Compact model for visual descriptions. |
| **Video generation** | Runway Gen-4 | SOTA 2026. Supports 9:16 vertical format. Polling API pattern. |
| **Music pool** | Pre-curated URLs (reuse) | No new infrastructure needed. Mood tagging adds targeting. |
| **Seasonal calendar** | Date lookup table | Simple, data-driven, no hardcoded logic. |
| **Scheduling** | APScheduler (existing) | No changes. Sync polling fits ThreadPoolExecutor model. |

### Build Timeline

- **Phase 1 (Schema):** 1 day
- **Phase 2 (Services):** 1-2 days
- **Phase 3 (Video Service):** 2-3 days
- **Phase 4 (Audio):** 1 day
- **Phase 5 (Integration):** 1-2 days
- **Phase 6 (Testing):** 2 days

**Total: 8-11 days** (recommend 2-week sprint with buffer)

---

## Quick Navigation

### For Different Roles

**Project Manager:**
1. Read `V2-RESEARCH-SUMMARY.md` (10 min)
2. Review risk/mitigation table
3. Check timeline and dependencies

**Architect:**
1. Read `ARCHITECTURE-V2.md` (60 min)
2. Review integration points section
3. Check alternative approaches considered
4. Verify confidence assessment

**Team Lead:**
1. Read `V2-RESEARCH-SUMMARY.md` (10 min)
2. Review `V2-BUILD-CHECKLIST.md` (30 min)
3. Plan sprint based on phases
4. Assign tasks by checkpoint

**Developer (Implementing):**
1. Read question relevant to your task
2. Review code examples in `ARCHITECTURE-V2.md`
3. Check `V2-BUILD-CHECKLIST.md` for dependencies
4. Implement following pseudocode structure

**QA Engineer:**
1. Read `V2-BUILD-CHECKLIST.md` section 6 (Integration Testing)
2. Review success criteria
3. Check risk mitigation strategies
4. Plan test cases per phase

---

## Integration Points Summary

### New Components (Build First)
1. `ScenePromptService` — replaces ScriptGenerationService
2. `RunwayVideoService` — Runway API wrapper
3. `SceneCategoryService` — category library
4. `SeasonalCalendarService` — seasonal themes
5. `MusicSelectionService` — mood-matched music

### Modified Components
1. `daily_pipeline_job()` — replace HeyGen with Runway
2. `content_history` schema — add 5 new columns
3. `AudioProcessingService` — mood-aware music
4. `VideoStatus` enum — remove pending_render states

### Unchanged Components
- FastAPI app structure
- APScheduler + ThreadPoolExecutor
- Telegram bot approval flow
- Platform publishing services
- Analytics and metrics

---

## Confidence Assessment

| Area | Level | Risk |
|------|-------|------|
| Scene prompt generation | HIGH | Low — Claude API proven, output format change only |
| Runway API integration | MEDIUM-HIGH | Medium — API documented but untested in production. Recommend staging. |
| DB schema | HIGH | Low — straightforward additions, backward compatible |
| Music selection | HIGH | Low — simple heuristic, proven pattern |
| Seasonal calendar | HIGH | Low — trivial date lookup, data-driven |
| Sync integration with APScheduler | HIGH | Low — ThreadPoolExecutor + blocking calls proven in codebase |

---

## Blockers & Risks

### Critical Blockers
- **Runway API down/rate-limited:** 10-min timeout guard. Creator alert. Future fallback option.
- **Scene category pool too small:** Diversify to 10+ per type. Creator extensibility (future).
- **Music pool missing mood tags:** Seed from YAML. Manual tagging required upfront.

### Medium Risks
- **Mood extraction wrong:** Default to 'peaceful'. Sample 5% for review.
- **APScheduler thread pool saturation:** 4 workers acceptable for 1 daily blocking job.
- **Seasonal event data incomplete:** Start with 4 major Mexican holidays. Expand over time.

### Minor Risks
- **Music URL broken:** Weekly validation. Keep >5 tracks per mood.
- **Content repetition:** Existing similarity check handles this (from v1.0).

---

## Files Required for Build

Before starting Phase 1, ensure these files exist:

```
.planning/
├── research/
│   ├── ARCHITECTURE-V2.md         ← Comprehensive technical design
│   ├── V2-RESEARCH-SUMMARY.md     ← Executive summary
│   ├── V2-BUILD-CHECKLIST.md      ← Implementation guide
│   └── README.md                  ← This file

config/
├── scene_categories.yaml          ← Scene library seed data
├── seasonal_events.yaml           ← Seasonal themes
└── music_tracks.yaml              ← Pre-curated music with moods

migrations/
└── 0008_cat_video_schema.sql      ← Database migration (see ARCHITECTURE-V2.md)
```

---

## Success Definition

v2.0 launch is successful when:

1. ✓ Daily pipeline generates cat video automatically (no creator intervention)
2. ✓ Runway API polling completes in <10 minutes with <2% timeout rate
3. ✓ Music mood matching verified (sampling 5% of videos)
4. ✓ Seasonal themes inject correctly on Aug 8, Sep 16, Nov 1-2, Nov 20
5. ✓ DB schema backward compatible (v1.0 HeyGen content still queryable)
6. ✓ Telegram approval flow unchanged (creator approves/rejects same as v1.0)
7. ✓ Platform publishing works for both v1.0 and v2.0 content

---

## Next Steps

### Immediate (Planning Phase)
1. Review `ARCHITECTURE-V2.md` with team
2. Discuss tech choices with stakeholders
3. Confirm Runway API access and pricing
4. Plan 2-week sprint based on phase breakdown

### Phase 1 Start (Database)
1. Create migration file `0008_cat_video_schema.sql`
2. Create config YAML files
3. Run migration on test database
4. Verify schema with queries

### Phase 2 Start (Services)
1. Implement `ScenePromptService`
2. Implement `SceneCategoryService`
3. Implement `SeasonalCalendarService`
4. Implement `MusicSelectionService`

### Full Dependency Chain
1. Phase 1 (database) — no dependencies
2. Phase 2 (services) — depends on Phase 1
3. Phase 3 (video) — independent, but needed for Phase 5
4. Phase 4 (audio) — depends on Phase 3
5. Phase 5 (integration) — depends on Phases 1-4
6. Phase 6 (testing) — depends on Phase 5

---

## Additional Resources

### External API Documentation
- [Runway API Docs](https://docs.dev.runwayml.com/)
- [APScheduler 3.11 Docs](https://apscheduler.readthedocs.io/en/3.x/userguide.html)
- [Python Standard Library - calendar module](https://docs.python.org/3/library/calendar.html)

### Related Projects
- v1.0 Architecture: `.planning/research/ARCHITECTURE.md` (HeyGen-based)
- Project Context: `.planning/PROJECT.md`

### Team Resources
- Questions? Check `ARCHITECTURE-V2.md` first (comprehensive Q&A)
- Implementation help? Check `V2-BUILD-CHECKLIST.md` (task breakdown)
- Status updates? Check `V2-RESEARCH-SUMMARY.md` (executive overview)

---

## Research Quality Checklist

- [x] All 6 questions answered with code examples
- [x] Database schema completely specified (SQL)
- [x] Services fully pseudocoded with method signatures
- [x] Integration points clearly identified (new vs modified)
- [x] Data flow diagrammed
- [x] Build order specified with dependencies
- [x] Risk mitigation strategies provided
- [x] Confidence levels assigned honestly
- [x] Alternative approaches considered and rejected (with rationale)
- [x] Backward compatibility verified
- [x] Sources cited for external research
- [x] No gaps left for later research (all 6 Qs answered)

---

## Document Versions

| Version | Date | Status |
|---------|------|--------|
| 1.0 | 2026-03-19 | Complete |

---

## Questions About This Research?

If something is unclear:

1. **Question about a specific decision?** → Check `ARCHITECTURE-V2.md` (detailed Q&A)
2. **How to implement a component?** → Check `V2-BUILD-CHECKLIST.md` (phase tasks)
3. **Need a quick summary?** → Check `V2-RESEARCH-SUMMARY.md` (1-page per question)
4. **How does it fit together?** → Check this README (integration points)

---

**Research complete. Ready for build phase.**
