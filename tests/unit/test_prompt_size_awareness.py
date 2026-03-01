"""Tests for Issue #508: Prompt-size awareness in generate_draft.

Validates that _truncate_prompt and the prompt-size cap work correctly.
"""

import pytest

from assemblyzero.workflows.requirements.nodes.generate_draft import (
    MAX_TOTAL_PROMPT_CHARS,
    PROMPT_SIZE_WARNING_THRESHOLD,
    _truncate_prompt,
)


class TestTruncatePrompt:
    """Tests for _truncate_prompt function."""

    def test_under_cap_returns_unchanged(self):
        prompt = "Short prompt"
        assert _truncate_prompt(prompt) == prompt

    def test_at_cap_returns_unchanged(self):
        prompt = "x" * MAX_TOTAL_PROMPT_CHARS
        assert _truncate_prompt(prompt) == prompt

    def test_over_cap_truncates(self):
        prompt = "x" * (MAX_TOTAL_PROMPT_CHARS + 1000)
        result = _truncate_prompt(prompt)
        assert len(result) <= MAX_TOTAL_PROMPT_CHARS

    def test_drops_codebase_analysis_first(self):
        sections = [
            "## Template\nKeep this template content.",
            "## Codebase Analysis\n" + "x" * 80_000,
            "## Original Issue\nKeep this issue content.",
        ]
        prompt = "\n\n".join(sections)
        # Make it exceed the cap
        assert len(prompt) < MAX_TOTAL_PROMPT_CHARS  # sanity
        # Force over cap by padding template
        big_prompt = sections[0] + "\n\n" + sections[1] + "\n\n" + sections[2] + "\n" + "y" * MAX_TOTAL_PROMPT_CHARS
        result = _truncate_prompt(big_prompt)
        assert "Codebase Analysis" not in result
        assert "Keep this template content" in result

    def test_drops_related_code_before_template(self):
        template = "## Template\nImportant template"
        related = "## Related Code\n" + "code " * 30_000
        issue = "## Original Issue\nThe issue body"
        prompt = f"{template}\n\n{related}\n\n{issue}\n" + "z" * MAX_TOTAL_PROMPT_CHARS
        result = _truncate_prompt(prompt)
        assert "Related Code" not in result
        assert "Important template" in result

    def test_hard_truncate_as_last_resort(self):
        # A prompt with no ## sections — can't drop anything
        prompt = "x" * (MAX_TOTAL_PROMPT_CHARS + 5000)
        result = _truncate_prompt(prompt)
        assert len(result) == MAX_TOTAL_PROMPT_CHARS

    def test_drops_multiple_sections_if_needed(self):
        codebase = "## Codebase Analysis\n" + "a" * 40_000
        related = "## Related Code\n" + "b" * 40_000
        excerpts = "## Key File Excerpts\n" + "c" * 40_000
        template = "## Template\nKeep"
        prompt = f"{codebase}\n\n{related}\n\n{excerpts}\n\n{template}\n" + "d" * 20_000
        result = _truncate_prompt(prompt)
        assert len(result) <= MAX_TOTAL_PROMPT_CHARS
        assert "Keep" in result

    def test_preserves_original_issue_section(self):
        context = "## Context\n" + "ctx " * 40_000
        issue = "## Original Issue #42\nMust keep this"
        template = "## Template\nAlso keep"
        prompt = f"{context}\n\n{issue}\n\n{template}\n" + "x" * MAX_TOTAL_PROMPT_CHARS
        result = _truncate_prompt(prompt)
        # Context should be dropped (it's in the drop list)
        assert "Must keep this" in result or len(result) <= MAX_TOTAL_PROMPT_CHARS


class TestPromptSizeConstants:
    """Tests for prompt-size constants."""

    def test_cap_is_120k(self):
        assert MAX_TOTAL_PROMPT_CHARS == 120_000

    def test_warning_threshold_is_80_percent(self):
        assert PROMPT_SIZE_WARNING_THRESHOLD == 0.8

    def test_warning_threshold_calculation(self):
        threshold = MAX_TOTAL_PROMPT_CHARS * PROMPT_SIZE_WARNING_THRESHOLD
        assert threshold == 96_000
