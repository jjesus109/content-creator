---
phase: quick-003
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - src/app/settings.py
  - src/app/services/heygen.py
  - scripts/dry_run_heygen_submit.py
autonomous: true
requirements: []

must_haves:
  truths:
    - "HeyGenService.submit() sends a payload that matches the verified v2 structure"
    - "avatar_id, voice_id, and gesture_prompt are driven from Settings (not hardcoded)"
    - "dry-run script submits a real HeyGen job and prints the returned video_id"
  artifacts:
    - path: "src/app/settings.py"
      provides: "heygen_gesture_prompt setting"
      contains: "heygen_gesture_prompt"
    - path: "src/app/services/heygen.py"
      provides: "Corrected payload builder"
      contains: "use_avatar_iv_model"
    - path: "scripts/dry_run_heygen_submit.py"
      provides: "CLI to submit a real HeyGen job and print video_id"
      contains: "video_id"
  key_links:
    - from: "src/app/services/heygen.py"
      to: "src/app/settings.py"
      via: "get_settings().heygen_gesture_prompt"
      pattern: "heygen_gesture_prompt"
---

<objective>
Align HeyGenService.submit() with the verified HeyGen v2 API payload structure, add
heygen_gesture_prompt to Settings, and create a dry-run script that submits a real render
job and prints its video_id (without waiting for completion).

Purpose: The existing payload has wrong dimension types, missing character fields, wrong
voice field types, and an incorrect background structure. The verified payload is the
ground truth from a working real request. This plan makes production code match it exactly.

Output:
- src/app/settings.py — new `heygen_gesture_prompt` field
- src/app/services/heygen.py — corrected submit() payload
- scripts/dry_run_heygen_submit.py — real HeyGen job submission CLI
</objective>

<execution_context>
@./.claude/get-shit-done/workflows/execute-plan.md
</execution_context>

<context>
@.planning/STATE.md
@src/app/settings.py
@src/app/services/heygen.py
@scripts/dry_run_script_generation.py
</context>

<tasks>

<task type="auto">
  <name>Task 1: Add heygen_gesture_prompt to Settings</name>
  <files>src/app/settings.py</files>
  <action>
    Add one new field to the Settings class in the HeyGen section (after heygen_ambient_music_urls):

    ```python
    heygen_gesture_prompt: str  # Avatar gesture instruction sent as character.prompt in v2 API
    ```

    No default — Pydantic raises ValidationError at startup if the env var is absent.
    This follows the existing "all 7 HeyGen fields required" project decision from Phase 03-01.

    The env var name will be HEYGEN_GESTURE_PROMPT (Pydantic case-insensitive mapping).
  </action>
  <verify>
    <automated>cd /Users/jesusalbino/Projects/content-creation && python -c "import sys; sys.path.insert(0,'src'); from app.settings import Settings; import inspect; src=inspect.getsource(Settings); assert 'heygen_gesture_prompt' in src, 'field missing'; print('OK')"</automated>
  </verify>
  <done>Settings class contains heygen_gesture_prompt: str with no default value.</done>
</task>

<task type="auto">
  <name>Task 2: Rewrite HeyGenService.submit() payload to match verified v2 structure</name>
  <files>src/app/services/heygen.py</files>
  <action>
    Replace the payload dict inside HeyGenService.submit() with the verified structure below.
    Do NOT touch anything else in the file (pick_background_url, _process_completed_render,
    _handle_render_failure remain unchanged).

    The verified payload structure to implement:

    ```python
    payload = {
        "caption": True,
        "dimension": {
            "width": "1920",
            "height": "1080",
        },
        "title": "Daily video",
        "video_inputs": [
            {
                "character": {
                    "type": "avatar",
                    "scale": 1,
                    "avatar_style": "normal",
                    "talking_style": "stable",
                    "avatar_id": settings.heygen_avatar_id,
                    "use_avatar_iv_model": True,
                    "prompt": settings.heygen_gesture_prompt,
                },
                "voice": {
                    "type": "text",
                    "speed": "1",
                    "pitch": "0",
                    "duration": "1",
                    "voice_id": settings.heygen_voice_id,
                    "input_text": script_text,
                },
            }
        ],
        "callback_url": settings.heygen_webhook_url,
    }
    ```

    Key changes from the old payload:
    - `caption` changed from False to True
    - `dimension` values are now strings "1920"/"1080" (16:9 landscape) instead of integers 1080/1920
    - `character` gains: scale, talking_style, use_avatar_iv_model, prompt
    - `voice` gains: pitch, duration; speed changed from float 1.0 to string "1"
    - `background` block removed from video_inputs (not in verified payload)
    - `callback_url` kept at top level (webhook still needed for production render notifications)
    - `title` added as "Daily video"

    The `background_url` parameter is now unused in submit(). Keep it in the method signature
    for now (callers in daily_pipeline_job.py pass it) but stop using it in the payload.
    Add a comment: `# background_url retained in signature for caller compatibility; not used in v2 payload`.
    Do NOT remove it from callers — that is out of scope.

    Update the logger.info call to also log `gesture_prompt=settings.heygen_gesture_prompt[:40]`
    (first 40 chars for readability).
  </action>
  <verify>
    <automated>cd /Users/jesusalbino/Projects/content-creation && python -c "
import sys; sys.path.insert(0,'src')
import inspect
from app.services.heygen import HeyGenService
src = inspect.getsource(HeyGenService.submit)
assert 'use_avatar_iv_model' in src, 'missing use_avatar_iv_model'
assert '\"1920\"' in src, 'dimension width must be string'
assert 'talking_style' in src, 'missing talking_style'
assert 'heygen_gesture_prompt' in src, 'missing gesture_prompt reference'
assert 'caption.*True' not in src or 'caption\": True' in src or \"caption': True\" in src, 'caption must be True'
print('OK')
"</automated>
  </verify>
  <done>
    HeyGenService.submit() payload matches the verified v2 structure:
    caption=True, dimension as strings, character has scale/talking_style/use_avatar_iv_model/prompt,
    voice has speed/pitch/duration as strings. background block removed.
  </done>
</task>

<task type="auto">
  <name>Task 3: Create dry_run_heygen_submit.py — submits real HeyGen job, prints video_id</name>
  <files>scripts/dry_run_heygen_submit.py</files>
  <action>
    Create scripts/dry_run_heygen_submit.py. It must:

    1. Add src/ to sys.path and load_dotenv() — same pattern as dry_run_script_generation.py
    2. Instantiate HeyGenService (real, no mocks — this hits the live HeyGen API)
    3. Call submit() with a short hardcoded Spanish test script and a dummy background_url=""
       (background is no longer used in the payload, so any string is fine)
    4. Print the returned video_id prominently
    5. Print a note explaining the job is now rendering in HeyGen and can be monitored
       at https://app.heygen.com/videos

    Use argparse with one optional flag: --script (default: a short ~20-word Spanish phrase
    for testing, e.g. "En cada momento de quietud, encontramos la claridad que el ruido del mundo nos roba.")

    Error handling: wrap the submit() call in try/except requests.HTTPError and print the
    response body on failure (response.text) to aid debugging.

    Full file structure:

    ```python
    #!/usr/bin/env python3
    """
    Dry-run HeyGen video submission against the real HeyGen v2 API.

    Submits a render job and prints the video_id. Does NOT wait for completion.
    Monitor progress at: https://app.heygen.com/videos

    Usage:
        python scripts/dry_run_heygen_submit.py
        python scripts/dry_run_heygen_submit.py --script "Tu texto aquí."

    Requirements:
        HEYGEN_API_KEY, HEYGEN_AVATAR_ID, HEYGEN_VOICE_ID, HEYGEN_WEBHOOK_URL,
        HEYGEN_GESTURE_PROMPT must be set in .env
    """
    import sys, os, argparse
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

    from dotenv import load_dotenv
    load_dotenv()

    import requests
    from app.services.heygen import HeyGenService

    DEFAULT_SCRIPT = (
        "En cada momento de quietud, encontramos la claridad "
        "que el ruido del mundo nos roba."
    )

    def main() -> None:
        parser = argparse.ArgumentParser(
            description="Submit a real HeyGen render job and print the video_id."
        )
        parser.add_argument(
            "--script",
            default=DEFAULT_SCRIPT,
            help="Spanish script text to render (default: short test phrase)",
        )
        args = parser.parse_args()

        sep = "=" * 60
        print(sep)
        print("DRY RUN: HeyGen Video Submit")
        print(f"Script ({len(args.script.split())} words): {args.script}")
        print(sep)

        svc = HeyGenService()
        try:
            video_id = svc.submit(script_text=args.script, background_url="")
            print(f"\n[SUCCESS]")
            print(f"video_id: {video_id}")
            print(f"\nJob is rendering. Monitor at: https://app.heygen.com/videos")
            print(f"The webhook will fire to HEYGEN_WEBHOOK_URL when complete.")
        except requests.HTTPError as exc:
            print(f"\n[FAILED] HTTP {exc.response.status_code}")
            print(exc.response.text)
            sys.exit(1)

        print(sep)

    if __name__ == "__main__":
        main()
    ```
  </action>
  <verify>
    <automated>cd /Users/jesusalbino/Projects/content-creation && python -c "
import ast, pathlib
src = pathlib.Path('scripts/dry_run_heygen_submit.py').read_text()
assert 'HeyGenService' in src
assert 'video_id' in src
assert 'HTTPError' in src
assert 'argparse' in src
# syntax check
ast.parse(src)
print('OK')
"</automated>
  </verify>
  <done>
    scripts/dry_run_heygen_submit.py exists, passes syntax check, imports HeyGenService,
    handles HTTPError, and prints video_id on success.
  </done>
</task>

</tasks>

<verification>
Run all three automated verify commands above. All should print "OK".

Optionally (if HEYGEN_* env vars are set in .env):
  python scripts/dry_run_heygen_submit.py

Expected output: a video_id string (format: UUID-like hex string from HeyGen).
</verification>

<success_criteria>
- Settings has heygen_gesture_prompt: str with no default
- HeyGenService.submit() payload has: caption=True, dimension as strings "1920"/"1080",
  character.use_avatar_iv_model=True, character.talking_style="stable", character.prompt=settings.heygen_gesture_prompt,
  voice.speed="1", voice.pitch="0", voice.duration="1", no background block
- scripts/dry_run_heygen_submit.py can be run with live credentials and prints a real video_id
</success_criteria>

<output>
No SUMMARY.md needed for quick tasks. Update .planning/STATE.md Quick Tasks Completed table
to add entry for task 003 after execution.
</output>
