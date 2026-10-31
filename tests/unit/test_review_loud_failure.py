"""The requirements reviewer node (N3) under standard 0034 (#3585).

Each test is named for its ledger line in
docs/audits/0908-loud-failure-sweep-ledger.md (lines at 79e18ad1). A review
that cannot reach a usable verdict returns ``error_message``, which
``route_after_review`` sends to HALT, and HALT alerts. A failed reviewer call
is reported with the provider's own cause, never as an unreadable response.
The audit_dir and the target repository's structure are settled before the
reviewer is paid for, and an APPROVED draft whose resolutions cannot be
applied stops rather than going forward without them.
"""
from __future__ import annotations

import importlib
import inspect
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from assemblyzero.core.llm_provider import LLMCallResult
from assemblyzero.workflows.requirements.graph import route_after_review

rv = importlib.import_module("assemblyzero.workflows.requirements.nodes.review")

TIERED = "## Tier 1: BLOCKING Issues\n\n- [ ] No issues found.\n\n## Tier 2: HIGH PRIORITY\n\n- [ ] Name the log file.\n"


def _verdict(verdict: str = "APPROVED", rationale: str = TIERED) -> str:
    return json.dumps({
        "verdict": verdict, "rationale": rationale,
        "feedback_items": [], "open_questions": [],
    })


def _result(response: str = "", success: bool = True, error: str | None = None):
    return LLMCallResult(
        success=success, response=response, raw_response=response,
        error_message=error, provider="fake", model_used="fake-model",
        duration_ms=1, attempts=1,
    )


class _Reviewer:
    def __init__(self, *results):
        self._results = list(results)
        self.calls = 0

    def invoke(self, *args, **kwargs):
        self.calls += 1
        return self._results.pop(0)


def _state(tmp_path: Path, **overrides) -> dict:
    root = tmp_path / "az"
    (root / "docs" / "skills").mkdir(parents=True, exist_ok=True)
    (root / "docs" / "skills" / "0702c-LLD-Review-Prompt.md").write_text(
        "Review the LLD.\n", encoding="utf-8",
    )
    target = tmp_path / "target"
    (target / "src").mkdir(parents=True, exist_ok=True)
    audit = tmp_path / "audit"
    audit.mkdir(exist_ok=True)
    state = {
        "workflow_type": "lld", "assemblyzero_root": str(root),
        "target_repo": str(target), "audit_dir": str(audit),
        "current_draft": "# 42 - Feature: A widget\n\n## 1. Context\n\nText.\n",
        "issue_number": 42, "verdict_count": 0, "error_message": "",
    }
    state.update(overrides)
    return state


def _run(state: dict, *results):
    reviewer = _Reviewer(*results)
    with patch.object(rv, "get_provider", return_value=reviewer):
        out = rv.review(state)
    return out, reviewer


def _halts(state: dict, out: dict) -> bool:
    return bool(out.get("error_message")) and route_after_review({**state, **out}) == "HALT"


class TestReviewerCalls:
    def test_101_a_failed_reviewer_call_halts_with_the_providers_cause(self, tmp_path):
        state = _state(tmp_path)

        out, reviewer = _run(state, _result(success=False, error="claude -p timed out after 900s"))

        assert _halts(state, out)
        assert "claude -p timed out after 900s" in out["error_message"]
        assert reviewer.calls == 1, "a failed call is not re-asked as if it were unreadable"

    def test_101_the_helper_raises_on_a_failed_call(self):
        reviewer = _Reviewer(_result(success=False, error="HTTP 503"))
        with pytest.raises(rv.ReviewerCallError, match="HTTP 503"):
            rv._invoke_reviewer_with_feedback_schema(reviewer, "draft", "system")

    def test_122_a_failed_re_ask_halts_with_its_cause(self, tmp_path):
        state = _state(tmp_path)

        out, reviewer = _run(
            state, _result("neither JSON nor the template"),
            _result(success=False, error="HTTP 529 overloaded"),
        )

        assert _halts(state, out)
        assert "HTTP 529 overloaded" in out["error_message"]
        assert reviewer.calls == 2


class TestVerdictContract:
    def test_306_a_revise_with_no_tier_sections_halts_naming_the_contract(self, tmp_path):
        state = _state(tmp_path)

        out, _ = _run(state, _result(_verdict("REVISE", "Needs more tests.")))

        assert _halts(state, out)
        assert "Tier" in out["error_message"]
        assert "REVISE" in out["error_message"]

    def test_306_kept_a_tiered_revise_with_no_tier1_issue_is_approved(self, tmp_path):
        state = _state(tmp_path)

        out, _ = _run(state, _result(_verdict("REVISE")))

        assert out["error_message"] == ""
        assert out["lld_status"] == "APPROVED"

    def test_306_kept_a_tier1_section_without_tier2_is_read_as_blocked(self, tmp_path):
        """It says whether anything blocks, so it is no contract break; it is
        not approved, since approving needs the whole template (#1511)."""
        state = _state(tmp_path)
        rationale = "## Tier 1: BLOCKING Issues\n\n- [ ] No issues found.\n"

        out, _ = _run(state, _result(_verdict("REVISE", rationale)))

        assert out["error_message"] == ""
        assert out["lld_status"] == "BLOCKED"

    def test_306_kept_a_tiered_revise_with_a_tier1_issue_is_blocked(self, tmp_path):
        state = _state(tmp_path)
        rationale = "## Tier 1: BLOCKING Issues\n\n- [ ] The cache has no bound.\n\n## Tier 2: HIGH\n"

        out, _ = _run(state, _result(_verdict("REVISE", rationale)))

        assert out["error_message"] == ""
        assert out["lld_status"] == "BLOCKED"


class TestPreconditions:
    @pytest.mark.parametrize("audit", ["", "missing"])
    def test_328_no_audit_dir_halts_before_the_reviewer_is_called(self, tmp_path, audit):
        state = _state(tmp_path)
        state["audit_dir"] = str(tmp_path / audit) if audit else ""

        out, reviewer = _run(state)

        assert reviewer.calls == 0
        assert _halts(state, out)
        assert "audit_dir" in out["error_message"]

    def test_438_a_target_that_cannot_be_listed_halts(self, tmp_path, monkeypatch):
        state = _state(tmp_path)
        target = Path(state["target_repo"])
        real_iterdir = Path.iterdir

        def iterdir(self):
            if self == target:
                raise PermissionError(13, "Permission denied", str(self))
            return real_iterdir(self)

        monkeypatch.setattr(Path, "iterdir", iterdir)
        out, reviewer = _run(state)

        assert reviewer.calls == 0
        assert _halts(state, out)
        assert "PermissionError" in out["error_message"]

    def test_438_a_target_that_is_not_a_directory_raises(self, tmp_path):
        with pytest.raises(NotADirectoryError, match="no-such-repo"):
            rv._build_target_repo_context(str(tmp_path / "no-such-repo"), str(tmp_path / "az"))

    def test_438_an_empty_target_is_said_to_be_empty_not_unreadable(self, tmp_path):
        target = tmp_path / "empty"
        target.mkdir()
        block = rv._build_target_repo_context(str(target), str(tmp_path / "az"))
        assert "could not be enumerated" not in block
        assert "no top-level entries" in block

    def test_438_kept_a_self_build_needs_no_block(self, tmp_path):
        assert rv._build_target_repo_context(str(tmp_path), str(tmp_path)) == ""


class TestDraftUpdate:
    def test_553_resolutions_that_cannot_be_applied_halt(self, tmp_path):
        state = _state(tmp_path)

        with patch(
            "assemblyzero.workflows.requirements.parsers.draft_updater.update_draft",
            return_value=(state["current_draft"], ["Could not find open question 2 in the draft"]),
        ):
            out, _ = _run(state, _result(_verdict("APPROVED")))

        assert _halts(state, out)
        assert "Could not find open question 2" in out["error_message"]

    def test_557_a_missing_parser_is_not_swallowed(self):
        assert "except ImportError" not in inspect.getsource(rv._update_draft_with_verdict)

    def test_560_a_parser_that_crashes_halts_naming_it(self, tmp_path):
        state = _state(tmp_path)

        with patch(
            "assemblyzero.workflows.requirements.parsers.verdict_parser.parse_verdict",
            side_effect=ValueError("no verdict section"),
        ):
            out, _ = _run(state, _result(_verdict("APPROVED")))

        assert _halts(state, out)
        assert "ValueError: no verdict section" in out["error_message"]

    def test_560_kept_a_clean_approval_goes_forward(self, tmp_path):
        state = _state(tmp_path)

        out, _ = _run(state, _result(_verdict("APPROVED")))

        assert out["error_message"] == ""
        assert out["lld_status"] == "APPROVED"
        assert Path(out["current_verdict_path"]).is_file()


def test_592_the_unused_verdict_guesser_is_gone():
    """It defaulted to BLOCKED on a verdict it could not read and nothing in
    the package called it; the parser module keeps its own."""
    assert not hasattr(rv, "_parse_verdict_status")
