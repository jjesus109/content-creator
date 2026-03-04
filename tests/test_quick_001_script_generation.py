"""
Quick Task 001 — Script Generation: Hook + 120-word hard cap

Tests for:
- HARD_WORD_LIMIT = 120 defined at module level
- _word_count helper correctness
- generate_script system prompt contains 120 and hook instruction
- summarize_if_needed uses effective_target + HARD_WORD_LIMIT

No live API calls — uses import/inspect only.
"""
import os
import sys
import inspect

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


def test_hard_word_limit_constant():
    """HARD_WORD_LIMIT = 120 must be importable from script_generation module."""
    from app.services.script_generation import HARD_WORD_LIMIT
    assert HARD_WORD_LIMIT == 120, f"Expected 120, got {HARD_WORD_LIMIT}"


def test_word_count_basic():
    """_word_count('hola mundo') == 2."""
    from app.services.script_generation import _word_count
    assert _word_count("hola mundo") == 2


def test_word_count_empty():
    """_word_count('') == 0."""
    from app.services.script_generation import _word_count
    assert _word_count("") == 0


def test_generate_script_prompt_contains_hard_limit():
    """generate_script system prompt must reference the 120-word absolute ceiling."""
    from app.services.script_generation import HARD_WORD_LIMIT
    import inspect
    from app.services.script_generation import ScriptGenerationService
    src = inspect.getsource(ScriptGenerationService.generate_script)
    assert "HARD_WORD_LIMIT" in src, "generate_script must reference HARD_WORD_LIMIT constant"
    assert "LIMITE ABSOLUTO" in src or "120" in src, "generate_script prompt must mention 120-word limit"


def test_generate_script_prompt_contains_hook_instruction():
    """generate_script system prompt must contain a mandatory first-phrase hook instruction."""
    from app.services.script_generation import ScriptGenerationService
    src = inspect.getsource(ScriptGenerationService.generate_script)
    # The hook instruction should appear as item 0 before the 6 pillars
    assert "PRIMERA FRASE OBLIGATORIA" in src or "hook" in src.lower(), (
        "generate_script must contain a mandatory hook instruction as item 0"
    )
    assert "PRIMERA FRASE OBLIGATORIA" in src, (
        "generate_script must contain '0. PRIMERA FRASE OBLIGATORIA' hook instruction"
    )


def test_summarize_if_needed_uses_effective_target():
    """summarize_if_needed must use effective_target = min(target_words, HARD_WORD_LIMIT)."""
    from app.services.script_generation import ScriptGenerationService
    src = inspect.getsource(ScriptGenerationService.summarize_if_needed)
    assert "effective_target" in src, "effective_target not found in summarize_if_needed"
    assert "HARD_WORD_LIMIT" in src, "HARD_WORD_LIMIT not referenced in summarize_if_needed"


def test_summarize_if_needed_guardrails_contain_120():
    """summarize_if_needed guardrails must explicitly mention 120-word ceiling."""
    from app.services.script_generation import ScriptGenerationService
    src = inspect.getsource(ScriptGenerationService.summarize_if_needed)
    assert "HARD_WORD_LIMIT" in src, "HARD_WORD_LIMIT must appear in summarize_if_needed guardrails"
    assert "La primera frase" in src or "hook" in src.lower(), (
        "summarize_if_needed guardrails must include hook first-phrase instruction"
    )
