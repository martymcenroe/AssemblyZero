"""A run's pytest runs in the target's environment, or halts by name (#4490).

`run_pytest` inherited the workflow's VIRTUAL_ENV, which poetry takes as already
active, so every Python target was tested in AssemblyZero's virtualenv. Stripping
that is not enough: `poetry run pytest` looks the command up on PATH, so a target
with no pytest ran another project's. The coverage check imported pytest_cov in
the workflow's own process, which proved nothing about the target.

The interpreters here are real: `venv` builds one with nothing in it, and only
the name poetry gives for it is supplied. So "the workflow's own pytest_cov does
not satisfy the check" is measured, in a second interpreter, not asserted.
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import venv
from pathlib import Path
from unittest.mock import patch

import pytest

from assemblyzero.workflows import provisioning, target_env
from assemblyzero.workflows.target_env import TargetEnvironmentError, require_pytest
from assemblyzero.workflows.testing.framework_detector import TestFramework
from assemblyzero.workflows.testing.nodes import e2e_validation
from assemblyzero.workflows.testing.nodes import verify_phases as vp
from assemblyzero.workflows.testing.runner_registry import get_framework_config
from assemblyzero.workflows.testing.runners.base_runner import BaseTestRunner
from assemblyzero.workflows.testing.runners.pytest_runner import PytestRunner
from tools import rehearse_two_frameworks as rehearsal

PROJECT = '[tool.poetry]\nname = "target"\nversion = "0.1.0"\npackage-mode = false\n'
TOOLS_ONLY = '[tool.ruff]\nline-length = 100\n\n[tool.pytest.ini_options]\ntestpaths = ["tests"]\n'


def _completed(command, returncode=0, stdout="", stderr=""):
    return subprocess.CompletedProcess(command, returncode, stdout, stderr)


def _site_packages(environment: Path) -> Path:
    found = list(environment.glob("lib/python*/site-packages")) or list(
        environment.glob("Lib/site-packages")
    )
    assert len(found) == 1, found
    return found[0]


def _install(environment: Path, *modules: str) -> None:
    """A module the real interpreter can find, standing in for the package."""
    for module in modules:
        package = _site_packages(environment) / module
        package.mkdir()
        (package / "__init__.py").write_text("", encoding="utf-8")


@pytest.fixture(scope="module")
def empty_environment(tmp_path_factory) -> Path:
    """A real virtualenv with nothing in it. Module scope: it takes a moment."""
    environment = tmp_path_factory.mktemp("target-env") / "venv"
    venv.create(environment, with_pip=False)
    return environment


@pytest.fixture
def environment(empty_environment, tmp_path) -> Path:
    """The real interpreter, with a site-packages of this test's own."""
    site = _site_packages(empty_environment)
    for entry in site.iterdir():
        for inner in entry.iterdir():
            inner.unlink()
        entry.rmdir()
    return empty_environment


@pytest.fixture
def project(tmp_path) -> Path:
    root = tmp_path / "target"
    root.mkdir()
    (root / "pyproject.toml").write_text(PROJECT, encoding="utf-8")
    return root


@pytest.fixture
def poetry_names(monkeypatch):
    """`poetry env info --path` answers with the given path; the interpreter it
    names is really run. Returns the calls and their environments."""

    def answering(path: Path, returncode: int = 0, stderr: str = "") -> list:
        calls: list = []

        def run(command, **kwargs):
            calls.append((list(command), kwargs))
            if list(command[:2]) == ["poetry", "env"]:
                return _completed(command, returncode, f"{path}\n", stderr)
            return subprocess.run(
                command, cwd=kwargs["cwd"], capture_output=True, text=True, check=False,
                env=kwargs["env"],
            )

        monkeypatch.setattr(target_env, "run_command", run)
        return calls

    return answering


def _pytest_runs(monkeypatch, stdout: str = "1 passed in 0.01s") -> list:
    """Stand in for the pytest run itself, recording what it was given."""
    runs: list = []

    def run(command, **kwargs):
        runs.append((list(command), kwargs))
        return _completed(command, 0, stdout)

    monkeypatch.setattr(vp, "run_command", run)
    return runs


@pytest.fixture
def workflow_virtualenv(monkeypatch, tmp_path) -> Path:
    """The condition a real run is in: under `poetry run` of another project."""
    other = tmp_path / "assemblyzero-venv"
    monkeypatch.setenv("VIRTUAL_ENV", str(other))
    monkeypatch.setenv("POETRY_ACTIVE", "1")
    monkeypatch.setenv("PATH", os.pathsep.join([str(other / "bin"), os.environ["PATH"]]))
    return other


def _assert_shed(env: dict[str, str], virtualenv: Path) -> None:
    assert "VIRTUAL_ENV" not in env
    assert "POETRY_ACTIVE" not in env
    assert str(virtualenv / "bin") not in env["PATH"].split(os.pathsep)


class TestT1TheRunIsInTheTargetsEnvironment:
    """R1, AC1. Each of these fails on `main`."""

    def test_run_pytest_gives_the_child_no_virtualenv(
        self, project, environment, poetry_names, workflow_virtualenv, monkeypatch
    ):
        _install(environment, "pytest")
        poetry_names(environment)
        runs = _pytest_runs(monkeypatch)

        vp.run_pytest(["tests/test_x.py"], repo_root=project)

        command, kwargs = runs[0]
        assert command[:3] == ["poetry", "run", "pytest"]
        assert kwargs["cwd"] == str(project)
        _assert_shed(kwargs["env"], workflow_virtualenv)

    def test_it_still_asks_for_full_summary_lines(
        self, project, environment, poetry_names, monkeypatch
    ):
        """#2319 stands: the environment changed, not what it was for."""
        _install(environment, "pytest")
        poetry_names(environment)
        runs = _pytest_runs(monkeypatch)

        vp.run_pytest([], repo_root=project)

        assert runs[0][1]["env"]["COLUMNS"] == vp.PYTEST_OUTPUT_COLUMNS

    def test_the_questions_are_asked_outside_the_virtualenv_too(
        self, project, environment, poetry_names, workflow_virtualenv
    ):
        """Asked under VIRTUAL_ENV, poetry names AssemblyZero's environment
        (measured 2026-11-01), so the check would pass on the wrong one."""
        _install(environment, "pytest")
        calls = poetry_names(environment)

        require_pytest(project)

        assert len(calls) == 2
        for _command, kwargs in calls:
            _assert_shed(kwargs["env"], workflow_virtualenv)

    def test_the_runners_subprocess_has_no_virtualenv(self, tmp_path, workflow_virtualenv):
        runner = PytestRunner(
            config=dict(get_framework_config(TestFramework.PYTEST)),
            project_root=str(tmp_path),
        )
        with patch(
            "assemblyzero.workflows.testing.runners.base_runner.run_command",
            return_value=_completed(["x"], stdout="1 passed"),
        ) as run:
            runner.run_tests(test_paths=["tests/test_x.py"])

        _assert_shed(run.call_args.kwargs["env"], workflow_virtualenv)

    def test_every_runner_shares_that_subprocess(self):
        """The JavaScript runners inherit the same call; none of them overrides it."""
        assert "_run_subprocess" not in vars(PytestRunner)
        assert BaseTestRunner._run_subprocess is PytestRunner._run_subprocess

    def test_e2e_has_no_virtualenv_and_keeps_its_sandbox(
        self, tmp_path, workflow_virtualenv, monkeypatch
    ):
        monkeypatch.setattr(e2e_validation_module(), "require_pytest", lambda _root: None)
        with patch.object(
            e2e_validation_module(), "run_command", return_value=_completed(["x"]),
        ) as run:
            e2e_validation_module().run_e2e_tests(["tests/test_x.py"], "/sandbox", tmp_path)

        env = run.call_args.kwargs["env"]
        _assert_shed(env, workflow_virtualenv)
        assert env["E2E_SANDBOX_REPO"] == "/sandbox"

    def test_nothing_else_in_a_run_starts_pytest(self):
        """Every pytest a run starts goes through one of the three pinned above."""
        package = Path(target_env.__file__).parent
        starters = sorted(
            path.relative_to(package).as_posix()
            for path in package.rglob("*.py")
            if '"poetry", "run", "pytest"' in path.read_text(encoding="utf-8")
        )

        assert starters == [
            "testing/nodes/e2e_validation.py",
            "testing/nodes/verify_phases.py",
            "testing/runners/pytest_runner.py",
        ]


def e2e_validation_module():
    """The module, not the function of the same name the package exports."""
    import importlib

    return importlib.import_module(e2e_validation.__module__)


class TestTheTargetsOwnPytest:
    """R1. Stripping the virtualenv is not enough: `poetry run pytest` falls
    through PATH, and on 2026-11-01 a target that declared no pytest ran the one
    in another project's virtualenv and exited 0."""

    def test_a_target_with_no_pytest_halts_and_nothing_runs(
        self, project, environment, poetry_names, monkeypatch
    ):
        poetry_names(environment)
        monkeypatch.setattr(vp, "run_command", lambda *a, **k: pytest.fail("pytest ran"))

        with pytest.raises(vp.PhaseStepError, match="pytest is not installed") as raised:
            vp.run_pytest([], repo_root=project)

        assert str(environment) in str(raised.value)
        assert "PATH" in str(raised.value)

    def test_the_e2e_run_refuses_it_too(self, project, environment, poetry_names):
        poetry_names(environment)
        module = e2e_validation_module()

        with patch.object(module, "run_command") as run, pytest.raises(
            module.E2ERunFailed, match="pytest is not installed",
        ):
            module.run_e2e_tests(["tests/test_x.py"], None, project)

        run.assert_not_called()

    def test_the_runner_refuses_it_as_its_contract_says(
        self, project, environment, poetry_names
    ):
        poetry_names(environment)
        runner = PytestRunner(
            config=dict(get_framework_config(TestFramework.PYTEST)),
            project_root=str(project),
        )

        with pytest.raises(OSError, match="pytest is not installed"):
            runner.require_dependencies()

    def test_a_project_never_installed_is_named(self, project, poetry_names):
        """Measured: exit 1 and nothing on either stream."""
        poetry_names("", returncode=1)

        with pytest.raises(TargetEnvironmentError) as raised:
            require_pytest(project)

        message = str(raised.value)
        assert "poetry names no environment" in message
        assert "exited 1" in message and "no output" in message
        assert "`poetry install`" in message

    def test_poetrys_own_words_are_carried(self, project, poetry_names):
        poetry_names("", returncode=1, stderr="The Poetry configuration is invalid")

        with pytest.raises(TargetEnvironmentError, match="configuration is invalid"):
            require_pytest(project)

    def test_an_environment_with_no_python_is_named(self, project, tmp_path, poetry_names):
        hollow = tmp_path / "hollow"
        hollow.mkdir()
        poetry_names(hollow)

        with pytest.raises(TargetEnvironmentError, match="holds no python"):
            require_pytest(project)

    @pytest.mark.parametrize(
        "failure", [FileNotFoundError("poetry"), subprocess.TimeoutExpired("poetry", 60)],
    )
    def test_a_poetry_that_cannot_answer_is_named(self, project, monkeypatch, failure):
        def run(*_args, **_kwargs):
            raise failure

        monkeypatch.setattr(target_env, "run_command", run)

        with pytest.raises(TargetEnvironmentError, match="could not answer"):
            require_pytest(project)

    def test_a_probe_that_fails_is_named(self, project, environment, monkeypatch):
        def run(command, **_kwargs):
            if list(command[:2]) == ["poetry", "env"]:
                return _completed(command, 0, f"{environment}\n")
            return _completed(command, 1, stderr="the interpreter fell over")

        monkeypatch.setattr(target_env, "run_command", run)

        with pytest.raises(TargetEnvironmentError, match="the interpreter fell over"):
            require_pytest(project)

    @pytest.mark.parametrize("printed", ["not json", "null"])
    def test_a_probe_that_prints_no_answer_is_named(
        self, project, environment, monkeypatch, printed
    ):
        def run(command, **_kwargs):
            if list(command[:2]) == ["poetry", "env"]:
                return _completed(command, 0, f"{environment}\n")
            return _completed(command, 0, printed)

        monkeypatch.setattr(target_env, "run_command", run)

        with pytest.raises(TargetEnvironmentError, match="not its answer"):
            require_pytest(project)


class TestT2CoverageIsDecidedByTheTarget:
    """R2, AC2."""

    def test_the_workflows_own_pytest_cov_does_not_satisfy_the_check(
        self, project, environment, poetry_names, monkeypatch
    ):
        assert importlib.util.find_spec("pytest_cov"), "the premise: this process has it"
        _install(environment, "pytest")
        poetry_names(environment)
        monkeypatch.setattr(vp, "run_command", lambda *a, **k: pytest.fail("the suite ran"))

        with pytest.raises(vp.PhaseStepError, match="pytest-cov is not installed") as raised:
            vp.run_pytest(["tests/test_x.py"], coverage_module="pkg", repo_root=project)

        message = str(raised.value)
        assert str(environment) in message
        assert "poetry add --group dev pytest-cov" in message

    def test_a_target_with_it_measures(self, project, environment, poetry_names, monkeypatch):
        _install(environment, "pytest", "pytest_cov")
        poetry_names(environment)
        runs = _pytest_runs(monkeypatch)

        vp.run_pytest(["tests/test_x.py"], coverage_module=["pkg", "lib"], repo_root=project)

        command = runs[0][0]
        assert "--cov=pkg" in command and "--cov=lib" in command
        assert "--cov-fail-under=0" in command

    def test_a_run_with_no_coverage_needs_no_pytest_cov(
        self, project, environment, poetry_names, monkeypatch
    ):
        """The red phase and the full-suite gate measure nothing."""
        _install(environment, "pytest")
        poetry_names(environment)
        runs = _pytest_runs(monkeypatch)

        vp.run_pytest(["tests/test_x.py"], repo_root=project)

        assert not any(flag.startswith("--cov") for flag in runs[0][0])

    def test_the_question_goes_to_the_targets_interpreter(
        self, project, environment, poetry_names
    ):
        _install(environment, "pytest", "pytest_cov")
        calls = poetry_names(environment)

        require_pytest(project, coverage=True)

        probe, _kwargs = calls[1]
        assert Path(probe[0]).parent.parent == environment
        assert probe[-2:] == ["pytest", "pytest_cov"]


class TestT3ATargetWithNoProjectOfItsOwn:
    """R3, AC3. The defined outcome is the halt: there is no environment to name,
    because nothing declares one. Poetry is not asked, because with no project in
    the directory it walks up and answers for a parent's."""

    @pytest.fixture
    def no_poetry(self, monkeypatch):
        monkeypatch.setattr(
            target_env, "run_command", lambda *a, **k: pytest.fail("poetry was asked"),
        )

    def test_a_pyproject_that_only_configures_tools_halts(self, tmp_path, no_poetry):
        (tmp_path / "pyproject.toml").write_text(TOOLS_ONLY, encoding="utf-8")

        with pytest.raises(TargetEnvironmentError) as raised:
            require_pytest(tmp_path)

        message = str(raised.value)
        assert "no Python project of its own" in message
        assert "only configures tools" in message
        assert str(tmp_path / "pyproject.toml") in message

    def test_no_pyproject_at_all_halts_though_a_parent_has_a_project(self, project, no_poetry):
        """A nested directory is where poetry's walk reaches another project:
        measured on 2026-11-01, from a directory inside AssemblyZero."""
        nested = project / "nested"
        nested.mkdir()

        with pytest.raises(TargetEnvironmentError, match="does not exist"):
            require_pytest(nested)

    def test_run_pytest_halts_as_a_phase_step(self, tmp_path, no_poetry, monkeypatch):
        (tmp_path / "pyproject.toml").write_text(TOOLS_ONLY, encoding="utf-8")
        monkeypatch.setattr(vp, "run_command", lambda *a, **k: pytest.fail("pytest ran"))

        with pytest.raises(vp.PhaseStepError, match="no Python project of its own"):
            vp.run_pytest([], repo_root=tmp_path)

    def test_a_pyproject_that_is_not_toml_is_named(self, tmp_path, no_poetry):
        (tmp_path / "pyproject.toml").write_text("[not toml", encoding="utf-8")

        with pytest.raises(TargetEnvironmentError, match="could not be read as TOML"):
            require_pytest(tmp_path)

    @pytest.mark.parametrize("table", ["[project]\nname = 'x'\n", PROJECT])
    def test_either_way_of_declaring_a_project_counts(
        self, tmp_path, poetry_names, environment, table
    ):
        (tmp_path / "pyproject.toml").write_text(table, encoding="utf-8")
        _install(environment, "pytest")
        poetry_names(environment)

        require_pytest(tmp_path)

    def test_provisioning_and_the_gate_mean_the_same_thing_by_a_project(self, tmp_path):
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(TOOLS_ONLY, encoding="utf-8")

        assert provisioning._declares_project(pyproject) is False
        assert target_env.declares_project(pyproject) is False


class TestTheRehearsalReadsPytestsHeader:
    def test_it_lists_every_plugin(self):
        header = "rootdir: /x\nplugins: cov-7.1.0, langsmith-0.8.18, anyio-4.15.1\ncollected 1 item\n"

        assert rehearsal.listed_plugins(header) == [
            "cov-7.1.0", "langsmith-0.8.18", "anyio-4.15.1",
        ]

    def test_a_pytest_with_no_plugin_prints_no_line(self):
        assert rehearsal.listed_plugins("rootdir: /x\ncollected 1 item\n") == []


def test_the_probe_is_valid_for_any_list_of_modules(environment):
    """Run for real, so the module's `_PROBE` is what is proved."""
    python = next(
        p for p in (environment / "bin" / "python", environment / "Scripts" / "python.exe")
        if p.is_file()
    )
    _install(environment, "pytest")

    done = subprocess.run(
        [str(python), "-c", target_env._PROBE, "pytest", "absent_module"],
        capture_output=True, text=True, check=True,
    )

    assert json.loads(done.stdout) == {"pytest": True, "absent_module": False}
