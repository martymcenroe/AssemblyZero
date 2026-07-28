"""Spec-stage quality gates: traceability and honest validation reporting.

Three hardening-campaign rolls died on specs whose own test code could not
pass (#1866), and the console called a spec "7/7 checks passed" when most of
those checks had nothing to check (#1870).
"""

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
