"""The green loop grades the contract, measures the feature, and gives a
plateau two strikes (#2709, #2710, #2711).

boostgauge run-issue4-172600 (2026-09-02) was the first Phase 2 run to reach
the implementation stage with a scaffold its validator accepted. It ended on
three defects in the green loop, none of them in the generated code:

* the implementer deleted the scaffolded spec suite -- #460's rule, written
  for ``assert False`` stubs that #2316 later replaced with the spec's own
  tests -- and the green phase graded three tests the implementer wrote;
* coverage was measured on the first source file only, the abstract base,
  while ``collectors/windows.py`` went unmeasured;
* one non-improving iteration halted a five-iteration loop that had just
  snapshotted its best state.

Nothing here reaches a model: the bookkeeping is a pure helper, the pytest
runner is captured at ``run_command``, and the green phase is driven with
``run_pytest`` patched, the way ``test_verify_green_stagnation_both_branches``
already does.
"""

from __future__ import annotations

import inspect
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from assemblyzero.workflows.testing.nodes import verify_phases
from assemblyzero.workflows.testing.nodes.implementation import (
    orchestrator as impl_orchestrator,
)
from assemblyzero.workflows.testing.nodes.implementation.orchestrator import (
    merge_test_files,
)
from assemblyzero.workflows.testing.nodes.verify_phases import (
    COVERAGE_PLATEAU_STRIKES,
    coverage_plateau_verdict,
    run_pytest,
    verify_green_phase,
)

#: The five files run 9's LLD listed, in the order the implementer wrote them.
RUN9_FILES = (
    "src/boostgauge/collector.py",
    "src/boostgauge/collectors/windows.py",
    "tests/unit/test_collector.py",
    "tests/integration/test_windows_collector.py",
    "tests/benchmark/test_windows_collector.py",
)


def _state(tmp_path: Path, **overrides):
    base = {
        "test_files": [str(tmp_path / "tests" / "test_example.py")],
        "repo_root": str(tmp_path),
        "audit_dir": str(tmp_path / "audit"),
        "file_counter": 0,
        "issue_number": 4,
        "iteration_count": 1,
        "max_iterations": 5,
        "coverage_target": 95,
        "implementation_files": [],
        "skip_e2e": True,
        "previous_coverage": -1.0,
        "previous_passed": -1,
    }
    base.update(overrides)
    return base


def _pytest(returncode, passed=0, failed=0, errors=0, coverage=0, report=""):
    return {
        "returncode": returncode,
        "stdout": f"{passed} passed, {failed} failed\n{report}",
        "stderr": "",
        "parsed": {
            "passed": passed, "failed": failed,
            "errors": errors, "coverage": coverage,
        },
    }


#: A real term-missing table for the all-pass branch, which enforces the
#: coverage-measurement law (#2636): the target must appear in the report.
REPORT_72 = """
Name                 Stmts   Miss  Cover   Missing
--------------------------------------------------
src/pkg/thing.py        50     14    72%   10-23
--------------------------------------------------
TOTAL                   50     14    72%
"""


def _one_module(tmp_path: Path) -> str:
    """A src-layout package with one module; returns the module's path."""
    (tmp_path / "src" / "pkg").mkdir(parents=True, exist_ok=True)
    (tmp_path / "src" / "pkg" / "__init__.py").touch()
    thing = tmp_path / "src" / "pkg" / "thing.py"
    thing.touch()
    return str(thing)


# ---------------------------------------------------------------------------
# #2709: the scaffold is the contract
# ---------------------------------------------------------------------------


class TestTheScaffoldIsTheContract:
    def _scaffold(self, tmp_path: Path, body: str) -> Path:
        scaffold = tmp_path / "tests" / "test_issue_4.py"
        scaffold.parent.mkdir(parents=True, exist_ok=True)
        scaffold.write_text(body, encoding="utf-8")
        return scaffold

    def test_a_spec_suite_scaffold_survives_and_runs_first(self, tmp_path: Path) -> None:
        scaffold = self._scaffold(tmp_path, "def test_req_1():\n    assert 1 == 1\n")
        real = [str(tmp_path / "tests" / "unit" / "test_collector.py")]

        result = merge_test_files(
            scaffold_path=scaffold, scaffold_is_spec_suite=True,
            real_test_files=real, prior_test_files=[str(scaffold)],
        )

        assert scaffold.exists()
        assert result == [str(scaffold)] + real

    def test_a_stub_scaffold_is_still_replaced_as_460_intended(self, tmp_path: Path) -> None:
        scaffold = self._scaffold(tmp_path, "def test_req_1():\n    assert False, 'TDD RED'\n")
        real = [str(tmp_path / "tests" / "unit" / "test_collector.py")]

        result = merge_test_files(
            scaffold_path=scaffold, scaffold_is_spec_suite=False,
            real_test_files=real, prior_test_files=[str(scaffold)],
        )

        assert not scaffold.exists()
        assert result == real

    def test_no_implementer_tests_leaves_the_list_alone(self, tmp_path: Path) -> None:
        scaffold = self._scaffold(tmp_path, "def test_req_1():\n    assert 1 == 1\n")

        result = merge_test_files(
            scaffold_path=scaffold, scaffold_is_spec_suite=True,
            real_test_files=[], prior_test_files=["a.py", "b.py"],
        )

        assert result == ["a.py", "b.py"]
        assert scaffold.exists()

    def test_the_scaffold_is_listed_once_even_if_the_implementer_touched_it(
        self, tmp_path: Path
    ) -> None:
        scaffold = self._scaffold(tmp_path, "def test_req_1():\n    assert 1 == 1\n")
        other = str(tmp_path / "tests" / "unit" / "test_collector.py")

        result = merge_test_files(
            scaffold_path=scaffold, scaffold_is_spec_suite=True,
            real_test_files=[other, str(scaffold)], prior_test_files=[str(scaffold)],
        )

        assert result == [str(scaffold), other]

    def test_implement_code_routes_through_the_helper(self) -> None:
        """The unlink lives in the helper's legacy branch and nowhere else."""
        source = inspect.getsource(impl_orchestrator.implement_code)
        assert "merge_test_files(" in source
        assert "scaffold_path.unlink()" not in source
        assert '"test_files": test_files_after' in source


# ---------------------------------------------------------------------------
# #2710: coverage scope is the whole feature
# ---------------------------------------------------------------------------


class TestCoverageScopeIsTheWholeFeature:
    def _capture(self, coverage_module, coverage_target=95):
        with patch.object(verify_phases, "run_command") as run_command:
            run_command.return_value = SimpleNamespace(
                returncode=0, stdout="", stderr=""
            )
            run_pytest(
                ["tests/test_x.py"],
                coverage_module=coverage_module,
                coverage_target=coverage_target,
            )
        return run_command.call_args.args[0]

    def test_one_cov_flag_per_target_in_order(self) -> None:
        cmd = self._capture(["boostgauge.collector", "boostgauge.collectors.windows"])
        assert cmd.count("--cov=boostgauge.collector") == 1
        assert cmd.count("--cov=boostgauge.collectors.windows") == 1
        assert cmd.index("--cov=boostgauge.collector") < cmd.index(
            "--cov=boostgauge.collectors.windows"
        )
        assert cmd.count("--cov-report=term-missing") == 1
        assert "--cov-fail-under=95" in cmd

    def test_a_single_string_is_a_one_entry_list(self) -> None:
        cmd = self._capture("boostgauge.collector")
        assert [c for c in cmd if c.startswith("--cov=")] == ["--cov=boostgauge.collector"]

    def test_no_targets_means_no_cov_flags(self) -> None:
        cmd = self._capture(None)
        assert not [c for c in cmd if c.startswith("--cov")]

    @patch("assemblyzero.workflows.testing.nodes.verify_phases.run_pytest")
    def test_run_9s_files_yield_both_modules_and_no_test(self, mock_pytest, tmp_path: Path) -> None:
        """A src-layout package with a subpackage, exactly boostgauge's shape."""
        (tmp_path / "src" / "boostgauge" / "collectors").mkdir(parents=True)
        (tmp_path / "src" / "boostgauge" / "__init__.py").touch()
        (tmp_path / "src" / "boostgauge" / "collectors" / "__init__.py").touch()
        for rel in RUN9_FILES:
            path = tmp_path / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.touch()
        mock_pytest.return_value = _pytest(0, passed=9, coverage=96)

        verify_green_phase(_state(
            tmp_path, implementation_files=[str(tmp_path / rel) for rel in RUN9_FILES]
        ))

        # The first call is the measured run; a passing run calls again for
        # the regression check, without coverage.
        first = mock_pytest.call_args_list[0]
        assert first.kwargs["coverage_module"] == [
            "boostgauge.collector", "boostgauge.collectors.windows",
        ]

    @patch("assemblyzero.workflows.testing.nodes.verify_phases.run_pytest")
    def test_a_single_file_feature_is_unchanged(self, mock_pytest, tmp_path: Path) -> None:
        thing = _one_module(tmp_path)
        mock_pytest.return_value = _pytest(0, passed=1, coverage=100)

        verify_green_phase(_state(tmp_path, implementation_files=[thing]))

        assert mock_pytest.call_args_list[0].kwargs["coverage_module"] == ["pkg.thing"]

    @patch("assemblyzero.workflows.testing.nodes.verify_phases.run_pytest")
    def test_a_target_missing_from_the_report_is_named(self, mock_pytest, tmp_path: Path) -> None:
        """#2636's law, per target: the second module never reached the
        report, so the run is refused for THAT module by name."""
        (tmp_path / "src" / "pkg").mkdir(parents=True)
        (tmp_path / "src" / "pkg" / "__init__.py").touch()
        (tmp_path / "src" / "pkg" / "thing.py").touch()
        (tmp_path / "src" / "pkg" / "other.py").touch()
        mock_pytest.return_value = _pytest(1, passed=3, coverage=72, report=REPORT_72)

        result = verify_green_phase(_state(
            tmp_path,
            implementation_files=[
                str(tmp_path / "src" / "pkg" / "thing.py"),
                str(tmp_path / "src" / "pkg" / "other.py"),
            ],
            previous_passed=3, previous_coverage=72.0,
        ))

        assert result["next_node"] == "end"
        assert "pkg.other" in result["error_message"]
        assert "pkg.thing" not in result["error_message"]


# ---------------------------------------------------------------------------
# #2711: a plateau gets two strikes
# ---------------------------------------------------------------------------


class TestAPlateauGetsTwoStrikes:
    def test_run_9s_sequence_earns_a_second_iteration(self) -> None:
        """72.0% / 3 passing, then 70.0% / 2 passing and 1 failing: one strike,
        no halt. The same plateau again: two strikes, halt."""
        strikes, halt = coverage_plateau_verdict({}, 70.0, 72.0, 2, 3, ["test_req_2"], [])
        assert (strikes, halt) == (1, False)

        strikes, halt = coverage_plateau_verdict(
            {"coverage_plateau_strikes": 1}, 70.0, 70.0, 2, 2, [], []
        )
        assert (strikes, halt) == (2, True)

    def test_an_improving_iteration_clears_the_count(self) -> None:
        """#2029's live case, with a strike already on the board."""
        assert coverage_plateau_verdict(
            {"coverage_plateau_strikes": 1}, 98.0, 97.0, 22, 20,
            ["t_a"], ["t_a", "t_b", "t_c"],
        ) == (0, False)

    def test_a_first_iteration_is_never_a_strike(self) -> None:
        assert coverage_plateau_verdict({}, 40.0, -1.0, 3, -1, [], []) == (0, False)

    def test_the_bar_is_two(self) -> None:
        assert COVERAGE_PLATEAU_STRIKES == 2

    @patch("assemblyzero.workflows.testing.nodes.verify_phases.run_pytest")
    def test_the_failing_branch_routes_back_on_the_first_strike(
        self, mock_pytest, tmp_path: Path
    ) -> None:
        """Run 9's halt, replayed: it now goes back to the implementer."""
        mock_pytest.return_value = _pytest(1, passed=2, failed=1, coverage=70)

        result = verify_green_phase(_state(
            tmp_path, previous_passed=3, previous_coverage=72.0,
            previous_green_failures=[],
        ))

        assert result["next_node"] == "N4_implement_code", result.get("error_message")
        assert result["coverage_plateau_strikes"] == 1

    @patch("assemblyzero.workflows.testing.nodes.verify_phases.run_pytest")
    def test_the_failing_branch_advises_on_the_second_strike_and_keeps_going(
        self, mock_pytest, tmp_path: Path, capsys
    ) -> None:
        """#2723: the second strike used to end the run. It now says what it
        sees and routes back to the implementer; the iteration cap decides."""
        mock_pytest.return_value = _pytest(1, passed=2, failed=1, coverage=70)

        result = verify_green_phase(_state(
            tmp_path, previous_passed=2, previous_coverage=70.0,
            previous_green_failures=[], coverage_plateau_strikes=1,
        ))

        assert result["next_node"] == "N4_implement_code"
        assert result["error_message"] == ""
        printed = capsys.readouterr().out
        assert "Coverage stagnant" in printed
        assert "across 3 iterations" in printed
        assert "[gate:impl.stagnation.coverage]" in printed
        assert result["coverage_plateau_strikes"] == 2

    @patch("assemblyzero.workflows.testing.nodes.verify_phases.run_pytest")
    def test_the_all_pass_branch_routes_to_test_additions_on_the_first_strike(
        self, mock_pytest, tmp_path: Path
    ) -> None:
        thing = _one_module(tmp_path)
        mock_pytest.return_value = _pytest(1, passed=3, coverage=72, report=REPORT_72)

        result = verify_green_phase(_state(
            tmp_path, implementation_files=[thing],
            previous_passed=3, previous_coverage=72.0,
        ))

        assert result["next_node"] == "N4c_augment_tests", result.get("error_message")
        assert result["coverage_plateau_strikes"] == 1

    @patch("assemblyzero.workflows.testing.nodes.verify_phases.run_pytest")
    def test_the_all_pass_branch_advises_on_the_second_strike(
        self, mock_pytest, tmp_path: Path, capsys
    ) -> None:
        thing = _one_module(tmp_path)
        mock_pytest.return_value = _pytest(1, passed=3, coverage=72, report=REPORT_72)

        result = verify_green_phase(_state(
            tmp_path, implementation_files=[thing],
            previous_passed=3, previous_coverage=72.0,
            coverage_plateau_strikes=1,
        ))

        assert result["error_message"] == ""
        assert result["next_node"] != "end"
        assert "Coverage stagnant" in capsys.readouterr().out
        assert result["coverage_plateau_strikes"] == 2

    @patch("assemblyzero.workflows.testing.nodes.verify_phases.run_pytest")
    def test_the_advisory_still_says_stagnant_for_the_classifier(
        self, mock_pytest, tmp_path: Path, capsys
    ) -> None:
        """#1939: the classifier matches the word, so a reword that drops it
        would file the event under the wrong class. #2723 moved the sentence
        from the halt message to the log, and it keeps the word."""
        thing = _one_module(tmp_path)
        mock_pytest.return_value = _pytest(1, passed=3, coverage=72, report=REPORT_72)
        verify_green_phase(_state(
            tmp_path, implementation_files=[thing],
            previous_passed=3, previous_coverage=72.0,
            coverage_plateau_strikes=1,
        ))
        printed = capsys.readouterr().out
        assert "stagnant" in printed.lower()
        assert "Continuing; the budget decides." in printed
