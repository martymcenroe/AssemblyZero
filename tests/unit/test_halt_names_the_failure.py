"""A halted run must say what it could not fix (#2042).

Two rolls of boostgauge #2 stopped on 2026-07-31 reporting `Error: unknown`
with an empty halt message. The failing check and its detail had been printed
earlier in the run and were dropped at the halt, so the exit code and the
summary between them said only that something stopped.

Characterising those two failures took two runs plus re-executing both checkers
by hand against preserved artifacts. Everything needed was already on the
validation result and simply never left the node that produced it.
"""


from assemblyzero.workflows.requirements.graph import describe_validation_failure


def _result(*messages, warnings=()):
    violations = [
        {"severity": "error", "message": m} for m in messages
    ] + [{"severity": "warning", "message": w} for w in warnings]
    return {"passed": False, "violations": violations}


class TestTheFailureIsNamed:
    def test_a_single_error_is_reported_verbatim(self):
        summary = describe_validation_failure(
            _result("No requirements found in Section 3")
        )
        assert "No requirements found in Section 3" in summary

    def test_several_errors_are_all_named(self):
        summary = describe_validation_failure(
            _result("REQ-1 has no test coverage", "REQ-2 has no test coverage")
        )
        assert "REQ-1" in summary and "REQ-2" in summary

    def test_the_live_case_produces_something_actionable(self):
        """The message that was lost: 0 scenarios from section 10."""
        summary = describe_validation_failure(
            _result("Section 10.1 produced no test scenarios")
        )
        assert "Section 10.1" in summary
        assert summary != "no validation detail was recorded"


class TestItStaysReadable:
    def test_a_long_list_is_capped_and_says_so(self):
        """A halt that dumps forty violations is read as noise, which is no
        more use than the empty message it replaces."""
        summary = describe_validation_failure(_result(*[f"err {i}" for i in range(10)]))

        assert "and 7 more" in summary
        assert summary.count(";") == 2

    def test_warnings_are_not_reported_as_the_cause(self):
        """Only errors block; naming warnings would misdirect the reader."""
        summary = describe_validation_failure(
            _result("the real error", warnings=("cosmetic", "style"))
        )
        assert "the real error" in summary
        assert "cosmetic" not in summary


class TestDegradedInputs:
    def test_a_missing_result_still_says_something(self):
        assert describe_validation_failure(None) == "no validation detail was recorded"

    def test_a_failure_with_no_error_violations_is_admitted(self):
        """Rather than claiming a cause that is not there."""
        summary = describe_validation_failure({"passed": False, "violations": []})
        assert "no error-level violations" in summary

    def test_a_violation_without_a_message_does_not_crash(self):
        summary = describe_validation_failure(
            {"passed": False, "violations": [{"severity": "error"}]}
        )
        assert "no message" in summary


class TestTheRouterCarriesIt:
    def test_the_halt_sets_a_non_empty_error_message(self):
        """The whole point: the summary has to reach the halt payload, not just
        stdout, or the exit path still reports 'unknown'."""
        from assemblyzero.workflows.requirements.graph import (
            route_after_validate_test_plan,
        )

        state = {
            "test_plan_validation_result": _result("Section 10.1 produced no rows"),
            "iteration_count": 3,
            "max_iterations": 3,
        }
        assert route_after_validate_test_plan(state) == "HALT"
        assert state.get("error_message"), "the halt must name the failure"
        assert "Section 10.1" in state["error_message"]

    def test_a_loop_back_does_not_set_an_error(self):
        """Iterations that will retry are not failures and must not look like
        them."""
        from assemblyzero.workflows.requirements.graph import (
            route_after_validate_test_plan,
        )

        state = {
            "test_plan_validation_result": _result("fixable"),
            "iteration_count": 1,
            "max_iterations": 3,
        }
        assert route_after_validate_test_plan(state) == "N1_generate_draft"
        assert not state.get("error_message")
