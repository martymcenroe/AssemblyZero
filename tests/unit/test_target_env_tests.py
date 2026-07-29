"""Tests execute in the TARGET repo's environment (#1904).

Every test result of the boostgauge campaign before this fix ran in
AssemblyZero's venv: bare ``pytest`` resolved from the orchestrator's PATH,
and unprovisioned worktrees let ``poetry run`` fall through to PATH anyway.
Phase 3 passed on AZ's Pillow; phase 4 died on the target's psutil.
"""

from unittest.mock import patch

from assemblyzero.workflows.testing.framework_detector import TestFramework
from assemblyzero.workflows.testing.runner_registry import get_framework_config
from assemblyzero.workflows.testing.runners.pytest_runner import PytestRunner


def _runner(tmp_path):
    return PytestRunner(
        config=dict(get_framework_config(TestFramework.PYTEST)),
        project_root=str(tmp_path),
    )


class TestPytestRunsInTargetEnv:
    def test_command_goes_through_poetry_run(self, tmp_path):
        runner = _runner(tmp_path)
        with patch.object(
            runner, "_run_subprocess", return_value=("1 passed", 0)
        ) as sub:
            runner.run_tests(test_paths=["tests/unit/test_x.py"])

        command = sub.call_args[0][0]
        assert command[:3] == ["poetry", "run", "pytest"], (
            "bare pytest resolves from the orchestrator's PATH — AZ's venv, "
            "not the target's"
        )

    def test_extra_args_and_paths_still_ride_along(self, tmp_path):
        runner = _runner(tmp_path)
        with patch.object(
            runner, "_run_subprocess", return_value=("1 passed", 0)
        ) as sub:
            runner.run_tests(
                test_paths=["tests/unit/test_x.py"],
                extra_args=["--cov=pkg"],
            )

        command = sub.call_args[0][0]
        assert "--cov=pkg" in command
        assert "tests/unit/test_x.py" in command


class TestE2EAlsoUsesPoetryRun:
    def test_source_has_no_bare_pytest_command(self):
        """Pin at the source level: the e2e node builds its command through
        poetry run, matching verify_phases."""
        import importlib
        from pathlib import Path

        # `import ...e2e_validation as mod` binds the package attribute of
        # the same name (the function) — importlib returns the real module.
        mod = importlib.import_module(
            "assemblyzero.workflows.testing.nodes.e2e_validation"
        )
        source = Path(mod.__file__).read_text(encoding="utf-8")
        assert '"poetry", "run", "pytest"' in source
        assert '\n    cmd = [\n        "pytest",' not in source
