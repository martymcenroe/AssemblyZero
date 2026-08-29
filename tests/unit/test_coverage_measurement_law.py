"""Coverage is measured or it is named absent — never rendered as a number.

The boostgauge #331 roll of 2026-08-28 (`run-issue331-201554`) wrote the
renderer, passed 15 tests, and halted anyway:

    [N5]  15 passed, 0 failed | Coverage: 0.0%
    [N5]  all 15 test(s) pass; coverage 0.0% < 95% -- this is a test gap,
          routing to test additions (never to implementation)
    [N4c] coverage report named no uncovered lines; nothing specific to
          target -- returning to verification
    [STAGNANT] Coverage stagnant: 0.0% -> 0.0%. ... The LLD or spec likely
          needs manual editing

Three renderings of one empty measurement, and the halt blamed the two
artifacts that had just passed.

**Neither issue's stated mechanism survived the evidence.** No PR regressed the
derivation -- `_path_to_cov_target` is untouched since #1507. The env is an
EDITABLE install (`boostgauge.pth` -> `.../boostgauge/src`), not the
non-editable copy the issue described, and there is no site-packages copy at
all. The real cause is smaller and total: **`--cov` never accepts a `.py`
path**, for any input, so the report was empty rather than zero.

`TestPathFormNeverMeasures` is that finding as a program: it runs pytest twice
against a real repo on disk and compares. Everything else here is downstream of
it.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from assemblyzero.workflows.testing.coverage_report import (
    ABSENT,
    MEASURED,
    read_coverage,
)
from assemblyzero.workflows.testing.nodes.verify_phases import (
    _is_python_package_dir,
    _path_to_cov_target,
)

MOD = '''\
def render(size):
    if size < 128:
        raise ValueError("too small")
    return size * 3
'''

TEST = '''\
import pkg.sub.mod


def test_renders():
    assert pkg.sub.mod.render(256) == 768
'''

#: The run's report shape: tests ran, no coverage table at all.
ABSENT_REPORT = "15 passed, 0 failed\n"

#: Genuine 0%: the table exists and every line is uncovered.
ZERO_REPORT = (
    "15 passed, 0 failed\n"
    "Name                              Stmts   Miss  Cover   Missing\n"
    "------------------------------------------------------------------\n"
    "src/boostgauge/skins/stingray.py     40     40     0%   1-40\n"
    "------------------------------------------------------------------\n"
    "TOTAL                                40     40     0%\n"
)

AT_TARGET_REPORT = (
    "15 passed, 0 failed\n"
    "Name                              Stmts   Miss  Cover   Missing\n"
    "------------------------------------------------------------------\n"
    "src/boostgauge/skins/stingray.py     40      2    95%   17, 22\n"
    "------------------------------------------------------------------\n"
    "TOTAL                                40      2    95%\n"
)

TARGET = "boostgauge.skins.stingray"


# ---------------------------------------------------------------------------
# #2636 -- the finding, run rather than argued
# ---------------------------------------------------------------------------


class TestPathFormNeverMeasures:
    """Two real pytest runs. The claim is measured, not reasoned about."""

    @pytest.fixture
    def repo(self, tmp_path: Path) -> Path:
        root = tmp_path / "repo"
        (root / "src" / "pkg" / "sub").mkdir(parents=True)
        (root / "src" / "pkg" / "__init__.py").write_text("", encoding="utf-8")
        (root / "src" / "pkg" / "sub" / "__init__.py").write_text("", encoding="utf-8")
        (root / "src" / "pkg" / "sub" / "mod.py").write_text(MOD, encoding="utf-8")
        (root / "tests").mkdir()
        (root / "tests" / "test_mod.py").write_text(TEST, encoding="utf-8")
        return root

    def _run(self, repo: Path, target: str) -> str:
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", "tests", f"--cov={target}",
             "--cov-report=term-missing", "-q", "-p", "no:cacheprovider"],
            cwd=str(repo), capture_output=True, text=True,
            encoding="utf-8", errors="replace",
            env={**os.environ, "PYTHONPATH": str(repo / "src")},
            timeout=180,
        )
        return proc.stdout + proc.stderr

    def test_a_py_path_target_collects_nothing(self, repo: Path) -> None:
        """Even with PYTHONPATH pointing at the very file being measured."""
        out = self._run(repo, "src/pkg/sub/mod.py")

        assert "was never imported" in out
        assert read_coverage(out, "src/pkg/sub/mod.py").state == ABSENT

    def test_a_module_target_measures(self, repo: Path) -> None:
        """The control. Same repo, same tests, same file -- it is the TARGET
        FORM that decides, not the install layout."""
        out = self._run(repo, "pkg.sub.mod")

        reading = read_coverage(out, "pkg.sub.mod")
        assert reading.state == MEASURED
        assert (reading.percent or 0) > 0

    def test_a_directory_target_measures_too(self, repo: Path) -> None:
        """Which is why the non-package fallback degrades to the directory."""
        reading = read_coverage(self._run(repo, "src/pkg"), "pkg")
        assert reading.state == MEASURED


class TestTheDerivationSurvivesASubpackageOnlyTree:
    """The exact tree that broke #331: `src/boostgauge/` holding only `skins/`.

    No `__init__.py`, no direct `.py` file. `_is_python_package_dir` answered
    "not a package", so the target fell to path form and measured nothing.
    """

    @pytest.fixture
    def repo(self, tmp_path: Path) -> Path:
        (tmp_path / "src" / "boostgauge" / "skins").mkdir(parents=True)
        (tmp_path / "src" / "boostgauge" / "skins" / "stingray.py").write_text(
            MOD, encoding="utf-8"
        )
        return tmp_path

    def test_the_331_shape_yields_module_form(self, repo: Path) -> None:
        assert _path_to_cov_target(
            "src/boostgauge/skins/stingray.py", repo
        ) == "boostgauge.skins.stingray"

    def test_a_dir_of_only_subpackages_is_a_package(self, repo: Path) -> None:
        assert _is_python_package_dir(repo / "src" / "boostgauge") is True

    def test_the_08_26_shape_still_yields_module_form(self, tmp_path: Path) -> None:
        """The pre-regression tree, pinned so the old behaviour cannot be lost
        while fixing the new one: `__init__.py` plus sibling modules."""
        pkg = tmp_path / "src" / "boostgauge"
        (pkg / "skins").mkdir(parents=True)
        (pkg / "__init__.py").write_text("", encoding="utf-8")
        (pkg / "config.py").write_text("X = 1\n", encoding="utf-8")
        (pkg / "skins" / "stingray.py").write_text(MOD, encoding="utf-8")

        assert _path_to_cov_target(
            "src/boostgauge/skins/stingray.py", tmp_path
        ) == "boostgauge.skins.stingray"

    def test_a_backslash_path_resolves_the_same_on_every_platform(
        self, tmp_path: Path
    ) -> None:
        """CI caught this on Linux while Windows passed.

        A backslash is an ordinary filename character on POSIX, so
        `Path("tools\\\\x.py").parent` is `.` there and the fallback kept the
        backslash in the target. Separators are normalised before splitting.
        """
        (tmp_path / "tools").mkdir()

        assert _path_to_cov_target("tools\\my_script.py", tmp_path) == "tools"
        assert _path_to_cov_target("tools/my_script.py", tmp_path) == "tools"

    def test_a_directory_of_plain_directories_is_not_a_package(
        self, tmp_path: Path
    ) -> None:
        """The control that keeps the widening honest: subdirectories with no
        Python in them do not make a package."""
        (tmp_path / "src" / "assets" / "images").mkdir(parents=True)

        assert _is_python_package_dir(tmp_path / "src" / "assets") is False


# ---------------------------------------------------------------------------
# #2637 -- three states, one accessor
# ---------------------------------------------------------------------------


class TestTheThreeStates:
    def test_absent_is_absent(self) -> None:
        reading = read_coverage(ABSENT_REPORT, TARGET)
        assert reading.state == ABSENT
        assert reading.percent is None, "absence must not carry a number"

    def test_genuine_zero_is_measured_with_its_lines(self) -> None:
        reading = read_coverage(ZERO_REPORT, TARGET)
        assert reading.state == MEASURED
        assert reading.percent == 0.0
        assert reading.at_zero is True
        assert reading.uncovered == {
            "src/boostgauge/skins/stingray.py": ["1-40"]
        }

    def test_at_target_is_measured(self) -> None:
        reading = read_coverage(AT_TARGET_REPORT, TARGET)
        assert reading.state == MEASURED
        assert reading.percent == 95.0
        assert reading.at_zero is False

    def test_a_full_report_naming_another_file_is_absent(self) -> None:
        """Coverage ran, but not on the thing under test."""
        elsewhere = AT_TARGET_REPORT.replace(
            "src/boostgauge/skins/stingray.py", "src/boostgauge/config.py"
        )
        assert read_coverage(elsewhere, TARGET).state == ABSENT

    def test_a_total_without_parseable_rows_is_still_measured(self) -> None:
        """Absence is claimed only on positive evidence. An abbreviated report
        is not a measurement failure, or every unfamiliar layout becomes one."""
        assert read_coverage("3 passed\nTOTAL 100 10 90%", TARGET).state == MEASURED

    def test_a_hundred_percent_row_names_no_uncovered_lines(self) -> None:
        """The separator line is not a missing-line range. `\\s` spans newlines,
        so an earlier form of this parser swallowed `-----` as one and a fully
        covered file reported uncovered lines."""
        report = (
            "3 passed\n"
            "Name          Stmts   Miss  Cover   Missing\n"
            "--------------------------------------------\n"
            "pkg/x.py         10      0   100%\n"
            "--------------------------------------------\n"
            "TOTAL            10      0   100%\n"
        )
        assert read_coverage(report, "pkg").uncovered == {}


class TestTheFailureMessage:
    def test_it_names_the_target_and_what_was_found(self) -> None:
        message = read_coverage(ZERO_REPORT.replace(
            "src/boostgauge/skins/stingray.py", "src/boostgauge/config.py"
        ), TARGET).failure_message()

        assert TARGET in message
        assert "src/boostgauge/config.py" in message

    def test_it_refuses_the_three_wrong_renderings(self) -> None:
        message = read_coverage(ABSENT_REPORT, TARGET).failure_message()

        assert "0.0%" not in message and "0%" not in message
        assert "not a test gap" in message
        assert "not a defect in the LLD or spec" in message

    def test_it_quotes_coverages_own_reason_when_present(self) -> None:
        noisy = ABSENT_REPORT + "CoverageWarning: Module x was never imported.\n"
        assert "was never imported" in read_coverage(
            noisy, TARGET
        ).failure_message()


class TestBothConsumersAgree:
    """#1698: two parsers of one report is the class, and the N5/N4c
    contradiction on run-201554 is the live proof. Same reading, same verdict,
    from both call sites."""

    @pytest.mark.parametrize(
        "report,expected",
        [(ABSENT_REPORT, ABSENT), (ZERO_REPORT, MEASURED),
         (AT_TARGET_REPORT, MEASURED)],
    )
    def test_one_reading_per_report(self, report: str, expected: str) -> None:
        assert read_coverage(report, TARGET).state == expected

    def test_n4c_halts_on_the_run_201554_shape(self, tmp_path: Path) -> None:
        from assemblyzero.workflows.testing.nodes.augment_tests import (
            augment_tests_for_coverage,
        )

        test_file = tmp_path / "test_x.py"
        test_file.write_text("def test_a():\n    assert 1\n", encoding="utf-8")

        result = augment_tests_for_coverage({
            "green_phase_output": ABSENT_REPORT,
            "test_files": [str(test_file)],
            "repo_root": str(tmp_path),
            "coverage_achieved": 0.0,
            "coverage_target": 95,
            "coverage_module": TARGET,
        })

        assert result["next_node"] == "end"
        assert "COVERAGE MEASUREMENT FAILED" in result["error_message"]

    def test_n5_halts_on_the_run_201554_shape(self, tmp_path: Path) -> None:
        """The other half of the acceptance: the SAME named failure from N5.

        The observed state exactly -- 15 passed, 0 failed, no coverage table.
        """
        from unittest.mock import patch

        from assemblyzero.workflows.testing.nodes.verify_phases import (
            verify_green_phase,
        )

        impl = tmp_path / "src" / "boostgauge" / "skins"
        impl.mkdir(parents=True)
        (impl / "stingray.py").write_text(MOD, encoding="utf-8")

        state = {
            "issue_number": 331,
            "repo_root": str(tmp_path),
            "test_files": [str(tmp_path / "t.py")],
            "audit_dir": "",
            "file_counter": 0,
            "coverage_target": 95,
            "iteration_count": 0,
            "max_iterations": 5,
            "implementation_files": [str(impl / "stingray.py")],
            "skip_e2e": True,
            "previous_coverage": -1.0,
            "previous_passed": -1,
        }

        with patch(
            "assemblyzero.workflows.testing.nodes.verify_phases.run_pytest"
        ) as mock_pytest:
            mock_pytest.return_value = {
                "returncode": 1,
                "stdout": ABSENT_REPORT,
                "stderr": "",
                "parsed": {
                    "passed": 15, "failed": 0, "errors": 0, "coverage": 0,
                },
            }
            result = verify_green_phase(state)

        assert result["next_node"] == "end"
        assert "COVERAGE MEASUREMENT FAILED" in result["error_message"]
        assert "not a test gap" in result["error_message"]
        assert "not a defect in the LLD or spec" in result["error_message"]
        assert "stagnant" not in result["error_message"].lower()

    def test_n5_does_not_preempt_the_zero_collected_law(self) -> None:
        """#2548 owns zero-collected, and its diagnosis is more specific.

        A coverage complaint must never displace "collected 0 tests" -- the
        run has no tests, not an unmeasured module.
        """
        reading = read_coverage("collected 0 items\n", TARGET)

        assert reading.state == ABSENT  # true, and deliberately not acted on
        # The node's own gate requires passed_count > 0; pinned end-to-end by
        # tests/unit/test_zero_needs_denominator.py, which still passes.

    def test_n4c_still_targets_a_genuine_zero(self) -> None:
        """The control: a real 0% is a real test gap, stays measured, and
        carries the uncovered lines N4c needs to target."""
        reading = read_coverage(ZERO_REPORT, TARGET)

        assert reading.measured
        assert reading.uncovered == {
            "src/boostgauge/skins/stingray.py": ["1-40"]
        }

    def test_the_two_states_are_distinguishable(self) -> None:
        """The denominator law in one line: absent and zero must not render
        alike (#2546/#2552/#2608)."""
        absent = read_coverage(ABSENT_REPORT, TARGET)
        zero = read_coverage(ZERO_REPORT, TARGET)

        assert absent.state != zero.state
        assert absent.percent is None and zero.percent == 0.0


# ---------------------------------------------------------------------------
# #2638 -- the red-phase claim states only what is known
# ---------------------------------------------------------------------------


class TestTheRedPhaseClaim:
    def test_the_prediction_is_dropped_when_tests_will_be_rewritten(self) -> None:
        """run-201554: the test file was in `files_to_implement`, printed four
        lines after the claim that the loop could not converge. It converged."""
        from assemblyzero.workflows.testing.nodes.verify_phases import (
            _tests_are_an_implementation_target,
        )

        assert _tests_are_an_implementation_target({
            "test_files": ["tests/visual/test_stingray_static.py"],
            "files_to_implement": [
                {"path": "src/boostgauge/skins/stingray.py"},
                {"path": "tests/visual/test_stingray_static.py"},
            ],
        }) is True

    def test_the_claim_stands_when_the_tests_are_not_a_target(self) -> None:
        """The control. A genuinely unwinnable suite nobody will rewrite may
        still be called one -- that is #2317's whole point."""
        from assemblyzero.workflows.testing.nodes.verify_phases import (
            _tests_are_an_implementation_target,
        )

        assert _tests_are_an_implementation_target({
            "test_files": ["tests/visual/test_stingray_static.py"],
            "files_to_implement": [{"path": "src/boostgauge/skins/stingray.py"}],
        }) is False

    def test_no_targets_at_all_keeps_the_claim(self) -> None:
        from assemblyzero.workflows.testing.nodes.verify_phases import (
            _tests_are_an_implementation_target,
        )

        assert _tests_are_an_implementation_target({"test_files": ["t.py"]}) is False

    def test_plain_string_targets_are_understood(self) -> None:
        """`implementation_files` carries strings where `files_to_implement`
        carries dicts; both name the same thing."""
        from assemblyzero.workflows.testing.nodes.verify_phases import (
            _tests_are_an_implementation_target,
        )

        assert _tests_are_an_implementation_target({
            "test_files": ["tests/visual/test_stingray_static.py"],
            "implementation_files": ["tests/visual/test_stingray_static.py"],
        }) is True
