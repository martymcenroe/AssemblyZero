"""A halt must say why (Closes #2197).

A spec sub-workflow that halted at its iteration cap recorded an empty
error_message. The banner printed `Error: unknown`, `Stage: orchestrator_unknown`
at the orchestrator level, the stage table's error column was blank, and the
persisted orchestration state carried `error_message: ""`. Observed on
boostgauge `run-issue1-124144` (2026-08-10), whose own narration knew exactly
why it stopped: "Max iterations (3) reached with verdict REVISE - halting".

The cause is structural. The routers decide the halt, and a router's state
writes are discarded at the graph boundary (#2018), so nothing reached
error_message. The fix is in two layers: the nodes record the reason where they
know it, and the HALT node synthesizes one from state when they do not.

What must NOT change: #2233 leaves error_message empty on purpose for a
finalize repair, because an in-flight repair is not a failure. That path routes
to the drafter and never reaches HALT, which is why the fallback is scoped to
the HALT node. `TestTheRepairPathIsUntouched` pins it.
"""

from unittest.mock import patch

import pytest

from assemblyzero.core.halt_node import (
    describe_halt_from_state,
    describe_iteration_cap,
)
from assemblyzero.workflows.implementation_spec.nodes.validate_completeness import (
    validate_completeness,
)


class TestTheCapMessage:
    def test_it_names_the_cap_and_the_verdict(self):
        message = describe_iteration_cap(3, "REVISE", "The spec invents pixel geometry.")

        assert "3" in message
        assert "REVISE" in message
        assert "pixel geometry" in message

    def test_one_round_reads_as_singular(self):
        assert "1 review round" in describe_iteration_cap(1, "REVISE")

    def test_only_the_first_feedback_line_is_carried(self):
        """The banner is a verdict, not a transcript."""
        message = describe_iteration_cap(
            3, "REVISE", "First objection.\nSecond objection.\nThird."
        )
        assert "First objection." in message
        assert "Second objection." not in message

    def test_a_long_line_is_truncated(self):
        message = describe_iteration_cap(3, "REVISE", "x" * 900)
        assert len(message) < 500
        assert message.endswith("...")

    def test_no_feedback_still_names_the_cap(self):
        message = describe_iteration_cap(3, "REVISE", "")
        assert "3" in message and "REVISE" in message
        assert "Last feedback" not in message


class TestTheHaltNodeFallback:
    """No halt path may print "unknown" again, including ones no node
    anticipated -- two-strike stagnation reaches HALT from the router alone."""

    def test_a_capped_review_is_described(self):
        message = describe_halt_from_state(
            {
                "review_verdict": "REVISE",
                "review_iteration": 3,
                "max_iterations": 3,
                "review_feedback": "The spec invents pixel geometry.",
            },
            "implementation_spec",
        )
        assert "REVISE" in message and "pixel geometry" in message

    def test_unresolved_checks_are_described(self):
        message = describe_halt_from_state(
            {"completeness_issues": ["a", "b", "c", "d"], "review_iteration": 2},
            "implementation_spec",
        )
        assert "4 unresolved check(s)" in message
        assert "a; b; c" in message

    def test_a_verdict_without_a_cap_is_still_described(self):
        """Two-strike stagnation: the router halts, the node recorded nothing,
        and the iteration count is below the cap."""
        message = describe_halt_from_state(
            {"review_verdict": "REVISE", "review_iteration": 2, "max_iterations": 3},
            "implementation_spec",
        )
        assert "REVISE" in message
        assert "no recorded reason" in message

    def test_an_empty_state_says_so_rather_than_unknown(self):
        message = describe_halt_from_state({}, "implementation_spec")

        assert "unknown" not in message.lower()
        assert "implementation_spec" in message
        assert "state snapshot" in message

    def test_it_reports_state_rather_than_re_deciding(self):
        """A synthesized message that disagreed with the real reason would be
        worse than the blank it replaces, so every branch names a field it
        read. Pinned by the requirements workflow's own field names working
        too -- the fallback is not spec-specific."""
        message = describe_halt_from_state(
            {"lld_status": "BLOCKED", "iteration_count": 3, "max_iterations": 3,
             "current_verdict": "Two criteria contradict."},
            "requirements",
        )
        assert "BLOCKED" in message and "contradict" in message


class TestTheHaltNodeUsesIt:
    def test_an_empty_error_message_is_replaced(self, tmp_path, monkeypatch):
        from assemblyzero.core import halt_node

        captured = {}

        class _Plan:
            state_path = ""

            def save(self, _dir):
                return tmp_path / "plan.md"

            def print_summary(self):
                pass

        def _generate(**kwargs):
            captured.update(kwargs)
            return _Plan()

        monkeypatch.setattr(halt_node, "generate_recovery_plan", _generate)
        monkeypatch.setattr(
            halt_node, "save_state_snapshot",
            lambda *a, **k: tmp_path / "state.json",
        )

        node = halt_node.create_halt_node("implementation_spec")
        node({
            "issue_number": 1,
            "error_message": "",
            "review_verdict": "REVISE",
            "review_iteration": 3,
            "max_iterations": 3,
            "review_feedback": "The spec invents pixel geometry.",
        })

        assert "unknown" not in captured["error_message"].lower(), (
            'the halt banner printed "Error: unknown", which is the defect'
        )
        assert "REVISE" in captured["error_message"]

    def test_a_real_error_message_is_left_alone(self, tmp_path, monkeypatch):
        from assemblyzero.core import halt_node

        captured = {}

        class _Plan:
            state_path = ""

            def save(self, _dir):
                return tmp_path / "plan.md"

            def print_summary(self):
                pass

        monkeypatch.setattr(
            halt_node, "generate_recovery_plan",
            lambda **kw: (captured.update(kw), _Plan())[1],
        )
        monkeypatch.setattr(
            halt_node, "save_state_snapshot",
            lambda *a, **k: tmp_path / "state.json",
        )

        halt_node.create_halt_node("implementation_spec")({
            "issue_number": 1,
            "error_message": "Spec review BLOCKED: REQUIREMENTS CONFLICT: ...",
        })

        assert captured["error_message"].startswith("Spec review BLOCKED")


class TestTheCompletenessCap:
    """The other iteration-cap halt in the same workflow."""

    def _state(self, iteration, max_iterations=3, shown=()):
        return {
            "spec_draft": "# Spec\n\n" + ("body line\n" * 40),
            "files_to_modify": [],
            "pattern_references": [],
            "repo_root": "",
            "lld_content": "",
            "review_iteration": iteration,
            "max_iterations": max_iterations,
            # #2304: a check that has never reached a revision prompt now earns
            # one grace instead of halting, so the halt-with-reason case is
            # specifically the one where every failing check HAS been tried.
            "checks_shown_to_drafter": list(shown),
        }

    def _at_the_cap_with_everything_tried(self, patched):
        """Run once to discover what this spec fails, then again with those
        marked as already shown.

        Derived rather than hardcoded: naming the failing checks would couple
        this test to which ones happen to trip on a minimal spec, and the next
        check added would break it for a reason unrelated to the halt.
        """
        with patch(
            "assemblyzero.workflows.implementation_spec.nodes."
            "validate_completeness.check_modify_files_have_excerpts",
            return_value=patched,
        ):
            first = validate_completeness(self._state(iteration=3))
            tried = first["checks_shown_to_drafter"]
            return validate_completeness(
                self._state(iteration=3, shown=tried)
            )

    def test_a_failure_at_the_cap_records_a_reason(self, capsys):
        out = self._at_the_cap_with_everything_tried(
            {"check_name": "x", "passed": False,
             "details": "missing excerpt for a.py"},
        )
        capsys.readouterr()

        assert out["error_message"], (
            "the last failure the budget allows goes to HALT, and it recorded "
            "nothing"
        )
        assert "Iteration cap" in out["error_message"]
        assert "missing excerpt" in out["error_message"]

    def test_an_untried_check_at_the_cap_gets_a_grace_instead_of_a_halt(self, capsys):
        """#2304: the same scenario with the check NOT yet shown is a grace,
        not a halt. Pinned beside its sibling so the two cannot be confused."""
        with patch(
            "assemblyzero.workflows.implementation_spec.nodes."
            "validate_completeness.check_modify_files_have_excerpts",
            return_value={"check_name": "x", "passed": False, "details": "missing excerpt for a.py"},
        ):
            out = validate_completeness(self._state(iteration=3, shown=()))
        capsys.readouterr()

        assert out["error_message"] == ""
        assert "x" in out["grace_revision_for"]

    def test_the_halt_message_says_the_checks_were_actually_tried(self, capsys):
        """'the halt message must distinguish the two cases' -- otherwise
        'N revisions ended with 1 unresolved check' reads as a stubborn
        drafter when the truth may be that it was never asked."""
        out = self._at_the_cap_with_everything_tried(
            {"check_name": "x", "passed": False,
             "details": "missing excerpt for a.py"},
        )
        capsys.readouterr()

        assert "shown to the drafter and survived a revision" in out["error_message"]

    def test_a_failure_below_the_cap_records_nothing(self, capsys):
        """The run is still going. A pending revision is not a failure, and a
        message here would halt a loop that should keep turning."""
        with patch(
            "assemblyzero.workflows.implementation_spec.nodes."
            "validate_completeness.check_modify_files_have_excerpts",
            return_value={"check_name": "x", "passed": False, "details": "missing excerpt"},
        ):
            out = validate_completeness(self._state(iteration=1))
        capsys.readouterr()

        assert out["error_message"] == ""
        assert out["validation_passed"] is False

    def test_a_pass_at_the_cap_records_nothing(self, capsys):
        out = validate_completeness(self._state(iteration=3))
        capsys.readouterr()

        if out["validation_passed"]:
            assert out["error_message"] == ""


class TestTheRepairPathIsUntouched:
    """#2233 leaves error_message empty ON PURPOSE for a finalize repair: an
    in-flight repair is not a failure. The operator flagged this explicitly as
    the thing not to regress."""

    def test_a_repair_still_routes_to_the_drafter_not_halt(self):
        from assemblyzero.workflows.requirements.graph import route_after_finalize

        assert route_after_finalize({
            "finalize_repair_pending": True,
            "error_message": "",
        }) == "N1_generate_draft"

    def test_the_fallback_cannot_reach_a_repair(self):
        """The synthesis lives in the HALT node, and a pending repair never
        arrives there. That is why it is safe."""
        from assemblyzero.workflows.requirements.graph import route_after_finalize

        for pending in (True, False):
            assert route_after_finalize({
                "finalize_repair_pending": pending, "error_message": "",
            }) != "HALT"


@pytest.mark.parametrize(
    "state",
    [
        {},
        {"review_verdict": "REVISE"},
        {"completeness_issues": []},
        {"review_iteration": 3, "max_iterations": 3},
    ],
)
def test_no_synthesized_message_is_ever_the_word_unknown(state):
    """The whole point. Whatever the state, the operator gets a sentence."""
    message = describe_halt_from_state(state, "implementation_spec")

    assert message.strip()
    assert message.strip().lower() != "unknown"
    assert "Error: unknown" not in message
