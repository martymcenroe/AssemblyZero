"""Spec-stage quality gates: traceability and honest validation reporting.

Three hardening-campaign rolls died on specs whose own test code could not
pass (#1866), and the console called a spec "7/7 checks passed" when most of
those checks had nothing to check (#1870).
"""

from unittest.mock import MagicMock

from assemblyzero.workflows.implementation_spec.nodes.review_spec import (
    REVIEWER_SYSTEM_PROMPT,
)
from assemblyzero.workflows.implementation_spec.nodes.validate_completeness import (
    _log_check,
)


class TestReviewerChecksAssertionTraceability:
    """#1866: the reviewer must hunt assertions that no behaviour supports."""

    def test_prompt_demands_traceability(self):
        assert "ASSERTION TRACEABILITY" in REVIEWER_SYSTEM_PROMPT
        assert "#1866" in REVIEWER_SYSTEM_PROMPT

    def test_prompt_names_the_three_observed_failure_shapes(self):
        text = REVIEWER_SYSTEM_PROMPT.lower()
        # contradicts the spec's own behaviour text
        assert "contradicts" in text
        # asserts an unspecified side effect
        assert "side effect" in text
        # cannot hold on the platform the tests run on
        assert "sys.platform" in text

    def test_prompt_requires_blocking_not_merely_noting(self):
        assert "BLOCK" in REVIEWER_SYSTEM_PROMPT

    def test_prompt_keeps_its_original_review_dimensions(self):
        for dimension in ("Completeness", "Concreteness", "Specificity", "Feasibility"):
            assert dimension in REVIEWER_SYSTEM_PROMPT


class TestNotApplicableChecksAreNotPasses:
    """#1870: 'nothing to check' must not read as 'verified'."""

    def test_not_applicable_check_logs_as_na(self, capsys):
        _log_check({
            "check_name": "modify_files_have_excerpts",
            "passed": True,
            "details": "No Modify files in LLD — check not applicable.",
        })
        out = capsys.readouterr().out
        assert "[N/A" in out
        assert "[PASS]" not in out

    def test_real_pass_still_logs_as_pass(self, capsys):
        _log_check({
            "check_name": "data_structures_have_examples",
            "passed": True,
            "details": "All 3 data structures carry concrete examples.",
        })
        out = capsys.readouterr().out
        assert "[PASS]" in out

    def test_failure_still_logs_as_fail(self, capsys):
        _log_check({
            "check_name": "functions_have_io_examples",
            "passed": False,
            "details": "2 functions lack input/output examples.",
        })
        out = capsys.readouterr().out
        assert "[FAIL]" in out


class TestBlockedVerdictSaysWhy:
    """#1889: the gate's finding must survive into the run record."""

    def _state(self, tmp_path):
        return {
            "spec_draft": "# Spec\n" + ("x" * 200),
            "lld_content": "# LLD",
            "audit_dir": str(tmp_path / "audit"),
            "issue_number": 41,
            "cost_budget_usd": 0.0,
        }

    def _spec_result(self, verdict, rationale="", items=None):
        return {
            "verdict": verdict,
            "rationale": rationale,
            "feedback_items": items or [],
            "source": "structured",
        }

    def _run(self, tmp_path, spec_result):
        from unittest.mock import patch

        from assemblyzero.workflows.implementation_spec.nodes.review_spec import (
            review_spec,
        )

        base = "assemblyzero.workflows.implementation_spec.nodes.review_spec"
        with patch(f"{base}.get_provider", return_value=MagicMock()), patch(
            f"{base}._invoke_reviewer_with_spec_schema",
            return_value=(spec_result, ""),
        ):
            return review_spec(self._state(tmp_path))

    def test_blocked_carries_its_reason_into_error_message(self, tmp_path):
        result = self._run(
            tmp_path,
            self._spec_result(
                "BLOCKED", rationale="Assertion T080 contradicts section 5.2."
            ),
        )
        assert result["review_verdict"] == "BLOCKED"
        assert "BLOCKED" in result["error_message"]
        assert "T080" in result["error_message"]

    def test_approved_leaves_error_message_empty(self, tmp_path):
        result = self._run(tmp_path, self._spec_result("APPROVED", rationale="fine"))
        assert result["error_message"] == ""

    def test_revise_leaves_error_message_empty(self, tmp_path):
        """REVISE must keep routing to another revision, not halt."""
        result = self._run(tmp_path, self._spec_result("REVISE", rationale="tighten"))
        assert result["error_message"] == ""

    def test_blocked_prints_the_feedback(self, tmp_path, capsys):
        self._run(
            tmp_path,
            self._spec_result("BLOCKED", rationale="Unwinnable assertion in T080."),
        )
        assert "Unwinnable assertion" in capsys.readouterr().out

    def test_verdict_persists_even_when_audit_dir_is_absent(self, tmp_path):
        """The run that exposed this wrote no verdict file at all."""
        audit = tmp_path / "audit"
        assert not audit.exists()
        self._run(tmp_path, self._spec_result("BLOCKED", rationale="because"))
        written = list(audit.glob("*readiness-verdict.md"))
        assert written, "a blocked verdict must leave a record"
        assert "because" in written[0].read_text(encoding="utf-8")
