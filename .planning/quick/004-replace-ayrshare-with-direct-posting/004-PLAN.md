---
phase: quick-004
plan: 004
type: execute
wave: 1
depends_on: []
files_modified:
  - .planning/PROJECT.md
  - .planning/REQUIREMENTS.md
  - .planning/ROADMAP.md
  - .planning/STATE.md
autonomous: true
requirements: [PUBL-01, PUBL-02, PUBL-03, PUBL-04]

must_haves:
  truths:
    - "No planning document references Ayrshare as the publishing mechanism"
    - "All publishing references describe direct API posting per platform (TikTok Content Publishing API, Meta Graph API, YouTube Data API v3)"
    - "SCRTY-01 no longer lists AYRSHARE_API_KEY as a required secret"
    - "PUBL-01 and PUBL-04 requirements describe direct API calls, not a single Ayrshare aggregator call"
    - "STATE.md blocker about Ayrshare is removed; decisions referencing ayrshare_api_key are updated"
  artifacts:
    - path: ".planning/PROJECT.md"
      provides: "Updated constraints and key decisions — Ayrshare replaced with per-platform direct API note"
    - path: ".planning/REQUIREMENTS.md"
      provides: "Updated PUBL-01, PUBL-04, and SCRTY-01 requirements; v2 section updated"
    - path: ".planning/ROADMAP.md"
      provides: "Updated Phase 5 goal, success criteria, and plan descriptions — no Ayrshare"
    - path: ".planning/STATE.md"
      provides: "Updated decisions and blockers — Ayrshare blocker removed, ayrshare_api_key decisions reworded"
  key_links:
    - from: "REQUIREMENTS.md PUBL-01"
      to: "four platform-specific API calls"
      via: "direct API description"
      pattern: "TikTok Content Publishing API|Meta Graph API|YouTube Data API"
    - from: "STATE.md decisions"
      to: "ayrshare_api_key references"
      via: "updated wording to per-platform credentials"
      pattern: "direct.*API|per-platform"
---

<objective>
Update all living planning documents to reflect the architectural decision to replace
Ayrshare with direct social media API posting for Phase 5.

Purpose: Ayrshare was the original publishing aggregator. The decision is to post
directly to each platform's native API: TikTok Content Publishing API, Meta Graph API
(Instagram + Facebook Pages), and YouTube Data API v3. Planning documents must reflect
the actual architecture going forward — especially since Phase 7 (Hardening) is still
in progress and references these designs.

Output: Four updated planning documents (PROJECT.md, REQUIREMENTS.md, ROADMAP.md,
STATE.md) with all Ayrshare references replaced by accurate direct-API descriptions.
Phase 5 completed SUMMARY/PLAN/VERIFICATION files are NOT modified — they are
historical records of what was implemented.
</objective>

<execution_context>
@./.claude/get-shit-done/workflows/execute-plan.md
@./.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/REQUIREMENTS.md
@.planning/STATE.md
</context>

<tasks>

<task type="auto">
  <name>Task 1: Update PROJECT.md and REQUIREMENTS.md</name>
  <files>.planning/PROJECT.md, .planning/REQUIREMENTS.md</files>
  <action>
Update .planning/PROJECT.md:

1. In the "Active" requirements list, change:
   - "Auto-publish to TikTok, IG Reels, FB Reels, YT Shorts via Ayrshare/Buffer API"
   to:
   - "Auto-publish to TikTok, IG Reels, FB Reels, YT Shorts via direct platform APIs (TikTok Content Publishing API, Meta Graph API, YouTube Data API v3)"

2. In the "Constraints" table, change the "Tech — Publishing" row from:
   - "Ayrshare (single POST → 4 platforms); Buffer as fallback"
   to:
   - "Direct platform APIs: TikTok Content Publishing API, Meta Graph API (Instagram + Facebook Pages), YouTube Data API v3"

3. In the "Key Decisions" table, update the "Ayrshare vs Buffer" row:
   - Change Decision column from "Ayrshare vs Buffer" to "Direct APIs vs Ayrshare aggregator"
   - Change Rationale column to "Direct API control: no third-party rate limits, no aggregator cost, full platform compliance"
   - Change Outcome column to "Direct posting chosen — TikTok Content Publishing API, Meta Graph API (Instagram/Facebook), YouTube Data API v3"

Update .planning/REQUIREMENTS.md:

1. SCRTY-01 currently lists "Ayrshare" in the API keys list. Change:
   - "All API keys (OpenAI, HeyGen, ElevenLabs, Ayrshare, Telegram) stored as encrypted environment variables"
   to:
   - "All API keys (OpenAI, HeyGen, ElevenLabs, TikTok, Meta/Facebook, YouTube, Telegram) stored as encrypted environment variables — never hardcoded"

2. PUBL-01 currently describes a single Ayrshare call. Change:
   - "Approved video is published to TikTok, Instagram Reels, Facebook Reels, and YouTube Shorts via a single Ayrshare API call"
   to:
   - "Approved video is published to TikTok, Instagram Reels, Facebook Reels, and YouTube Shorts via direct platform APIs: TikTok Content Publishing API, Meta Graph API (Instagram + Facebook Pages), YouTube Data API v3"

3. PUBL-04 currently describes Ayrshare failure as the failure trigger. Change:
   - "If Ayrshare publish fails, bot automatically sends the original video file and post copy to Telegram for immediate manual posting"
   to:
   - "If any platform publish fails, bot automatically sends the original video file and post copy to Telegram for immediate manual posting as fallback"

4. In the v2 Requirements section, there is no Ayrshare-specific v2 item, so no change needed there. Check for any remaining Ayrshare occurrences and remove/replace them.
  </action>
  <verify>
    <automated>grep -n "Ayrshare\|ayrshare\|Buffer" /Users/jesusalbino/Projects/content-creation/.planning/PROJECT.md /Users/jesusalbino/Projects/content-creation/.planning/REQUIREMENTS.md || echo "CLEAN — no Ayrshare references remain"</automated>
  </verify>
  <done>PROJECT.md and REQUIREMENTS.md contain no Ayrshare references; publishing mechanism is described as direct platform APIs throughout both documents.</done>
</task>

<task type="auto">
  <name>Task 2: Update ROADMAP.md and STATE.md</name>
  <files>.planning/ROADMAP.md, .planning/STATE.md</files>
  <action>
Update .planning/ROADMAP.md:

1. Phase 5 description line (in the "## Phases" overview list):
   - Change "via Ayrshare with publish verification" to "via direct platform APIs with publish verification"

2. Phase 5 Goal line (under "### Phase 5: Multi-Platform Publishing"):
   - Change "via Ayrshare" to "via direct platform APIs"
   - Full replacement: "Approved content is published to all four platforms at peak engagement hours, publication success is verified, and a Telegram fallback fires automatically if publishing fails"

3. Phase 5 Success Criteria item 1:
   - Change "A single Ayrshare API call publishes the approved video to TikTok, Instagram Reels, Facebook Reels, and YouTube Shorts simultaneously with the generated post copy"
   to:
   - "The approved video is published to TikTok, Instagram Reels, Facebook Reels, and YouTube Shorts via direct platform APIs (TikTok Content Publishing API, Meta Graph API, YouTube Data API v3) with platform-specific post copy"

4. Phase 5 Success Criteria item 4:
   - Change "If Ayrshare publish fails, the system automatically sends the original video file and post copy to the creator's Telegram as a manual posting fallback"
   to:
   - "If any platform publish fails, the system automatically sends the original video file and post copy to the creator's Telegram as a manual posting fallback"

5. Phase 5 Plan descriptions (the "- [ ]" lines):
   - Change "05-01-PLAN.md — Migration 0005 (publish_events table + 4 platform copy columns) + Settings extension (ayrshare_api_key, audience_timezone, peak_hour_*) + tenacity dependency"
   to:
   - "05-01-PLAN.md — Migration 0005 (publish_events table + 4 platform copy columns) + Settings extension (platform API credentials, audience_timezone, peak_hour_*) + tenacity dependency"
   - Change "05-03-PLAN.md — PublishingService (Ayrshare wrapper + tenacity retry) + platform_publish job + publish_verify job + Telegram publish helpers"
   to:
   - "05-03-PLAN.md — PublishingService (per-platform direct API clients + tenacity retry) + platform_publish job + publish_verify job + Telegram publish helpers"

6. Phase 7 Plan 07-01 description:
   - Change "E2E integration test: daily_pipeline_job() with real Anthropic + mocked HeyGen/Ayrshare/Telegram, content_history row assertions"
   to:
   - "E2E integration test: daily_pipeline_job() with real Anthropic + mocked HeyGen/PublishingService/Telegram, content_history row assertions"

Update .planning/STATE.md:

1. In the "Blockers/Concerns" section, remove or update this line:
   - "- [Phase 5]: Ayrshare TikTok content policy and plan tier limits are MEDIUM confidence — confirm before Phase 5 implementation"
   Replace with:
   - "- [Phase 5]: Direct platform API credentials (TikTok Content Publishing API, Meta Graph API, YouTube Data API v3) must be provisioned before re-implementing Phase 5"

2. In the "Decisions" section, find the Phase 05 decisions that mention ayrshare_api_key and update them. Specifically:
   - The decision "ayrshare_api_key has no default — Pydantic raises ValidationError at startup if AYRSHARE_API_KEY env var not set"
   Change to:
   - "Platform API credentials have no defaults — Pydantic raises ValidationError at startup if TIKTOK_CLIENT_KEY, META_ACCESS_TOKEN, YOUTUBE_CLIENT_SECRET env vars are not set"

3. Find in the Decisions list under "[Research]":
   - "- [Research]: Ayrshare TikTok support and plan tier limits must be confirmed before starting Phase 5"
   Change to:
   - "- [Research]: Direct platform APIs chosen for Phase 5 — TikTok Content Publishing API, Meta Graph API (Instagram/Facebook), YouTube Data API v3; Ayrshare aggregator replaced"

4. Scan remaining STATE.md content for any other "Ayrshare" or "ayrshare" occurrences and replace with equivalent direct-API language.
  </action>
  <verify>
    <automated>grep -n "Ayrshare\|ayrshare" /Users/jesusalbino/Projects/content-creation/.planning/ROADMAP.md /Users/jesusalbino/Projects/content-creation/.planning/STATE.md || echo "CLEAN — no Ayrshare references remain"</automated>
  </verify>
  <done>ROADMAP.md and STATE.md contain no Ayrshare references. Phase 5 goal, success criteria, plan descriptions, decisions, and blockers all describe direct platform API posting. Phase 7 E2E test description no longer references mocked Ayrshare.</done>
</task>

</tasks>

<verification>
After both tasks complete, run a final cross-document scan:

```
grep -rn "Ayrshare\|ayrshare" \
  /Users/jesusalbino/Projects/content-creation/.planning/PROJECT.md \
  /Users/jesusalbino/Projects/content-creation/.planning/REQUIREMENTS.md \
  /Users/jesusalbino/Projects/content-creation/.planning/ROADMAP.md \
  /Users/jesusalbino/Projects/content-creation/.planning/STATE.md
```

Expected result: zero matches. Any match is a gap to fix before marking complete.

Phase 5 SUMMARY/PLAN/VERIFICATION files are intentionally excluded — they are historical
records and should preserve the original implementation context.
</verification>

<success_criteria>
- Zero occurrences of "Ayrshare" or "ayrshare" in PROJECT.md, REQUIREMENTS.md, ROADMAP.md, and STATE.md
- Publishing is consistently described as direct platform APIs in all four documents
- SCRTY-01 lists platform-specific API key names, not AYRSHARE_API_KEY
- PUBL-01 describes per-platform API calls; PUBL-04 describes generic publish failure (not Ayrshare failure)
- STATE.md blocker references direct-API credential provisioning, not Ayrshare plan tier limits
- All changes are documentation-only — no source code files modified
</success_criteria>

<output>
After completion, create `.planning/quick/004-replace-ayrshare-with-direct-posting/004-SUMMARY.md`

Include:
- What was changed in each file (brief per-file summary)
- Grep verification result (zero Ayrshare matches)
- Note that Phase 5 SUMMARY/PLAN/VERIFICATION/UAT/RESEARCH/CONTEXT files were intentionally preserved as historical records
</output>
