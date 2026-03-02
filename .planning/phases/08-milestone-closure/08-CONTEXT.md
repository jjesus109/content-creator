# Phase 8: Milestone Closure - Context

**Gathered:** 2026-03-02
**Status:** Ready for planning

<domain>
## Phase Boundary

Close all v1 audit gaps identified in `v1-MILESTONE-AUDIT.md` so that `/gsd:audit-milestone` returns `passed`. Three closure tasks plus one design-decision documentation:
1. Write the missing Phase 5 VERIFICATION.md (formal report — only documentation artifact missing)
2. Fix the broken E2E test assertion in `test_phase07_e2e.py:139` by adding a second test that covers the render-completion path
3. Delete the orphaned `src/app/scheduler/jobs/circuit_breaker.py` (stale, never imported)
4. Update REQUIREMENTS.md to close INT-02 by design decision: TikTok is manual-only (copy sent to creator via Telegram, creator posts manually — no API publishing, no metrics collection)

No new features. No new pipeline stages. This phase exists entirely to satisfy the audit.

</domain>

<decisions>
## Implementation Decisions

### E2E test fix (08-02)
- **Keep the existing test unchanged** — `test_daily_pipeline_writes_content_history` tests `daily_pipeline_job()` correctly; the DB row, `heygen_job_id`, `video_status`, and `HeyGen.submit.assert_called_once()` assertions stay
- **Add a second test** that calls `_process_completed_render()` directly and asserts `mock_approval.assert_called_once()` (i.e., `send_approval_message_sync` was called)
- The broken assertion (`mock_all_externals["approval"].assert_called_once()`) at line 139 is NOT removed — the existing test is kept intact; the second test correctly targets the render-completion code path where approval delivery actually happens

### Phase 5 VERIFICATION.md format (08-01)
- **Full Phase 7 format** — same structure as `07-VERIFICATION.md`:
  - Observable Truths table (4 rows: one per PUBL-01 through PUBL-04)
  - Required Artifacts table (key Phase 5 files: publishing.py, publish_verify.py, platform_publish.py, migration 0005)
  - Key Link Verification table (Phase 4 → Phase 5 approval wiring, Phase 5 → Phase 6 metrics trigger)
  - Requirements Coverage table
  - Human Verification Required section (UAT 8/8 already passed — notes only)
- Evidence sources to synthesize: `05-UAT.md` (8/8 pass), `05-0{1..5}-SUMMARY.md` frontmatter, integration checker findings from the audit report

### TikTok design decision (08-04 or incorporated into 08-01)
- TikTok is **manual-only by design**: system generates TikTok copy, sends it to creator in the Telegram approval message, creator posts manually
- No TikTok API publishing — `MANUAL_PLATFORMS = {"tiktok"}` is correct and intentional
- No TikTok metrics collection — `_fetch_tiktok()` returning `None` when token is empty is acceptable behavior; no OAuth route needed
- Update `REQUIREMENTS.md` to explicitly document this as a design decision, not a gap. INT-02 from the audit is closed by decision.
- The Phase 5 VERIFICATION.md should note this as a known limitation acknowledged by design

### Orphaned file deletion (08-03)
- Delete `src/app/scheduler/jobs/circuit_breaker.py` — confirmed never imported anywhere; all production code uses `app.services.circuit_breaker`
- No import graph cleanup needed (it's unreachable); no migration or config references to update

### Claude's Discretion
- Exact table layout within the VERIFICATION.md (column widths, row ordering)
- Whether the TikTok documentation update is its own plan (08-04) or folded into 08-01
- Structure of the second E2E test fixture — whether to extend the existing `mock_all_externals` fixture or create a new targeted fixture for the render-completion path

</decisions>

<specifics>
## Specific Ideas

- The Phase 5 VERIFICATION.md should note that UAT 8/8 tests were performed in a prior session (`05-UAT.md`) — the VERIFICATION is a synthesis, not a re-run
- TikTok manual-posting design: creator receives the TikTok copy in Telegram (already working) and posts it themselves — this is the intended final behavior, not a temporary workaround
- The second E2E test should mirror the pattern in `test_phase07_e2e.py` but call `_process_completed_render()` after setting up a `content_history` row with `video_status = pending_render` and `video_url` populated

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `07-VERIFICATION.md`: Template/reference for the full verification format to replicate for Phase 5
- `05-UAT.md`: Primary evidence source for VERIFICATION.md — 8/8 tests with expected/result pairs
- `05-0{1..5}-SUMMARY.md`: Frontmatter `requirements-completed` lists for Requirements Coverage table
- `v1-MILESTONE-AUDIT.md`: Integration checker findings confirming Phase 4→5 and Phase 5→6 wiring (already verified)
- `tests/test_phase07_e2e.py`: Existing test file — `mock_all_externals` fixture and `daily_pipeline_job` test to keep unchanged

### Established Patterns
- VERIFICATION.md format: YAML frontmatter with `phase`, `verified`, `status`, `score`; markdown body with Observable Truths, Required Artifacts, Key Links, Requirements Coverage, Human Verification sections
- Integration checker already confirmed: `handle_approve()` → `schedule_platform_publishes()` WIRED in `approval_flow.py:91-113`; `platform_publish_job` success block schedules `harvest_metrics_job` via `DateTrigger(now+48h)` WIRED in `platform_publish.py:103-114`

### Integration Points
- `_process_completed_render()` lives in `src/app/services/heygen.py` — the new E2E test needs to import and call it
- `src/app/scheduler/jobs/circuit_breaker.py` is the deletion target — no import graph update needed
- `REQUIREMENTS.md` is the documentation target for the TikTok design decision

</code_context>

<deferred>
## Deferred Ideas

- Full TikTok code removal (strip `tiktok_access_token` from settings, `_fetch_tiktok()` from MetricsService, `MANUAL_PLATFORMS` entry from publishing.py) — user confirmed manual posting is intentional; code removal is out of scope for v1 closure
- TikTok API publishing via direct integration — explicitly out of scope; manual-only is the final v1 design

</deferred>

---

*Phase: 08-milestone-closure*
*Context gathered: 2026-03-02*
