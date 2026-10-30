"""N2 generate_spec under standard 0034 (#3585).

Each test is named for its ledger line in
docs/audits/0908-loud-failure-sweep-ledger.md. Every failure here returns an
``error_message`` naming the node and the issue, which
``route_after_generate_spec`` sends to HALT, and HALT alerts. A failure that
can be seen before the drafter is called halts before the call is paid for.
"""
from __future__ import annotations

import importlib
import inspect
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from assemblyzero.workflows.implementation_spec.graph import route_after_generate_spec

# `nodes/__init__` re-exports the FUNCTION generate_spec, which shadows the
# module of the same name, so the module is imported by its dotted path.
gs = importlib.import_module(
    "assemblyzero.workflows.implementation_spec.nodes.generate_spec"
)

PREVIOUS = "# Spec\n\n## Section 10: Tests\n\n```python\ndef test_one():\n    assert f() == 1\n```\n"
REVISED = "# Spec\n\n## Section 10: Tests\n\n```python\ndef test_one():\n    assert f() == 2\n```\n"
DRAFT = "# Implementation Spec\n\n" + "A line of the spec.\n" * 20


def _drafter(response: str = DRAFT, success: bool = True) -> Mock:
    drafter = Mock()
    drafter.invoke.return_value = Mock(
        success=success, response=response, error_message=None,
        input_tokens=0, output_tokens=0,
    )
    return drafter


def _state(tmp_path: Path, **extra) -> dict:
    lineage = tmp_path / "lineage"
    lineage.mkdir(exist_ok=True)
    state = {
        "config_mock_mode": True,
        "lld_content": "# LLD\n\ncontent\n",
        "current_state_snapshots": {},
        "pattern_references": [],
        "assemblyzero_root": "",
        "repo_root": "",
        "issue_number": 42,
        "audit_dir": str(lineage),
        "review_iteration": 0,
    }
    state.update(extra)
    return state


def _run(state: dict, drafter: Mock | None = None, template: str | None = "# Template"):
    drafter = drafter or _drafter()
    patches = [patch.object(gs, "get_provider", return_value=drafter)]
    if template is not None:
        patches.append(patch.object(gs, "load_template", return_value=template))
    for p in patches:
        p.start()
    try:
        return gs.generate_spec(state), drafter
    finally:
        for p in patches:
            p.stop()


def _halts(result: dict, *needles: str) -> None:
    message = result["error_message"]
    assert message, "the node must return an error_message"
    assert route_after_generate_spec(result) == "HALT"
    assert "[N2]" in message and "#42" in message
    for needle in needles:
        assert needle in message, f"{needle!r} not in {message!r}"


class TestTheNodeHalts:
    def test_328_a_missing_template_halts_naming_the_issue_and_path(self, tmp_path):
        result, drafter = _run(_state(tmp_path, assemblyzero_root=str(tmp_path)), template=None)
        _halts(result, "0701-implementation-spec-template.md", "FileNotFoundError")
        drafter.invoke.assert_not_called()

    def test_397_no_fail_open_tag_remains(self):
        assert "fail-open" not in inspect.getsource(gs)

    def test_616_an_empty_drafter_response_halts(self, tmp_path):
        result, _ = _run(_state(tmp_path), drafter=_drafter(response=""))
        _halts(result, "empty")

    def test_616_a_response_that_is_only_whitespace_halts(self, tmp_path):
        result, _ = _run(_state(tmp_path), drafter=_drafter(response="  \n\n "))
        _halts(result, "empty")

    def test_662_a_missing_audit_dir_halts_before_the_drafter_is_called(self, tmp_path):
        result, drafter = _run(_state(tmp_path, audit_dir=str(tmp_path / "gone")))
        _halts(result, "gone")
        drafter.invoke.assert_not_called()

    def test_662_no_audit_dir_in_state_halts(self, tmp_path):
        result, drafter = _run(_state(tmp_path, audit_dir=""))
        _halts(result, "audit directory")
        drafter.invoke.assert_not_called()

    def test_662_a_draft_that_cannot_be_saved_halts(self, tmp_path):
        with patch.object(gs, "save_audit_file", side_effect=PermissionError(13, "denied")):
            result, _ = _run(_state(tmp_path))
        _halts(result, "PermissionError")

    def test_747_a_verdict_pinning_cannot_read_halts_before_the_drafter_is_called(
        self, tmp_path,
    ):
        """It used to pass the revision unenforced with a stdout note."""
        result, drafter = _run(_state(
            tmp_path, spec_draft=PREVIOUS, review_feedback="Please make it better overall.",
        ), drafter=_drafter(response=REVISED))
        _halts(result, "pinning")
        drafter.invoke.assert_not_called()

    def test_747_apply_pinning_itself_raises_on_an_unreadable_verdict(self, tmp_path):
        with pytest.raises(gs.PinningCannotRunError):
            gs._apply_pinning(
                {}, PREVIOUS, REVISED, response="",
                review_feedback="Please make it better overall.", completeness_issues=[],
            )

    def test_a_verdict_that_names_a_test_still_revises(self, tmp_path):
        """Kept: a readable verdict is pinned and the revision lands."""
        result, _ = _run(_state(
            tmp_path, spec_draft=PREVIOUS,
            review_feedback="REVISE: `test_one` asserts the wrong value.",
        ), drafter=_drafter(response=REVISED))
        assert result["error_message"] == ""
        assert "== 2" in result["spec_draft"]

    def test_a_clean_draft_is_saved_to_lineage(self, tmp_path):
        result, _ = _run(_state(tmp_path))
        assert result["error_message"] == ""
        assert Path(result["spec_draft_path"]).is_file()


class TestCompliantRows:
    """Compliant, pinned: each already returned an error_message routed to
    HALT. 582 is pinned by test_spec_edit_script.py's
    test_exhausted_attempts_halt_naming_the_blocks, and 602 by
    test_implementation_spec_workflow.py's test_handles_drafter_failure."""

    def test_410_a_failed_preflight_halts(self, tmp_path):
        failed = Mock(passed=False, warnings=["agy did not answer"])
        with patch("assemblyzero.core.preflight.preflight_for_specs", return_value=failed):
            result, drafter = _run(_state(
                tmp_path, config_mock_mode=False, config_drafter="gemini:3.1-pro",
            ))
        assert "[PREFLIGHT] Gemini unavailable: agy did not answer" == result["error_message"]
        assert route_after_generate_spec(result) == "HALT"
        drafter.invoke.assert_not_called()

    def test_425_a_drafter_that_cannot_be_built_halts(self, tmp_path):
        with patch.object(gs, "get_provider", side_effect=ValueError("unknown provider")):
            result = gs.generate_spec(_state(tmp_path))
        assert result["error_message"] == "Invalid drafter: unknown provider"
        assert route_after_generate_spec(result) == "HALT"

    def test_610_a_spend_over_the_budget_halts(self, tmp_path):
        with patch.object(gs, "get_cumulative_cost", return_value=5.0):
            result, _ = _run(_state(tmp_path, cost_budget_usd=1.0))
        assert result["error_message"].startswith("[BUDGET]")
        assert route_after_generate_spec(result) == "HALT"


class TestThePromptBudget:
    MANIFEST = "| row | expects |\n|---|---|\n| N4.2 | the binding value |\n"

    def test_1416_the_binding_manifest_is_never_dropped(self):
        prompt = gs.build_drafter_prompt(
            lld_content="# LLD\n\nshort",
            current_state={},
            patterns=[],
            template="",
            issue_number=42,
            project_context="## Project Context\n\n" + "context padding line\n" * 7000,
            assertion_manifest=self.MANIFEST,
        )
        assert len(prompt) <= gs.MAX_TOTAL_PROMPT_CHARS
        assert "the binding value" in prompt
        assert "context padding line" not in prompt

    def test_1416_the_lld_body_is_never_dropped(self):
        """The LLD's own ## sections used to read as unknown sections and
        were dropped first."""
        lld = "# LLD\n\n## 1. Context\n\nwhy\n\n## 2. Proposed Changes\n\nthe change that matters\n"
        prompt = gs.build_drafter_prompt(
            lld_content=lld,
            current_state={},
            patterns=[],
            template="",
            issue_number=42,
            project_context="## Project Context\n\n" + "context padding line\n" * 7000,
        )
        assert "the change that matters" in prompt
        assert len(prompt) <= gs.MAX_TOTAL_PROMPT_CHARS

    def test_1416_the_draft_and_its_complaints_survive_a_revision_trim(self):
        """No reviewer feedback, so the full revision prompt is built. The
        draft's own ## sections used to be dropped first."""
        prompt = gs.build_drafter_prompt(
            lld_content="# LLD\n\nshort",
            # Each excerpt is capped at MAX_SNAPSHOT_CHARS, so thirteen files.
            current_state={f"f{i}.py": "x = 1\n" * 2000 for i in range(13)},
            patterns=[],
            template="",
            issue_number=42,
            existing_draft="# Spec\n\n## 3. Tests\n\nthe draft body\n",
            completeness_issues=["a completeness complaint"],
        )
        assert "the draft body" in prompt
        assert "a completeness complaint" in prompt
        assert "x = 1" not in prompt
        assert len(prompt) <= gs.MAX_TOTAL_PROMPT_CHARS

    def test_1436_required_parts_over_the_budget_raise(self):
        with pytest.raises(gs.PromptBudgetError) as caught:
            gs.build_drafter_prompt(
                lld_content="# LLD\n\n" + "an LLD line\n" * 12000,
                current_state={},
                patterns=[],
                template="",
                issue_number=42,
            )
        assert "over" in str(caught.value)

    def test_1436_the_node_halts_on_a_prompt_over_budget(self, tmp_path):
        result, drafter = _run(_state(
            tmp_path, lld_content="# LLD\n\n" + "an LLD line\n" * 12000,
        ))
        _halts(result, "budget")
        drafter.invoke.assert_not_called()

    def test_a_prompt_under_the_budget_is_unchanged(self):
        prompt = gs.build_drafter_prompt(
            lld_content="# LLD\n\nshort", current_state={}, patterns=[],
            template="", issue_number=42,
        )
        assert "CONTEXT TRIMMED" not in prompt
        assert "short" in prompt
