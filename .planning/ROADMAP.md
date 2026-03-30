# Roadmap: Autonomous Content Machine

## Milestones

- ✅ **v1.0 Autonomous Content Machine** — Phases 1-8 (shipped 2026-03-02)
- ✅ **v2.0 Mexican Cat Content Machine** — Phases 9-11 (shipped 2026-03-20)
- 🚧 **v3.0 Grey Kitten Character Refresh** — Phases 12+ (in progress)

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

### Phase 12: Grey Kitten Unified Prompt Generation

**Goal:** Replace CHARACTER_BIBLE concatenation with AI-generated unified scene prompts that naturally incorporate the new grey kitten character description. Persist the generated prompt to content_history and include it in Telegram creator notifications.
**Requires**: New cat character: "A full-body, high-definition 3D render of an ultra-cute, sitting light grey kitten. The kitten has huge, wide, expressive blue eyes and a cheerful, open-mouthed smile showing its pink tongue. Its soft fur texture is highly detailed."
**Depends on:** Phase 11
**Plans:** 3/3 plans complete

Plans:
- [ ] 12-01-PLAN.md — Update CHARACTER_BIBLE to grey kitten + create PromptGenerationService
- [ ] 12-02-PLAN.md — Wire PromptGenerationService into daily_pipeline.py + remove KlingService concatenation
- [ ] 12-03-PLAN.md — Update broken tests + add PromptGenerationService test coverage

### Phase 13: Kitten Scenario Video Generation - Hook Climax Conclusion Stories

**Goal:** Replace the static scene selection pipeline with dynamic GPT-4o scenario generation. Each daily video follows a hook→climax→conclusion story arc (flowing prose, Kling AI 3.0 multi-shot). Dual embedding anti-repetition catches both semantic (story type) and visual/stylistic (Kling prompt) repetition.
**Requirements**: SCN-13-01, SCN-13-02, SCN-13-03, SCN-13-04, SCN-13-05
**Depends on:** Phase 12
**Plans:** 3/4 plans executed

Plans:
- [x] 13-01-PLAN.md — Create categories.json + migration 0012 + extend SceneEngine with pick_scenario_arc()
- [x] 13-02-PLAN.md — Add SimilarityService.is_too_similar_prompt() + update PromptGenerationService arc system prompt
- [x] 13-03-PLAN.md — Wire pick_scenario_arc + prompt_embedding into daily_pipeline.py
- [ ] 13-04-PLAN.md — Phase 13 test coverage + human checkpoint for first arc videos
