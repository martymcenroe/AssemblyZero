"""#2676: the scaffold routing decision is computed once, in the node.

run-issue384-044442: a FIRST-attempt validation failure printed [EXHAUSTED]
and silently ended the testing workflow as success — no halt, no red phase,
no implementation — and the pipeline merged a PR containing an assertion-free
stub and no code. The node had correctly decided "regenerate" (no previous
hash, attempts under the cap), then stored this attempt's hash; the router
recomputed `exhausted_reason` from the updated state and compared the attempt
against its own hash — always byte-identical, spuriously exhausted, and the
escalate edge ends the graph without an error_message.

The node now carries `scaffold_route` in its result and the router reads it.
Escalate therefore structurally implies the node wrote the DETERMINISTIC
FAILURE halt.
"""

from __future__ import annotations

import hashlib

from assemblyzero.workflows.testing.nodes.validate_tests_mechanical import (
    MAX_SCAFFOLD_ATTEMPTS,
    should_regenerate,
    validate_tests_mechanical_node,
)

#: One real test, one assertion-free stub — the run's exact validation error
#: class ("has no assertions - only pass/docstring").
INVALID_SUITE = '''
def test_req_010_real():
    value = 1 + 1
    assert value == 2

def test_req_020_stub():
    """Only a docstring lives here."""
    pass
'''

VALID_SUITE = '''
from myproj.config import write_config

def test_req_010_real(tmp_path):
    path = tmp_path / "c.json"
    write_config(path)
    assert path.exists()

def test_req_020_also_real(tmp_path):
    path = tmp_path / "d.json"
    write_config(path)
    assert path.read_text() != ""
'''


def _state(**overrides: object) -> dict:
    state = {
        "generated_tests": INVALID_SUITE,
        "parsed_scenarios": {"scenarios": []},
        "scaffold_attempts": 0,
        "previous_scaffold_hash": "",
    }
    state.update(overrides)
    return state


def _after_node(state: dict) -> tuple[dict, dict]:
    result = validate_tests_mechanical_node(state)
    merged = {**state, **result}
    return result, merged


class TestFirstAttemptFailureRegenerates:
    """The run-issue384-044442 regression pin."""

    def test_the_node_carries_regenerate(self) -> None:
        result, _ = _after_node(_state())
        assert result["validation_result"]["is_valid"] is False
        assert result["scaffold_route"] == "regenerate"
        assert "error_message" not in result

    def test_the_router_reads_the_carried_route(self) -> None:
        """Pre-#2676 this returned 'escalate': the router recomputed against
        the node's own just-stored hash and found the attempt byte-identical
        to itself."""
        _, merged = _after_node(_state())
        assert should_regenerate(merged) == "regenerate"


class TestTrueExhaustionStillEscalatesWithTheHalt:
    def test_byte_identical_second_attempt(self) -> None:
        prior = hashlib.sha256(INVALID_SUITE.encode()).hexdigest()
        result, merged = _after_node(
            _state(previous_scaffold_hash=prior, scaffold_attempts=1)
        )
        assert result["scaffold_route"] == "escalate"
        assert "byte for byte" in result["error_message"]
        assert should_regenerate(merged) == "escalate"

    def test_attempts_cap(self) -> None:
        result, merged = _after_node(
            _state(
                previous_scaffold_hash="something-else",
                scaffold_attempts=MAX_SCAFFOLD_ATTEMPTS - 1,
            )
        )
        assert result["scaffold_route"] == "escalate"
        assert "limit of" in result["error_message"]
        assert should_regenerate(merged) == "escalate"


class TestValidSuiteContinues:
    def test_continue_is_carried_and_read(self) -> None:
        result, merged = _after_node(_state(generated_tests=VALID_SUITE))
        assert result["validation_result"]["is_valid"] is True, (
            result["validation_result"]["errors"]
        )
        assert result["scaffold_route"] == "continue"
        assert should_regenerate(merged) == "continue"


class TestFallbackWithoutTheCarriedKey:
    def test_a_valid_legacy_state_continues(self) -> None:
        """Resumed state that predates the key still routes."""
        assert should_regenerate(
            {"validation_result": {"is_valid": True}}
        ) == "continue"


class TestTheCarriedKeySurvivesTheGraphMerge:
    """#2679: the #2678 repair shipped inert because these tests merged node
    result into state by hand (`{**state, **result}`), bypassing the graph's
    TypedDict schema filter — which dropped the undeclared `scaffold_route`
    between the node's return and the router's read. run-issue384-054226
    replayed the silent fail-open with the fixed code present and ran the
    fallback anyway, and the pipeline merged a second junk PR.

    The schema IS the merge contract: every key the node carries for the
    router must be declared in it."""

    def test_scaffold_route_is_declared_in_the_state_schema(self) -> None:
        from assemblyzero.workflows.testing.state import TestingWorkflowState

        annotations = TestingWorkflowState.__annotations__
        assert "scaffold_route" in annotations, (
            "scaffold_route is not declared in TestingWorkflowState — the "
            "graph merge drops undeclared keys, the router falls back to the "
            "hash recompute, and the #2676 fail-open returns (#2679)"
        )

    def test_every_key_the_node_carries_is_declared(self) -> None:
        """The general form: the node's result keys on the live failure shape
        must all survive the schema, so a future carried key cannot repeat
        this defect by omission."""
        from assemblyzero.workflows.testing.state import TestingWorkflowState

        result, _ = _after_node(_state())
        undeclared = set(result) - set(TestingWorkflowState.__annotations__)
        assert not undeclared, (
            f"node result key(s) not declared in TestingWorkflowState — the "
            f"graph merge will drop them silently: {sorted(undeclared)}"
        )
