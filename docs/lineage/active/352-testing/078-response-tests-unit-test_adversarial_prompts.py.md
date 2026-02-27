

```python
"""Unit tests for prompt construction.

Issue #352: Multi-Model Adversarial Testing Node (Gemini vs Claude)
"""

import pytest

from assemblyzero.workflows.testing.adversarial_prompts import (
    build_adversarial_analysis_prompt,
    build_adversarial_system_prompt,
)


class TestBuildAdversarialSystemPrompt:
    """Tests for build_adversarial_system_prompt (T180)."""

    def test_no_mock_enforcement(self):
        """T180: System prompt explicitly forbids mocks."""
        prompt = build_adversarial_system_prompt()
        assert "NEVER" in prompt
        assert "mock" in prompt.lower()
        assert "MagicMock" in prompt
        assert "monkeypatch" in prompt

    def test_requires_four_categories(self):
        """System prompt requires all four analysis categories."""
        prompt = build_adversarial_system_prompt()
        assert "uncovered_edge_cases" in prompt
        assert "false_claims" in prompt
        assert "missing_error_handling" in prompt
        assert "implicit_assumptions" in prompt

    def test_json_output_required(self):
        """System prompt requires JSON output."""
        prompt = build_adversarial_system_prompt()
        assert "JSON" in prompt

    def test_returns_string(self):
        """System prompt returns a non-empty string."""
        prompt = build_adversarial_system_prompt()
        assert isinstance(prompt, str)
        assert len(prompt) > 0

    def test_severity_levels_documented(self):
        """System prompt documents severity levels."""
        prompt = build_adversarial_system_prompt()
        assert "critical" in prompt
        assert "high" in prompt
        assert "medium" in prompt

    def test_max_test_cases_mentioned(self):
        """System prompt mentions maximum test case limit."""
        prompt = build_adversarial_system_prompt()
        assert "15" in prompt

    def test_no_markdown_code_blocks_instruction(self):
        """System prompt instructs not to wrap in markdown code blocks."""
        prompt = build_adversarial_system_prompt()
        assert "Do NOT wrap" in prompt or "code block" in prompt.lower()

    def test_assert_requirement(self):
        """System prompt requires assert statements in tests."""
        prompt = build_adversarial_system_prompt()
        assert "assert" in prompt.lower()

    def test_test_prefix_requirement(self):
        """System prompt requires test_ prefix on function names."""
        prompt = build_adversarial_system_prompt()
        assert "test_" in prompt


class TestBuildAdversarialAnalysisPrompt:
    """Tests for build_adversarial_analysis_prompt (T170)."""

    def test_prompt_contains_all_sections(self):
        """T170: Built prompt contains impl code, LLD, existing tests, patterns."""
        prompt = build_adversarial_analysis_prompt(
            implementation_code="def foo():\n    return 42",
            lld_content="## Requirements\n1. foo returns 42",
            existing_tests="def test_foo():\n    assert foo() == 42",
            adversarial_patterns=["Boundary: test empty input"],
        )

        assert "def foo():" in prompt
        assert "Requirements" in prompt
        assert "def test_foo():" in prompt
        assert "Boundary: test empty input" in prompt

    def test_empty_existing_tests(self):
        """When existing_tests is empty, note is included."""
        prompt = build_adversarial_analysis_prompt(
            implementation_code="def foo(): pass",
            lld_content="# LLD",
            existing_tests="",
            adversarial_patterns=["Boundary"],
        )

        assert "No existing tests provided" in prompt

    def test_schema_included(self):
        """Prompt includes the JSON schema."""
        prompt = build_adversarial_analysis_prompt(
            implementation_code="x",
            lld_content="y",
            existing_tests="z",
            adversarial_patterns=[],
        )

        assert "uncovered_edge_cases" in prompt
        assert "test_cases" in prompt

    def test_returns_string(self):
        """Analysis prompt returns a non-empty string."""
        prompt = build_adversarial_analysis_prompt(
            implementation_code="def foo(): pass",
            lld_content="# LLD",
            existing_tests="",
            adversarial_patterns=["Boundary"],
        )
        assert isinstance(prompt, str)
        assert len(prompt) > 0

    def test_implementation_code_section(self):
        """Prompt includes implementation code section header."""
        prompt = build_adversarial_analysis_prompt(
            implementation_code="def bar(): return 1",
            lld_content="# LLD",
            existing_tests="",
            adversarial_patterns=[],
        )
        assert "Implementation Code Under Test" in prompt
        assert "def bar(): return 1" in prompt

    def test_lld_section(self):
        """Prompt includes LLD section header."""
        prompt = build_adversarial_analysis_prompt(
            implementation_code="x",
            lld_content="## Feature Design\nSome claims here",
            existing_tests="",
            adversarial_patterns=[],
        )
        assert "Low-Level Design" in prompt or "LLD" in prompt
        assert "Some claims here" in prompt

    def test_existing_tests_section_when_provided(self):
        """Prompt includes existing test suite section when tests are provided."""
        prompt = build_adversarial_analysis_prompt(
            implementation_code="x",
            lld_content="y",
            existing_tests="def test_existing():\n    assert True",
            adversarial_patterns=[],
        )
        assert "Existing Test Suite" in prompt
        assert "def test_existing():" in prompt
        assert "No existing tests provided" not in prompt

    def test_multiple_patterns_listed(self):
        """Multiple adversarial patterns are all listed in the prompt."""
        patterns = [
            "Boundary: test empty strings",
            "Contract: verify preconditions",
            "Resource: test timeout behavior",
        ]
        prompt = build_adversarial_analysis_prompt(
            implementation_code="x",
            lld_content="y",
            existing_tests="z",
            adversarial_patterns=patterns,
        )
        for pattern in patterns:
            assert pattern in prompt

    def test_no_mock_reminder(self):
        """Prompt includes a reminder about no mocks."""
        prompt = build_adversarial_analysis_prompt(
            implementation_code="x",
            lld_content="y",
            existing_tests="z",
            adversarial_patterns=[],
        )
        assert "mock" in prompt.lower() or "NO mock" in prompt

    def test_instructions_section(self):
        """Prompt includes instructions section."""
        prompt = build_adversarial_analysis_prompt(
            implementation_code="x",
            lld_content="y",
            existing_tests="z",
            adversarial_patterns=[],
        )
        assert "Instructions" in prompt

    def test_json_only_requirement(self):
        """Prompt specifies JSON-only response requirement."""
        prompt = build_adversarial_analysis_prompt(
            implementation_code="x",
            lld_content="y",
            existing_tests="z",
            adversarial_patterns=[],
        )
        assert "JSON" in prompt

    def test_schema_has_required_fields(self):
        """Prompt schema includes all required test case fields."""
        prompt = build_adversarial_analysis_prompt(
            implementation_code="x",
            lld_content="y",
            existing_tests="z",
            adversarial_patterns=[],
        )
        assert "test_id" in prompt
        assert "target_function" in prompt
        assert "category" in prompt
        assert "test_code" in prompt
        assert "claim_challenged" in prompt
        assert "severity" in prompt

    def test_empty_patterns_list(self):
        """Empty patterns list still produces a valid prompt."""
        prompt = build_adversarial_analysis_prompt(
            implementation_code="def foo(): pass",
            lld_content="# LLD",
            existing_tests="",
            adversarial_patterns=[],
        )
        assert isinstance(prompt, str)
        assert len(prompt) > 0
        # Should still have the patterns section header
        assert "Adversarial Testing Patterns" in prompt
```
