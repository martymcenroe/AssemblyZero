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

    def test_failed_analysis_call_fails_open(self):
        provider = _provider_returning(None, success=False, error="503 storm")
        with patch(f"{MODULE}.get_provider", return_value=provider):
            result = analyze_requirements(_state())
        assert result == {}

    def test_unparseable_response_fails_open(self):
        provider = _provider_returning("I think it looks fine!")
        with patch(f"{MODULE}.get_provider", return_value=provider):
            result = analyze_requirements(_state())
        assert result == {}

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
        assert parsed == {"is_consistent": True, "conflicts": []}

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
