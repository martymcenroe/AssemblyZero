"""A zero needs a denominator, and the validator sees what pytest will (#2546/#2547).

boostgauge run-issue331-235455, the first run ever to reach the green phase:
a batch-written tests/visual/conftest.py re-registered --generate-baselines
(already registered by tests/conftest.py), pytest died at conftest load with
``ValueError: option names {'--generate-baselines'} already added`` and exit
code 1, the green gate read "0 passed, 0 failed" as ALL PASSING, diagnosed
the 0% coverage as a test gap, added tests to a suite that cannot load, and
halted as "Coverage stagnant: 0.0% -> 0.0%" blaming the LLD and spec.

Verified against the preserved post-impl checkpoint (boostgauge e819825,
reproduced read-only: the duplicate registration kills collection with 13
collectable tests behind it; removing it collects all 13, so the missing
skins/__init__.py is benign). Also refuted while verifying: the validator did
NOT proceed past exhausted retries — attempt 2 validated and the log printed
[SUCCESS]; the killing conftest was batch-written, and the batch path omitted
repo_root, silently skipping every validation beyond syntax.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from assemblyzero.core.recovery_plan import _build_recommendation
from assemblyzero.workflows.testing.nodes.implementation.parsers import (
    validate_code_response,
    validate_conftest_options,
)
from assemblyzero.workflows.testing.nodes.verify_phases import (
    _summarize_collection_failure,
    verify_green_phase,
)

#: The live collection death, distilled: pytest's stderr tail.
COLLECTION_OUTPUT = """\
Traceback (most recent call last):
  File "conftest.py", line 6, in pytest_addoption
    parser.addoption(
  File "argparsing.py", line 429, in addoption
    raise ValueError(f"option names {conflict} already added")
ValueError: option names {'--generate-baselines'} already added
"""


def _pytest_result(passed: int, failed: int, output: str = "") -> dict:
    return {
        "returncode": 1,
        "stdout": output,
        "stderr": "",
        "parsed": {"passed": passed, "failed": failed, "errors": 0,
                   "coverage": 0.0},
    }


def _state(tmp_path: Path, **overrides: object) -> dict:
    state = {
        "repo_root": str(tmp_path),
        "issue_number": 331,
        "audit_dir": "",
        "test_files": [],
        "implementation_files": [],
        "files_to_modify": [],
        "coverage_target": 95,
        "iteration_count": 0,
    }
    state.update(overrides)
    return state


class TestZeroCollectedIsNeverAPass:
    @patch("assemblyzero.workflows.testing.nodes.verify_phases.run_pytest")
    def test_first_zero_routes_to_the_loop_as_a_named_repair(
        self, mock_pytest, tmp_path: Path, capsys,
    ) -> None:
        mock_pytest.return_value = _pytest_result(0, 0, COLLECTION_OUTPUT)

        result = verify_green_phase(_state(tmp_path))
        printed = capsys.readouterr().out

        assert result["next_node"] == "N4_implement_code"
        assert result["zero_collected_strikes"] == 1
        assert "collected 0 tests" in result["test_failure_summary"]
        assert "--generate-baselines" in result["test_failure_summary"], (
            "the collection error travels as the repair task"
        )
        assert "collection is broken" in printed
        assert "test gap" not in printed, (
            "zero collected must never read as a coverage/test gap"
        )
        assert "all 0 test(s) pass" not in printed

    @patch("assemblyzero.workflows.testing.nodes.verify_phases.run_pytest")
    def test_second_zero_halts_naming_the_collection_error(
        self, mock_pytest, tmp_path: Path, capsys,
    ) -> None:
        mock_pytest.return_value = _pytest_result(0, 0, COLLECTION_OUTPUT)

        result = verify_green_phase(
            _state(tmp_path, zero_collected_strikes=1, iteration_count=1)
        )
        capsys.readouterr()

        assert result["next_node"] == "end"
        assert "collected 0 tests" in result["error_message"]
        assert "ValueError" in result["error_message"]
        assert "not implicated" in result["error_message"], (
            "the halt must exonerate the LLD and spec by name"
        )
        assert "Coverage stagnant" not in result["error_message"]

    @patch("assemblyzero.workflows.testing.nodes.verify_phases.run_pytest")
    def test_a_nonzero_denominator_keeps_the_ordinary_paths(
        self, mock_pytest, tmp_path: Path, capsys,
    ) -> None:
        mock_pytest.return_value = _pytest_result(8, 5, "8 passed, 5 failed")

        result = verify_green_phase(_state(tmp_path))
        printed = capsys.readouterr().out

        assert result["next_node"] == "N4_implement_code"
        assert "collection is broken" not in printed

    def test_the_recovery_advice_names_collection_not_the_lld(self) -> None:
        advice = _build_recommendation(
            "stagnation",
            "Green phase failed: pytest collected 0 tests on 2 iterations -- "
            "collection is broken ...",
            "testing",
        )
        assert "ZERO tests" in advice
        assert "not implicated" in advice
        assert "LLD or spec likely needs manual editing" not in advice

    def test_ordinary_stagnation_advice_is_unchanged(self) -> None:
        advice = _build_recommendation(
            "stagnation",
            "Coverage stagnant: 42.0% -> 42.5% (< 1% improvement).",
            "testing",
        )
        assert "manual editing" in advice or "GENERATED TEST FILE" in advice


class TestCollectionFailureSummary:
    def test_the_live_valueerror_is_extracted(self) -> None:
        summary = _summarize_collection_failure(COLLECTION_OUTPUT)
        assert summary.startswith("ValueError:")
        assert "--generate-baselines" in summary

    def test_no_exception_line_returns_empty_not_invented(self) -> None:
        assert _summarize_collection_failure("nothing ran\n") == ""


PARENT_CONFTEST = """\
def pytest_addoption(parser):
    parser.addoption("--generate-baselines", action="store_true")
"""

CHILD_CONFTEST = """\
def pytest_addoption(parser):
    parser.addoption("--generate-baselines", action="store_true",
                     help="Generate baseline images for visual tests")
"""


class TestConftestOptionValidation:
    """#2547: the write-time check for the exact defect that killed the run."""

    def _repo(self, tmp_path: Path) -> Path:
        (tmp_path / "tests" / "visual").mkdir(parents=True)
        (tmp_path / "tests" / "conftest.py").write_text(
            PARENT_CONFTEST, encoding="utf-8"
        )
        return tmp_path

    def test_the_killing_conftest_is_rejected_with_the_finding_named(
        self, tmp_path: Path,
    ) -> None:
        repo = self._repo(tmp_path)
        ok, error = validate_conftest_options(
            CHILD_CONFTEST, "tests/visual/conftest.py", repo
        )
        assert ok is False
        assert "--generate-baselines" in error
        assert "tests" in error  # names the ancestor carrying it
        assert "zero tests" in error or "collects zero" in error

    def test_it_reaches_the_shared_validator_when_repo_root_travels(
        self, tmp_path: Path,
    ) -> None:
        """The batch path now passes repo_root (#2547), so the batch-written
        conftest that killed the run gets exactly this rejection."""
        repo = self._repo(tmp_path)
        ok, error = validate_code_response(
            CHILD_CONFTEST, "tests/visual/conftest.py", "",
            repo_root=str(repo),
        )
        assert ok is False
        assert "already registers" in error

    def test_a_fresh_flag_passes(self, tmp_path: Path) -> None:
        repo = self._repo(tmp_path)
        ok, error = validate_conftest_options(
            "def pytest_addoption(parser):\n"
            "    parser.addoption('--fresh-flag', action='store_true')\n",
            "tests/visual/conftest.py", repo,
        )
        assert ok is True, error

    def test_a_non_conftest_file_is_untouched(self, tmp_path: Path) -> None:
        repo = self._repo(tmp_path)
        ok, _ = validate_conftest_options(
            CHILD_CONFTEST, "tests/visual/test_x.py", repo
        )
        assert ok is True

    def test_a_root_level_conftest_has_no_in_repo_ancestors(
        self, tmp_path: Path,
    ) -> None:
        ok, _ = validate_conftest_options(
            PARENT_CONFTEST, "conftest.py", tmp_path
        )
        assert ok is True

    def test_unparseable_new_code_abstains_here(self, tmp_path: Path) -> None:
        """Syntax is the syntax check's finding; this check judges options."""
        repo = self._repo(tmp_path)
        ok, _ = validate_conftest_options(
            "def broken(:", "tests/visual/conftest.py", repo
        )
        assert ok is True
