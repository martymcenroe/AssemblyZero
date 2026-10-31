"""N5 review_spec under standard 0034 (#3585).

Each test is named for its ledger line in
docs/audits/0908-loud-failure-sweep-ledger.md. Every failure returns an
``error_message`` that ``route_after_review`` sends to HALT, which alerts; a
failure that can be seen before the reviewer is called halts before the call
is paid for. A must-resolve filing that fails alerts the operator itself,
because the halt it rides on does not name it.
"""
from __future__ import annotations

import importlib
import inspect
import json
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from assemblyzero.core.verdict_schema import StructuredContractError
from assemblyzero.workflows.implementation_spec.graph import route_after_review

# `nodes/__init__` re-exports the FUNCTION review_spec, which shadows the
# module of the same name, so the module is imported by its dotted path.
rs = importlib.import_module("assemblyzero.workflows.implementation_spec.nodes.review_spec")

SPEC = "# Implementation Spec\n\n" + "A line of the spec under review.\n" * 10
APPROVED = json.dumps({"verdict": "APPROVED", "rationale": "Ready", "feedback_items": []})


def _reviewer(response: str = APPROVED, success: bool = True, error: str | None = None):
    reviewer = Mock()
    reviewer.invoke.return_value = Mock(success=success, response=response, error_message=error)
    return reviewer


def _state(tmp_path: Path, **extra) -> dict:
    audit = tmp_path / "lineage"
    audit.mkdir(exist_ok=True)
    state = {
        "spec_draft": SPEC,
        "lld_content": "# LLD\n\nthe design\n",
        "issue_number": 42,
        "audit_dir": str(audit),
        "review_iteration": 0,
        "max_iterations": 3,
        "cost_budget_usd": 0.0,
    }
    state.update(extra)
    return state


def _run(state: dict, reviewer: Mock | None = None):
    reviewer = reviewer or _reviewer()
    with patch.object(rs, "get_provider", return_value=reviewer):
        return rs.review_spec(state), reviewer


def _halts(result: dict, *needles: str) -> None:
    message = result["error_message"]
    assert message, "the node must return an error_message"
    assert route_after_review(result) == "HALT"
    for needle in needles:
        assert needle in message, f"{needle!r} not in {message!r}"


class TestTheNodeHalts:
    def test_170_a_failed_reviewer_call_halts(self, tmp_path):
        """Compliant, pinned: (None, error) reaches the node's halt."""
        result, _ = _run(_state(tmp_path), _reviewer(success=False, error="agy timed out"))
        _halts(result, "Spec review LLM call failed", "agy timed out")

    def test_173_an_empty_reviewer_response_halts(self, tmp_path):
        """Compliant, pinned."""
        result, _ = _run(_state(tmp_path), _reviewer(response="   "))
        _halts(result, "empty response")

    def test_203_no_fail_open_tag_remains(self):
        assert "fail-open" not in inspect.getsource(rs)

    def test_329_an_empty_draft_halts_without_a_call(self, tmp_path):
        """Compliant, pinned."""
        result, reviewer = _run(_state(tmp_path, spec_draft=""))
        _halts(result, "Spec draft is empty")
        reviewer.invoke.assert_not_called()

    def test_334_a_draft_under_the_minimum_halts_without_a_call(self, tmp_path):
        result, reviewer = _run(_state(tmp_path, spec_draft="# Spec\n\nshort"))
        _halts(result, "[N5]", "#42", f"{len('# Spec' + chr(10) * 2 + 'short')} chars")
        reviewer.invoke.assert_not_called()

    def test_338_a_draft_over_the_review_limit_halts_without_a_call(self, tmp_path):
        """It used to be cut at the limit, and an APPROVED verdict on the
        part then stood for the whole."""
        big = "# Spec\n\n" + "x" * (rs.MAX_SPEC_SIZE + 10)
        result, reviewer = _run(_state(tmp_path, spec_draft=big))
        _halts(result, "[N5]", "#42", f"{rs.MAX_SPEC_SIZE:,}")
        reviewer.invoke.assert_not_called()

    def test_403_a_verdict_nobody_can_read_halts(self, tmp_path):
        """Compliant, pinned."""
        unknown = {"verdict": "UNKNOWN", "rationale": "", "feedback_items": []}
        with patch.object(rs, "_invoke_reviewer_with_spec_schema", return_value=(unknown, "")):
            result, _ = _run(_state(tmp_path))
        _halts(result, "no extractable verdict")

    def test_432_a_verdict_that_cannot_be_saved_halts(self, tmp_path):
        with patch.object(rs, "save_audit_file", side_effect=PermissionError(13, "denied")):
            result, _ = _run(_state(tmp_path))
        _halts(result, "[N5]", "#42", "PermissionError")

    def test_432_no_audit_dir_halts_without_a_call(self, tmp_path):
        result, reviewer = _run(_state(tmp_path, audit_dir=""))
        _halts(result, "[N5]", "audit directory")
        reviewer.invoke.assert_not_called()

    def test_432_a_missing_audit_dir_is_still_created(self, tmp_path):
        """Kept (#1889): a set but absent directory is made, not refused."""
        result, _ = _run(_state(tmp_path, audit_dir=str(tmp_path / "new" / "lineage")))
        assert result["error_message"] == ""
        assert list((tmp_path / "new" / "lineage").glob("*readiness-verdict.md"))

    def test_the_halt_is_loud_on_stderr(self, tmp_path, capsys):
        _run(_state(tmp_path, spec_draft="# Spec\n\nshort"))
        assert "ERROR" in capsys.readouterr().err

    def test_an_approved_review_passes(self, tmp_path):
        result, _ = _run(_state(tmp_path))
        assert result["error_message"] == ""
        assert result["review_verdict"] == "APPROVED"


class TestTheReviewInput:
    def test_641_a_long_lld_is_sent_whole(self, tmp_path):
        """FIXED differently: the LLD is no longer cut at 50,000 chars, so
        the reviewer never judges traceability against part of it. LLDs on
        disk here run to 58,000 chars, so a halt would stop real runs."""
        lld = "# LLD\n\n" + "a requirement line\n" * 4000 + "THE LAST REQUIREMENT\n"
        assert len(lld) > 50_000
        content = rs._build_review_content(
            spec_draft=SPEC, lld_content=lld, issue_number=42, review_iteration=0,
        )
        assert "THE LAST REQUIREMENT" in content
        assert "truncated" not in content.lower()

    def test_641_the_node_reviews_a_long_lld_whole(self, tmp_path):
        lld = "# LLD\n\n" + "a requirement line\n" * 4000 + "THE LAST REQUIREMENT\n"
        result, reviewer = _run(_state(tmp_path, lld_content=lld))
        assert result["error_message"] == ""
        sent = reviewer.invoke.call_args.args[1]
        assert "THE LAST REQUIREMENT" in sent


class TestVerdictParsing:
    def test_771_an_empty_response_raises(self):
        """It used to make up a BLOCKED verdict the reviewer never issued."""
        with pytest.raises(StructuredContractError, match="empty"):
            rs.parse_review_verdict("")

    def test_771_a_blank_response_raises(self):
        with pytest.raises(StructuredContractError):
            rs.parse_review_verdict("  \n ")


class TestConflictFiling:
    RATIONALE = "REQUIREMENTS CONFLICT: 'A' says one thing; 'B' says another."

    def test_558_a_failed_filing_alerts_the_operator(self, tmp_path, operator_alerts):
        def boom(*args, **kwargs):
            raise RuntimeError("gh exploded")

        with patch("assemblyzero.speedrun.must_resolve.file_must_resolve", boom), patch(
            "assemblyzero.speedrun.must_resolve.conflict_from_rationale",
            return_value=MagicMock(),
        ):
            rs._file_conflict_if_any({"repo_root": str(tmp_path), "issue_number": 42}, self.RATIONALE)

        assert len(operator_alerts) == 1
        alert = operator_alerts[0]
        assert "must-resolve" in alert["what"] and "#42" in alert["what"]
        assert "RuntimeError: gh exploded" == alert["cause"]
        assert "halts" in alert["consequence"]

    def test_an_ordinary_blocked_verdict_files_nothing_and_alerts_nothing(
        self, tmp_path, operator_alerts,
    ):
        rs._file_conflict_if_any({"repo_root": str(tmp_path), "issue_number": 42}, "plain")
        assert operator_alerts == []
