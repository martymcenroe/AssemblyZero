"""#2344 / #2345: a stage may not report passed while holding a failing test.

`run-issue7-231606` ended with `31 passed, 1 failed` as its last N5 result and
recorded impl as PASSED. Running its shipped artifact confirms it:

    FAILED tests/test_issue_7.py::test_config_path_non_windows
    1 failed, 31 passed, config.py 100% coverage

Nothing lied. N5's freeze branch correctly returned an empty error_message --
it was routing to another revision, not failing. The router then hit an
iteration cap it computed from a DIFFERENT default than the one N5 had just
printed, returned "end" without a word, and the empty error survived to a
verdict that read "no error" as "tests pass".

The pr stage would have pushed and opened a PR from that branch.
"""

from __future__ import annotations

import pytest

from assemblyzero.workflows.orchestrator.stages import _unresolved_test_failures
from assemblyzero.workflows.testing.graph import route_after_green
from assemblyzero.workflows.testing.nodes.e2e_validation import (
    _extract_failed_test_names,
)
from assemblyzero.workflows.testing.state import DEFAULT_MAX_ITERATIONS

# The real shape of `pytest -v` output: the failure appears twice.
VERBOSE_OUTPUT = """
tests/test_issue_7.py::test_req_1 PASSED                                 [  3%]
tests/test_issue_7.py::test_config_path_non_windows FAILED               [ 96%]
tests/test_issue_7.py::test_req_22 PASSED                                [100%]

=========================== short test summary info ===========================
FAILED tests/test_issue_7.py::test_config_path_non_windows - pathlib.UnsupportedOperation
1 failed, 31 passed in 0.42s
"""


# ---------------------------------------------------------- #2345: the count


def test_verbose_output_yields_one_name_per_failure() -> None:
    """'1 failed' is true; 'same 2 test(s)' was the lie."""
    names = _extract_failed_test_names(VERBOSE_OUTPUT)

    assert names == ["tests/test_issue_7.py::test_config_path_non_windows"]
    assert "[" not in names, "the progress bracket is not a test"


def test_the_count_matches_pytest() -> None:
    assert len(_extract_failed_test_names(VERBOSE_OUTPUT)) == 1


def test_summary_only_output_still_parses() -> None:
    output = (
        "=========================== short test summary info ===========\n"
        "FAILED tests/a.py::test_x - AssertionError\n"
        "FAILED tests/b.py::TestC::test_y - ValueError\n"
    )
    assert _extract_failed_test_names(output) == [
        "tests/a.py::test_x", "tests/b.py::TestC::test_y",
    ]


def test_a_clean_run_reports_nothing() -> None:
    assert _extract_failed_test_names("31 passed in 0.4s") == []


# ------------------------------------------------- #2344: one iteration cap


def test_the_cap_has_one_value_everywhere() -> None:
    """Two defaults for one missing key is what dropped the loop-back."""
    import inspect

    from assemblyzero.workflows.testing import graph
    from assemblyzero.workflows.testing.nodes import verify_phases

    for module in (graph, verify_phases):
        source = inspect.getsource(module)
        assert 'state.get("max_iterations", 3)' not in source, module.__name__
        assert 'state.get("max_iterations", 5)' not in source, module.__name__


def test_the_seeded_cap_governs_the_router() -> None:
    """With the cap seeded, the freeze's loop-back is honoured."""
    state = {
        "error_message": "",
        "next_node": "N4_implement_code",
        "iteration_count": 3,
        "max_iterations": DEFAULT_MAX_ITERATIONS,
    }
    assert route_after_green(state) == "N4_implement_code"


def test_the_cap_still_stops_the_loop(capsys: pytest.CaptureFixture[str]) -> None:
    """And when it does stop, it says so rather than ending silently."""
    state = {
        "error_message": "",
        "next_node": "N4_implement_code",
        "iteration_count": DEFAULT_MAX_ITERATIONS,
        "max_iterations": DEFAULT_MAX_ITERATIONS,
    }
    assert route_after_green(state) == "end"
    assert "ITERATION CAP" in capsys.readouterr().out


# ------------------------------------------------- #2344: measured verdicts


def test_the_run_that_shipped_is_now_a_failure() -> None:
    """The exact sub-workflow state from run-issue7-231606."""
    sub_result = {
        "error_message": "",
        "previous_green_failures": [
            "tests/test_issue_7.py::test_config_path_non_windows",
        ],
        "coverage_achieved": 100.0,
    }
    assert _unresolved_test_failures(sub_result) == 1


def test_a_genuine_pass_is_still_a_pass() -> None:
    """Every success path resets both keys; none may become a false halt."""
    assert _unresolved_test_failures({
        "error_message": "",
        "previous_green_failures": [],
        "full_suite_regressions": [],
    }) == 0


def test_a_full_suite_regression_is_not_a_pass() -> None:
    """#842's gate zeroes the green set while carrying regressions.

    Checking only previous_green_failures would let a regressed repo through
    the same cap-and-report-passed hole.
    """
    assert _unresolved_test_failures({
        "error_message": "",
        "previous_green_failures": [],
        "full_suite_regressions": ["tests/other.py::test_z"],
    }) == 1


@pytest.mark.parametrize("sub_result", [
    {},
    {"previous_green_failures": None},
    {"previous_green_failures": "not a list"},
    {"full_suite_regressions": 3},
])
def test_an_unanswerable_state_never_invents_a_failure(sub_result: dict) -> None:
    """A verdict check must not turn a genuine pass into a spurious halt."""
    assert _unresolved_test_failures(sub_result) == 0
