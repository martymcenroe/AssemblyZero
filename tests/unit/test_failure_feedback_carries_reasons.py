"""#2319 / #2320: the reviser must be told WHY a test failed, not just which.

On boostgauge #7 the implementation reviser received 36 bare test names and
produced a six-line cosmetic diff. Two independent causes:

  #2319  pytest truncates each `short test summary info` line to the terminal
         width. Captured through a pipe it assumes 80 columns, so the
         ` - AssertionError: ...` half was cut off.
  #2320  `--tb=short` tracebacks were captured and then discarded, because
         the summary builder read only the short-summary section. That block
         held `assert False` on the source line -- the whole diagnosis.

These tests drive REAL pytest through a REAL pipe, because both defects are
properties of how pytest behaves when its output is captured. A hand-built
output string would have been written with the reasons already present and
would have proved nothing.
"""

from __future__ import annotations

import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from assemblyzero.workflows.testing.nodes.verify_phases import (
    PYTEST_OUTPUT_COLUMNS,
    _build_failure_summary,
    _extract_traceback_blocks,
    _pytest_env,
)

# pytest prints paths relative to its rootdir, so the DISPLAYED length is what
# decides whether the reason gets cut. This nesting puts `FAILED <path>::<name>
# - <reason>` comfortably over 80 columns and comfortably under 200 -- which is
# what lets one fixture demonstrate both the defect and the repair.
_DEEP = "generated/worktree/tests"


@pytest.fixture(scope="module")
def failing_suite(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Path]:
    """A suite with two distinct causes and one repeated cause.

    Returns (rootdir, relative test path). Running with cwd=rootdir is what
    keeps the displayed path realistic; pointing pytest at an absolute path
    from elsewhere changes rootdir and with it the truncation behaviour.
    """
    root = tmp_path_factory.mktemp("suite")
    nested = root / _DEEP
    nested.mkdir(parents=True)
    path = nested / "test_generated_scenarios.py"
    path.write_text(textwrap.dedent('''
        def test_scenario_alpha():
            assert False, 'TDD RED: test_scenario_alpha not implemented'

        def test_scenario_beta():
            assert False, 'TDD RED: test_scenario_beta not implemented'

        def test_shared_cause_one():
            raise TypeError("unsupported operand")

        def test_shared_cause_two():
            raise TypeError("unsupported operand")
    ''').lstrip(), encoding="utf-8")
    return root, Path(_DEEP) / "test_generated_scenarios.py"


def _run_pytest(suite: tuple[Path, Path], env: dict[str, str] | None) -> str:
    root, rel = suite
    result = subprocess.run(
        [sys.executable, "-m", "pytest", str(rel), "-v", "--tb=short",
         "-p", "no:cacheprovider", "-o", "addopts="],
        cwd=str(root),
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        env=env,
    )
    return result.stdout + result.stderr


def test_default_capture_loses_the_reason(failing_suite: tuple[Path, Path]) -> None:
    """Characterise #2319 -- at the piped default the reasons are gone.

    If this ever stops holding, pytest changed its truncation behaviour and
    the fix below may no longer be load-bearing. Failing here is the signal
    to re-check, not a reason to delete the test.
    """
    env = os.environ.copy()
    env["COLUMNS"] = "80"
    output = _run_pytest(failing_suite, env)

    summary_lines = [
        line for line in output.splitlines() if line.startswith("FAILED ")
    ]
    assert summary_lines, "expected FAILED lines in the short summary"
    assert not any(" - " in line for line in summary_lines), (
        "at 80 columns every reason should be cut, got:\n"
        + "\n".join(summary_lines)
    )


def test_pytest_env_restores_the_reason(failing_suite: tuple[Path, Path]) -> None:
    """#2319: the captured summary carries complete reasons again."""
    output = _run_pytest(failing_suite, _pytest_env())

    summary_lines = [
        line for line in output.splitlines() if line.startswith("FAILED ")
    ]
    assert summary_lines
    assert any(
        "AssertionError: TDD RED: test_scenario_alpha not implemented" in line
        for line in summary_lines
    ), "the complete assertion reason must survive:\n" + "\n".join(summary_lines)
    assert any("TypeError: unsupported operand" in line for line in summary_lines)


def test_pytest_env_inherits_and_only_sets_columns() -> None:
    """The venv and PATH must survive -- this replaces the environment."""
    env = _pytest_env()
    assert env["COLUMNS"] == PYTEST_OUTPUT_COLUMNS
    for key in ("PATH", "SYSTEMROOT", "HOME"):
        if key in os.environ:
            assert env[key] == os.environ[key]


def test_summary_carries_source_line_and_error(failing_suite: tuple[Path, Path]) -> None:
    """#2320: the acceptance for the pair -- reason AND source line, verbatim."""
    output = _run_pytest(failing_suite, _pytest_env())
    summary = _build_failure_summary(output)

    assert "assert False, 'TDD RED: test_scenario_alpha not implemented'" in summary, (
        "the failing source line must reach the reviser verbatim"
    )
    assert "AssertionError: TDD RED: test_scenario_alpha not implemented" in summary
    assert "TypeError: unsupported operand" in summary


def test_summary_survives_an_80_column_capture(failing_suite: tuple[Path, Path]) -> None:
    """Belt and braces: tracebacks are not width-truncated.

    Even if COLUMNS were lost, the traceback half of the repair still
    delivers the diagnosis. The two fixes are independent on purpose.
    """
    env = os.environ.copy()
    env["COLUMNS"] = "80"
    summary = _build_failure_summary(_run_pytest(failing_suite, env))

    assert "assert False" in summary
    assert "AssertionError" in summary


def test_identical_causes_are_collapsed(failing_suite: tuple[Path, Path]) -> None:
    """#2320: N tests failing on one cause is one fact, stated once."""
    output = _run_pytest(failing_suite, _pytest_env())
    blocks = _extract_traceback_blocks(output)

    assert blocks.count("TypeError: unsupported operand") == 1, (
        "the repeated cause should appear once, not per-test"
    )
    assert "and 1 more with the same error" in blocks


def test_2058_grouping_revives_once_reasons_arrive(failing_suite: tuple[Path, Path]) -> None:
    """#2058's root-cause grouping needs the reason its regex parses.

    Verified rather than assumed, per the issue: with reasons present the
    two same-cause tests collapse into a single `2 test(s):` group.
    """
    output = _run_pytest(failing_suite, _pytest_env())
    summary = _build_failure_summary(output)

    assert "2 test(s): TypeError: unsupported operand" in summary, (
        f"expected a grouped root cause, got:\n{summary[:600]}"
    )


def test_no_failures_yields_empty_summary() -> None:
    assert _build_failure_summary("1 passed in 0.01s") == ""
    assert _extract_traceback_blocks("1 passed in 0.01s") == ""
