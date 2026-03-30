"""
TDD RED: PromptGenerationService tests.
Phase 12-01 Task 2

Tests that PromptGenerationService correctly generates or falls back to
a unified prompt string for Kling AI video generation.

Written before implementation — must FAIL until prompt_generation.py exists.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from unittest.mock import MagicMock, patch, PropertyMock


def _make_mock_settings():
    """Build mock settings with required API keys."""
    settings = MagicMock()
    settings.openai_api_key = "sk-test-mock-key"
    return settings


def _make_mock_response(text: str, prompt_tokens: int = 100, completion_tokens: int = 50):
    """Build a mock OpenAI chat completion response."""
    response = MagicMock()
    response.choices[0].message.content = text
    response.usage.prompt_tokens = prompt_tokens
    response.usage.completion_tokens = completion_tokens
    return response


def test_import_prompt_generation_service():
    """PromptGenerationService must be importable from prompt_generation module."""
    from app.services.prompt_generation import PromptGenerationService
    assert PromptGenerationService is not None


def test_generate_unified_prompt_returns_string():
    """generate_unified_prompt must return a non-empty string on success."""
    with patch("app.services.prompt_generation.get_settings", return_value=_make_mock_settings()), \
         patch("app.services.prompt_generation.OpenAI") as mock_openai_cls:
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_client.chat.completions.create.return_value = _make_mock_response(
            "A cute grey kitten with blue eyes explores a sunlit kitchen."
        )
        from app.services.prompt_generation import PromptGenerationService
        svc = PromptGenerationService()
        result = svc.generate_unified_prompt("The kitten sits by the window.")
        assert isinstance(result, str), "generate_unified_prompt must return a str"
        assert len(result) > 0, "generate_unified_prompt must return a non-empty str"


def test_generate_unified_prompt_gpt4o_success():
    """On GPT-4o success, returns the text from the response (not concatenation fallback)."""
    expected_text = "An ultra-cute grey kitten with huge blue eyes investigates a bubbling pot on the stove."
    with patch("app.services.prompt_generation.get_settings", return_value=_make_mock_settings()), \
         patch("app.services.prompt_generation.OpenAI") as mock_openai_cls:
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_client.chat.completions.create.return_value = _make_mock_response(expected_text)
        from app.services.prompt_generation import PromptGenerationService
        svc = PromptGenerationService()
        result = svc.generate_unified_prompt("Kitchen exploration scene.")
        assert result == expected_text


def test_generate_unified_prompt_fallback_on_exception():
    """On GPT-4o failure, returns CHARACTER_BIBLE + '\\n\\n' + scene_prompt."""
    from app.services.kling import CHARACTER_BIBLE

    with patch("app.services.prompt_generation.get_settings", return_value=_make_mock_settings()), \
         patch("app.services.prompt_generation.OpenAI") as mock_openai_cls:
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_client.chat.completions.create.side_effect = RuntimeError("API down")
        from app.services.prompt_generation import PromptGenerationService
        # Patch tenacity retry to not actually sleep/retry
        with patch("app.services.prompt_generation._call_gpt4o_with_backoff", side_effect=RuntimeError("API down")):
            svc = PromptGenerationService()
            scene = "The kitten naps on a warm blanket."
            result = svc.generate_unified_prompt(scene)
            expected = f"{CHARACTER_BIBLE}\n\n{scene}"
            assert result == expected, f"Fallback must be CHARACTER_BIBLE + scene, got: {result!r}"


def test_generate_unified_prompt_never_raises():
    """generate_unified_prompt must NEVER raise — always returns a usable string."""
    with patch("app.services.prompt_generation.get_settings", return_value=_make_mock_settings()), \
         patch("app.services.prompt_generation.OpenAI") as mock_openai_cls:
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        with patch("app.services.prompt_generation._call_gpt4o_with_backoff", side_effect=Exception("total failure")):
            from app.services.prompt_generation import PromptGenerationService
            svc = PromptGenerationService()
            result = svc.generate_unified_prompt("Any scene.")
            assert isinstance(result, str) and len(result) > 0


def test_fallback_logs_warning():
    """logger.warning must be called when falling back to concatenation."""
    with patch("app.services.prompt_generation.get_settings", return_value=_make_mock_settings()), \
         patch("app.services.prompt_generation.OpenAI") as mock_openai_cls, \
         patch("app.services.prompt_generation.logger") as mock_logger:
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        with patch("app.services.prompt_generation._call_gpt4o_with_backoff", side_effect=RuntimeError("fail")):
            from app.services.prompt_generation import PromptGenerationService
            svc = PromptGenerationService()
            svc.generate_unified_prompt("Scene prompt here.")
            mock_logger.warning.assert_called_once()


def test_last_cost_usd_set_on_success():
    """self._last_cost_usd must be set to a float after successful GPT-4o call."""
    with patch("app.services.prompt_generation.get_settings", return_value=_make_mock_settings()), \
         patch("app.services.prompt_generation.OpenAI") as mock_openai_cls:
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_client.chat.completions.create.return_value = _make_mock_response(
            "Unified prompt text.", prompt_tokens=500, completion_tokens=100
        )
        from app.services.prompt_generation import PromptGenerationService
        svc = PromptGenerationService()
        svc.generate_unified_prompt("Test scene.")
        assert isinstance(svc._last_cost_usd, float), "_last_cost_usd must be a float"
        assert svc._last_cost_usd > 0.0, "_last_cost_usd must be positive on success"


def test_last_cost_usd_zero_on_fallback():
    """self._last_cost_usd must be 0.0 on GPT-4o failure (fallback)."""
    with patch("app.services.prompt_generation.get_settings", return_value=_make_mock_settings()), \
         patch("app.services.prompt_generation.OpenAI") as mock_openai_cls:
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        with patch("app.services.prompt_generation._call_gpt4o_with_backoff", side_effect=RuntimeError("fail")):
            from app.services.prompt_generation import PromptGenerationService
            svc = PromptGenerationService()
            svc.generate_unified_prompt("Test scene.")
            assert svc._last_cost_usd == 0.0


def test_call_gpt4o_with_backoff_is_module_level():
    """_call_gpt4o_with_backoff must be a module-level function, not an instance method."""
    import inspect
    from app.services import prompt_generation
    assert hasattr(prompt_generation, "_call_gpt4o_with_backoff"), (
        "_call_gpt4o_with_backoff must be at module level"
    )
    func = prompt_generation._call_gpt4o_with_backoff
    # It should be a function (or tenacity-wrapped function), not a method
    # Checking it's not defined on the class
    assert not hasattr(prompt_generation.PromptGenerationService, "_call_gpt4o_with_backoff")


# ── Phase 12-03 required tests ─────────────────────────────────────────────────

def test_generate_unified_prompt_returns_gpt4o_result():
    """generate_unified_prompt returns GPT-4o output on success."""
    expected = "A tiny grey kitten with huge blue eyes bats at a yarn ball in golden afternoon light."

    with patch("app.services.prompt_generation.OpenAI") as mock_openai_cls, \
         patch("app.services.prompt_generation.get_settings") as mock_settings:
        mock_settings.return_value.openai_api_key = "sk-test"
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_client.chat.completions.create.return_value = _make_mock_response(expected)

        from app.services.prompt_generation import PromptGenerationService
        svc = PromptGenerationService()
        result = svc.generate_unified_prompt("A kitten bats at yarn.")

    assert result == expected, f"Expected GPT-4o output, got: {result!r}"


def test_generate_unified_prompt_fallback_on_failure():
    """generate_unified_prompt falls back to CHARACTER_BIBLE concatenation when GPT-4o fails."""
    scene_prompt = "A grey kitten investigates a fallen clay pot on a sun-drenched patio."

    with patch("app.services.prompt_generation.OpenAI") as mock_openai_cls, \
         patch("app.services.prompt_generation.get_settings") as mock_settings, \
         patch("app.services.prompt_generation._call_gpt4o_with_backoff",
               side_effect=Exception("GPT-4o API unavailable")):
        mock_settings.return_value.openai_api_key = "sk-test"
        mock_openai_cls.return_value = MagicMock()

        from app.services.prompt_generation import PromptGenerationService, CHARACTER_BIBLE
        svc = PromptGenerationService()
        result = svc.generate_unified_prompt(scene_prompt)

    expected_fallback = f"{CHARACTER_BIBLE}\n\n{scene_prompt}"
    assert result == expected_fallback, (
        f"Fallback must be CHARACTER_BIBLE + newlines + scene_prompt.\nGot: {result!r}"
    )


def test_prompt_generation_never_raises():
    """generate_unified_prompt must not propagate exceptions — always returns a string."""
    with patch("app.services.prompt_generation.OpenAI") as mock_openai_cls, \
         patch("app.services.prompt_generation.get_settings") as mock_settings, \
         patch("app.services.prompt_generation._call_gpt4o_with_backoff",
               side_effect=RuntimeError("Unexpected error")):
        mock_settings.return_value.openai_api_key = "sk-test"
        mock_openai_cls.return_value = MagicMock()

        from app.services.prompt_generation import PromptGenerationService
        svc = PromptGenerationService()
        try:
            result = svc.generate_unified_prompt("test scene")
            assert isinstance(result, str) and len(result) > 0
        except Exception as e:
            raise AssertionError(
                f"generate_unified_prompt must never raise but raised: {e}"
            ) from e


def test_prompt_generation_tracks_cost():
    """_last_cost_usd is set to a positive value after a successful GPT-4o call."""
    gpt_text = "Animated grey kitten with blue eyes leaps through a sunlit garden."

    with patch("app.services.prompt_generation.OpenAI") as mock_openai_cls, \
         patch("app.services.prompt_generation.get_settings") as mock_settings:
        mock_settings.return_value.openai_api_key = "sk-test"
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        # 200 prompt tokens + 60 output tokens -> cost > 0
        mock_client.chat.completions.create.return_value = _make_mock_response(
            gpt_text, prompt_tokens=200, completion_tokens=60
        )

        from app.services.prompt_generation import PromptGenerationService
        svc = PromptGenerationService()
        svc.generate_unified_prompt("A kitten explores the garden.")

    assert svc._last_cost_usd > 0.0, (
        f"_last_cost_usd must be positive after successful GPT-4o call, got {svc._last_cost_usd}"
    )


def test_prompt_generation_cost_zero_on_fallback():
    """_last_cost_usd is reset to 0.0 when GPT-4o fails and fallback is used."""
    with patch("app.services.prompt_generation.OpenAI") as mock_openai_cls, \
         patch("app.services.prompt_generation.get_settings") as mock_settings, \
         patch("app.services.prompt_generation._call_gpt4o_with_backoff",
               side_effect=Exception("timeout")):
        mock_settings.return_value.openai_api_key = "sk-test"
        mock_openai_cls.return_value = MagicMock()

        from app.services.prompt_generation import PromptGenerationService
        svc = PromptGenerationService()
        svc._last_cost_usd = 0.999  # simulate previous cost — must be reset
        svc.generate_unified_prompt("test scene")

    assert svc._last_cost_usd == 0.0, (
        f"_last_cost_usd must be 0.0 on fallback, got {svc._last_cost_usd}"
    )


def test_prompt_generation_system_prompt_contains_animated():
    """The prompt sent to GPT-4o must contain 'animated' and 'ultra-cute' framing."""
    captured_prompts = []

    def capture_call(*args, **kwargs):
        if "messages" in kwargs:
            for msg in kwargs["messages"]:
                captured_prompts.append(msg.get("content", ""))
        return _make_mock_response("A cute kitten plays in the sun.")

    with patch("app.services.prompt_generation.OpenAI") as mock_openai_cls, \
         patch("app.services.prompt_generation.get_settings") as mock_settings:
        mock_settings.return_value.openai_api_key = "sk-test"
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_client.chat.completions.create.side_effect = capture_call

        from app.services.prompt_generation import PromptGenerationService
        svc = PromptGenerationService()
        svc.generate_unified_prompt("A kitten in a garden.")

    assert captured_prompts, "No prompts captured — GPT-4o was not called"
    full_prompt = " ".join(captured_prompts).lower()
    assert "animated" in full_prompt, f"System prompt must contain 'animated', got: {full_prompt[:200]}"
    assert "ultra-cute" in full_prompt, f"System prompt must contain 'ultra-cute', got: {full_prompt[:200]}"


# ── Phase 13: Arc-preservation system prompt tests ──────────────────────────

def test_system_prompt_contains_arc_keywords():
    """Phase 13 (SCN-13-03): _SYSTEM_PROMPT must contain hook/climax/conclusion arc keywords."""
    from app.services.prompt_generation import _SYSTEM_PROMPT
    prompt_lower = _SYSTEM_PROMPT.lower()
    assert "hook" in prompt_lower, "_SYSTEM_PROMPT must mention 'hook'"
    assert "climax" in prompt_lower, "_SYSTEM_PROMPT must mention 'climax'"
    assert "conclusion" in prompt_lower, "_SYSTEM_PROMPT must mention 'conclusion'"


def test_system_prompt_requires_flowing_prose():
    """Phase 13 (SCN-13-03): _SYSTEM_PROMPT must require flowing prose (not explicit time markers)."""
    from app.services.prompt_generation import _SYSTEM_PROMPT
    assert "flowing prose" in _SYSTEM_PROMPT.lower(), "_SYSTEM_PROMPT must mention 'flowing prose'"
    # Must prohibit explicit time markers
    assert "do not use explicit time markers" in _SYSTEM_PROMPT.lower() or \
           "not use explicit time markers" in _SYSTEM_PROMPT.lower(), (
        "_SYSTEM_PROMPT must prohibit explicit time markers (e.g., 'In the first 3 seconds...')"
    )


def test_system_prompt_instructs_arc_preservation_in_each_beat():
    """Phase 13 (SCN-13-03): _SYSTEM_PROMPT must instruct weaving kitten into each narrative beat."""
    from app.services.prompt_generation import _SYSTEM_PROMPT
    assert "each" in _SYSTEM_PROMPT.lower() and "beat" in _SYSTEM_PROMPT.lower(), (
        "_SYSTEM_PROMPT must instruct character presence in each narrative beat"
    )


def test_system_prompt_output_is_3_to_5_sentences():
    """Phase 13 (SCN-13-03): _SYSTEM_PROMPT must request 3-5 sentences (not 2-4 from Phase 12)."""
    from app.services.prompt_generation import _SYSTEM_PROMPT
    assert "3-5 sentences" in _SYSTEM_PROMPT, (
        "_SYSTEM_PROMPT must request 3-5 sentences for arc prompts (was 2-4 in Phase 12)"
    )
