"""Requirements conflicts halt with the conflict named, at both ends (#1899/#1900).

boostgauge#125 is the reference incident: issue #41 specified two different
floors for a decaying peak, and the contradiction cost two rolls three impl
iterations each plus a third roll's entire revise budget before a human
diagnosed it from transcripts. The remedy is layered:

- N0c (pre-flight, #1899): an analysis gate at the front of the
  requirements workflow reads the issue as one document and halts BEFORE
  generation when two criteria specify different outcomes for the same
  situation. Fail-open: an unavailable analysis never kills the roll.
- Reviewer escalation (mid-pipeline backstop, #1900): the spec reviewer
  BLOCKS with a 'REQUIREMENTS CONFLICT:' rationale when its objection
  traces to the source requirements, instead of burning revise cycles.
- Shared classification: the marker maps to error_type
  requirements_conflict — non-transient, with a recovery recommendation
  that says exactly what the operator must rule on.
"""

from unittest.mock import MagicMock, patch

from assemblyzero.core.halt_node import classify_error
from assemblyzero.core.recovery_plan import (
    TRANSIENT_ERROR_TYPES,
    generate_recovery_plan,
)
from assemblyzero.workflows.requirements.graph import (
    route_after_analyze_requirements,
)
from assemblyzero.workflows.requirements.nodes.analyze_requirements import (
    REQUIREMENTS_CONFLICT_MARKER,
    _format_conflict_message,
    _parse_analysis,
    analyze_requirements,
)

MODULE = "assemblyzero.core.llm_provider"

CONFLICT_JSON = (
    '{"is_consistent": false, "conflicts": [{'
    '"criterion_a": "the floor is the highest value still in the window", '
    '"criterion_b": "the needle drifts toward the most recent value", '
    '"diverging_situation": "whenever the window maximum is not the latest sample"'
    "}]}"
)
CONSISTENT_JSON = '{"is_consistent": true, "conflicts": []}'


def _state(**overrides):
    state = {
        "issue_title": "feat: telltale needles",
        "issue_body": "## Behavior\nPeaks decay.\n## Criteria\n- floor rules",
        "config_mock_mode": False,
        "config_drafter": "gemini:3.1-pro",
    }
    state.update(overrides)
    return state


def _provider_returning(response, success=True, error=None):
    provider = MagicMock()
    provider.invoke.return_value = MagicMock(
        success=success, response=response, error_message=error
    )
    return provider


class TestN0cGate:
    def test_conflict_halts_with_both_sentences_named(self):
        provider = _provider_returning(CONFLICT_JSON)
        with patch(f"{MODULE}.get_provider", return_value=provider):
            result = analyze_requirements(_state())
        msg = result.get("error_message", "")
        assert msg.startswith(REQUIREMENTS_CONFLICT_MARKER)
        assert "highest value still in the window" in msg
        assert "most recent value" in msg
        assert "window maximum is not the latest sample" in msg

    def test_consistent_requirements_proceed(self):
        provider = _provider_returning(CONSISTENT_JSON)
        with patch(f"{MODULE}.get_provider", return_value=provider):
            result = analyze_requirements(_state())
        assert result == {}

    def test_failed_analysis_call_fails_closed(self):
        """#2474 reversed #1899's fail-open ruling. A gate that could not reach
        the governance model stops the run instead of letting it draft against
        requirements nobody checked."""
        provider = _provider_returning(None, success=False, error="503 storm")
        with patch(f"{MODULE}.get_provider", return_value=provider):
            result = analyze_requirements(_state())
        assert result.get("requirements_unverified"), "must not proceed"
        assert result != {}, (
            "returning the clean value here is the collapse #2474 fixed"
        )

    def test_unparseable_response_fails_closed(self):
        provider = _provider_returning("I think it looks fine!")
        with patch(f"{MODULE}.get_provider", return_value=provider):
            result = analyze_requirements(_state())
        assert "unparseable" in result.get("requirements_unverified", "")

    def test_mock_mode_skips_entirely(self):
        with patch(f"{MODULE}.get_provider") as gp:
            result = analyze_requirements(_state(config_mock_mode=True))
        assert result == {}
        gp.assert_not_called()

    def test_empty_issue_body_skips(self):
        with patch(f"{MODULE}.get_provider") as gp:
            result = analyze_requirements(_state(issue_body="   "))
        assert result == {}
        gp.assert_not_called()

    def test_fenced_json_is_tolerated(self):
        parsed = _parse_analysis(f"```json\n{CONSISTENT_JSON}\n```")
        # #2830: the parser always returns the canonical shape, notes included.
        assert parsed == {"is_consistent": True, "conflicts": [], "notes": []}

    def test_route_halts_on_error_message(self):
        assert (
            route_after_analyze_requirements({"error_message": "REQUIREMENTS CONFLICT: x"})
            == "HALT"
        )
        assert (
            route_after_analyze_requirements({"error_message": ""})
            == "N1_generate_draft"
        )


class TestSharedClassification:
    def test_marker_classifies_requirements_conflict(self):
        msg = _format_conflict_message(
            [
                {
                    "criterion_a": "a",
                    "criterion_b": "b",
                    "diverging_situation": "s",
                }
            ]
        )
        assert classify_error(msg) == "requirements_conflict"

    def test_reviewer_blocked_rationale_classifies_the_same(self):
        """#1900: the spec reviewer's BLOCKED rationale uses the same
        marker, so a mid-pipeline conflict gets the same typed halt."""
        rationale = (
            "REQUIREMENTS CONFLICT: 'floor = highest value in window' vs "
            "'floor = most recent value' — diverge when window max is stale."
        )
        assert classify_error(rationale) == "requirements_conflict"

    def test_requirements_conflict_is_not_transient(self):
        assert "requirements_conflict" not in TRANSIENT_ERROR_TYPES

    def test_recovery_plan_tells_the_operator_what_to_do(self):
        plan = generate_recovery_plan(
            issue_number=41,
            workflow="requirements",
            stage="N0c_analyze_requirements",
            error_type="requirements_conflict",
            error_message="REQUIREMENTS CONFLICT: a vs b",
            state={},
        )
        assert plan.is_transient is False
        assert "acceptance criteria" in plan.recommendation
        assert "re-run" in plan.recommendation

    def test_capacity_still_wins_its_own_classification(self):
        """The new first-position branch must not shadow capacity."""
        assert (
            classify_error("Capacity exhausted after 3 retries (503/529)")
            == "capacity_exhausted"
        )


class TestUnverifiedClassification:
    """#2474: a gate that could not RUN classifies apart from one that ran and
    found a contradiction. The two need opposite operator responses."""

    def _message(self, why="All credentials failed: 503/529 capacity storms"):
        provider = _provider_returning(None, success=False, error=why)
        with patch(f"{MODULE}.get_provider", return_value=provider):
            return analyze_requirements(_state())["error_message"]

    def test_the_halt_message_classifies_as_unverified(self):
        assert classify_error(self._message()) == "requirements_unverified"

    def test_it_does_not_classify_as_a_conflict(self):
        """Sending the operator to rule on a contradiction in requirements
        nothing ever read is the collapse #2474 removed."""
        assert classify_error(self._message()) != "requirements_conflict"

    def test_the_quoted_transport_failure_does_not_capture_it(self):
        """The reason text quotes the provider verbatim, so it is full of
        capacity markers. Classifying on those would produce 'wait 15 minutes
        and retry', which skips the part the operator has to know."""
        assert classify_error(self._message()) != "capacity_exhausted"

    def test_it_is_not_transient(self):
        """A transient class tells the launcher it may retry unattended, and
        the point of this halt is that a human learns the requirements were
        never checked before anything spends again."""
        assert "requirements_unverified" not in TRANSIENT_ERROR_TYPES

    def test_the_launcher_does_not_read_it_as_a_conflict(self):
        """`is_requirements_conflict` is a SUBSTRING test on the halt message,
        and the launcher exits 93 on it -- stop this issue, never redraw,
        continue the batch. That is right for a conflict and wrong here: an
        unverified gate is usually a transient outage that a later attempt
        clears. A reword of the halt message that let the marker appear in it
        would silently retire every retry this failure should get.
        """
        from assemblyzero.core.exit_codes import is_requirements_conflict

        assert not is_requirements_conflict(self._message())

    def test_the_recovery_plan_names_the_gate_rerun(self):
        plan = generate_recovery_plan(
            issue_number=331,
            workflow="requirements",
            stage="N0c_analyze_requirements",
            error_type="requirements_unverified",
            error_message="REQUIREMENTS UNVERIFIED: ...",
            state={},
        )
        assert plan.is_transient is False
        assert "check_requirements.py" in plan.recommendation
        assert "not a clean check" in plan.recommendation.lower()
