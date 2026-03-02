# Phase 8: Milestone Closure - Research

**Researched:** 2026-03-02
**Domain:** Documentation synthesis, test integrity, code hygiene — no new features
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

#### E2E test fix (08-02)
- **Keep the existing test unchanged** — `test_daily_pipeline_writes_content_history` tests `daily_pipeline_job()` correctly; the DB row, `heygen_job_id`, `video_status`, and `HeyGen.submit.assert_called_once()` assertions stay
- **Add a second test** that calls `_process_completed_render()` directly and asserts `mock_approval.assert_called_once()` (i.e., `send_approval_message_sync` was called)
- The broken assertion (`mock_all_externals["approval"].assert_called_once()`) at line 139 is NOT removed — the existing test is kept intact; the second test correctly targets the render-completion code path where approval delivery actually happens

#### Phase 5 VERIFICATION.md format (08-01)
- **Full Phase 7 format** — same structure as `07-VERIFICATION.md`:
  - Observable Truths table (4 rows: one per PUBL-01 through PUBL-04)
  - Required Artifacts table (key Phase 5 files: publishing.py, publish_verify.py, platform_publish.py, migration 0005)
  - Key Link Verification table (Phase 4 → Phase 5 approval wiring, Phase 5 → Phase 6 metrics trigger)
  - Requirements Coverage table
  - Human Verification Required section (UAT 8/8 already passed — notes only)
- Evidence sources to synthesize: `05-UAT.md` (8/8 pass), `05-0{1..5}-SUMMARY.md` frontmatter, integration checker findings from the audit report

#### TikTok design decision (08-04 or incorporated into 08-01)
- TikTok is **manual-only by design**: system generates TikTok copy, sends it to creator in the Telegram approval message, creator posts manually
- No TikTok API publishing — `MANUAL_PLATFORMS = {"tiktok"}` is correct and intentional
- No TikTok metrics collection — `_fetch_tiktok()` returning `None` when token is empty is acceptable behavior; no OAuth route needed
- Update `REQUIREMENTS.md` to explicitly document this as a design decision, not a gap. INT-02 from the audit is closed by decision.
- The Phase 5 VERIFICATION.md should note this as a known limitation acknowledged by design

#### Orphaned file deletion (08-03)
- Delete `src/app/scheduler/jobs/circuit_breaker.py` — confirmed never imported anywhere; all production code uses `app.services.circuit_breaker`
- No import graph cleanup needed (it's unreachable); no migration or config references to update

### Claude's Discretion
- Exact table layout within the VERIFICATION.md (column widths, row ordering)
- Whether the TikTok documentation update is its own plan (08-04) or folded into 08-01
- Structure of the second E2E test fixture — whether to extend the existing `mock_all_externals` fixture or create a new targeted fixture for the render-completion path

### Deferred Ideas (OUT OF SCOPE)
- Full TikTok code removal (strip `tiktok_access_token` from settings, `_fetch_tiktok()` from MetricsService, `MANUAL_PLATFORMS` entry from publishing.py) — user confirmed manual posting is intentional; code removal is out of scope for v1 closure
- TikTok API publishing via direct integration — explicitly out of scope; manual-only is the final v1 design
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| PUBL-01 | Approved video is published to TikTok (manual), Instagram Reels, Facebook Reels, and YouTube Shorts | 08-01: VERIFICATION.md synthesizes UAT 8/8, SUMMARY frontmatter, and integration audit confirming code is wired. TikTok manual design documented in REQUIREMENTS.md. |
| PUBL-02 | Publish is scheduled at peak engagement hours per platform, not immediately on approval | 08-01: Observable Truth confirms `schedule_platform_publishes()` uses `PLATFORM_PEAK_HOURS` DateTrigger. UAT test 7 (schedule_platform_publishes skips TikTok) confirms 3-platform scheduling. |
| PUBL-03 | System verifies post-publish status on each platform 30 minutes after scheduled publish time | 08-01: Observable Truth confirms `verify_publish_job` signature and dispatch. UAT test 8 confirms `verify_publish_job` uses `external_post_id`. Integration audit confirms wiring. |
| PUBL-04 | If Ayrshare publish fails, bot automatically sends the original video file and post copy to Telegram for immediate manual posting | 08-01: Observable Truth confirms `platform_publish.py` failure path sends Supabase Storage URL + platform copy. UAT confirms fallback behavior. Integration audit confirms wiring. |
</phase_requirements>

---

## Summary

Phase 8 is a documentation and hygiene phase. All four requirements (PUBL-01 through PUBL-04) are already implemented in the codebase — the audit confirmed 26/26 integration points wired and 8/8 UAT tests passing for Phase 5. The gap is a missing formal VERIFICATION.md for Phase 5 that the audit system requires before issuing a `passed` verdict.

The three remaining tasks are: (1) a documentation synthesis — writing the Phase 5 VERIFICATION.md by aggregating already-verified evidence from `05-UAT.md`, five SUMMARY files, and the milestone audit's integration checker findings; (2) a test repair — adding a second E2E test that correctly targets the `_process_completed_render()` → `send_approval_message_sync` code path (the existing broken assertion at line 139 stays, but a new test validates approval delivery correctly); (3) a dead-code deletion — removing `src/app/scheduler/jobs/circuit_breaker.py`, which is confirmed unreachable.

There is no new code to write. No new services, APIs, or migrations are needed. The planner should treat this phase as three atomic closure tasks that can be completed in a single session.

**Primary recommendation:** Execute 08-01 (VERIFICATION.md synthesis) first, then 08-02 (second E2E test), then 08-03 (delete orphan). REQUIREMENTS.md TikTok documentation update can be a standalone 08-04 task or appended to 08-01; research recommends folding it into 08-01 since both are documentation edits that close INT-02.

---

## Standard Stack

### Core

| Tool | Version | Purpose | Why Standard |
|------|---------|---------|--------------|
| pytest | >=8.0 (dev dep) | Test runner for new E2E test | Already established; `pytest.mark.e2e` registered in pyproject.toml |
| Python `unittest.mock` | stdlib | Mocking in the new E2E test | Already used throughout test suite; no new dep |
| `uv run pytest` | project venv | Run tests locally | Established per 05-05-SUMMARY.md — `python` unavailable on macOS dev; use `uv run pytest` |

### Supporting

| Tool | Version | Purpose | When to Use |
|------|---------|---------|-------------|
| `git rm` | — | Delete orphaned file from index + working tree | 08-03 deletion task |
| Markdown | — | VERIFICATION.md document format | 08-01 synthesis |

### No External Libraries Required

This phase adds zero new production or dev dependencies. All tools are already installed.

**Run test suite:**
```bash
# Smoke tests (no credentials needed)
uv run pytest tests/test_phase05_smoke.py -v

# E2E tests (ANTHROPIC_API_KEY required, skipped if absent)
uv run pytest tests/test_phase07_e2e.py -v -m e2e

# Full suite excluding e2e
uv run pytest -v -m "not e2e"

# Full suite including e2e (requires credentials)
uv run pytest -v
```

---

## Architecture Patterns

### VERIFICATION.md Format (Phase 7 Template)

The project has an established VERIFICATION.md format, documented by `07-VERIFICATION.md`. The Phase 5 document MUST follow this format exactly.

**YAML Frontmatter:**
```yaml
---
phase: 05-multi-platform-publishing
verified: 2026-03-02T00:00:00Z
status: passed
score: 4/4 must-haves verified
---
```

**Body sections (in order):**
1. Header with goal, verified date, status
2. `## Goal Achievement` → `### Observable Truths` table (4 rows for PUBL-01 through PUBL-04)
3. `### Required Artifacts` table (key Phase 5 files with status VERIFIED)
4. `### Key Link Verification` table (cross-phase wiring)
5. `### Requirements Coverage` table (plan → requirement mapping)
6. `### Human Verification Required` section (UAT already done — note only)
7. `### Gaps Summary` (none)

**File location:** `.planning/phases/05-multi-platform-publishing/05-VERIFICATION.md`

### E2E Test Addition Pattern

**Existing test structure (must stay unchanged):**
```python
# tests/test_phase07_e2e.py

pytestmark = pytest.mark.e2e

@pytest.fixture(autouse=True)
def clear_lru_cache():
    yield
    from app.settings import get_settings
    get_settings.cache_clear()

@pytest.fixture
def mock_all_externals():
    # Mocks: HeyGenService, register_video_poller, send_alert_sync, send_approval_message_sync
    ...

@pytest.mark.skipif(not os.getenv("ANTHROPIC_API_KEY"), reason="...")
def test_daily_pipeline_writes_content_history(mock_all_externals):
    ...
    mock_all_externals["heygen"].submit.assert_called_once()
    mock_all_externals["approval"].assert_called_once()  # line 139 — stays as-is
```

**New test to add (second test in same file):**
The second test must:
- Call `_process_completed_render(video_id, heygen_signed_url)` directly
- Mock the three external calls that `_process_completed_render` makes: `AudioProcessingService.process_video_audio`, `VideoStorageService.upload`, and `send_approval_message_sync`
- Set up a `content_history` row with `video_status = pending_render` and a valid `heygen_job_id` in the DB (requires `SUPABASE_URL`/`SUPABASE_KEY` or a mock)
- Assert `send_approval_message_sync` was called exactly once after completion

**Key import path:** `_process_completed_render` lives in `src/app/services/heygen.py` at module level (not inside a class). Import as:
```python
from app.services.heygen import _process_completed_render
```

**Patch targets for the new test (follow "patch where looked up" rule):**
- `app.services.audio_processing.AudioProcessingService` — instantiated inside `_process_completed_render` body via lazy import
- `app.services.video_storage.VideoStorageService` — same
- `app.services.telegram.send_approval_message_sync` — imported lazily at line 202 of heygen.py

**Fixture design options (Claude's discretion area):**

Option A — Extend `mock_all_externals` fixture (not recommended): The existing fixture mocks at `daily_pipeline_job` scope and would need additional patches for audio/storage services not needed by the first test.

Option B — New targeted fixture (recommended): Create a second fixture `mock_render_completion_externals` that patches exactly the three callables `_process_completed_render` uses. Keeps first test clean and isolated.

```python
@pytest.fixture
def mock_render_completion_externals():
    """Mock externals for _process_completed_render direct call test."""
    with patch("app.services.audio_processing.AudioProcessingService") as mock_audio_cls, \
         patch("app.services.video_storage.VideoStorageService") as mock_storage_cls, \
         patch("app.services.telegram.send_approval_message_sync") as mock_approval:

        mock_audio_cls.return_value.process_video_audio.return_value = b"fake-video-bytes"
        mock_storage_cls.return_value.upload.return_value = "https://storage.supabase.co/fake.mp4"

        yield {
            "audio": mock_audio_cls.return_value,
            "storage": mock_storage_cls.return_value,
            "approval": mock_approval,
        }
```

**DB setup for the second test:**
`_process_completed_render` reads and writes `content_history` using the real `get_supabase()` client. The test therefore needs a real `content_history` row with `video_status=pending_render`. Options:

- **Use live Supabase** (same as the first test pattern) and `skipif` on missing credentials
- **Mock `get_supabase()`** — avoids live DB but requires patching at `app.services.heygen.get_supabase`

The simplest approach consistent with existing patterns: add `SUPABASE_URL` + `SUPABASE_KEY` to the `skipif` condition, insert a test row, call `_process_completed_render`, assert approval called, then clean up.

### Anti-Patterns to Avoid

- **Do not remove line 139** (`mock_all_externals["approval"].assert_called_once()`) — this is a locked decision. The existing test stays intact even though the assertion currently fails with live credentials. The new second test is the fix.
- **Do not add the TikTok OAuth route** — INT-02 is closed by design decision documented in REQUIREMENTS.md, not by implementing a route.
- **Do not strip TikTok code** — removing `tiktok_access_token` from settings, `_fetch_tiktok()`, or `MANUAL_PLATFORMS` is explicitly out of scope (deferred).
- **Do not update the import graph** after deleting `circuit_breaker.py` — the file is confirmed unreachable; no imports reference it.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Verification document format | Custom format | Phase 7 VERIFICATION.md template | Consistency — audit tooling reads a specific format |
| Test isolation for `_process_completed_render` | Complex DB fixtures | Targeted mock fixture (Option B above) | Simpler, matches existing smoke test patterns |
| TikTok gap closure | OAuth route implementation | REQUIREMENTS.md documentation update | Intentional design decision, not a missing feature |

**Key insight:** Every problem in this phase has a pre-existing solution — template (Phase 7 VERIFICATION.md), pattern (existing E2E fixture), or decision (TikTok is manual-only). Nothing needs to be invented.

---

## Common Pitfalls

### Pitfall 1: Removing Line 139 Instead of Adding a Second Test
**What goes wrong:** Deleting `mock_all_externals["approval"].assert_called_once()` from line 139 instead of adding a second test that correctly targets the render-completion path.
**Why it happens:** The audit says "fix the broken assertion" — easiest fix is deletion.
**How to avoid:** CONTEXT.md explicitly locks this: the existing test stays unchanged. The fix is additive (new test), not subtractive.
**Warning signs:** Plan says "remove line 139" — stop and re-read CONTEXT.md.

### Pitfall 2: Wrong Patch Target for `_process_completed_render` Mocks
**What goes wrong:** Patching `app.services.heygen.AudioProcessingService` instead of `app.services.audio_processing.AudioProcessingService`.
**Why it happens:** `_process_completed_render` uses lazy imports (`from app.services.audio_processing import AudioProcessingService` inside function body). Python's mock "patch where looked up" rule applies — patch at the source module, not at the import site.
**How to avoid:** Always patch at the module where the class is defined, not where it's imported.
**Warning signs:** Mock not being called despite function executing.

### Pitfall 3: Phase 5 VERIFICATION.md Missing Evidence Traceability
**What goes wrong:** Writing the VERIFICATION.md without citing specific source evidence for each Observable Truth.
**Why it happens:** It's tempting to write "VERIFIED" without citing the UAT test number or integration checker line.
**How to avoid:** Each row in the Observable Truths table must cite: UAT test number (from `05-UAT.md`), SUMMARY frontmatter plan (e.g., `05-03-SUMMARY.md`), and/or integration checker finding from `v1-MILESTONE-AUDIT.md`.
**Warning signs:** VERIFICATION.md that could be a fabrication — no artifact file paths, no commit hashes, no UAT test references.

### Pitfall 4: Forgetting the `nyquist_validation` Config Check
**What goes wrong:** Looking for `workflow.nyquist_validation` in config.json and failing to find it, then assuming it's `false`.
**Why it happens:** The key is absent from config.json (only `research`, `plan_check`, `verifier` are present under `workflow`).
**How to avoid:** Absent key = treat as `false`. No Validation Architecture section needed.

### Pitfall 5: REQUIREMENTS.md TikTok Update Scope Creep
**What goes wrong:** Editing REQUIREMENTS.md beyond the INT-02 documentation update — e.g., removing TikTok from `PUBL-01` text, or marking ANLX-01 as incomplete.
**Why it happens:** INT-02 touches both ANLX-01 (TikTok metrics) and PUBL-01 (TikTok publishing). The update should only document the design decision, not alter requirement status or text.
**How to avoid:** The update adds a note/footnote or updates the v2 requirements section to make TikTok OAuth explicitly v2. The v1 checkboxes and requirement descriptions stay intact.

---

## Code Examples

### Observable Truths Pattern (from 07-VERIFICATION.md)

```markdown
| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Approved video is published to Instagram, Facebook, YouTube via platform jobs; TikTok copy sent to creator manually | VERIFIED | `publishing.py`: `AUTO_PLATFORMS = {"instagram","facebook","youtube"}`; `MANUAL_PLATFORMS = {"tiktok"}`; UAT test 7 confirms schedule skips TikTok; 05-03-SUMMARY.md lists PUBL-01 in requirements-completed |
| 2 | Publish scheduled at peak hours per platform, not immediately on approval | VERIFIED | `schedule_platform_publishes()` uses `PLATFORM_PEAK_HOURS` DateTrigger; UAT test 7 pass; 05-01-SUMMARY.md peak_hour_* settings documented |
| 3 | System verifies post-publish status 30 minutes after scheduled publish | VERIFIED | `publish_verify.py`: `verify_publish_job(content_history_id, platform, external_post_id)` calls `PublishingService().get_post_status()`; UAT test 8 pass; 05-03-SUMMARY.md PUBL-03 listed |
| 4 | On Ayrshare publish failure, bot sends video URL + platform copy to Telegram for manual posting | VERIFIED | `platform_publish.py` except block: `send_platform_failure_sync(video_url, platform_copy)`; UAT test 6 (confirmation shows TikTok manual block); 05-03-SUMMARY.md PUBL-04 listed |
```

### Required Artifacts Pattern (from 07-VERIFICATION.md)

```markdown
| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `migrations/0005_publishing.sql` | publish_events table + 4 platform copy columns on content_history | VERIFIED | Created in 05-01; commit 7435ab1; UAT test 2 confirmed `external_post_id` column present |
| `src/app/services/publishing.py` | PublishingService with per-platform publish methods; MANUAL_PLATFORMS/AUTO_PLATFORMS | VERIFIED | UAT test 4 confirmed; 05-03-SUMMARY.md commit 43f2694 |
| `src/app/scheduler/jobs/platform_publish.py` | publish_to_platform_job with success/failure Telegram paths | VERIFIED | UAT test 3/4/6; 05-03-SUMMARY.md commit 8b1e258 |
| `src/app/scheduler/jobs/publish_verify.py` | verify_publish_job using external_post_id | VERIFIED | UAT test 8; 05-03-SUMMARY.md commit 8b1e258 |
| `src/app/telegram/handlers/approval_flow.py` | handle_approve wired to schedule_platform_publishes | VERIFIED | UAT test 7; 05-04-SUMMARY.md commit de350e5 |
| `tests/test_phase05_smoke.py` | 12 smoke tests passing (0 failures) | VERIFIED | 05-05-SUMMARY.md commit ce0c735; 12/12 pass |
```

### Key Link Verification Pattern

```markdown
| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `approval_flow.handle_approve` | `schedule_platform_publishes()` | Local import + direct call | WIRED | Confirmed by audit: `approval_flow.py:91-113`; 05-04-SUMMARY.md task 1 commit de350e5 |
| `platform_publish_job` success block | `harvest_metrics_job` | `DateTrigger(now+48h)` | WIRED | Confirmed by audit: `platform_publish.py:103-114`; Phase 5→6 wiring verified |
| `platform_publish_job` failure block | `send_platform_failure_sync` | Direct call | WIRED | `platform_publish.py` except block; UAT test 6 pass |
| `publish_to_platform_job` | `verify_publish_job` | `DateTrigger(now+30min)` | WIRED | 05-03-SUMMARY.md; stable job ID `verify_{content_history_id}_{platform}` |
```

### Second E2E Test Sketch

```python
# Source: research synthesis from heygen.py lines 147-212 and existing mock patterns
@pytest.mark.skipif(
    not os.getenv("SUPABASE_URL") or not os.getenv("SUPABASE_KEY"),
    reason="SUPABASE_URL/SUPABASE_KEY not set — render completion test skipped"
)
def test_render_completion_sends_approval_message(mock_render_completion_externals):
    """
    Tests _process_completed_render() directly — the code path where
    send_approval_message_sync is actually called (webhook/poller path, not daily_pipeline_job).

    This is the correct target for the approval mock assertion.
    daily_pipeline_job() only calls HeyGen.submit(); approval delivery
    happens after render completes via _process_completed_render().
    """
    from app.services.heygen import _process_completed_render
    from app.services.database import get_supabase

    # Insert a content_history row with video_status=pending_render
    supabase = get_supabase()
    fake_job_id = "test-render-job-e2e"
    result = supabase.table("content_history").insert({
        "heygen_job_id": fake_job_id,
        "video_status": "pending_render",
        "script_text": "Test script for render completion E2E",
        "topic_summary": "test topic",
    }).execute()
    content_history_id = result.data[0]["id"]

    try:
        # Call the render-completion function directly
        _process_completed_render(
            video_id=fake_job_id,
            heygen_signed_url="https://fake-heygen-signed.url/video.mp4"
        )

        # Assert approval message was sent exactly once
        mock_render_completion_externals["approval"].assert_called_once()
        call_kwargs = mock_render_completion_externals["approval"].call_args
        assert call_kwargs.kwargs["content_history_id"] == content_history_id
        assert "storage.supabase.co" in call_kwargs.kwargs.get("video_url", "")

    finally:
        # Clean up test row
        supabase.table("content_history").delete().eq("id", content_history_id).execute()
```

### REQUIREMENTS.md TikTok Design Decision Update

The update should add an explicit note to the v2 section for `ANLX-TKTOK-01` and close INT-02. Suggested addition after the current v2 table:

```markdown
**TikTok Design Decision (v1 closure):**
TikTok publishing in v1 is intentionally manual: `MANUAL_PLATFORMS = {"tiktok"}` in `publishing.py`.
The system generates TikTok copy and delivers it to the creator in the Telegram approval message;
the creator posts manually. No TikTok API publishing route is implemented.

TikTok metrics collection (`_fetch_tiktok()`) degrades gracefully when `TIKTOK_ACCESS_TOKEN` is
empty string (default). This is acceptable v1 behavior — TikTok OAuth (`/auth/tiktok`) is a v2
feature tracked as `ANLX-TKTOK-01`. Audit gap INT-02 is **closed by design decision**.
```

---

## Evidence Inventory for 08-01 (Phase 5 VERIFICATION.md)

This table maps each PUBL requirement to its complete evidence trail. The planner should ensure 08-01 cites all of these.

| Req | UAT Test | SUMMARY Plans | Integration Audit | Files |
|-----|----------|---------------|-------------------|-------|
| PUBL-01 | Tests 4, 5, 6, 7 (all pass) | 05-01, 05-02, 05-03, 05-04, 05-05 frontmatter | `handle_approve → schedule_platform_publishes` WIRED (`approval_flow.py:91-113`) | `publishing.py`, `platform_publish.py`, `approval_flow.py` |
| PUBL-02 | Test 7 (schedule skips TikTok, 3 jobs only) | 05-01, 05-03, 05-04, 05-05 frontmatter | Same as PUBL-01 | `publishing.py:PLATFORM_PEAK_HOURS`, `schedule_platform_publishes()` |
| PUBL-03 | Test 8 (`verify_publish_job` uses `external_post_id`) | 05-03, 05-05 frontmatter | `platform_publish.py:103-114` schedules verify job | `publish_verify.py`, `platform_publish.py` |
| PUBL-04 | Test 6 (confirmation shows TikTok manual block) | 05-03, 05-05 frontmatter | `platform_publish.py` except block → `send_platform_failure_sync` | `platform_publish.py`, `telegram.py` (failure helpers) |

**TikTok note:** UAT test 7 confirms `schedule_platform_publishes()` only schedules 3 jobs (Instagram, Facebook, YouTube). TikTok copy is delivered in the approval message (test 5). This is correct v1 behavior. PUBL-01 counts TikTok as satisfied because manual delivery via Telegram IS the publishing mechanism for TikTok in v1.

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| No Phase 5 VERIFICATION.md | Write 05-VERIFICATION.md synthesizing existing evidence | Phase 8 | Closes audit blocker; PUBL-01–04 status moves from `partial` to `satisfied` |
| Broken E2E assertion at line 139 | Add second test targeting `_process_completed_render` directly | Phase 8 | FLOW-01 gap closed; E2E test suite is correct |
| Orphaned `circuit_breaker.py` | Delete file | Phase 8 | INT-01 gap closed; no stale code risk |
| INT-02 (TikTok OAuth) marked as gap | Document as design decision in REQUIREMENTS.md | Phase 8 | INT-02 closed; v2 tracker (`ANLX-TKTOK-01`) already in place |

**After Phase 8 completes:**
- Requirements score: 26/26 satisfied (4 partial → satisfied)
- Phase verifications: 7/7 complete
- E2E flows: 5/5 (broken test fixed)
- Orphaned code: 0
- `/gsd:audit-milestone` should return `passed`

---

## Open Questions

1. **Should the second E2E test use a live Supabase or mock `get_supabase()`?**
   - What we know: `_process_completed_render` calls `get_supabase()` multiple times (initial UPDATE, storage upload, SELECT for content_history_id, final UPDATE)
   - What's unclear: Mocking `get_supabase()` requires chaining multiple `.table().update().eq()...execute()` mock calls, which is brittle
   - Recommendation: Use live Supabase with `skipif` on missing credentials, mirroring the existing first test pattern. Insert + cleanup in finally block.

2. **Should 08-04 (TikTok REQUIREMENTS.md update) be a standalone plan or folded into 08-01?**
   - What we know: Both are documentation edits; 08-01 already writes a `.planning/` file; REQUIREMENTS.md is a project-root file
   - Recommendation: Fold into 08-01 as a second task. Both edits are < 5 minutes and share no code risk. A standalone plan adds overhead without benefit.

---

## Sources

### Primary (HIGH confidence)

- `.planning/v1-MILESTONE-AUDIT.md` — Complete gap list, integration checker findings, closure actions required; read directly
- `.planning/phases/07-hardening/07-VERIFICATION.md` — Template format for Phase 5 VERIFICATION.md; read directly
- `.planning/phases/05-multi-platform-publishing/05-UAT.md` — 8/8 test evidence for all PUBL requirements; read directly
- `.planning/phases/05-multi-platform-publishing/05-0{1..5}-SUMMARY.md` — requirements-completed frontmatter and key-decisions; read directly
- `tests/test_phase07_e2e.py` — Exact line 139 assertion, fixture structure, mock targets; read directly
- `src/app/services/heygen.py` (lines 147–213) — `_process_completed_render` function body, lazy import paths, patch targets; read directly
- `src/app/scheduler/jobs/circuit_breaker.py` — Confirmed orphaned file (missing Phase 7 methods: `is_daily_halted`, `clear_daily_halt`); read directly
- `.planning/phases/08-milestone-closure/08-CONTEXT.md` — All locked implementation decisions; read directly
- `.planning/REQUIREMENTS.md` — PUBL-01–04 definitions and traceability table; read directly
- `pyproject.toml` — Test framework (pytest>=8.0), `pytest.mark.e2e` registration, no `nyquist_validation` in config

### Secondary (MEDIUM confidence)

- `.planning/STATE.md` — Project history, decision log; corroborates that Phase 7 is complete and Phase 8 is the gap closure phase

### Tertiary (LOW confidence)

None — all findings are grounded in direct file reads.

---

## Metadata

**Confidence breakdown:**
- Phase 5 evidence synthesis: HIGH — all evidence files read directly; nothing inferred
- E2E test fix approach: HIGH — `_process_completed_render` source read; patch targets verified
- Orphaned file deletion: HIGH — file confirmed to exist, imports confirmed absent in audit
- REQUIREMENTS.md TikTok update: HIGH — design decision locked in CONTEXT.md

**Research date:** 2026-03-02
**Valid until:** Phase 8 is a one-session closure task; research does not expire
