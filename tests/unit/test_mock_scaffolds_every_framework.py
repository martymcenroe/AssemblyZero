"""A mock run scaffolds every framework of the run (#4438).

`_mock_scaffold_tests` wrote one pytest file whatever the run was, so a mock on
a target with pytest at its root and Vitest in `web/` could not pass N2.5, and
the two-framework path had never run end to end, not even under `--mock`.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from assemblyzero.workflows.testing.framework_detector import TestFramework
from assemblyzero.workflows.testing.nodes.load_lld import _mock_load_lld
from assemblyzero.workflows.testing.nodes.scaffold_tests import scaffold_tests
from assemblyzero.workflows.testing.nodes.validate_tests_mechanical import (
    validate_tests_mechanical_node,
)
from assemblyzero.workflows.testing.runner_registry import (
    checkpoint_safe,
    get_framework_config,
)
from tools import rehearse_two_frameworks as rehearsal

PYTHON_OK = {"passed": 1, "exit": 0, "failures": []}
VITEST_OK = {"raw_output": "1 passed", "passed": 1, "exit_code": 0}


def _loaded(root: Path, tmp_path: Path) -> dict:
    """The state N0 hands a mock run, on `root`."""
    audit = tmp_path / "audit"
    audit.mkdir()
    state = {
        "issue_number": 42, "repo_root": str(root), "audit_dir": str(audit),
        "mock_mode": True, "file_counter": 0,
    }
    return {**state, **_mock_load_lld(state)}


@pytest.fixture
def two_frameworks(tmp_path: Path) -> Path:
    root, _ = rehearsal.build_target(tmp_path)
    return root


class TestT1TheMockScaffoldsEveryFramework:
    def test_one_python_file_and_one_typescript_file(self, two_frameworks, tmp_path):
        state = _loaded(two_frameworks, tmp_path)

        result = scaffold_tests(state)

        files = [Path(f).relative_to(two_frameworks).as_posix() for f in result["test_files"]]
        assert sorted(files) == ["tests/test_issue_42.py", "web/tests/issue_42.test.ts"]
        assert all(Path(f).is_file() for f in result["test_files"])
        typescript = (two_frameworks / "web/tests/issue_42.test.ts").read_text(encoding="utf-8")
        assert "vitest" in typescript
        assert result["error_message"] == ""

    def test_the_pytest_scaffold_stays_what_the_validator_reads(self, two_frameworks, tmp_path):
        result = scaffold_tests(_loaded(two_frameworks, tmp_path))

        assert "def test_" in result["generated_tests"]

    def test_n2_5_accepts_the_pair(self, two_frameworks, tmp_path):
        state = _loaded(two_frameworks, tmp_path)
        state.update(scaffold_tests(state))
        runner = MagicMock()
        runner.validate_test_file.return_value = []

        with patch(
            "assemblyzero.workflows.testing.nodes.validate_tests_mechanical.get_runner",
            return_value=runner,
        ):
            result = validate_tests_mechanical_node(state)

        assert not result.get("error_message")
        assert not result.get("scaffold_validation_errors")


class TestAMocksPlaceholdersAlertNoOne:
    """#4489: every mock run that reached N2.5 emailed the operator."""

    def _validate(self, state: dict) -> None:
        runner = MagicMock()
        runner.validate_test_file.return_value = []
        with patch(
            "assemblyzero.workflows.testing.nodes.validate_tests_mechanical.get_runner",
            return_value=runner,
        ):
            validate_tests_mechanical_node(state)

    def test_t1_a_mock_run_alerts_no_one_and_says_why(
        self, two_frameworks, tmp_path, capsys, operator_alerts
    ):
        state = _loaded(two_frameworks, tmp_path)
        state.update(scaffold_tests(state))

        self._validate(state)

        assert not operator_alerts
        assert "[MOCK] The scaffold is placeholders by design" in capsys.readouterr().out

    def test_t2_a_real_runs_placeholders_still_alert(
        self, two_frameworks, tmp_path, operator_alerts
    ):
        state = _loaded(two_frameworks, tmp_path)
        state.update(scaffold_tests(state))
        state["mock_mode"] = False

        self._validate(state)

        assert [alert["what"] for alert in operator_alerts] == [
            "the scaffold is placeholders only"
        ]


def _configs(*frameworks: TestFramework) -> list[dict]:
    return [
        checkpoint_safe({**get_framework_config(f), "working_directory": None})
        for f in frameworks
    ]


class TestARunOfOneFramework:
    def test_a_pytest_run_writes_the_one_pytest_file(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        state = {**_loaded(repo, tmp_path), "framework_configs": _configs(TestFramework.PYTEST)}

        result = scaffold_tests(state)

        assert [Path(f).name for f in result["test_files"]] == ["test_issue_42.py"]

    def test_a_vitest_run_writes_no_python(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        state = {**_loaded(repo, tmp_path), "framework_configs": _configs(TestFramework.VITEST)}

        result = scaffold_tests(state)

        assert [Path(f).name for f in result["test_files"]] == ["issue_42.test.ts"]


def test_a_framework_the_run_cannot_scaffold_halts_by_name(two_frameworks, tmp_path):
    state = _loaded(two_frameworks, tmp_path)

    with patch(
        "assemblyzero.workflows.testing.nodes.scaffold_tests.generate_ts_test_file_content",
        side_effect=ValueError("no such template"),
    ):
        result = scaffold_tests(state)

    assert "vitest (web)" in result["error_message"]
    assert "no such template" in result["error_message"]


class TestTheProvisionStepCannotPassOnNothing:
    """`step_provision` needs the network, so its verdict is held here (#4438 T3)."""

    @staticmethod
    def _step(tmp_path, *, python: dict, vitest: dict, lines=("poetry install", "npm ci")):
        runner = MagicMock()
        runner.run_tests.return_value = vitest
        with (
            patch("assemblyzero.workflows.provisioning.provision_worktree", return_value=list(lines)),
            patch.object(rehearsal, "pytest_proof", return_value=python),
            patch(
                "assemblyzero.workflows.testing.nodes.verify_phases.get_runner",
                return_value=runner,
            ),
            patch.object(rehearsal, "_remove_worktree"),
        ):
            return rehearsal.step_provision(tmp_path), runner

    def test_both_suites_passing_passes(self, tmp_path):
        code, runner = self._step(tmp_path, python=PYTHON_OK, vitest=VITEST_OK)

        assert code == 0
        assert runner.run_tests.call_args.kwargs["test_paths"] is None

    def test_a_suite_that_ran_nothing_fails(self, tmp_path):
        vitest = {"raw_output": "no tests", "passed": 0, "exit_code": 0}

        code, _ = self._step(tmp_path, python=PYTHON_OK, vitest=vitest)

        assert code == 1

    def test_a_failing_suite_fails(self, tmp_path):
        python = {"passed": 3, "exit": 1, "failures": []}

        code, _ = self._step(tmp_path, python=python, vitest=VITEST_OK)

        assert code == 1

    def test_a_pytest_proof_that_did_not_hold_fails_a_passing_suite(self, tmp_path):
        """#4490: green suites do not excuse testing in the wrong environment."""
        python = {"passed": 1, "exit": 0, "failures": ["listed plugins: ['langsmith']"]}

        code, _ = self._step(tmp_path, python=python, vitest=VITEST_OK)

        assert code == 1
