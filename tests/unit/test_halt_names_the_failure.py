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


class TestTheNodeCarriesIt:
    """The message must ride the NODE's return. The first version of this fix
    mutated state inside the conditional-edge router; a router returns a node
    name and its state writes are discarded at the graph boundary (#2018's
    channel rule) -- so the summary printed and the run still halted with
    `Error: unknown`. The unit test passed because it called the router as a
    plain function, where the mutation is visible: it tested the function,
    not the graph."""

    def _node_state(self, iteration, tmp_path, draft="## 3. Requirements\n"):
        return {
            "current_draft": draft,
            "iteration_count": iteration,
            "max_iterations": 3,
            "test_plan_validation_attempts": 0,
            "audit_dir": str(tmp_path),
        }

    def test_the_final_failed_iteration_returns_the_message(self, tmp_path):
        from assemblyzero.workflows.requirements.nodes.validate_test_plan import (
            validate_test_plan_node,
        )

        updates = validate_test_plan_node(self._node_state(2, tmp_path))
        assert updates.get("error_message"), "final iteration must name the failure"
        assert "revision(s)" in updates["error_message"]

    def test_an_earlier_iteration_loops_without_an_error(self, tmp_path):
        from assemblyzero.workflows.requirements.nodes.validate_test_plan import (
            validate_test_plan_node,
        )

        updates = validate_test_plan_node(self._node_state(0, tmp_path))
        assert updates.get("error_message") == ""
        assert updates.get("lld_status") == "BLOCKED"

    def test_the_failing_draft_is_preserved(self, tmp_path):
        """Both LLD halts of boostgauge #2 judged content that was destroyed
        with the worktree; the drafter regression they rejected could not be
        inspected at all."""
        from assemblyzero.workflows.requirements.nodes.validate_test_plan import (
            validate_test_plan_node,
        )

        validate_test_plan_node(self._node_state(0, tmp_path))
        kept = list(tmp_path.glob("failed-draft-iter*.md"))
        assert kept, "the rejected draft must outlive the run"
        body = kept[0].read_text(encoding="utf-8")
        assert "## 3. Requirements" in body
        assert "validation feedback" in body

    def test_the_router_halts_on_the_node_set_error(self):
        """End of the chain: error_message present -> HALT, first check."""
        from assemblyzero.workflows.requirements.graph import (
            route_after_validate_test_plan,
        )

        assert route_after_validate_test_plan({"error_message": "named failure"}) == "HALT"
