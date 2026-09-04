"""The spec-stage pair: escalation routing (#2331) and error paths (#2333).

Two defects with one shape. A spec that cannot produce a usable suite was
degrading quietly instead of stopping, and a spec that could not clear the
coverage gate was reporting a number that read as though it would.

`tests/fixtures/issue7_run153937/spec-0007.md` is the real artifact behind
both. Its twenty-three tests all pass, its requirement coverage was reported
as 100 percent, and it measured 80 percent statements against the
implementation the pipeline produced from it.
"""
from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]

from assemblyzero.workflows.implementation_spec.error_path_coverage import (  # noqa: E402
    error_path_coverage,
    format_report,
    split_fences,
)
from assemblyzero.workflows.implementation_spec.nodes.validate_completeness import (  # noqa: E402
    check_error_paths_have_tests,
)
from assemblyzero.workflows.testing.graph import route_after_validate  # noqa: E402
from assemblyzero.workflows.testing.nodes.validate_tests_mechanical import (  # noqa: E402
    DETERMINISTIC_FAILURE,
    MAX_SCAFFOLD_ATTEMPTS,
    exhausted_reason,
    should_regenerate,
    validate_tests_mechanical_node,
)

SPEC_0007 = ROOT / "tests" / "fixtures" / "issue7_run153937" / "spec-0007.md"

HOLLOW = '''
import pytest

def test_a():
    assert False, "TDD RED: not implemented"

def test_b():
    assert False, "TDD RED: not implemented"
'''

SPEC_WITH_BODIES = {
    "imports": "",
    "functions": [{"name": "test_a", "source": "def test_a():\n    assert 1"}],
}


@pytest.fixture(scope="module")
def spec_0007() -> str:
    return SPEC_0007.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# #2331: escalation is a named halt, not a quieter route to implementation
# ---------------------------------------------------------------------------


class TestEscalationHalts:
    def test_an_exhausted_scaffold_no_longer_reaches_implementation(self):
        """The defect itself. This used to return N4_implement_code."""
        state = {
            "validation_result": {"is_valid": False},
            "scaffold_attempts": MAX_SCAFFOLD_ATTEMPTS,
            "generated_tests": HOLLOW,
        }
        assert should_regenerate(state) == "escalate"
        assert route_after_validate(state) == "end"

    def test_a_valid_suite_still_goes_to_the_red_phase(self):
        state = {"validation_result": {"is_valid": True}, "scaffold_attempts": 0}
        assert route_after_validate(state) == "N3_verify_red"

    def test_attempts_remaining_still_regenerate(self):
        state = {
            "validation_result": {"is_valid": False},
            "scaffold_attempts": 1,
            "generated_tests": HOLLOW,
        }
        assert should_regenerate(state) == "regenerate"
        assert route_after_validate(state) == "N2_scaffold_tests"

    def test_the_halt_is_named_and_marked_deterministic(self):
        """An unnamed halt is the silent degradation wearing a different hat.

        The token is what keeps the orchestrator from retrying it. A
        deterministic scaffolder reproducing its own output will reproduce it
        again, and #2337 paid three attempts in twelve seconds to learn that.
        """
        state = {
            "generated_tests": HOLLOW,
            "parsed_scenarios": {"scenarios": []},
            "scaffold_attempts": MAX_SCAFFOLD_ATTEMPTS,
            "spec_test_suite": SPEC_WITH_BODIES,
        }
        result = validate_tests_mechanical_node(state)

        assert DETERMINISTIC_FAILURE in result["error_message"]
        assert "wrong side" in result["error_message"]
        assert result["next_node"] == "end"

    def test_a_stagnant_scaffold_halts_before_the_attempt_limit(self):
        import hashlib

        previous = hashlib.sha256(HOLLOW.encode()).hexdigest()
        state = {
            "generated_tests": HOLLOW,
            "parsed_scenarios": {"scenarios": []},
            "scaffold_attempts": 0,
            "previous_scaffold_hash": previous,
            "spec_test_suite": SPEC_WITH_BODIES,
        }
        result = validate_tests_mechanical_node(state)

        assert DETERMINISTIC_FAILURE in result["error_message"]
        assert "byte for byte" in result["error_message"]

    def test_a_valid_suite_is_never_halted_for_being_invalid(self):
        """Renamed and narrowed by #2767 (operator ruling 2026-09-04).

        This asserted that a valid suite is never halted, full stop, with
        `scaffold_attempts` already at the cap. That invariant is what the
        ruling overturned: the scaffold budget now counts every regeneration,
        because a budget that counts only failures is not a budget, and a
        suite arriving after the allowance is spent stops the loop.

        What is still true, and is what this now pins: a valid suite is never
        halted for failing validation, and one that arrives with budget
        remaining proceeds. The regression that would matter -- a run whose
        third scaffold finally validates being killed at the moment it
        succeeded -- is pinned by the test below.
        """
        real = "import pytest\n\ndef test_a():\n    assert 1 == 1\n"
        state = {
            "generated_tests": real,
            "parsed_scenarios": {"scenarios": []},
            "scaffold_attempts": 0,
        }
        result = validate_tests_mechanical_node(state)
        assert "error_message" not in result
        assert result["scaffold_route"] == "continue"

    def test_the_scaffold_that_finally_validates_is_allowed_through(self):
        """The no-regression case for #2767, and the reason the valid path's
        threshold is `>` rather than `>=`.

        Two scaffolds failed validation; the third passed. That run produced
        exactly what was asked for, and the retry budget exists to allow the
        retry that got there.
        """
        real = "import pytest\n\ndef test_a():\n    assert 1 == 1\n"
        state = {
            "generated_tests": real,
            "parsed_scenarios": {"scenarios": []},
            "scaffold_attempts": MAX_SCAFFOLD_ATTEMPTS - 1,
        }
        result = validate_tests_mechanical_node(state)

        assert result["scaffold_attempts"] == MAX_SCAFFOLD_ATTEMPTS
        assert "error_message" not in result, (
            "the third scaffold validated and was halted anyway"
        )
        assert result["scaffold_route"] == "continue"

    def test_a_valid_suite_past_the_cap_stops_the_loop(self):
        """#2767's other half: once the allowance is spent, a suite that
        validates and still cannot be used ends the run on the budget."""
        real = "import pytest\n\ndef test_a():\n    assert 1 == 1\n"
        state = {
            "generated_tests": real,
            "parsed_scenarios": {"scenarios": []},
            "scaffold_attempts": MAX_SCAFFOLD_ATTEMPTS,
        }
        result = validate_tests_mechanical_node(state)

        assert result["scaffold_route"] == "escalate"
        assert "scaffold budget is spent" in result["error_message"]
        assert "cannot be validated" not in result["error_message"], (
            "the halt says a suite that validated could not be validated"
        )

    def test_one_condition_serves_both_callers(self):
        """The route and the halt message must never disagree.

        They are computed from `exhausted_reason` for that reason: a route
        that ends a run whose state records no failure is exactly the silent
        degradation #2331 is about.
        """
        state = {"scaffold_attempts": MAX_SCAFFOLD_ATTEMPTS}
        assert exhausted_reason(state, HOLLOW, MAX_SCAFFOLD_ATTEMPTS)
        assert exhausted_reason(state, HOLLOW, 0) == ""

    def test_the_hash_is_compared_before_it_is_overwritten(self):
        """Order matters: the node stores this attempt's hash on the way out.

        Naming the halt after that store would compare the attempt against
        itself, which always matches, and every failed first attempt would
        halt as stagnant.
        """
        state = {
            "generated_tests": HOLLOW,
            "parsed_scenarios": {"scenarios": []},
            "scaffold_attempts": 0,
            "spec_test_suite": SPEC_WITH_BODIES,
        }
        result = validate_tests_mechanical_node(state)

        assert "error_message" not in result
        assert result["previous_scaffold_hash"]


class TestThreeEightySixSurvives:
    """The reason #2317's gating was reconsidered and kept.

    A scaffold of nothing but `assert False, "TDD RED: ..."` is what the
    scaffolder is supposed to emit before any implementation exists. #386
    closed the reject-and-regenerate loop that rejecting it created, and a
    blanket "hollow is invalid" rule reopens that loop exactly.
    """

    def test_a_hollow_suite_with_no_spec_bodies_stays_valid(self):
        state = {
            "generated_tests": HOLLOW,
            "parsed_scenarios": {"scenarios": []},
            "scaffold_attempts": 0,
        }
        result = validate_tests_mechanical_node(state)
        assert result["validation_result"]["is_valid"] is True

    def test_a_hollow_suite_the_spec_could_fix_is_rejected(self):
        state = {
            "generated_tests": HOLLOW,
            "parsed_scenarios": {"scenarios": []},
            "scaffold_attempts": 0,
            "spec_test_suite": SPEC_WITH_BODIES,
        }
        result = validate_tests_mechanical_node(state)
        assert result["validation_result"]["is_valid"] is False


# ---------------------------------------------------------------------------
# #2333: error paths the spec mandates and never tests
# ---------------------------------------------------------------------------


class TestErrorPathCoverageOnTheRealSpec:
    def test_the_spec_that_could_not_clear_the_gate_is_caught(self, spec_0007):
        """Acceptance: the gap is identified at the spec stage, not two later."""
        report = error_path_coverage(spec_0007)
        assert report.ran
        assert not report.ok

    def test_the_unasserted_exception_is_the_one_coverage_missed(self, spec_0007):
        """`FileNotFoundError` is config.py line 53 in the run's own report."""
        report = error_path_coverage(spec_0007)

        assert report.raised == {"FileNotFoundError": 1, "ValueError": 2}
        assert report.asserted == {"ValueError"}
        assert report.untested == ["FileNotFoundError"]

    def test_the_platform_branch_is_the_other_one(self, spec_0007):
        """One `os.name` branch, no test varying it: config.py lines 25-27."""
        report = error_path_coverage(spec_0007)

        assert report.platform_branches == 1
        assert report.platform_tested is False
        assert report.platform_gap is True

    def test_handlers_are_disclosed_and_never_failed(self, spec_0007):
        """Whether a test reaches an except cannot be read from the text.

        Reporting them as violations would produce findings this module
        cannot defend, so they are counted and named as not measured.
        """
        report = error_path_coverage(spec_0007)
        assert report.handlers == 5

        text = format_report(report)
        assert "Not measured here: statement coverage" in text
        assert "5 except handler(s)" in text

    def test_it_names_every_gap_in_one_pass(self, spec_0007):
        text = format_report(error_path_coverage(spec_0007))
        assert "FileNotFoundError" in text
        assert "platform branch" in text

    def test_the_node_check_fails_on_it(self, spec_0007):
        check = check_error_paths_have_tests(spec_0007)
        assert check["check_name"] == "error_paths_have_tests"
        assert check["passed"] is False
        assert "FileNotFoundError" in check["details"]


class TestErrorPathCoverageNegatives:
    def test_a_spec_that_tests_its_error_paths_passes(self):
        spec = (
            "## 5. Functions\n\n```python\n"
            "def load(path):\n"
            "    if not path.exists():\n"
            "        raise FileNotFoundError(path)\n"
            "    return 1\n"
            "```\n\n"
            "## 10.1 Tests\n\n```python\n"
            "def test_missing_file():\n"
            "    with pytest.raises(FileNotFoundError):\n"
            "        load(missing)\n"
            "```\n"
        )
        report = error_path_coverage(spec)

        assert report.ok
        assert report.untested == []
        assert "Every error path the spec mandates has a test" in format_report(report)

    def test_the_unittest_form_counts_too(self):
        spec = (
            "```python\ndef f():\n    raise ValueError('x')\n```\n"
            "```python\ndef test_f():\n    self.assertRaises(ValueError, f)\n```\n"
        )
        assert error_path_coverage(spec).untested == []

    def test_control_flow_raises_are_not_error_paths(self):
        """SystemExit is argparse's normal exit, asserted by code not by type."""
        spec = (
            "```python\ndef main():\n    raise SystemExit(0)\n```\n"
            "```python\ndef test_main():\n    assert True\n```\n"
        )
        report = error_path_coverage(spec)
        assert report.raised == {}
        assert report.ok

    def test_a_platform_branch_with_a_test_that_varies_it_passes(self):
        spec = (
            "```python\ndef p():\n    if os.name == 'nt':\n        return 1\n```\n"
            "```python\ndef test_p(monkeypatch):\n"
            "    monkeypatch.setattr(os, 'name', 'nt')\n```\n"
        )
        report = error_path_coverage(spec)
        assert report.platform_tested is True
        assert report.platform_gap is False

    def test_a_spec_with_no_implementation_fence_is_not_applicable(self):
        """The #1870 convention: a vacuous check reports so, never a pass."""
        report = error_path_coverage("## 10.1\n\n```python\ndef test_a():\n    pass\n```\n")

        assert report.ran is False
        assert "not applicable" in format_report(report)

    def test_test_fences_are_not_read_as_implementation(self):
        """A `raise` inside a test is the test's own setup, not a mandate."""
        spec = (
            "```python\ndef f():\n    return 1\n```\n"
            "```python\ndef test_f():\n    raise RuntimeError('setup')\n```\n"
        )
        code, tests = split_fences(spec)

        assert "raise RuntimeError" in tests
        assert "raise RuntimeError" not in code
        assert error_path_coverage(spec).raised == {}


class TestRequirementCoverageStopsPredictingTheGate:
    def test_the_summary_names_which_coverage_it_reports(self):
        """The number was true; what it implied was not (#2333).

        A fully covered LLD is the case that matters. That is precisely when
        the old wording read as a clean forecast of a gate it never measured.
        """
        from assemblyzero.core.validation.test_plan_validator import (
            validate_test_plan,
        )
        from tests.unit.test_test_plan_validator import LLD_FULL_COVERAGE

        result = validate_test_plan(LLD_FULL_COVERAGE)
        summary = result["summary"]

        assert result["coverage_percentage"] == 100.0
        assert "Requirement coverage:" in summary
        assert "statement coverage is a separate number" in summary
        assert "requirements mapped" in summary
