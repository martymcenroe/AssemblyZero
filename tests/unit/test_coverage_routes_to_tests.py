"""#2327: a coverage shortfall is a test gap, and must never reach implementation.

Measured on boostgauge #7: the spec's own test functions run against the
implementation give 23 passed and 80% coverage against a 95% gate, with every
uncovered statement in error handling that spec section 11.1 requires the code
to have and no requirement asks any test to reach.

Routing that to implementation revision is worse than useless. The cheapest
edit that raises statement coverage is to DELETE the uncovered code, so the
loop would be rewarded for removing exactly the error handling the spec
mandates -- silently, since every test still passes and the number goes up.

These tests pin the routing and the guarantee that the implementation is never
touched on this path.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from assemblyzero.workflows.testing.graph import (
    MAX_COVERAGE_AUGMENT_ATTEMPTS,
    route_after_green,
)
from assemblyzero.workflows.testing.nodes.augment_tests import (
    augment_tests_for_coverage,
    build_augment_prompt,
    parse_uncovered_lines,
)

# A real `--cov-report=term-missing` tail, matching the shape N5 captures.
COVERAGE_REPORT = """
Name                        Stmts   Miss  Cover   Missing
---------------------------------------------------------
src/boostgauge/__init__.py      0      0   100%
src/boostgauge/app.py          50      9    82%   31-33, 77, 84-88
src/boostgauge/config.py       45     10    78%   25-27, 53, 59, 76-78, 88-89
---------------------------------------------------------
TOTAL                          95     19    80%
"""


def test_uncovered_lines_are_parsed_per_file() -> None:
    uncovered = parse_uncovered_lines(COVERAGE_REPORT)

    assert set(uncovered) == {
        "src/boostgauge/app.py", "src/boostgauge/config.py",
    }
    assert uncovered["src/boostgauge/config.py"] == [
        "25-27", "53", "59", "76-78", "88-89",
    ]


def test_fully_covered_files_and_total_are_skipped() -> None:
    """A file with no Missing column is not a target, and TOTAL is not a file."""
    uncovered = parse_uncovered_lines(COVERAGE_REPORT)
    assert "src/boostgauge/__init__.py" not in uncovered
    assert not any("TOTAL" in key for key in uncovered)


def test_no_coverage_report_yields_no_targets() -> None:
    assert parse_uncovered_lines("23 passed in 0.2s") == {}


def test_prompt_forbids_touching_the_implementation() -> None:
    """The instruction that keeps the corruption off the table."""
    prompt = build_augment_prompt(
        "tests/test_issue_7.py", "def test_a():\n    assert 1\n",
        {"src/boostgauge/config.py": "53: raise ValueError('bad json')"},
        coverage_achieved=80.0, coverage_target=95,
    )

    assert "Do NOT modify the implementation" in prompt
    assert "ADDITIONAL" in prompt
    assert "53: raise ValueError('bad json')" in prompt, (
        "the request must name real uncovered code, not just line numbers"
    )


# ------------------------------------------------------------------ routing


def _green_state(**overrides: object) -> dict:
    state = {
        "error_message": "",
        "next_node": "N4c_augment_tests",
        "iteration_count": 0,
        "max_iterations": 3,
        "coverage_augment_attempts": 0,
    }
    state.update(overrides)
    return state


def test_coverage_shortfall_routes_to_test_additions() -> None:
    assert route_after_green(_green_state()) == "N4c_augment_tests"


def test_coverage_shortfall_never_routes_to_implementation() -> None:
    """The whole point: no state on this path may reach implementation."""
    for attempts in range(MAX_COVERAGE_AUGMENT_ATTEMPTS + 2):
        for iteration in range(5):
            decision = route_after_green(_green_state(
                coverage_augment_attempts=attempts, iteration_count=iteration,
            ))
            assert decision != "N4_implement_code", (
                f"coverage shortfall reached implementation at "
                f"attempts={attempts}, iteration={iteration}"
            )


def test_exhausted_attempts_halt_rather_than_fall_through() -> None:
    """#3585: the halt is HALT, which alerts; it was END, which tells no one."""
    state = _green_state(
        coverage_augment_attempts=MAX_COVERAGE_AUGMENT_ATTEMPTS,
    )
    assert route_after_green(state) == "HALT"


def test_iteration_cap_still_applies() -> None:
    assert route_after_green(_green_state(iteration_count=3)) == "HALT"


def test_a_genuine_implementation_loop_is_unaffected() -> None:
    """Failing tests still route to implementation, as before."""
    state = _green_state(next_node="N4_implement_code")
    assert route_after_green(state) == "N4_implement_code"


# ------------------------------------------------------------------ the node


def test_node_halts_when_nothing_to_target(
    tmp_path: Path,
) -> None:
    """A shortfall N5 named no line for: halt, change nothing.

    #3585: it returned to N5, which measured the same shortfall and sent it
    back, uncounted. A shortfall nobody can locate now halts.

    #4436: N5 reads the report and names the lines; this node reads no report.
    """
    test_file = tmp_path / "test_x.py"
    test_file.write_text("def test_a():\n    assert 1\n", encoding="utf-8")
    before = test_file.read_text(encoding="utf-8")

    result = augment_tests_for_coverage({
        "uncovered_changed_lines": {},
        "test_files": [str(test_file)],
        "repo_root": str(tmp_path),
        "coverage_achieved": 80.0,
        "coverage_target": 95,
        "coverage_module": "pkg",
    })

    assert result["next_node"] == "end"
    assert "names no uncovered line" in result["error_message"]
    assert test_file.read_text(encoding="utf-8") == before


def test_nothing_named_is_never_an_all_clear(tmp_path: Path) -> None:
    """#2637, the run-201554 shape: N4c must not read "no lines" as all-clear.
    That reading is half of the contradiction that produced the stagnation
    halt. #4436: an unreadable report now halts at N5, which is the one reader
    of it, so a state naming nothing here halts on its own."""
    test_file = tmp_path / "test_x.py"
    test_file.write_text("def test_a():\n    assert 1\n", encoding="utf-8")

    result = augment_tests_for_coverage({
        "test_files": [str(test_file)],
        "repo_root": str(tmp_path),
        "coverage_achieved": 0.0,
        "coverage_target": 95,
    })

    assert result["next_node"] == "end"
    assert "names no uncovered line" in result["error_message"]


def test_node_halts_with_no_test_file() -> None:
    """#3585: it returned to N5 with no reason."""
    result = augment_tests_for_coverage({
        "green_phase_output": COVERAGE_REPORT, "test_files": [],
    })
    assert result["next_node"] == "end"
    assert "no test file" in result["error_message"]


def test_a_python_gap_with_no_python_test_file_halts_naming_the_lines(tmp_path: Path) -> None:
    """#4436: a framework with changed source and no test file of the run is
    judged on its whole suite. N4c must not append pytest functions to a
    `.test.ts`, which is what `coverage_target_file` would hand it."""
    typescript = tmp_path / "a.test.ts"
    typescript.write_text("// a test\n", encoding="utf-8")

    result = augment_tests_for_coverage({
        "uncovered_changed_lines": {"pkg/a.py": [3, 4]},
        "test_files": [str(typescript)],
        "repo_root": str(tmp_path),
        "coverage_achieved": 0.0,
        "coverage_target": 95,
    })

    assert result["next_node"] == "end"
    assert "no Python test file" in result["error_message"]
    assert "pkg/a.py: 3-4" in result["error_message"]
    assert typescript.read_text(encoding="utf-8") == "// a test\n"


def test_node_never_names_an_implementation_file_as_its_output() -> None:
    """Structural guarantee: N4c only ever writes the test file.

    Asserted against the source, so a later edit that starts writing an
    implementation path fails here rather than in a post-mortem.
    """
    source = (
        Path(__file__).resolve().parents[2]
        / "assemblyzero" / "workflows" / "testing" / "nodes" / "augment_tests.py"
    ).read_text(encoding="utf-8")

    assert "write_text" in source
    # The only write target is the test path. #2902's vetting writes it
    # more than once (candidate, restore, merged); every write is still to
    # test_path.
    writes = [
        line.strip() for line in source.splitlines()
        if ".write_text(" in line
    ]
    targets = {line.split(".write_text(")[0] for line in writes}
    assert writes and targets == {"test_path"}, (
        f"N4c must write only the test file, found: {writes}"
    )


@pytest.mark.parametrize("bad", ["", "   ", "not a table at all"])
def test_malformed_reports_are_not_targets(bad: str) -> None:
    assert parse_uncovered_lines(bad) == {}
