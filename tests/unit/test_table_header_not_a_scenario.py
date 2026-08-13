"""#2318: a test-table column HEADING must never become a test scenario.

The boostgauge #7 LLD leads its test plan with

    | Test ID | Test Description | Expected Behavior | Status |

Both guards in `parse_test_scenarios` compared the whole cell against a
fixed list, and "test id" was in neither. The heading became a scenario, the
scaffolder emitted a test named `test_id`, and its docstring was the row's
remaining column names. It was planned, scaffolded, reviewed and graded
against across two implementation iterations, and it never existed.

Deciding token-wise is what generalises: the fix must hold for `Test Name`,
`Req ID` and any other heading a future LLD format uses, not just the one
phrasing that was observed.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from assemblyzero.workflows.testing.nodes.load_lld import (
    _is_header_cell,
    extract_test_plan_section,
    parse_test_scenarios,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "issue7_run153937"


@pytest.mark.parametrize("cell", [
    "Test ID", "test id", "TEST ID", "Test  ID",
    "ID", "Test Name", "Req ID", "Expected Output", "Pass Criteria",
    "Scenario", "Type", "Description", "Status", "Test Description",
    "Expected Behavior", "Expected Behaviour",
])
def test_headings_are_recognised(cell: str) -> None:
    assert _is_header_cell(cell) is True


@pytest.mark.parametrize("cell", [
    "T010", "010", "T090", "test_req_1",
    "First run no config", "Position matrix tests",
    "Threshold live reload", "",
])
def test_scenario_ids_are_not_headings(cell: str) -> None:
    assert _is_header_cell(cell) is False


def test_the_real_lld_no_longer_yields_test_id() -> None:
    """The regression, against the artifact that produced it."""
    lld = (FIXTURES / "LLD-007.md").read_text(encoding="utf-8")
    scenarios = parse_test_scenarios(extract_test_plan_section(lld))

    names = [s["name"] for s in scenarios]
    assert "test_id" not in names, "the heading row leaked in again"

    # The real scenarios both survive: 12 summary rows + 23 detail rows.
    assert len(names) == 35, f"expected 35 real scenarios, got {len(names)}"
    assert sum(1 for n in names if n.startswith("test_t")) == 12
    assert sum(1 for n in names if n[5:].isdigit()) == 23


def test_a_heading_only_table_yields_nothing() -> None:
    """The degenerate case: headings alone are not scenarios."""
    table = (
        "| Test ID | Test Description | Expected Behavior | Status |\n"
        "|---------|------------------|-------------------|--------|\n"
    )
    assert parse_test_scenarios(table) == []
