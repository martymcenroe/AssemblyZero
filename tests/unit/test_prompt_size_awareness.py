"""Tests for Issue #508: Prompt-size awareness in generate_draft.

#3585 retired the truncator these tests used to pin. It dropped whole prompt
sections (the codebase context, then the repository structure) and then
hard-truncated the rest, so the drafter wrote a design from a prompt nobody
had decided to send. A prompt over the cap now halts before the drafter is
called; a prompt within it is sent whole.
"""

import importlib
from unittest.mock import patch

import pytest

from assemblyzero.core.llm_provider import LLMCallResult
from assemblyzero.workflows.requirements.nodes.generate_draft import (
    MAX_TOTAL_PROMPT_CHARS,
    PROMPT_SIZE_WARNING_THRESHOLD,
)
from assemblyzero.workflows.requirements.state import create_initial_state

gd = importlib.import_module("assemblyzero.workflows.requirements.nodes.generate_draft")


class _Drafter:
    def __init__(self):
        self.calls: list[dict] = []

    def invoke(self, **kwargs):
        self.calls.append(kwargs)
        return LLMCallResult(
            success=True, response="# Draft\n", raw_response="# Draft\n",
            error_message=None, provider="fake", model_used="fake",
            duration_ms=1, attempts=1,
        )


def _run(tmp_path, prompt: str):
    templates = tmp_path / "docs" / "templates"
    templates.mkdir(parents=True, exist_ok=True)
    (templates / "0101-issue-template.md").write_text("# Template\n", encoding="utf-8")
    audit = tmp_path / "audit"
    audit.mkdir(exist_ok=True)
    state = dict(create_initial_state(
        workflow_type="issue", assemblyzero_root=str(tmp_path),
        target_repo=str(tmp_path), brief_file="brief.md",
    ))
    state.update(brief_content="# Brief", audit_dir=str(audit))
    drafter = _Drafter()
    with patch.object(gd, "get_provider", return_value=drafter), \
         patch.object(gd, "_build_prompt", return_value=prompt):
        out = gd.generate_draft(state)
    return out, drafter


class TestTheCapHaltsAndNothingIsCut:
    def test_the_truncator_is_gone(self):
        assert not hasattr(gd, "_truncate_prompt")

    @pytest.mark.parametrize("prompt", ["Short prompt", "x" * MAX_TOTAL_PROMPT_CHARS])
    def test_a_prompt_within_the_cap_is_sent_whole(self, tmp_path, prompt):
        out, drafter = _run(tmp_path, prompt)

        assert out["error_message"] == ""
        assert drafter.calls[0]["content"] == prompt

    @pytest.mark.parametrize("prompt", [
        "x" * (MAX_TOTAL_PROMPT_CHARS + 1000),
        "## Template\nKeep.\n\n## Codebase Analysis\n" + "x" * MAX_TOTAL_PROMPT_CHARS,
    ])
    def test_a_prompt_over_the_cap_halts_and_nothing_is_sent(self, tmp_path, prompt):
        out, drafter = _run(tmp_path, prompt)

        assert drafter.calls == []
        assert f"{len(prompt):,}" in out["error_message"]
        assert f"{MAX_TOTAL_PROMPT_CHARS:,}-char cap" in out["error_message"]


class TestPromptSizeConstants:
    """Tests for prompt-size constants."""

    def test_cap_is_120k(self):
        assert MAX_TOTAL_PROMPT_CHARS == 120_000

    def test_warning_threshold_is_80_percent(self):
        assert PROMPT_SIZE_WARNING_THRESHOLD == 0.8

    def test_warning_threshold_calculation(self):
        threshold = MAX_TOTAL_PROMPT_CHARS * PROMPT_SIZE_WARNING_THRESHOLD
        assert threshold == 96_000
