# Deferred Items

Items discovered during task execution that are out of scope for the current task.

---

## 2026-03-20 — Discovered during quick/260320-edq

**test_kling_fal_arguments_locked_spec fails: duration mismatch**

- **File:** `tests/test_kling_service.py`
- **Issue:** Test expects `duration == 20` but `kling.py` has `DEFAULT_KLING_DURATION = 15`
- **Status:** Pre-existing mismatch (kling.py was already modified before this task ran)
- **Action needed:** Either update `DEFAULT_KLING_DURATION` to 20 in `kling.py` or update the test to expect 15 — needs deliberate decision on the correct value
