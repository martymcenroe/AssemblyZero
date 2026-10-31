"""Tests for revise_test_plan node + route_after_review (#1072)."""

from __future__ import annotations

from typing import Any


from assemblyzero.workflows.testing.graph import route_after_review
from assemblyzero.workflows.testing.nodes.revise_test_plan import (
    MAX_REVISION_CYCLES,
    _parse_scenarios_from_table,
    revise_test_plan,
)


# ---------------------------------------------------------------------------
# route_after_review — policy dispatch
# ---------------------------------------------------------------------------


def test_route_default_revise_policy_routes_to_revise_node():
    """BLOCKED + revise policy + count<MAX → N1_5_revise_test_plan."""
    state: dict[str, Any] = {
        "test_plan_status": "BLOCKED",
        "test_plan_policy": "revise",
        "test_plan_revision_count": 0,
        "auto_mode": False,
    }
    assert route_after_review(state) == "N1_5_revise_test_plan"


def test_route_revise_policy_exhausts_after_max_cycles():
    """BLOCKED + revise policy + count==MAX → HALT (#3585; it ended at END)."""
    state: dict[str, Any] = {
        "test_plan_status": "BLOCKED",
        "test_plan_policy": "revise",
        "test_plan_revision_count": MAX_REVISION_CYCLES,
        "auto_mode": False,
    }
    assert route_after_review(state) == "HALT"


def test_route_strict_policy_ends_immediately():
    """BLOCKED + strict policy → HALT at once (#3585; it ended at END)."""
    state: dict[str, Any] = {
        "test_plan_status": "BLOCKED",
        "test_plan_policy": "strict",
        "test_plan_revision_count": 0,
        "auto_mode": False,
    }
    assert route_after_review(state) == "HALT"


def test_route_auto_policy_revises_like_revise():
    """BLOCKED + auto policy → N1_5_revise_test_plan (#3585).

    The auto policy used to continue to scaffold past the BLOCKED verdict,
    a failed gate read as a pass (ADR 0236). It now revises.
    """
    state: dict[str, Any] = {
        "test_plan_status": "BLOCKED",
        "test_plan_policy": "auto",
        "test_plan_revision_count": 0,
        "auto_mode": False,
    }
    assert route_after_review(state) == "N1_5_revise_test_plan"


def test_route_legacy_auto_mode_no_longer_bypasses_a_blocked_plan():
    """auto_mode=True revises a BLOCKED plan like the default policy (#3585)."""
    state: dict[str, Any] = {
        "test_plan_status": "BLOCKED",
        "test_plan_policy": "revise",
        "test_plan_revision_count": 0,
        "auto_mode": True,
    }
    assert route_after_review(state) == "N1_5_revise_test_plan"


def test_route_approved_goes_straight_to_scaffold_regardless_of_policy():
    """APPROVED is unchanged across policies."""
    for policy in ("revise", "auto", "strict"):
        state: dict[str, Any] = {
            "test_plan_status": "APPROVED",
            "test_plan_policy": policy,
            "test_plan_revision_count": 0,
            "auto_mode": False,
        }
        assert route_after_review(state) == "N2_scaffold_tests"


def test_route_error_with_no_auto_mode_halts():
    """error_message + auto_mode=False → HALT (#2756).

    Still a stop; the destination changed so the reason is written down by
    the node that owns halting. Since #3585 the two policy stops above halt
    too; N1's stop wrapper records their reason.
    """
    state: dict[str, Any] = {
        "error_message": "something blew up",
        "test_plan_status": "PENDING",
        "auto_mode": False,
    }
    assert route_after_review(state) == "HALT"


# ---------------------------------------------------------------------------
# revise_test_plan — mock mode (deterministic)
# ---------------------------------------------------------------------------


def test_revise_test_plan_mock_mode_increments_count():
    """Mock revise increments revision_count from 0 → 1."""
    state: dict[str, Any] = {
        "mock_mode": True,
        "requirements": ["1. First requirement", "2. Second requirement"],
        "test_plan_revision_count": 0,
    }
    update = revise_test_plan(state)
    assert update["test_plan_revision_count"] == 1


def test_revise_test_plan_mock_mode_clears_blocked_status():
    """Mock revise sets test_plan_status to PENDING for re-review."""
    state: dict[str, Any] = {
        "mock_mode": True,
        "requirements": ["1. Req one"],
        "test_plan_revision_count": 0,
    }
    update = revise_test_plan(state)
    assert update["test_plan_status"] == "PENDING"
    assert update["error_message"] == ""
    assert update["gemini_feedback"] == ""


def test_revise_test_plan_mock_mode_produces_one_scenario_per_req():
    """Mock revise satisfies the count gate (>= len(requirements))."""
    state: dict[str, Any] = {
        "mock_mode": True,
        "requirements": [
            "1. Cover X",
            "2. Cover Y",
            "3. Cover Z",
        ],
        "test_plan_revision_count": 0,
    }
    update = revise_test_plan(state)
    assert len(update["test_scenarios"]) == 3
    refs = {s["requirement_ref"] for s in update["test_scenarios"]}
    assert refs == {"REQ-1", "REQ-2", "REQ-3"}


def test_revise_test_plan_mock_mode_emits_markdown_table():
    """Mock revise's test_plan_section parses back into the same scenarios."""
    state: dict[str, Any] = {
        "mock_mode": True,
        "requirements": ["1. Req one", "2. Req two"],
        "test_plan_revision_count": 0,
    }
    update = revise_test_plan(state)
    parsed = _parse_scenarios_from_table(update["test_plan_section"])
    assert len(parsed) == 2


# ---------------------------------------------------------------------------
# _parse_scenarios_from_table — markdown parsing
# ---------------------------------------------------------------------------


def test_parse_scenarios_skips_header_and_separator():
    """Header rows and ---|--- separators don't become scenarios."""
    md = """
    | ID | Scenario | Type | Requirements |
    |---|---|---|---|
    | T001 | Test the thing | unit | REQ-1 |
    | T002 | Test the other | integration | Req 2 |
    """
    parsed = _parse_scenarios_from_table(md)
    assert len(parsed) == 2
    assert parsed[0]["requirement_ref"] == "REQ-1"
    assert parsed[1]["requirement_ref"] == "REQ-2"
    assert parsed[0]["test_type"] == "unit"
    assert parsed[1]["test_type"] == "integration"


def test_parse_scenarios_normalizes_id_format():
    """Bare numeric IDs become T-prefixed; T1 becomes T1 (not zero-padded)."""
    md = """
    | ID | Scenario | Type | Reqs |
    | 1 | A | unit | REQ-1 |
    | T7 | B | unit | REQ-2 |
    """
    parsed = _parse_scenarios_from_table(md)
    assert len(parsed) == 2
    assert parsed[0]["name"].startswith("t001_")
    assert parsed[1]["name"].startswith("t7_")


def test_parse_scenarios_handles_no_requirement_ref():
    """A row without a Req mention still parses (with empty req_ref)."""
    md = """
    | ID | Scenario | Type |
    | T001 | Standalone test | unit |
    """
    parsed = _parse_scenarios_from_table(md)
    assert len(parsed) == 1
    assert parsed[0]["requirement_ref"] == ""


def test_parse_scenarios_returns_empty_for_no_table():
    """Garbage input produces empty list, not exception."""
    assert _parse_scenarios_from_table("no table here at all") == []
    assert _parse_scenarios_from_table("") == []
